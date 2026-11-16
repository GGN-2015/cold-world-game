"""Exercise local heating, downed building, loot, and fixed equipment against SQLite."""

from collections import Counter
from math import hypot, isclose
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cold_world_game.actions import GameError
from cold_world_game.biome_layout import bridge_layout, chunk_biomes, ring_parameters
from cold_world_game.constants import AMMO_PACKS, BURN_SECONDS, CREATIVE_ITEMS, FIXED_HEATER_BURN_SECONDS, PLAYER_SPEED, TERRAIN_VERSION
from cold_world_game.models import Item, Monster, Structure, encode
from cold_world_game.procedural import RandomStream, chest_items, chunk_seed, plan, profile, ring_boundary
from cold_world_game.storage import Storage
from cold_world_game.world import World
from cold_world_game.wildlife import BRIDGE_REPAIRS_PER_CROSSING, CABLE_REPAIR_PARTS, DEVICE_REPAIR_SECONDS, SERVICE_GUN_REPAIR_PARTS, WRENCH_USES


def command(world, action, **fields):
    return world.execute("p", {"type": action, **fields})


def check_temperature(world):
    player = world.players["p"]
    player.x, player.y = 66, 0
    player.hunger = 9
    def place(kind, x, y):
        player.inventory[0] = Item.create(kind, 2 if kind == "floor" else 1)
        player.selected = 0
        command(world, "place", x=x, y=y)
        if kind == "floor":
            assert player.inventory[0].count == 1

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
    player.backpack[:2] = [Item.create("wood", 4), None]
    assert command(world, "craft", recipe="door")["output"] == "door"
    assert command(world, "craft", recipe="door")["output"] == "door"
    assert player.inventory[0].kind == "door" and player.inventory[0].count == 2
    door_id = command(world, "place", x=64, y=0)["id"]
    assert player.inventory[0].count == 1
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
    player.backpack[:4] = [Item.create("spare_part", SERVICE_GUN_REPAIR_PARTS + 2), None, Item.create("wood"), Item.create("lighter")]
    for device in (heater, gun):
        command(world, "input", aim=[device.x, device.y])
        assert command(world, "attack", pressed=True)["repaired"]
    assert wrench.uses == WRENCH_USES - 2 and player.backpack[0].count == 1
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
        assert world.players["p"].inventory[0].uses == WRENCH_USES - 2
        world.join("p")
        player = world.players["p"]
        player.x, player.y = 66, 0
        gun = world.structures[gun_id]
        with world.transaction():
            world.record_structure(gun_id, checkpoint=True)
            gun.repaired = False
        player.inventory[1] = Item.create("spare_part", 3)
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
        assert player.inventory[0].uses == WRENCH_USES - 2 and player.inventory[1].id == item_id
        assert player.inventory[1].count == 3
    finally:
        world.close()


def verify_generation(path):
    seed = 42
    settings = profile()
    old_settings = {key: value for key, value in settings.items() if key not in {"biome_ring"}}
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


def expect_rejection(world, code, action, **fields):
    try:
        command(world, action, **fields)
    except GameError as error:
        assert error.code == code
    else:
        raise AssertionError(f"{action} succeeded; expected {code}")


def verify_material_stacks(path):
    settings = profile()
    previous = {key: value for key, value in settings.items() if key != "stack_limits"}
    for seed in range(42, 58):
        old = chest_items(seed, 0, 0, 0, 0, previous)
        new = chest_items(seed, 0, 0, 0, 0, settings)
        assert Counter(item.kind for item in old if item) == Counter(
            item.kind for item in new if item for _ in range(item.count)
        )
    settings["loot"] = {"weapon": [], "consumable": [("spare_part", 1, [20])], "equipment": []}
    assert sorted(item.count for item in chest_items(42, 0, 0, 0, 0, settings) if item) == [4, 16]

    world = World(Storage(path), 42)
    try:
        world.join("p")
        player = world.players["p"]
        quill = Item.create("quill")
        original = Item.create("fireball_scroll")
        player.inventory[:] = [Item.create("wood") for _ in player.inventory]
        player.inventory[:2] = [quill, original]
        player.backpack[:] = [Item.create("wood") for _ in player.backpack]
        player.backpack[0] = Item.create("papyrus", 3)
        before = encode(player)
        expect_rejection(world, "inventory_full", "copy_scroll", kind=original.kind)
        assert encode(player) == before

        player.inventory[-1] = None
        charges = quill.uses
        assert command(world, "copy_scroll", kind=original.kind)["output"] == original.kind
        assert player.inventory[-1].kind == original.kind and player.inventory[-1].id != original.id
        assert player.inventory[1] is original and player.backpack[0].count == 2 and quill.uses == charges - 1

        player.backpack[0].count = 1
        command(world, "copy_scroll", kind=original.kind)
        assert player.backpack[0].kind == original.kind
        player.backpack[0] = Item.create("papyrus", 2)
        quill.uses = 1
        before = encode(player)
        with patch.object(world.storage, "save", side_effect=OSError("scroll copy save failed")):
            try:
                command(world, "copy_scroll", kind=original.kind)
            except OSError:
                pass
            else:
                raise AssertionError("Scroll copy should roll back when saving fails")
        assert encode(world.players["p"]) == before
    finally:
        world.close()


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
        player.inventory[3].count = profile()["stack_limits"]["door"]
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


