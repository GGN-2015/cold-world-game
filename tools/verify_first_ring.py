"""Exercise local heating, downed building, loot, and fixed equipment against SQLite."""

from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cold_world_game.actions import GameError
from cold_world_game.constants import AMMO_PACKS, BURN_SECONDS, CREATIVE_ITEMS, FIXED_HEATER_BURN_SECONDS, PLAYER_SPEED, TERRAIN_VERSION
from cold_world_game.models import Item, Structure, encode
from cold_world_game.procedural import plan, profile, ring_boundary
from cold_world_game.storage import Storage
from cold_world_game.world import World


def command(world, kind, **fields):
    return world.execute("p", {"type": kind, **fields})


def check_temperature(world):
    player = world.players["p"]
    player.x, player.y = 66, 0
    player.hunger = 9
    def place(kind, x, y):
        player.inventory[0] = Item.create(kind)
        player.selected = 0
        command(world, "place", x=x, y=y)

    world.elapsed = 480
    player.temperature = 0
    assert isclose(world.heating_at(player)[0], world.environment()["ambient_temperature"])
    place("floor", 66, 0)
    place("wall", 65, -2)
    place("campfire", 67, 0)
    fire = world.structure_at(67, 0)
    fire.burn_remaining = BURN_SECONDS
    assert world.heating_at(player) == (12, False, 0, 1)
    for x in range(64, 69):
        for y in range(-2, 3):
            if (x in (64, 68) or y in (-2, 2)) and not world.structure_at(x, y):
                world.add_structure(Structure("wall", x, y))
    assert world.heating_at(player) == (16, True, 12, 1)
    world.add_structure(Structure("floor", 66, -1))
    assert world.heating_at(player) == (20, True, 25, 1)
    world.add_structure(Structure("floor", 66, 1))
    world.add_structure(Structure("chest", 65, 1, slots=[None] * 30))
    assert world.heating_at(player) == (22, True, 42, 1)
    player.x = 65
    assert world.heating_at(player) == (22, True, 42, 2)
    player.x = 66
    for x in range(65, 68):
        for y in range(-1, 2):
            if not world.structure_at(x, y):
                world.add_structure(Structure("floor", x, y))
    assert world.heating_at(player) == (30, True, 100, 1)
    world.update_player_temperature(player, 20)
    assert player.temperature == 5
    player.x = 63
    assert world.heating_at(player)[3] is None
    player.x = 65
    assert world.heating_at(player) == (30, True, 100, 2)
    player.x = 66
    world.remove_structure(world.structure_at(64, 0))
    status = world.snapshot("p")["environment"]
    assert status["room_temperature"] == 12 and not status["room_sealed"] and status["floor_coverage"] == 0
    assert "cold_phase" not in status


def check_large_room(world):
    player = world.players["p"]
    with world.transaction():
        world.touch()
        for x in range(14, 33):
            for y in range(54, 65):
                if structure := world.structure_at(x, y):
                    world.remove_structure(structure)
                if x in (14, 32) or y in (54, 64):
                    world.add_structure(Structure("wall", x, y))
        world.add_structure(Structure("campfire", 16, 59, burn_remaining=BURN_SECONDS))
        player.x, player.y = 21, 59
        assert world.heating_at(player) == (7, False, 0, 5)
        player.x = 26
        assert world.heating_at(player) == (world.environment()["ambient_temperature"], False, 0, None)
        for y in range(55, 64):
            world.add_structure(Structure("wall", 23, y))
        player.x = 21
        assert world.heating_at(player) == (12, True, 0, 5)
        player.x = 26
        assert world.heating_at(player)[3] is None


def check_door(world):
    player = world.players["p"]
    player.x, player.y = 66, 0
    player.temperature = 4
    player.inventory[0] = None
    player.selected = 0
    player.backpack[:2] = [Item.create("wood"), Item.create("wood")]
    assert command(world, "craft", recipe="door")["output"] == "door"
    assert player.inventory[0].kind == "door"
    door_id = command(world, "place", x=64, y=0)["id"]
    door = world.structures[door_id]
    assert world.heating_at(player) == (30, True, 100, 1)
    assert world.barrier_blocks_movement(65, 0, 63, 0)
    assert not world.can_stand(64, 0)
    assert not world.visible(65, 0, 63, 0)
    _, previous = world.terrain_updates("p", {})
    assert command(world, "toggle_door", id=door_id)["door_open"]
    assert not door.solid and world.heating_at(player) == (12, False, 0, 1)
    assert not world.barrier_blocks_movement(65, 0, 63, 0)
    assert world.can_stand(64, 0) and world.visible(65, 0, 63, 0)
    changed, _ = world.terrain_updates("p", previous)
    assert any(entry["id"] == door_id and entry["door_open"] for patch in changed["add"] for entry in patch["add"])
    player.x = 64
    try:
        command(world, "toggle_door", id=door_id)
    except GameError as error:
        assert error.code == "occupied"
    else:
        raise AssertionError("Closed a door on a player")
    player.x = 66
    command(world, "input", aim=[64, 0])
    assert not command(world, "attack", pressed=True)["door_open"]
    assert world.heating_at(player)[1]
    assert command(world, "toggle_door", id=door_id)["door_open"]
    return door_id


