"""Measure each catalog item's effect and selected survival combinations."""

import argparse
import csv
import json
from collections import Counter
from itertools import combinations_with_replacement
from pathlib import Path
from tempfile import TemporaryDirectory

if __package__:
    from .combat_sweep import Arena, PLAYER, STEP, Setup
else:
    from combat_sweep import Arena, PLAYER, STEP, Setup

from cold_world_game import constants as rules
from cold_world_game.actions import GameError
from cold_world_game.expansion import carried_modifier
from cold_world_game.models import Item, Monster, Structure
from cold_world_game.procedural import profile
from cold_world_game.storage import Storage


class Fixture(Arena):
    def __init__(self, storage):
        super().__init__(storage, Setup("open_field", "bold", "automatic", 1, 42))
        self.waves.clear()
        self.ambient = -12

    def environment(self):
        return super().environment() | {"ambient_temperature": self.ambient}

    def update_monsters(self, seconds):
        # Fixed targets isolate damage, spread and statuses from target AI.
        pass


def command(world, kind, **fields):
    return world.execute(PLAYER, {"type": kind, **fields})


def hold(world, duration, aim=(1, 0), target=None, move=(0, 0)):
    command(world, "input", aim=list(aim), move=list(move), target_id=target)
    command(world, "attack", pressed=True)
    advance(world, duration)
    command(world, "attack", pressed=False)


def advance(world, seconds, move=(0, 0)):
    for tick in range(round(seconds / STEP)):
        if tick % 5 == 0:
            command(world, "input", move=list(move))
        world.tick(STEP)


def setup_item(world, kind):
    player = world.players[PLAYER]
    player.inventory[:] = [Item.create(kind)] + [None] * (len(player.inventory) - 1)
    player.backpack[:] = [None] * len(player.backpack)
    player.hunger = 4
    player.temperature = 12
    player.money = 20
    return player


def place(world, kind, point=(1, 0)):
    world.players[PLAYER].inventory[0] = Item.create(kind)
    identifier = command(world, "place", x=point[0], y=point[1])["id"]
    return world.structures[identifier]


def light(world, fire, igniter, fuel=1):
    player = world.players[PLAYER]
    player.backpack[:fuel + 1] = [Item.create(igniter)] + [Item.create("wood") for _ in range(fuel)]
    command(world, "open", id=fire.id)
    command(world, "transfer", **{"from": {"kind": "backpack", "slot": 0}, "to": {"kind": "igniter", "id": fire.id}})
    for index in range(1, fuel + 1):
        command(world, "transfer", **{"from": {"kind": "backpack", "slot": index}, "to": {"kind": "fuel", "id": fire.id}})
    command(world, "light", id=fire.id)
    command(world, "close")
    return next((item.uses for item in player.backpack if item and item.kind == igniter), 0)


def weapon(world, player, kind, category, distance=None):
    if distance is None:
        distance = min(2, rules.MELEE_WEAPONS[kind]["range"]) if category == "melee" else 4
    positions = ((distance, 0), (distance, 1), (distance + 1, -1))
    targets = [Monster(x, y, id=f"target-{index}", hp=100) for index, (x, y) in enumerate(positions)]
    world.monsters.update((target.id, target) for target in targets)
    item = player.inventory[0]
    before_ammo, before_uses, before_money = item.ammo, item.uses, player.money
    duration = rules.EXPLOSIVE_WEAPONS[kind]["duration"] if category == "explosive" else STEP
    hold(world, duration, positions[0], targets[0].id)
    advance(world, 5)
    damage = [round(100 - target.hp, 3) for target in targets]
    return {
        "target_damage": damage, "targets_hit": sum(value > 0 for value in damage),
        "ammo_spent": (before_ammo or 0) - (item.ammo or 0),
        "uses_spent": (before_uses or 0) - (item.uses or 0),
        "coins_spent": before_money - player.money, "consumed": player.inventory[0] is None,
        "freeze_applied": any(target.frozen_until > 1200 for target in targets),
        "burn_applied": any(target.burning_until > 1200 for target in targets),
    }