def verify_catalog_save_boundary(path):
    world = World(Storage(path), 42)
    try:
        save = world.export()
        assert save.pop("item_catalog_version") == world.catalog()["item_catalog_version"]
        world.storage.save(save)
    finally:
        world.storage.close()
    storage = Storage(path)
    try:
        try:
            World(storage)
        except ValueError as error:
            assert "Use a new save path" in str(error)
        else:
            raise AssertionError("Opened a save from before the item catalog reset")
        assert "item_catalog_version" not in storage.load()
    finally:
        storage.close()


def verify_fuel_and_reload(path):
    world = World(Storage(path), 45)
    try:
        world.join("p")
        player = world.players["p"]
        controls = world.controls["p"]
        player.x, player.y = 66, 0
        for x in range(65, 68):
            if existing := world.structure_at(x, 0):
                world.remove_structure(existing)
        fire = Structure("campfire", 67, 0, fuel=14)
        world.add_structure(fire)
        player.inventory[1] = Item.create("wood", 8)
        command(world, "open", id=fire.id)
        endpoints = {"from": {"kind": "inventory", "slot": 1}, "to": {"kind": "fuel", "id": fire.id}}
        assert command(world, "transfer", **endpoints)["count"] == 1
        assert player.inventory[1].count == 7 and fire.fuel == 15
        command(world, "transfer", **endpoints)
        expect_rejection(world, "invalid_fuel", "transfer", **endpoints)
        assert player.inventory[1].count == 6 and fire.fuel == 16

        command(world, "close")
        player.inventory[0] = Item.create("flamethrower")
        player.inventory[0].uses = 1
        player.backpack[0] = Item.create("gasoline")
        player.backpack[0].uses = 3
        player.inventory[2] = Item.create("gasoline")
        can_id = player.inventory[2].id
        assert command(world, "reload")["duration"] == 1.5
        world.elapsed += 1.5
        with world.transaction():
            world.update_reload(player, controls)
        assert player.inventory[0].uses == 8 and player.backpack[0] is None
        assert player.inventory[2].id == can_id and player.inventory[2].uses == 4
        player.inventory[0].uses = 7
        command(world, "reload")
        world.elapsed += 1.5
        before = encode(player)
        with patch.object(world.storage, "save", side_effect=OSError("forced reload save failure")):
            try:
                with world.transaction():
                    world.update_reload(player, controls)
            except OSError:
                pass
            else:
                raise AssertionError("Fuel transfer must roll back if saving fails")
        assert encode(world.players["p"]) == before
    finally:
        world.close()


