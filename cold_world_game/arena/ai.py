import math

from ..actions import GameError
from ..constants import (
    BULLET_BLOCKERS,
    DEFAULT_VIEWPORT,
    EXPLOSIVE_WEAPONS,
    GUNS,
    MELEE_WEAPONS,
    THROWABLE_WEAPONS,
)
from ..geometry import distance, normalized, segment_box
from ..hitboxes import monster_aim
from .perception import can_observe

VIEW_REACH = math.hypot(*DEFAULT_VIEWPORT) / 2 - .5
HEADINGS = tuple((math.cos(index * math.tau / 16), math.sin(index * math.tau / 16)) for index in range(16))
HANDHELD = GUNS.keys() | MELEE_WEAPONS.keys() | EXPLOSIVE_WEAPONS.keys() | THROWABLE_WEAPONS.keys()


class ArenaAI:
    def __init__(self, strategy="adaptive"):
        self.decision = "waiting"
        self.strategy = strategy
        self.trace = {}

    @staticmethod
    def wielded(world, player):
        controls = world.controls[player.id]
        seat = world.seated_structure(controls)
        if seat and seat.kind == "mounted_gun":
            return seat
        return player.inventory[player.selected]

    @staticmethod
    def usable(item):
        return item and item.kind in HANDHELD | {"mounted_gun"} and item.ammo != 0 and getattr(item, "uses", None) != 0

    def armed(self, world, player):
        controls = world.controls[player.id]
        return (self.usable(self.wielded(world, player)) or controls.reload_target
                or any(self.usable(item) for item in (*player.inventory, *player.backpack))
                or any(tile.kind == "mounted_gun" and tile.ammo and distance(player, tile) <= 2
                       for tile in world.structures.values()))

    def prepare(self, world, player, enemies):
        controls = world.controls[player.id]
        if controls.reload_target:
            return "reloading"
        current = self.wielded(world, player)
        if self.usable(current):
            return None
        for tile in world.structures.values():
            if tile.kind == "mounted_gun" and tile.ammo and distance(player, tile) <= 2 and all(distance(tile, foe) > 2 for foe in enemies):
                world.execute(player.id, {"type": "sit", "id": tile.id})
                return "mounted"
        _, pack, _, room = world.reload_source(player, controls)
        if pack and room > 0 and world.reload_packs(player, pack, whole=bool(controls.seat)):
            world.execute(player.id, {"type": "reload"})
            return "reloading"
        for slot, item in enumerate(player.inventory):
            if self.usable(item):
                world.execute(player.id, {"type": "select", "slot": slot})
                return "switch"
        for slot, item in enumerate(player.backpack):
            if self.usable(item):
                command = {"type": "transfer", "from": {"kind": "backpack", "slot": slot},
                           "to": {"kind": "inventory", "slot": player.selected}, "item_id": item.id}
                if current:
                    command["swap_item_id"] = current.id
                world.execute(player.id, command)
                return "switch"
        return None

    def step(self, world, player_id):
        player = world.players[player_id]
        controls = world.controls[player_id]
        enemies = [monster for monster in world.monsters.values() if can_observe(player, monster)]
        target = min(enemies, key=lambda monster: (distance(player, monster), monster.id), default=None)
        self.trace = {"strategy": self.strategy, "visible_targets": len(enemies)}
        if player.temperature < 5:
            return
        try:
            preparing = self.prepare(world, player, enemies)
        except GameError as error:
            preparing = None
            self.trace["error"] = error.code
        weapon = self.wielded(world, player)
        kind = weapon.kind if weapon else None
        mounted = kind == "mounted_gun"

        self.decision = preparing or "waiting"
        movement = (0.0, 0.0)
        aim = (player.x + 1, player.y)
        attack = False
        if target:
            separation = distance(player, target)
            away = normalized(player.x - target.x, player.y - target.y)
            aim = (target.x, target.y)
            if preparing == "reloading" or not self.usable(weapon):
                movement = away
                self.decision = preparing or "empty"
            elif mounted:
                attack = bool(controls.seat) and separation <= VIEW_REACH
                aim = self.aim(world, player, target, "rifle")
                self.decision = "mounted"
            else:
                melee = kind in MELEE_WEAPONS and kind not in THROWABLE_WEAPONS
                reach = world.melee_reach(player, weapon, MELEE_WEAPONS[kind]) if melee else EXPLOSIVE_WEAPONS.get(kind, {}).get("cast_range", VIEW_REACH)
                attack = separation <= reach
                aim = self.aim(world, player, target, kind)
                lower = reach * .85 if melee else min(3.2, reach * .65)
                upper = reach if melee else min(6, reach * .9)
                if separation < lower:
                    movement = away
                    self.decision = "retreat"
                elif separation > upper:
                    movement = (-away[0], -away[1])
                    self.decision = "approach"
                else:
                    self.decision = "melee" if melee else "fire"
                if not melee and self.strategy == "kite" and separation < min(6, reach * .8):
                    movement = away
                    self.decision = "retreat"
            if kind in GUNS and self.obstructed(world, player, aim):
                attack = False
                movement = (-away[1], away[0])
                self.decision = "flank"
            if self.strategy == "hold":
                movement = (0, 0)

        if not controls.seat:
            movement = self.evade(world, player, enemies, movement)
        self.trace.update(decision=self.decision, target=target.id if target else None, weapon=kind,
                          distance=round(distance(player, target), 2) if target else None,
                          attack_requested=attack, movement=list(movement), equipment_action=preparing)
        world.execute(player_id, {"type": "input", "move": list(movement), "aim": list(aim),
                                  "target_id": target.id if target else None, "viewport": list(DEFAULT_VIEWPORT)})
        if not attack:
            if controls.held:
                world.execute(player_id, {"type": "attack", "pressed": False})
            return
        repeating = mounted or kind == "rifle" or GUNS.get(kind, {}).get("automatic") or kind in EXPLOSIVE_WEAPONS or kind in THROWABLE_WEAPONS
        ready = player.next_axe_attack if kind in MELEE_WEAPONS else player.next_shot
        if not repeating and controls.held and world.elapsed + 1e-9 >= ready:
            world.execute(player_id, {"type": "attack", "pressed": False})
        if not controls.held and (repeating or world.elapsed + 1e-9 >= ready):
            try:
                self.trace["attack_result"] = world.execute(player_id, {"type": "attack", "pressed": True, "throw_only": kind in THROWABLE_WEAPONS})
            except GameError as error:
                self.trace["attack_error"] = error.code

    @staticmethod
    def obstructed(world, player, aim):
        return any(tile.kind in BULLET_BLOCKERS and tile.solid
                   and segment_box(player.x, player.y, *aim, tile.x, tile.y) is not None
                   for tile in world.nearby_structures(player.x, player.y, *aim))

    @staticmethod
    def aim(world, player, target, kind):
        gun = GUNS.get(kind)
        speed = (gun or THROWABLE_WEAPONS.get(kind, {})).get("speed", 0)
        flight = min(.8, distance(player, target) / speed) if speed else EXPLOSIVE_WEAPONS.get(kind, {}).get("flight_duration", 0)
        x, y = monster_aim(world, target) if gun else (target.x, target.y)
        dx, dy = world._velocities.get(target.id, (0, 0))
        x, y = x + dx * flight, y + dy * flight
        return x, y

    @staticmethod
    def clearance(x, y, dx, dy, duration):
        squared = dx * dx + dy * dy
        closest = min(duration, max(0.0, -(x * dx + y * dy) / squared)) if squared else 0.0
        return math.hypot(x + dx * closest, y + dy * closest)

    def evade(self, world, player, enemies, movement):
        speed = world.player_speed(player)
        missiles = [shot for shot in world.projectiles.values() if shot.hostile and can_observe(player, shot, radius=0)]
        nearby = [monster for monster in enemies if distance(player, monster) < 3.5]

        def exposure(direction):
            dx, dy = direction[0] * speed, direction[1] * speed
            bullet_cost = sum(max(0, .8 - self.clearance(shot.x - player.x, shot.y - player.y,
                              shot.velocity_x - dx, shot.velocity_y - dy, .6)) ** 2 for shot in missiles)
            contact_cost = sum(max(0, 1.0 - self.clearance(monster.x - player.x, monster.y - player.y,
                               -dx, -dy, .45)) ** 2 for monster in nearby)
            return 20 * bullet_cost + (12 * contact_cost if len(nearby) >= 2 or bullet_cost else 0)

        def walkable(direction):
            return world.can_stand(player.x + direction[0] * .55, player.y + direction[1] * .55, player_id=player.id)

        if walkable(movement) and not exposure(movement):
            return movement
        direction = min((move for move in HEADINGS if walkable(move)),
                        key=lambda move: exposure(move) + .2 * math.hypot(move[0] - movement[0], move[1] - movement[1]),
                        default=(0, 0))
        if direction != movement:
            self.decision = "dodge" if missiles else "breakout" if nearby else "flank"
        return direction