def warm_and_fire(world):
    player = world.players["p"]
    player.x, player.y = 66, 0
    player.temperature = 36
    player.hunger = 9
    world.elapsed = 560
    heater = Structure("fixed_heater", 65, 0)
    gun = Structure("service_gun", 68, 0, ammo=0)
    if surface := world.structure_at(65, 0):
        world.remove_structure(surface)
    world.remove_structure(world.structure_at(68, 0))
    world.add_structure(heater)
    world.add_structure(gun)
    player.selected = 0
    wrench = Item.create("repair_wrench")
    player.inventory[0] = wrench
    player.backpack[:4] = [Item.create(kind) for kind in ("spare_part", "spare_part", "wood", "lighter")]
    for device in (heater, gun):
        command(world, "input", aim=[device.x, device.y])
        assert command(world, "attack", pressed=True)["repaired"]
    assert wrench.uses == 10 and player.backpack[:2] == [None, None]
    assert gun.ammo == 0
    command(world, "open", id=heater.id)
    for slot, target in enumerate(("fuel", "igniter"), 2):
        command(world, "transfer", **{"from": {"kind": "backpack", "slot": slot}, "to": {"kind": target, "id": heater.id}})
    assert command(world, "light", id=heater.id)["lit"]
    assert heater.burn_remaining == FIXED_HEATER_BURN_SECONDS
    command(world, "close")
    command(world, "sit", id=gun.id)
    player.backpack[0] = Item.create("rifle_ammo")
    command(world, "reload")
    world.elapsed += 2
    world.tick(.05)
    assert player.backpack[0] is None and gun.ammo == AMMO_PACKS["rifle_ammo"]
    command(world, "input", aim=[gun.x + 1, gun.y])
    command(world, "attack", pressed=True)
    world.tick(.05)
    assert gun.ammo == AMMO_PACKS["rifle_ammo"] - 1
    gun.ammo = 1
    player.next_shot = 0
    world.tick(.05)
    assert gun.ammo == 0 and player.inventory[0].id == wrench.id
    return heater.id, gun.id