def audit_item(world, kind, category):
    player = setup_item(world, kind)
    if category in ("gun", "melee", "explosive"):
        observed = weapon(world, player, kind, category)
        assert sum(observed["target_damage"]) > 0
        return observed
    if category == "food":
        needs_fire = kind not in rules.READY_TO_EAT_FOODS
        if needs_fire:
            hold(world, .5)
            assert player.inventory[0].kind == kind
            world.add_structure(Structure("campfire", 1, 0, burn_remaining=20))
        before = player.hunger
        hold(world, .5, (0, 1))
        restored = round(player.hunger - before + .5 * rules.HUNGER_PER_MINUTE / 60, 4)
        assert restored == rules.FOODS[kind]
        return {"hunger_restored": restored, "needs_fire": needs_fire, "byproduct": player.inventory[0].kind if player.inventory[0] else None}
    if category == "healing":
        definition = rules.HEALING_ITEMS[kind]
        hold(world, definition["duration"])
        if "supplies" in definition:
            supplies = Counter(item.kind for item in player.backpack if item)
            assert supplies == definition["supplies"]
            return {"supplies": supplies}
        assert any(event["type"] == "heal" for event in world.events)
        return {"temperature_after": round(player.temperature, 3), "hunger_after": round(player.hunger, 3),
                "duration": definition["duration"], "uses": definition.get("uses", 1)}
    if category == "drink":
        hold(world, rules.DRINKS[kind]["duration"])
        assert player.excitement_remaining > 0
        advance(world, 15)
        return {"temperature_after_15s": round(player.temperature, 3), "felt_temperature": world.temperature_at(player)}
    if category == "revival":
        world.join("teammate")
        teammate = world.players["teammate"]
        teammate.x, teammate.y, teammate.temperature, teammate.hunger = 0.8, 0, 3, 1
        hold(world, rules.REVIVAL_ITEMS[kind]["duration"], (.8, 0), teammate.id)
        assert teammate.temperature >= 5
        return {"teammate_temperature": teammate.temperature, "teammate_hunger": teammate.hunger, "co_op_only": True}
    if category == "return":
        player.x = 8
        hold(world, rules.RETURN_ITEMS[kind]["duration"], (9, 0))
        assert (player.x, player.y) == (0, 0)
        return {"returned_to_origin": True, "duration": rules.RETURN_ITEMS[kind]["duration"], "uses": rules.RETURN_ITEMS[kind]["uses"]}
    if category == "igniter":
        fire = place(world, "campfire")
        charges = light(world, fire, kind)
        assert fire.lit and charges == rules.IGNITERS[kind] - 1
        return {"charges": rules.IGNITERS[kind], "fuel_seconds": fire.burn_remaining}
    if category == "equipment":
        player.temperature = 30
        initial_speed = world.player_speed(player)
        advance(world, 1, (1, 0))
        assert abs(player.x - initial_speed) < 1e-6
        return {"tiles_per_second_selected": initial_speed, "speed_multiplier": rules.EQUIPPED_ITEMS[kind]["speed_multiplier"]}
    if category == "passive":
        player.temperature = 30
        felt = world.temperature_at(player)
        advance(world, 6)
        natural_temperature, natural_hunger = player.temperature, player.hunger
        target_distance = 2 if kind == "axe_handle" else 1.25
        monster = Monster(target_distance, 0, id="test-monster", hp=100)
        world.monsters[monster.id] = monster
        player.inventory[1] = Item.create("axe")
        command(world, "select", slot=1)
        hold(world, STEP, (target_distance, 0), monster.id)
        world.hurt_player(player, 5, source=monster.id, direction=(-1, 0), knockback=1)
        world.drop_item(Item.create("wood"), player.x + 1, player.y)
        advance(world, STEP)
        return {"felt_temperature": felt, "temperature_after_6s": round(natural_temperature, 4),
                "hunger_after_6s": round(natural_hunger, 4), "monster_hit_temperature_loss": round(natural_temperature - player.temperature + STEP / 60 * world.body_temperature_rate(felt), 4),
                "knockback": round(abs(player.x), 3), "axe_damage": 100 - monster.hp,
                "picked_up_at_one_tile": not world.ground}
    if category == "material":
        assert command(world, "craft", recipe="campfire")["output"] == "campfire"
        return {"crafted": "campfire"}
    if category == "repair":
        device = Structure("service_gun", 1, 0, ammo=0)
        world.add_structure(device)
        player.inventory[:2] = [Item.create("repair_wrench"), Item.create("spare_part")]
        command(world, "input", aim=[1, 0])
        assert command(world, "attack", pressed=True)["repaired"]
        assert player.inventory[1] is None and player.inventory[0].uses == 11 and device.ammo == 48
        return {"repairable": device.kind, "ammo_after_repair": device.ammo, "parts_spent": 1, "wrench_uses_spent": 1}
    if category == "creative":
        assert player.creative_effects() == rules.CREATIVE_ITEMS[kind]
        return player.creative_effects()
    if category == "biome_tool":
        return {"carried": player.carries(kind)}
    if category == "building_wand":
        wand = rules.BUILDING_WANDS[kind]
        player.backpack[:len(wand["tiles"])] = [Item.create("wood") for _ in wand["tiles"]]
        result = command(world, "place", x=2, y=0)
        assert result["count"] == len(wand["tiles"]) and player.inventory[0].kind == kind
        return {"building": wand["building"], "placed": result["count"]}
    if category == "currency":
        before = player.money
        world.drop_item(Item.create("coin"), .4, 0)
        advance(world, STEP)
        assert player.money == before + 1
        return {"wallet_added": 1, "inventory_slot_used": False}

    structure = place(world, kind)
    assert world.structure_at(1, 0).id == structure.id
    result = {"placed": True, "blocks_movement": kind in rules.SOLID}
    if kind == "campfire":
        light(world, structure, "lighter")
        advance(world, 6)
        result["temperature_after_6s"] = round(player.temperature, 3)
    elif kind == "landmine":
        monster = Monster(1, 0, id="mine-target", hp=100)
        world.monsters[monster.id] = monster
        advance(world, STEP)
        assert monster.hp < 100 and structure.id not in world.structures
        result["damage"] = 100 - monster.hp
    elif kind == "chest":
        player.backpack[0] = Item.create("wood")
        command(world, "open", id=structure.id)
        command(world, "transfer", **{"from": {"kind": "backpack", "slot": 0}, "to": {"kind": "chest", "slot": 0, "id": structure.id}})
        assert structure.slots[0].kind == "wood"
        result["slots"] = len(structure.slots)
    elif kind == "piggy_bank":
        command(world, "open", id=structure.id)
        assert command(world, "bank", id=structure.id, operation="deposit", amount=2)["balance"] == 2
        assert command(world, "bank", id=structure.id, operation="withdraw", amount=2)["balance"] == 0
        result["round_trip_coins"] = 2
    elif kind in rules.MACHINE_OFFERS:
        command(world, "open", id=structure.id)
        for offer_id, recipe in rules.MACHINE_OFFERS[kind].items():
            player.backpack[:] = [
                Item.create(material) for material, count in recipe["inputs"].items()
                if material != "coin" for _ in range(count)
            ]
            player.backpack.extend([None] * (rules.BACKPACK_SLOTS - len(player.backpack)))
            player.money = 100
            assert command(world, "trade", id=structure.id, offer=offer_id)["output"] == recipe["output"]
        result["offers_exercised"] = len(rules.MACHINE_OFFERS[kind])
    return result


