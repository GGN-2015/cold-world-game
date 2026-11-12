from .actions import GameError
from .constants import EXPLOSIVE_WEAPONS
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
        if distance(player, structure) > 2 or not self.visible(player.x, player.y, structure.x, structure.y):
            raise GameError("out_of_range", "The seat must be visible and within 2 units")
        if any(other.seat == structure.id for other in self.controls.values()):
            raise GameError("seat_occupied", "Another player is already using this seat")
        if structure.kind == "mounted_gun" and any(distance(monster, structure) <= 2 + 1e-9 for monster in self.monsters.values()):
            raise GameError("seat_unsafe", "A monster is within 2 units of the mounted gun")
        self.touch()
        controls.stop_attack()
        controls.seat = structure.id
        controls.move_x = controls.move_y = 0.0
        controls.velocity_x = controls.velocity_y = 0.0
        controls.movement_epoch += 1
        player.x, player.y = structure.x, structure.y
        return {"seated": True, "id": structure.id}

    def fire_mounted_gun(self, player, controls, structure):
        if not controls.held or controls.ui or player.temperature < 5 or not structure.ammo or self.elapsed + 1e-9 < player.next_shot or player.last_shot_tick == self.tick_number:
            return
        self.record_structure(structure.id, checkpoint=True)
        weapon = Item("rifle", id=structure.id, ammo=structure.ammo)
        self.fire_gun(player, controls, weapon)
        structure.ammo = weapon.ammo

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