def verify_runtime(path):
    world = World(Storage(path), 42)
    try:
        world.join("p")
        with world.transaction():
            world.touch()
            for x in range(61, 75):
                for y in range(-6, 7):
                    if structure := world.structure_at(x, y):
                        world.remove_structure(structure)
        check_temperature(world)
        check_large_room(world)
        door_id = check_door(world)
        heater_id, gun_id = warm_and_fire(world)
        player = world.players["p"]
        player.x, player.y = 66, 0
        player.selected = 0
        player.inventory[1:3] = [None, None]
        vendor = Structure("vending_machine", 65, 1)
        if surface := world.structure_at(65, 1):
            world.remove_structure(surface)
        world.add_structure(vendor)
        command(world, "open", id=vendor.id)
        player.money = 5
        assert command(world, "trade", id=vendor.id, offer="buy_wrench")["output"] == "repair_wrench"
        assert command(world, "trade", id=vendor.id, offer="buy_spare_part")["output"] == "spare_part"
        assert [item.kind for item in player.inventory[1:3]] == ["repair_wrench", "spare_part"]
        player.inventory[1:] = [Item.create("wood") for _ in player.inventory[1:]]
        player.backpack[:] = [Item.create("wood") for _ in player.backpack]
        try:
            command(world, "trade", id=vendor.id, offer="buy_spare_part")
        except GameError as error:
            assert error.code == "inventory_full"
        else:
            raise AssertionError("Purchase succeeded in a full inventory")
        assert player.money == 1
        try:
            command(world, "craft", recipe="spare_part")
        except GameError as error:
            assert error.code == "invalid_recipe"
        else:
            raise AssertionError("Spare part could be crafted")
        player.backpack[0] = Item.create("wood")
        player.inventory[2] = None
        command(world, "craft", recipe="fence")
        assert player.inventory[2].kind == "fence" and player.inventory[2].count == 2
        assert player.backpack[0] is None
        player.inventory[2] = None
        wood_in_hotbar = sum(item.count for item in player.inventory if item and item.kind == "wood")
        with world.transaction():
            world.drop_item(Item.create("wood"), player.x, player.y)
            world.pickup(player)
        assert sum(item.count for item in player.inventory if item and item.kind == "wood") == wood_in_hotbar + 1
    finally:
        world.close()
    world = World(Storage(path))
    try:
        assert "cold_snap_epoch" not in world.export_metadata()
        assert world.structures[door_id].door_open
        assert world.structures[heater_id].repaired
        assert world.structures[gun_id].repaired and world.structures[gun_id].ammo == 0
        assert world.players["p"].inventory[0].uses == 10
        world.join("p")
        player = world.players["p"]
        player.x, player.y = 66, 0
        gun = world.structures[gun_id]
        with world.transaction():
            world.record_structure(gun_id, checkpoint=True)
            gun.repaired = False
        player.inventory[1] = Item.create("spare_part")
        item_id = player.inventory[1].id
        command(world, "input", aim=[gun.x, gun.y])
        with patch.object(world.storage, "save", side_effect=OSError("forced save failure")):
            try:
                command(world, "attack", pressed=True)
            except OSError:
                pass
            else:
                raise AssertionError("Repair succeeded despite a save failure")
        player = world.players["p"]
        assert not world.structures[gun_id].repaired and world.structures[gun_id].ammo == 0
        assert player.inventory[0].uses == 10 and player.inventory[1].id == item_id
    finally:
        world.close()


def verify_generation(path):
    seed = 42
    settings = profile()
    old_settings = {key: value for key, value in settings.items() if key not in {"loot", "quality_loot", "biome_ring", "biome_loot", "extra_chest_loot"}}
    old_settings["version"] = 21
    old_settings["ring"] = {"radius": 667, "gates": 24}
    world = World(Storage(path), seed)
    try:
        old_point = next((x, y) for x in range(40, 50) for y in range(-4, 5)
                         if (x, y) != (45, 1) and ring_boundary(seed, x, y, settings["size"], 667))
        before, _ = plan(seed, *old_point, old_settings)
        world.generation_profiles["21"] = old_settings
        world.chunks.add(old_point)
        world.chunk_versions[old_point] = 21
        world.remember_baseline(old_point, before)
        for structure in before:
            world.add_structure(structure)
        old = world.export()
        old["cold_snap_epoch"] = 0
        world.storage.save(old)
    finally:
        world.storage.close()
    world = World(Storage(path))
    try:
        assert world.chunk_versions[old_point] == 21
        assert "cold_phase" not in world.environment()
        assert all(encode(world.structures[entry.id]) == encode(entry) for entry in before)
        world.generate_chunk(45, 1)
        assert world.chunk_versions[45, 1] == TERRAIN_VERSION
        edge = next(item for item in world.structures.values() if item.kind in {"ring_wall", "ring_gate"})
        assert world.barrier_blocks_movement(edge.x - 1, edge.y, edge.x + 1, edge.y)
        assert not world.can_stand(edge.x, edge.y)
        edge_id = edge.id
        world.join("p")
        player = world.players["p"]
        player.x, player.y = 82, 0
        gate = Structure("ring_gate", 83, 0)
        with world.transaction():
            world.touch()
            for x in (82, 83, 84):
                if entry := world.structure_at(x, 0):
                    world.remove_structure(entry)
            world.add_structure(gate)
        player.selected = 1
        command(world, "input", aim=[gate.x, gate.y])
        command(world, "attack", pressed=True)
        for _ in range(30):
            command(world, "input", aim=[gate.x, gate.y])
            world.tick(.05)
        assert gate.id not in world.structures
        assert not world.barrier_blocks_movement(82, 0, 84, 0)
    finally:
        world.close()
    world = World(Storage(path))
    try:
        assert world.chunk_versions[old_point] == 21 and world.chunk_versions[45, 1] == TERRAIN_VERSION
        assert edge_id in world.structures
        assert gate.id not in world.structures
        assert all(encode(world.structures[entry.id]) == encode(entry) for entry in before)
    finally:
        world.close()