def combinations(world, name):
    player = setup_item(world, "axe")
    if name in {"coat_scarf", "lunchbox_duplicates", "boots_ring", "armor_helmet"}:
        items, metric, expected = {
            "coat_scarf": (("down_coat", "wool_scarf"), lambda: world.temperature_at(player), -6),
            "lunchbox_duplicates": (("insulated_lunchbox", "insulated_lunchbox"), lambda: carried_modifier(player, "hunger_drain_multiplier", minimum=True), .8),
            "boots_ring": (("snow_boots", "swiftness_ring"), lambda: world.player_speed(player), 3),
            "armor_helmet": (("armor_plate", "safety_helmet"), None, None),
        }[name]
        player.inventory[:2] = [Item.create(kind) for kind in items]
        if metric:
            together = metric()
            player.inventory[1] = None
            first_only = metric()
            assert together == first_only == expected
            return {"first_only": first_only, "together": together, "stacks": False}
        world.hurt_player(player, 5, source="monster", direction=(1, 0), knockback=1)
        assert (player.temperature, player.x) == (8, .75)
        return {"temperature_loss": 4, "knockback": .75}
    if name == "campfire_cooked_food":
        fire = place(world, "campfire")
        player.inventory[0] = Item.create("beef")
        hold(world, .5, (0, 1))
        assert player.inventory[0].kind == "beef"
        light(world, fire, "lighter")
        hold(world, .5, (0, 1))
        assert player.inventory[0] is None
        return {"temperature_after": round(player.temperature, 3), "hunger_after": round(player.hunger, 3)}
    if name == "fuel_pack_space":
        player.inventory[:] = [Item.create("wood") for _ in player.inventory]
        player.backpack[:] = [Item.create("wood") for _ in player.backpack]
        player.inventory[0] = Item.create("fuel_pack")
        hold(world, 1)
        assert player.inventory[0].kind == "fuel_pack"
        player.backpack[:4] = [None] * 4
        hold(world, 1)
        assert player.inventory[0].kind == "wood" and all(player.backpack)
        return {"wood": 5, "extra_free_slots_needed": 4}
    if name == "badge_weapon":
        player.inventory[1] = Item.create("sheriff_badge")
        small = Monster(1, 0, id="small", hp=100)
        armored = Monster(1, 1, id="armored", species="armored", hp=100)
        world.monsters.update((target.id, target) for target in (small, armored))
        hold(world, STEP, (1, 0), small.id)
        multiplier = rules.PASSIVE_ITEMS["sheriff_badge"]["damage_multiplier"]
        assert (100 - small.hp, 100 - armored.hp) == (rules.AXE["damage"] * multiplier, rules.AXE["damage"])
        return {"small_damage": 100 - small.hp, "armored_damage": 100 - armored.hp}
    if name == "ice_fire":
        player.inventory[:2] = [Item.create("ice_staff"), Item.create("flame_staff")]
        target = Monster(1.8, 0, id="mixed-target", hp=100)
        world.monsters[target.id] = target
        hold(world, STEP, (target.x, target.y), target.id)
        assert target.frozen_until > world.elapsed
        frozen_at = target.frozen_until
        advance(world, .5)
        command(world, "select", slot=1)
        hold(world, STEP, (target.x, target.y), target.id)
        assert target.frozen_until == frozen_at and target.burning_until > world.elapsed
        immediate_damage = 100 - target.hp
        advance(world, 3)
        assert 100 - target.hp > immediate_damage
        return {"coexisting_effects": ["freeze", "burn"], "damage_immediate": immediate_damage, "damage_after_3s": 100 - target.hp}
    if name == "warming_and_hunger":
        player.hunger = 0
        player.inventory[:2] = [Item.create("pocket_stove"), Item.create("compressed_biscuits")]
        hold(world, .5)
        assert player.temperature > 18 and player.hunger == 0
        starving = world.temperature_at(player)
        command(world, "select", slot=1)
        hold(world, .5)
        fed = world.temperature_at(player)
        assert starving == rules.STARVATION_AMBIENT and fed == -12
        return {"felt_temperature_while_starving": starving, "felt_temperature_after_food": fed}
    if name == "wood_campfire_igniter":
        player.backpack[0] = Item.create("wood")
        assert command(world, "craft", recipe="campfire")["output"] == "campfire"
        assert player.inventory[1].kind == "campfire"
        command(world, "select", slot=1)
        fire = world.structures[command(world, "place", x=1, y=0)["id"]]
        charges = light(world, fire, "lighter")
        assert fire.lit and charges == rules.IGNITERS["lighter"] - 1
        return {"wood_spent": 2, "ignitions_spent": 1, "burn_seconds": fire.burn_remaining}
    if name == "speed_and_weapon":
        player.temperature = 30
        player.inventory[:2] = [Item.create("handgun"), Item.create("swiftness_ring")]
        command(world, "select", slot=1)
        advance(world, 1, (1, 0))
        boosted = player.x
        command(world, "select", slot=0)
        advance(world, 1, (1, 0))
        assert round(boosted) == 12 and round(player.x - boosted) == 4
        return {"tiles_per_second_ring_selected": boosted, "tiles_per_second_weapon_selected": player.x - boosted}
    raise ValueError(name)