def verify_biome_pressure_and_room_spawns(path):
    world = World(Storage(path), 45)
    try:
        rooms = [monster for monster in world.monsters.values() if monster.id.startswith("room:")]
        assert rooms and all(monster.kind == "small" and monster.id != "room:0:0" for monster in rooms)
        removed = rooms[0].id
        with world.transaction():
            world.touch()
            del world.monsters[removed]
    finally:
        world.close()

    world = World(Storage(path))
    try:
        assert removed not in world.monsters and all(monster.id in world.monsters for monster in rooms[1:])
        point = (19, 17)
        assert point not in world.chunks
        with world.transaction():
            world.generate_chunk(*point)
        assert world.chunk_versions[point] == TERRAIN_VERSION
        point_monster = world.monsters["room:19:17"]
        assert point_monster.kind == "small" and world.structure_at(point_monster.x, point_monster.y) is None
        world.join("p")
        player, controls = world.players["p"], world.controls["p"]
        world.monsters.clear()
        player.x, player.y = 65, 0
        player.temperature = 36
        with patch.object(world, "monster_activity", return_value=(True, None)):
            for zones, factor in (((), 1), (("lake",), 3), (("fog",), 3), (("fog", "lake"), 3)):
                with patch.object(world, "biomes_at", return_value=zones):
                    controls.next_paced_spawn = None
                    world.spawn_monster()
                    assert 35 / factor <= controls.next_paced_spawn - world.elapsed <= 55 / factor
            world.monsters = {f"test:{index}": Monster(player.x + 20, index, id=f"test:{index}") for index in range(2)}
            controls.next_paced_spawn = world.elapsed
            with patch.object(world, "biomes_at", return_value=("lake",)), patch.object(world, "spawn_near_player", return_value=True) as spawn:
                controls.paced_spawn_biomes = ("lake",)
                world.spawn_monster()
                assert spawn.call_args.args[2] == ("lake",)
                assert 65 / 3 <= controls.next_paced_spawn - world.elapsed <= 90 / 3
    finally:
        world.close()


def verify_barrier_layout():
    seed = 45
    settings = profile()
    size, radius, width, *_ = parameters = ring_parameters(settings)
    assert radius == 1334
    piers, corridor = bridge_layout(seed, *parameters)
    successors = {next_pier for _, next_pier in piers.values()}
    main = branches = 0
    for root in piers.keys() - successors:
        point, repairs = root, 0
        while point in piers:
            successor = piers[point][1]
            assert point != successor and (point[0] == successor[0] or point[1] == successor[1])
            repairs += 1
            assert repairs <= BRIDGE_REPAIRS_PER_CROSSING
            point = successor
        if hypot(*root) < radius - width:
            assert repairs == BRIDGE_REPAIRS_PER_CROSSING and hypot(*point) > radius + width
            main += 1
        else:
            assert repairs == 2 and radius - width - size <= hypot(*point) <= radius + width + size
            branches += 1
    assert main and branches

    candidates = ((x, y) for x in range(84, 93) for y in range(-9, 10))
    forbidden = next(point for point in candidates if chunk_biomes(seed, *point, *parameters)
                     and RandomStream(chunk_seed(seed, *point)).random() >= .9)
    assert not plan(seed, *forbidden, settings)[1]
    for point in list(corridor)[:8]:
        objects, interior = plan(seed, *point, settings)
        assert not interior
        for item in objects:
            if (item.x, item.y) in corridor[point]:
                assert item.kind == "bridge_pier" and not item.solid and item.biome_link == list(piers[item.x, item.y][1])