def expect_rejection(world, code, kind, **fields):
    try:
        command(world, kind, **fields)
    except GameError as error:
        assert error.code == code
    else:
        raise AssertionError(f"{kind} succeeded; expected {code}")


def verify_creative(path):
    world = World(Storage(path), 42, admin="p")
    try:
        world.join("p")
        world.join("guest")
        try:
            world.execute("guest", {"type": "admin", "command": "creative"})
        except GameError as error:
            assert error.code == "admin_forbidden"
        else:
            raise AssertionError("Guest was allowed to grant creative items")
        player = world.players["p"]
        controls = world.controls["p"]
        player.x, player.y = 66, 0
        with world.transaction():
            world.touch()
            for x in range(64, 69):
                if entry := world.structure_at(x, 0):
                    world.remove_structure(entry)
            vendor = Structure("vending_machine", 67, 0)
            chest = Structure("chest", 68, 0, slots=[None] * 30)
            world.add_structure(vendor)
            world.add_structure(chest)
        player.temperature, player.hunger = 0, 0
        epoch = controls.movement_epoch
        assert world.player_speed(player) == 0
        expect_rejection(world, "materials_missing", "craft", recipe="door")
        command(world, "open", id=vendor.id)
        expect_rejection(world, "insufficient_money", "trade", id=vendor.id, offer="buy_cola")
        command(world, "close")
        command(world, "admin", command="creative")
        assert {item.kind for item in player.backpack if item} == CREATIVE_ITEMS.keys()
        assert (player.temperature, player.hunger) == (36, 10)
        assert controls.movement_epoch == epoch + 1
        assert world.player_speed(player) == PLAYER_SPEED * 2
        with world.transaction():
            world.hurt_player(player, 50, direction=(-1, 0), knockback=.25)
        assert player.x < 66 and (player.temperature, player.hunger) == (36, 10)
        world.update_player(player, controls, 1)
        assert (player.temperature, player.hunger) == (36, 10)
        assert command(world, "craft", recipe="door")["output"] == "door"
        assert player.inventory[3].kind == "door"
        expect_rejection(world, "materials_missing", "craft", recipe="recycle_fences")
        player.x = 66
        command(world, "open", id=vendor.id)
        assert command(world, "trade", id=vendor.id, offer="buy_cola")["output"] == "cola"
        assert player.money == 0 and player.inventory[4].kind == "cola"
        assert not (CREATIVE_ITEMS.keys() & profile()["items"].keys())
        command(world, "open", id=chest.id)
        shoes = next(slot for slot, item in enumerate(player.backpack) if item and item.kind == "creative_shoes")
        command(world, "transfer", **{"from": {"kind": "backpack", "slot": shoes}, "to": {"kind": "chest", "slot": 0, "id": chest.id}})
        assert world.player_speed(player) == PLAYER_SPEED
        command(world, "transfer", **{"from": {"kind": "chest", "slot": 0, "id": chest.id}, "to": {"kind": "backpack", "slot": shoes}})
        assert world.player_speed(player) == PLAYER_SPEED * 2
        command(world, "open", id=vendor.id)
        for storage in (player.inventory, player.backpack):
            storage[:] = [item or Item.create("wood") for item in storage]
        before = encode(player)
        expect_rejection(world, "inventory_full", "craft", recipe="door")
        expect_rejection(world, "inventory_full", "trade", id=vendor.id, offer="buy_cola")
        assert encode(player) == before
        player.inventory[-1] = None
        before = encode(player)
        with patch.object(world.storage, "save", side_effect=OSError("creative craft save failed")):
            try:
                command(world, "craft", recipe="door")
            except OSError:
                pass
            else:
                raise AssertionError("Craft should roll back when saving fails")
        assert encode(world.players["p"]) == before
    finally:
        world.close()
    world = World(Storage(path), admin="p")
    try:
        world.join("p")
        assert world.player_speed(world.players["p"]) == PLAYER_SPEED * 2
        assert world.snapshot("p")["you"]["creative"]["free_craft"]
    finally:
        world.close()


if __name__ == "__main__":
    with TemporaryDirectory() as directory:
        verify_runtime(Path(directory) / "weather.sqlite")
        verify_generation(Path(directory) / "terrain.sqlite")
        verify_creative(Path(directory) / "creative.sqlite")
    print("Passed heating, downed construction, hotbar priority, purchases, repair rollback, versioned terrain and creative items.")