def accessory_pair(world, kinds):
    first, second = kinds
    player = setup_item(world, first)
    player.temperature = 32
    player.hunger = 9
    player.inventory[1] = Item.create(second)
    player.backpack[0] = Item.create("axe")
    carried = set(kinds)
    bonus = max((rules.EXPANSION_ITEMS.get(kind, {}).get("settings", {}).get("ambient_bonus", 0) for kind in kinds))
    hunger_rate = rules.HUNGER_PER_MINUTE * (.8 if "insulated_lunchbox" in carried else 1)
    damage_taken = .8 if "armor_plate" in carried else 1
    knockback = .75 if "safety_helmet" in carried else 1
    multiplier = rules.PASSIVE_ITEMS["sheriff_badge"]["damage_multiplier"] if "sheriff_badge" in carried else 1
    blade_damage = multiplier * rules.AXE["damage"]
    selected_speeds = []
    for slot, kind in enumerate(kinds):
        command(world, "select", slot=slot)
        expected = rules.PLAYER_SPEED * rules.EQUIPPED_ITEMS.get(kind, {}).get("speed_multiplier", 1)
        assert abs(world.player_speed(player) - expected) < 1e-8
        selected_speeds.append(expected)
    assert world.temperature_at(player) == world.ambient + bonus
    advance(world, 1)
    assert abs(player.hunger - (9 - hunger_rate / 60)) < 1e-8
    ambient = world.temperature_at(player)
    assert ambient == world.ambient + bonus
    world.elapsed = 1200
    world.hurt_player(player, 5, source="monster", direction=(1, 0), knockback=1)
    assert abs(player.x - knockback) < 1e-8
    assert abs(player.hunger - (9 - hunger_rate / 60 - 5 * damage_taken)) < 1e-8
    drop = world.drop_item(Item.create("wood"), player.x + 1, player.y)
    advance(world, STEP)
    assert (drop.id not in world.ground) == ("collector_glove" in carried)
    command(world, "transfer", **{"from": {"kind": "backpack", "slot": 0}, "to": {"kind": "inventory", "slot": 3}})
    command(world, "select", slot=3)
    target = Monster(player.x + 1.25, 0, id="pair-target", hp=100)
    world.monsters[target.id] = target
    hold(world, STEP, (target.x, target.y), target.id)
    assert target.hp == 100 - blade_damage
    return {"items": list(kinds), "speeds": selected_speeds, "natural_hunger_rate": hunger_rate,
            "felt_temperature": ambient, "hit_damage_taken": 5 * damage_taken,
            "knockback": knockback, "axe_damage": blade_damage}


