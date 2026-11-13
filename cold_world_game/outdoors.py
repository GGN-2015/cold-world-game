from .actions import GameError
from .constants import BODY_RADIUS, EXPLOSIVE_WEAPONS, MAX_COINS
from .geometry import distance, tile
from .models import Item, Projectile
from .wildlife import SEATS


class Outdoors:
    def seated_structure(self, controls):
        structure = self.structures.get(controls.seat)
        return structure if structure and structure.kind in SEATS else None

    def sit(self, player, controls, structure_id):
        structure = self.structures.get(structure_id) if isinstance(structure_id, str) else None
        if structure is None or structure.kind not in SEATS:
            raise GameError("invalid_seat", "This seat no longer exists")
        if player.temperature < 5:
            raise GameError("downed", "Downed players cannot sit down")
        if controls.seat == structure.id:
            controls.seat = None
            controls.stop_attack()
            return {"seated": False}
        if structure.kind == "mounted_gun":
            if not structure.ammo:
                raise GameError("seat_empty", "The mounted gun has no ammunition")
        if distance(player, structure) > 2 or not self.visible(player.x, player.y, structure.x, structure.y):
            raise GameError("out_of_range", "The seat must be visible and within 2 units")
        if any(other.seat == structure.id for other in self.controls.values()):
            raise GameError("seat_occupied", "Another player is already using this seat")
        if structure.kind == "mounted_gun" and any(distance(monster, structure) <= 2 + 1e-9 for monster in self.monsters.values()):
            raise GameError("seat_unsafe", "A monster is within 2 units of the mounted gun")
        self.touch()
        if structure.kind == "mounted_gun":
            self.clear_mounted_exit(player, structure)
        controls.stop_attack()
        controls.seat = structure.id
        controls.move_x = controls.move_y = 0.0
        controls.velocity_x = controls.velocity_y = 0.0
        controls.movement_epoch += 1
        player.x, player.y = structure.x, structure.y
        return {"seated": True, "id": structure.id}

    def clear_mounted_exit(self, player, structure):
        obstruction = self.structure_at(structure.x + 1, structure.y)
        if obstruction is None or obstruction.kind == "floor":
            return
        if player.money > MAX_COINS - obstruction.balance:
            raise GameError("balance_limit", "The removed bank's coins would exceed the player balance limit")
        self.touch()
        for item in [*obstruction.slots, obstruction.igniter]:
            if item is not None:
                self.drop_item(item, obstruction.x, obstruction.y)
        for amount in range(obstruction.fuel):
            self.drop_item(Item.create("wood"), obstruction.x, obstruction.y)
        player.money += obstruction.balance
        for other in self.controls.values():
            if other.seat == obstruction.id:
                other.seat = None
                other.stop_attack()
                other.movement_epoch += 1
        self.emit_event("break", player.id, obstruction.kind, obstruction.x, obstruction.y, target=obstruction.id)
        self.remove_structure(obstruction)

    def fire_mounted_gun(self, player, controls, structure):
        if not structure.ammo:
            self.leave_empty_mounted_gun(player, controls, structure)
            return
        if not controls.held or controls.ui or player.temperature < 5 or self.elapsed + 1e-9 < player.next_shot or player.last_shot_tick == self.tick_number:
            return
        self.record_structure(structure.id, checkpoint=True)
        weapon = Item("rifle", id=structure.id, ammo=structure.ammo)
        self.fire_gun(player, controls, weapon)
        structure.ammo = weapon.ammo
        if not structure.ammo:
            self.leave_empty_mounted_gun(player, controls, structure)

    def leave_empty_mounted_gun(self, player, controls, structure):
        self.touch()
        self.clear_mounted_exit(player, structure)
        controls.seat = None
        controls.stop_attack()
        controls.move_x = controls.move_y = 0.0
        controls.velocity_x = controls.velocity_y = 0.0
        controls.movement_epoch += 1
        player.x, player.y = structure.x + 1, structure.y
        controls.ghost_monsters.update(monster.id for monster in self.monsters.values() if distance(player, monster) < BODY_RADIUS * 2)

    def collect_mine(self, monster):
        if not self._landmines:
            return
        structure = self.structure_at(tile(monster.x), tile(monster.y))
        if structure and structure.kind == "landmine":
            self._mine_triggers.add(structure.id)

    def detonate_mines(self):
        if not self._landmines:
            self._mine_triggers.clear()
            return
        for monster in self.monsters.values():
            self.collect_mine(monster)
        while self._mine_triggers:
            structure = self.structures.get(self._mine_triggers.pop())
            if structure is None or structure.kind != "landmine":
                continue
            self.touch()
            self.remove_structure(structure)
            settings = EXPLOSIVE_WEAPONS["grenade"]
            blast = Projectile(structure.x, structure.y, 0, 0, 0, settings["damage"], structure.owner or structure.id, kind="grenade", target_x=structure.x, target_y=structure.y)
            self.explode(blast)
