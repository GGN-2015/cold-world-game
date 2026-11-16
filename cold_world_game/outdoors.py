from .actions import GameError
from .biomes import BIOME_DEVICES
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
            controls.reload_target = None
            return {"seated": False}
        if distance(player, structure) > 2 or not self.visible(player.x, player.y, structure.x, structure.y):
            raise GameError("out_of_range", "The seat must be visible and within 2 units")
        if any(other.seat == structure.id for other in self.controls.values()):
            raise GameError("seat_occupied", "Another player is already using this seat")
        if structure.kind == "service_gun" and not structure.repaired:
            raise GameError("device_broken", "Repair this gun before using it")
        if structure.kind != "park_bench" and any(distance(monster, structure) <= 2 + 1e-9 for monster in self.monsters.values()):
            raise GameError("seat_unsafe", "A monster is within 2 units of the mounted gun")
        self.touch()
        controls.stop_attack()
        controls.reload_target = None
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
        if not structure.ammo or not controls.held or controls.ui or player.temperature < 5 or self.elapsed + 1e-9 < player.next_shot or player.last_shot_tick == self.tick_number:
            return
        self.record_structure(structure.id, checkpoint=True)
        weapon = Item("rifle", id=structure.id, ammo=structure.ammo)
        self.fire_gun(player, controls, weapon, mounted=True)
        structure.ammo = weapon.ammo

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

    def repair_device(self, player, controls, device, wrench, seconds=0):
        if player.temperature < 5 or distance(player, device) > 2 or not self.visible(player.x, player.y, device.x, device.y, ignore=device.id):
            raise GameError("out_of_range", "A standing player must be within 2 units of the device")
        if device.repaired:
            raise GameError("device_working", "This device is still working")
        if not wrench.uses:
            raise GameError("wrench_spent", "A usable wrench is required")
        part = next(((items, slot) for items in (player.backpack, player.inventory)
                     for slot, item in enumerate(items) if item and item.kind == "spare_part"), None)
        if not part:
            raise GameError("missing_spare_part", "Repair requires one spare part")
        persistent = device.kind in BIOME_DEVICES
        other = None
        if persistent:
            controls.held = True
            self.progress(controls, "repair:" + device.id, seconds)
            if controls.progress + 1e-9 < 1.5:
                return {"accepted": True}
            other = self.crossing_endpoint(device)
        self.record_structure(device.id, checkpoint=True)
        part[0][part[1]] = None
        wrench.uses -= 1
        if not wrench.uses:
            player.inventory[player.selected] = None
        device.repaired = True
        if persistent:
            self.finish_crossing_repair(device, other)
        controls.stop_attack()
        return {"repaired": True, "id": device.id}

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