GROUPS = {
    "gun": rules.GUNS, "melee": rules.MELEE_WEAPONS, "explosive": rules.EXPLOSIVE_WEAPONS,
    "food": rules.FOODS, "healing": rules.HEALING_ITEMS, "drink": rules.DRINKS,
    "revival": rules.REVIVAL_ITEMS, "return": rules.RETURN_ITEMS, "igniter": rules.IGNITERS,
    "equipment": rules.EQUIPPED_ITEMS, "passive": rules.PASSIVE_ITEMS, "structure": rules.BUILDINGS,
    "material": {"wood"}, "currency": {"coin"}, "repair": {"repair_wrench", "spare_part"},
    "creative": rules.CREATIVE_ITEMS,
    "biome_tool": set(rules.BIOME_ITEMS) - rules.MELEE_WEAPONS.keys() - rules.EXPLOSIVE_WEAPONS.keys(),
    "building_wand": rules.BUILDING_WANDS,
}
COMBINATIONS = ("coat_scarf", "lunchbox_duplicates", "boots_ring", "armor_helmet",
                "campfire_cooked_food", "fuel_pack_space", "badge_weapon", "ice_fire",
                "warming_and_hunger", "wood_campfire_igniter", "speed_and_weapon")


def sources():
    terrain = profile()
    locations = {}
    for kind in rules.CREATIVE_ITEMS:
        locations[kind] = {"admin_command": "creative"}
    for kind in rules.BIOME_ITEMS:
        locations[kind] = {"normal_chest_pool": "biome_loot"}
    for kind, chance in terrain["rare"]:
        locations.setdefault(kind, {})["rare_chest_roll"] = chance
    for kind, stream, chance in terrain["machines"]:
        locations.setdefault(kind, {})["building_roll"] = chance
    for group in ("foods", "igniters"):
        for kind in terrain[group]:
            locations.setdefault(kind, {})["common_chest_pool"] = group
    for kind in ("handgun", "shotgun", "rifle", "wood"):
        locations.setdefault(kind, {})["common_chest_pool"] = "guns" if kind != "wood" else "wood"
    for machine, offers in rules.MACHINE_OFFERS.items():
        for offer in offers.values():
            locations.setdefault(offer["output"], {}).setdefault("trades", []).append(
                {"machine": machine, "inputs": offer["inputs"], "count": offer["count"]},
            )
    for recipe in rules.RECIPES.values():
        locations.setdefault(recipe["output"], {}).setdefault("recipes", []).append(recipe)
    return locations


