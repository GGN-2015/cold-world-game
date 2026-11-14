import math

from ..constants import DEFAULT_VIEWPORT, EQUIPPED_ITEMS, EXPLOSIVE_WEAPONS, GUNS, MELEE_WEAPONS, PASSIVE_ITEMS, THROWABLE_WEAPONS
from ..geometry import distance, normalized, tile
from ..hitboxes import monster_aim
from ..wildlife import MONSTER_TYPES


BREAKOUT_DIRECTIONS = tuple((math.cos(index * math.tau / 16), math.sin(index * math.tau / 16)) for index in range(16))


def item_support(kind):
    if kind in GUNS or kind in MELEE_WEAPONS or kind in EXPLOSIVE_WEAPONS and not EXPLOSIVE_WEAPONS[kind]["coin_cost"]:
        return "weapon"
    if kind in PASSIVE_ITEMS:
        return "passive"
    if kind in EQUIPPED_ITEMS:
        return "equipment"
    return "unused"


class BoldAI:
    version = 6

    def __init__(self):
        self.decision = "waiting"
        self.breakout_until = 0.0
        self.breakout_direction = (0.0, 0.0)

    def step(self, world, player_id):
        player = world.players[player_id]
        controls = world.controls[player_id]
        monsters = world.visible_monsters(player)
        target = min(monsters, key=lambda monster: (distance(player, monster), monster.id), default=None)
        aim = [target.x, target.y] if target else [player.x + 1, player.y]
        movement = [0.0, 0.0]
        attack = False
        self.decision = "waiting"
        mounted = world.structures.get("arena-mounted-gun")
        seated = False
        if mounted and mounted.ammo:
            safe = all(distance(monster, mounted) > 2 + 1e-9 for monster in monsters)
            if controls.seat != mounted.id and distance(player, mounted) <= 2 and safe:
                world.execute(player_id, {"type": "sit", "id": mounted.id})
            seated = controls.seat == mounted.id
            if seated:
                self.decision = "mounted"
                attack = target is not None and distance(player, target) < math.hypot(*DEFAULT_VIEWPORT) / 2 - 0.5
                if target:
                    aim = list(monster_aim(world, target))
            elif safe:
                movement = list(normalized(mounted.x - player.x, mounted.y - player.y))
                self.decision = "mounting"
        if not seated and self.decision != "mounting" and target:
            separation = distance(player, target)
            slot = self.choose_weapon(player, separation)
            if slot is not None and player.selected != slot:
                world.execute(player_id, {"type": "select", "slot": slot})
            weapon = player.inventory[player.selected] if slot is not None else None
            melee = MELEE_WEAPONS.get(weapon.kind, {}) if weapon and weapon.kind not in THROWABLE_WEAPONS else {}
            reach = melee.get("range", math.hypot(*DEFAULT_VIEWPORT) / 2 - 1)
            if slot is None:
                equipment = next((index for index, item in enumerate(player.inventory) if item and item.kind in EQUIPPED_ITEMS), None)
                if equipment is not None and player.selected != equipment:
                    world.execute(player_id, {"type": "select", "slot": equipment})
                movement = list(normalized(player.x - target.x, player.y - target.y))
                self.decision = "empty"
            else:
                aim = self.aim(world, player, target, weapon)
                attack = separation <= reach
                if melee:
                    movement = list(normalized(target.x - player.x, target.y - player.y)) if separation > reach * 0.75 else list(normalized(player.x - target.x, player.y - target.y))
                    self.decision = "melee" if attack else "approach"
                elif separation < 3.2:
                    movement = list(normalized(player.x - target.x, player.y - target.y))
                    self.decision = "retreat"
                elif separation > min(6.0, reach * 0.8):
                    movement = list(normalized(target.x - player.x, target.y - player.y))
                    self.decision = "approach"
                else:
                    self.decision = "fire"
                movement = self.dodge(world, player, movement)
            movement = self.avoid_surround(world, player, target, monsters, movement, reach)
        if controls.seat and not seated:
            world.execute(player_id, {"type": "sit", "id": controls.seat})
        if mounted and not seated and (tile(aim[0]), tile(aim[1])) == (mounted.x, mounted.y):
            heading = normalized(aim[0] - player.x, aim[1] - player.y)
            if heading == (0, 0):
                heading = (1, 0)
            aim = [aim[0] + heading[0] * 2, aim[1] + heading[1] * 2]
        world.execute(player_id, {"type": "input", "move": movement, "aim": aim, "target_id": target.id if target else None, "viewport": list(DEFAULT_VIEWPORT)})
        item = player.inventory[player.selected]
        repeating = seated or item and (item.kind == "rifle" or GUNS.get(item.kind, {}).get("automatic") or item.kind in EXPLOSIVE_WEAPONS or item.kind in THROWABLE_WEAPONS)
        if not attack:
            if controls.held:
                world.execute(player_id, {"type": "attack", "pressed": False})
        elif repeating:
            if not controls.held:
                world.execute(player_id, {"type": "attack", "pressed": True, "throw_only": bool(item and item.kind in THROWABLE_WEAPONS)})
        else:
            ready = player.next_axe_attack if item and item.kind in MELEE_WEAPONS else player.next_shot
            if world.elapsed + 1e-9 >= ready:
                if controls.held:
                    world.execute(player_id, {"type": "attack", "pressed": False})
                world.execute(player_id, {"type": "attack", "pressed": True})

    def available_weapons(self, player):
        return [(index, item) for index, item in enumerate(player.inventory) if item and item_support(item.kind) == "weapon" and (item.ammo is None or item.ammo > 0) and (item.uses is None or item.uses > 0)]

    def has_usable_weapon(self, world, player_id):
        mounted = world.structures.get("arena-mounted-gun")
        return bool(mounted and (mounted.ammo or 0) > 0 or self.available_weapons(world.players[player_id]))

    def choose_weapon(self, player, separation):
        available = self.available_weapons(player)
        close = next((index for index, item in available if item.kind in MELEE_WEAPONS and item.kind not in THROWABLE_WEAPONS and separation <= MELEE_WEAPONS[item.kind]["range"]), None)
        if close is not None:
            return close
        ranged = next((index for index, item in available if item.kind in GUNS or item.kind in EXPLOSIVE_WEAPONS or item.kind in THROWABLE_WEAPONS), None)
        return ranged if ranged is not None else available[0][0] if available else None

    def aim(self, world, player, target, weapon):
        settings = GUNS.get(weapon.kind, THROWABLE_WEAPONS.get(weapon.kind, {}))
        speed = settings.get("speed", 0)
        flight = min(0.8, distance(player, target) / speed) if speed and not settings.get("instant") else 0
        if weapon.kind in EXPLOSIVE_WEAPONS:
            flight = EXPLOSIVE_WEAPONS[weapon.kind]["flight_duration"]
        velocity = world._velocities.get(target.id, (0, 0))
        horizontal, vertical = monster_aim(world, target) if speed and weapon.kind not in EXPLOSIVE_WEAPONS else (target.x, target.y)
        return [horizontal + velocity[0] * flight, vertical + velocity[1] * flight]

    def dodge(self, world, player, movement):
        for projectile in world.visible_projectiles(player):
            if not projectile.hostile:
                continue
            offset_x, offset_y = player.x - projectile.x, player.y - projectile.y
            speed_squared = projectile.velocity_x ** 2 + projectile.velocity_y ** 2
            if speed_squared <= 0:
                continue
            arrival = (offset_x * projectile.velocity_x + offset_y * projectile.velocity_y) / speed_squared
            if 0 < arrival < 0.55 and math.hypot(offset_x - projectile.velocity_x * arrival, offset_y - projectile.velocity_y * arrival) < 0.9:
                sideways = normalized(-projectile.velocity_y, projectile.velocity_x)
                sign = 1 if offset_x * sideways[0] + offset_y * sideways[1] >= 0 else -1
                self.decision = "dodge"
                return [sideways[0] * sign, sideways[1] * sign]
        return movement

    @staticmethod
    def approach_distance(offset_x, offset_y, velocity_x, velocity_y, horizon):
        speed_squared = velocity_x ** 2 + velocity_y ** 2
        arrival = max(0.0, min(horizon, -(offset_x * velocity_x + offset_y * velocity_y) / speed_squared)) if speed_squared > 1e-9 else 0.0
        return math.hypot(offset_x + velocity_x * arrival, offset_y + velocity_y * arrival)

    def avoid_surround(self, world, player, target, monsters, movement, reach):
        nearby = [monster for monster in monsters if distance(player, monster) <= 5.5]
        if len(nearby) < 2:
            self.breakout_until = 0.0
            self.breakout_direction = (0.0, 0.0)
            return movement
        bearings = sorted(math.atan2(monster.y - player.y, monster.x - player.x) for monster in nearby)
        largest_gap = max(second - first for first, second in zip(bearings, [*bearings[1:], bearings[0] + math.tau]))
        flanked = largest_gap < math.tau * 0.72
        crowded = sum(distance(player, monster) < 2.2 for monster in nearby) >= 2
        speed = world.player_speed(player)
        blocked = self.decision in {"retreat", "dodge", "empty"} and any(self.approach_distance(monster.x - player.x, monster.y - player.y, -movement[0] * speed, -movement[1] * speed, 0.6) < 0.95 for monster in nearby)
        if flanked or crowded or blocked:
            self.breakout_until = world.elapsed + 0.45
        elif world.elapsed >= self.breakout_until:
            self.breakout_direction = (0.0, 0.0)
            return movement
        threats = [(monster.x - player.x, monster.y - player.y, *world._velocities.get(monster.id, (0.0, 0.0)), MONSTER_TYPES[monster.kind]["damage"]) for monster in nearby]
        projectiles = [projectile for projectile in world.visible_projectiles(player) if projectile.hostile]
        preferred_range = min(6.0, reach * 0.8)

        def danger(direction):
            velocity_x, velocity_y = direction[0] * speed, direction[1] * speed
            cost = 0.0
            for offset_x, offset_y, enemy_x, enemy_y, weight in threats:
                relative_x, relative_y = enemy_x - velocity_x, enemy_y - velocity_y
                clearance = self.approach_distance(offset_x, offset_y, relative_x, relative_y, 0.6)
                ending = math.hypot(offset_x + relative_x * 0.6, offset_y + relative_y * 0.6)
                cost += weight * (18 * max(0.0, 1.1 - clearance) ** 2 + 1.5 / (ending + 0.45) ** 2)
            for projectile in projectiles:
                clearance = self.approach_distance(projectile.x - player.x, projectile.y - player.y, projectile.velocity_x - velocity_x, projectile.velocity_y - velocity_y, 0.55)
                cost += 12 * max(0.0, 0.8 - clearance) ** 2
            separation = math.hypot(target.x - player.x - velocity_x * 0.6, target.y - player.y - velocity_y * 0.6)
            cost += 0.25 * max(0.0, separation - preferred_range) ** 2
            cost -= 0.35 * (direction[0] * movement[0] + direction[1] * movement[1])
            cost -= 0.45 * (direction[0] * self.breakout_direction[0] + direction[1] * self.breakout_direction[1])
            return cost

        candidates = [tuple(movement), *BREAKOUT_DIRECTIONS]
        direction = min(candidates, key=danger)
        self.breakout_direction = direction
        self.decision = "breakout"
        return list(direction)


AI_TYPES = {"bold": BoldAI}