def verify_chain_and_crossing_repairs(path):
    world = World(Storage(path), 45)
    try:
        world.join("p")
        player = world.players["p"]
        player.x, player.y = 66, 0
        with world.transaction():
            world.touch()
            for x in range(65, 78):
                for y in range(-4, 8):
                    if entry := world.structure_at(x, y):
                        world.remove_structure(entry)
        root, nearby, one_gap, two_gaps = [Structure("tree", x, y) for x, y in ((70, 1), (71, 1), (70, 3), (73, 1))]
        for tree in (root, nearby, one_gap, two_gaps):
            world.add_structure(tree)
        assert world.harvest_tree(root, player, "chain_chainsaw")[1] == nearby
        world.remove_structure(nearby)
        extra = Structure("tree", 74, 1)
        world.add_structure(extra)
        assert world.harvest_tree(root, player, "chain_chainsaw") == [root, one_gap, two_gaps]
        world.remove_structure(one_gap)
        walls = [Structure("wall", 71, y) for y in range(3)]
        for wall in walls:
            world.add_structure(wall)
        assert world.harvest_tree(root, player, "chain_chainsaw") == [root]
        for entry in (root, two_gaps, extra, *walls):
            world.remove_structure(entry)

        pier = Structure("bridge_pier", 67, 0, biome_link=[72, 0])
        far_pier = Structure("bridge_pier", 72, 0, biome_anchor=[72, 0], biome_link=[76, 0])
        first = Structure("cable_station", 67, 1, biome_anchor=[67, 1], biome_link=[75, 1])
        second = Structure("cable_station", 75, 1, biome_anchor=[75, 1], biome_link=[67, 1])
        for entry in (pier, far_pier, first, second, Structure("floor", 68, 0)):
            world.add_structure(entry)
        assert world.can_stand(pier.x, pier.y, player_id=player.id)
        player.selected = 0
        player.inventory[0] = Item.create("repair_wrench")
        player.backpack[0] = Item.create("spare_part", CABLE_REPAIR_PARTS + 2)
        player.backpack[1] = Item.create("wood", 2)
        command(world, "input", aim=[pier.x, pier.y])
        expect_rejection(world, "missing_bridge_wood", "attack", pressed=True)
        assert player.backpack[0].count == CABLE_REPAIR_PARTS + 2 and player.inventory[0].uses == WRENCH_USES
        player.backpack[1].count = 5
        blocker = Structure("wall", 69, 0)
        world.add_structure(blocker)
        expect_rejection(world, "bridge_blocked", "attack", pressed=True)
        world.remove_structure(blocker)
        assert command(world, "attack", pressed=True)["wood"] == 3
        with world.transaction():
            world.update_player_attack(player, world.controls["p"], DEVICE_REPAIR_SECONDS)
        assert pier.repaired and all(world.structure_at(x, 0).kind == "bridge_deck" for x in range(69, 72))
        assert player.backpack[1].count == 2 and player.backpack[0].count == CABLE_REPAIR_PARTS + 1
        command(world, "input", aim=[first.x, first.y])
        command(world, "attack", pressed=True)
        with world.transaction():
            world.update_player_attack(player, world.controls["p"], DEVICE_REPAIR_SECONDS)
        assert (first.repair_parts, second.repair_parts) == (1, 1) and not first.repaired
        assert player.backpack[0].count == CABLE_REPAIR_PARTS
        ids = first.id, second.id
    finally:
        world.close()

    world = World(Storage(path))
    try:
        world.join("p")
        player = world.players["p"]
        first, second = (world.structures[identifier] for identifier in ids)
        assert (first.repair_parts, second.repair_parts) == (1, 1)
        assert world.structure_at(70, 0).kind == "bridge_deck"
        player.x, player.y = second.x - 1, second.y
        command(world, "input", aim=[second.x, second.y])
        for _ in range(CABLE_REPAIR_PARTS - 1):
            command(world, "attack", pressed=True)
            with world.transaction():
                world.update_player_attack(player, world.controls["p"], DEVICE_REPAIR_SECONDS)
        assert first.repaired and second.repaired and first.repair_parts == second.repair_parts == CABLE_REPAIR_PARTS
        assert player.inventory[0].uses == WRENCH_USES - CABLE_REPAIR_PARTS - 1
        assert player.backpack[0].count == 1
        assert command(world, "attack", pressed=True)["crossed"]
        player.x, player.y = 71, 0
        player.backpack[1].count = 4
        command(world, "input", aim=[72, 0])
        assert command(world, "attack", pressed=True)["wood"] == 4
        before = encode(player)
        with patch.object(world.storage, "save", side_effect=OSError("forced bridge save failure")):
            try:
                with world.transaction():
                    world.update_player_attack(player, world.controls["p"], DEVICE_REPAIR_SECONDS)
            except OSError:
                pass
            else:
                raise AssertionError("Bridge construction must roll back if saving fails")
        assert encode(world.players["p"]) == before and not world.structure_at(72, 0).repaired
        assert all(world.structure_at(x, 0) is None for x in range(73, 77))
    finally:
        world.close()


if __name__ == "__main__":
    with TemporaryDirectory() as directory:
        verify_runtime(Path(directory) / "weather.sqlite")
        verify_generation(Path(directory) / "terrain.sqlite")
        verify_material_stacks(Path(directory) / "materials.sqlite")
        verify_creative(Path(directory) / "creative.sqlite")
        verify_catalog_save_boundary(Path(directory) / "before-catalog.sqlite")
        verify_fuel_and_reload(Path(directory) / "fuel.sqlite")
        verify_biome_pressure_and_room_spawns(Path(directory) / "room-monsters.sqlite")
        verify_barrier_layout()
        verify_chain_and_crossing_repairs(Path(directory) / "crossings.sqlite")
    print("Passed survival and inventory, versioned terrain and spawns, chain harvest, straight bridges, and saved cable repairs.")