def in_world(probe, *arguments):
    with TemporaryDirectory(prefix="cold-item-audit-") as directory:
        storage = Storage(Path(directory) / "world.sqlite3")
        try:
            world = Fixture(storage)
            world.prepare()
            return probe(world, *arguments)
        finally:
            storage.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("replays/item-audit"))
    args = parser.parse_args()
    kinds = [item for group in GROUPS.values() for item in group]
    if len(kinds) != len(set(kinds)) or set(kinds) != rules.ITEM_KINDS:
        raise RuntimeError("Each current item must belong to exactly one audit group")
    results, errors = [], []
    locations = sources()
    for category, group in GROUPS.items():
        for kind in sorted(group):
            try:
                observed = in_world(audit_item, kind, category)
                if category == "gun":
                    for distance in (2, 8, 12):
                        observed[f"damage_at_{distance}_tiles"] = in_world(
                            lambda world: weapon(world, setup_item(world, kind), kind, category, distance),
                        )["target_damage"][0]
                item = Item.create(kind)
                results.append({"item": kind, "category": category, "default_ammo": item.ammo, "default_uses": item.uses,
                                "sources": locations.get(kind, {}), "observed": observed})
            except (AssertionError, GameError, RuntimeError) as error:
                errors.append({"item": kind, "error": str(error) or "Unexpected game outcome"})
    pairs = []
    for name in COMBINATIONS:
        try:
            pairs.append({"name": name, "observed": in_world(combinations, name)})
        except (AssertionError, GameError, RuntimeError) as error:
            errors.append({"combination": name, "error": str(error) or "Unexpected game outcome"})
    accessory_pairs = []
    accessories = sorted(rules.PASSIVE_ITEMS.keys() | rules.EQUIPPED_ITEMS.keys())
    for pair in combinations_with_replacement(accessories, 2):
        try:
            accessory_pairs.append(in_world(accessory_pair, pair))
        except (AssertionError, GameError, RuntimeError) as error:
            errors.append({"accessory_pair": pair, "error": str(error) or "Unexpected game outcome"})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {"catalog_count": len(kinds), "items": results, "combinations": pairs, "accessory_pairs": accessory_pairs, "errors": errors}
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with args.output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("item", "category", "default_ammo", "default_uses", "sources", "observed"))
        writer.writeheader()
        writer.writerows(row | {key: json.dumps(row[key], allow_nan=False) for key in ("sources", "observed")} for row in results)
    print(f"{len(results)}/{report['catalog_count']} items; {len(pairs)}/{len(COMBINATIONS)} combinations; "
          f"{len(accessory_pairs)}/{len(accessories) * (len(accessories) + 1) // 2} accessory pairs")
    for error in errors:
        print(error)
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
