"""Run paired combat and expedition fixtures against the current game rules."""

import argparse
import csv
import itertools
import json
import math
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory

if __package__:
    from .combat_sweep import Arena, GUN_RANGES, LOADOUTS, PLAYER, Setup, run_match
    from .item_audit import command, hold, light, place
else:
    from combat_sweep import Arena, GUN_RANGES, LOADOUTS, PLAYER, Setup, run_match
    from item_audit import command, hold, light, place

from cold_world_game import constants as rules
from cold_world_game.geometry import chunk, tile
from cold_world_game.models import Item, Structure
from cold_world_game.procedural import plan, profile
from cold_world_game.storage import Storage


RATION = "compressed_biscuits"
KIT_SLOTS = 6
CARRY_SLOTS = KIT_SLOTS + 2
ROUTE_LIMIT = 24 * 60
ROUTE_STEP = .5
RUNS = (41, 42, 43, 44)
ROUTES = {
    "mild": (-6, (620, 840), 2),
    "cold": (-12, (740, 1030), 2),
    "deep_cold": (-22, (860, 1130), 1),
    "no_loot": (-12, (15_000, 16_000), 0),
    "full_pack": (-12, (310, 390), 1),
}
BUILDS = {
    "rations": (RATION,) * 6,
    "travel": ("swiftness_ring",) + (RATION,) * 5,
    "boots": ("snow_boots",) + (RATION,) * 5,
    "insulation": ("down_coat",) + (RATION,) * 5,
    "double_insulation": ("down_coat", "wool_scarf") + (RATION,) * 4,
    "ration_saver": ("insulated_lunchbox",) + (RATION,) * 5,
    "warmers": ("pocket_stove", "warming_flask") + (RATION,) * 4,
    "first_aid": ("first_aid_kit", "first_aid_kit") + (RATION,) * 4,
    "cook": ("lighter", "wood", "wood", "festival_dumpling", "beef", "curry_rice"),
    "packed_fuel": ("lighter", "fuel_pack", "beef", "curry_rice", RATION, RATION),
    "fire_rations": ("lighter", "wood", "wood") + (RATION,) * 3,
    "balanced": ("down_coat", "swiftness_ring", "insulated_lunchbox") + (RATION,) * 3,
    "travel_heat": ("swiftness_ring", "warming_flask", "down_coat") + (RATION,) * 3,
    "travel_fire": ("swiftness_ring", "lighter", "wood", "wood", "beef", RATION),
    "defense_travel": ("armor_plate", "safety_helmet", "down_coat") + (RATION,) * 3,
    "clutter": ("wool_scarf", "safety_helmet", "collector_glove", "oreos", "seaweed_roll", "rice_cracker"),
}
COMBAT = {
    "sidearm": ("sidearm", ()),
    "spread": ("spread", ()),
    "automatic": ("automatic", ()),
    "precision": ("precision", ()),
    "freeze": ("freeze", ()),
    "burn": ("burn", ()),
    "rifle": ("rifle", ()),
    "ice_fire": ("ice_fire", ()),
    "fire_control": ("fire_control", ()),
    "auto_badge": ("automatic", ("sheriff_badge",)),
    "auto_armor": ("automatic", ("armor_plate",)),
    "auto_helmet": ("automatic", ("safety_helmet",)),
    "auto_defense": ("automatic", ("armor_plate", "safety_helmet")),
    "auto_badge_armor": ("automatic", ("sheriff_badge", "armor_plate")),
}


class RouteWorld(Arena):
    def __init__(self, storage, scenario, seed):
        self.ambient, spacing, food_count = ROUTES[scenario]
        rng = random.Random(seed)
        self.stops = []
        position = 0
        while position <= ROUTE_LIMIT * rules.PLAYER_SPEED * 3:
            position += rng.randint(*spacing)
            food = rng.choices(
                (RATION, "beef", "curry_rice", "mixed_nuts", "cola"),
                (22, 24, 12, 22, 20), k=food_count,
            )
            extra = rng.choices(("wood", "wood", "matches", "heat_patch", "glucose_vial", "fuel_pack"),
                                (32, 32, 14, 8, 9, 5), k=2 if food_count else 0)
            if scenario == "full_pack" and not self.stops:
                extra = ["down_coat", "warming_flask", "first_aid_kit"]
            self.stops.append((position, [*food, *extra]))
        super().__init__(storage, Setup("open_field", "bold", "sidearm", 1, seed))
        self.waves.clear()

    def ensure_terrain(self, x, y):
        if not self.chunks:
            self.origin_region = [(0, 0)]
        for point in itertools.product(range(chunk(x) - 1, chunk(x) + 2), (-1, 0, 1)):
            if point not in self.chunks:
                self.chunks.add(point)
                self._terrain_dirty = True

    def environment(self):
        return super().environment() | {"ambient_temperature": self.ambient}


def carried(player):
    return [item for item in (*player.inventory, *player.backpack) if item]


def slots(player, kind):
    return [index for index, item in enumerate(player.inventory) if item and item.kind == kind]


def put_in_hotbar(world, kind, source):
    player = world.players[PLAYER]
    index = player.inventory.index(None)
    command(world, "transfer", **{"from": source, "to": {"kind": "inventory", "slot": index}})
    assert player.inventory[index].kind == kind
    return index


class Expedition:
    def __init__(self, world, kit, pickup):
        if len(kit) != KIT_SLOTS:
            raise ValueError("Expedition loadouts must use exactly six kit slots")
        self.world = world
        world.join(PLAYER)
        self.player = world.players[PLAYER]
        self.player.inventory[:CARRY_SLOTS] = [Item.create(kind) for kind in ("handgun", "axe", *kit)]
        self.pickup = pickup
        self.cache_index = 0
        self.caches = 0
        self.taken = 0
        self.skipped = 0
        self.replaced = 0
        self.food_eaten = 0
        self.heat_used = 0
        self.fires = 0
        self.rest = 0.0
        self.first_downed = None
        self.fire = None
        self.history = []
        self.actions = []

    def use(self, kind, duration):
        index = slots(self.player, kind)[0]
        command(self.world, "select", slot=index)
        hold(self.world, duration, (self.player.x, self.player.y - 2))
        self.actions.append({"s": round(self.world.elapsed - self.start, 2), "use": kind})

    def supplies(self):
        return carried(self.player)

    def take_cache(self):
        x, loot = self.world.stops[self.cache_index]
        if self.player.x < x - .75:
            return
        self.cache_index += 1
        self.caches += 1
        cache = Structure("chest", x, 1, slots=[Item.create(kind) for kind in loot])
        with self.world.transaction():
            self.world.add_structure(cache)
        command(self.world, "open", id=cache.id)
        for index, item in sorted(enumerate(cache.slots), key=lambda pair: -self.value(pair[1])):
            if len(self.supplies()) >= CARRY_SLOTS:
                if self.pickup == "greedy":
                    self.skipped += 1
                    continue
                candidates = [(self.value(current), slot)
                              for slot, current in enumerate(self.player.inventory)
                              if current and current.kind not in {"axe", "handgun"}]
                value, replace_slot = min(candidates, default=(math.inf, None))
                if self.value(item) <= value:
                    self.skipped += 1
                    continue
                # Move the relinquished item into an empty chest slot.
                cache.slots.append(None)
                command(self.world, "transfer", **{
                    "from": {"kind": "inventory", "slot": replace_slot},
                    "to": {"kind": "chest", "id": cache.id, "slot": len(cache.slots) - 1},
                })
                self.replaced += 1
            put_in_hotbar(self.world, item.kind, {"kind": "chest", "id": cache.id, "slot": index})
            self.taken += 1
        command(self.world, "close")

    def value(self, item):
        p = self.player
        kind = item.kind
        items = self.supplies()
        if kind in rules.FOODS:
            ready = kind in rules.READY_TO_EAT_FOODS
            return rules.FOODS[kind] * (1.4 if p.hunger < 4 else 1) * (1 if ready else .65 if self.can_light() else .25)
        if kind in rules.IGNITERS:
            best = max((held.uses for held in items if held is not item and held.kind in rules.IGNITERS), default=0)
            return 1 + min(item.uses, 10) * .45 if item.uses > best else .2
        if kind in {"wood", "fuel_pack"}:
            can_light = any(held.kind in rules.IGNITERS for held in items)
            wood = sum(held.kind == "wood" and held is not item for held in items)
            return (4 if wood < 2 else 1.4) * (1 if can_light else .25)
        if kind in rules.HEALING_ITEMS:
            rule = rules.HEALING_ITEMS[kind]
            heat = rule.get("temperature_delta", 24 if "temperature" in rule else 0)
            hunger = rule.get("hunger_delta", 6 if "hunger" in rule else 0)
            return (heat / (4 if p.temperature < 17 else 9) + hunger / 2) * (item.uses or 1)
        if kind in {"down_coat", "wool_scarf"}:
            return 7 if kind == "down_coat" else .2 if any(held.kind == "down_coat" for held in items) else 3.5
        return 7 if kind in {"swiftness_ring", "snow_boots", "insulated_lunchbox"} else 1

    def can_light(self):
        items = self.supplies()
        return any(item.kind in rules.IGNITERS for item in items) and (
            sum(item.kind == "wood" for item in items) >= 2 or any(item.kind == "fuel_pack" for item in items)
        )

    def can_cook(self):
        return self.fire and self.fire.lit and abs(tile(self.player.x) - self.fire.x) + abs(tile(self.player.y) - self.fire.y) <= 3

    def light_fire(self):
        world, p = self.world, self.player
        if len(slots(p, "wood")) < 2:
            self.use("fuel_pack", 1)
            for index, item in enumerate(p.backpack):
                if item and item.kind == "wood" and len(slots(p, "wood")) < 2:
                    put_in_hotbar(world, "wood", {"kind": "backpack", "slot": index})
        command(world, "craft", recipe="campfire")
        index = next(index for index, item in enumerate(p.backpack) if item and item.kind == "campfire")
        slot = put_in_hotbar(world, "campfire", {"kind": "backpack", "slot": index})
        command(world, "select", slot=slot)
        x, y = tile(p.x), -1
        if world.structure_at(x, y):
            y = 1
        fire = world.structures[command(world, "place", x=x, y=y)["id"]]
        command(world, "open", id=fire.id)
        igniter_slot = max((i for i, item in enumerate(p.inventory) if item and item.kind in rules.IGNITERS), key=lambda i: p.inventory[i].uses)
        for kind, slot in (("igniter", igniter_slot), ("fuel", slots(p, "wood")[0])):
            command(world, "transfer", **{"from": {"kind": "inventory", "slot": slot}, "to": {"kind": kind, "id": fire.id}})
        command(world, "light", id=fire.id)
        command(world, "close")
        for index, item in enumerate(p.backpack):
            if item and item.kind in rules.IGNITERS and None in p.inventory:
                put_in_hotbar(world, item.kind, {"kind": "backpack", "slot": index})
        # Wood from a fuel pack may still be in the backpack. Load excess into the fire.
        for index, item in enumerate(p.backpack):
            if item and item.kind == "wood":
                command(world, "open", id=fire.id)
                command(world, "transfer", **{"from": {"kind": "backpack", "slot": index}, "to": {"kind": "fuel", "id": fire.id}})
                command(world, "close")
        self.fire = fire
        self.fires += 1
        self.actions.append({"s": round(world.elapsed - self.start, 2), "use": "campfire"})
        return True

    def act(self):
        world, p = self.world, self.player
        if p.temperature < 5 and self.first_downed is None:
            self.first_downed = round(world.elapsed - self.start, 2)
        if p.hunger <= 6 and p.temperature >= 5:
            options = [item.kind for item in p.inventory if item and item.kind in rules.FOODS
                       and (self.can_cook() or item.kind in rules.READY_TO_EAT_FOODS)]
            if options:
                self.use(max(options, key=rules.FOODS.get), .5)
                self.food_eaten += 1
                return True
            if slots(p, "glucose_vial") and p.hunger < 3:
                self.use("glucose_vial", .5)
                return True
        target_temperature = 31 if p.hunger > 1 else 17
        if self.can_cook() and p.temperature < target_temperature:
            self.rest += ROUTE_STEP
            command(world, "input", move=[0, 0])
            world.tick(ROUTE_STEP)
            return True
        if p.temperature < 14 or (p.hunger < 2 and slots(p, "first_aid_kit")):
            for kind in ("first_aid_kit", "heat_patch", "warming_flask", "pocket_stove", "field_supply"):
                if slots(p, kind):
                    self.use(kind, rules.HEALING_ITEMS[kind]["duration"])
                    self.heat_used += 1
                    return True
        if (p.temperature < 16 or p.hunger < 3 and any(item.kind in rules.FOODS for item in self.supplies())) and self.can_light() and not self.can_cook():
            if self.light_fire():
                return True
        if p.temperature < 5:
            return False
        for kind in ("swiftness_ring", "hiking_cane", "snow_boots"):
            choices = slots(p, kind)
            if choices:
                if p.selected != choices[0]:
                    command(world, "select", slot=choices[0])
                break
        stop_at = world.stops[self.cache_index][0] - .6
        movement = min(1, max(0, (stop_at - p.x) / (world.player_speed(p) * ROUTE_STEP)))
        command(world, "input", move=[movement, 0])
        world.tick(ROUTE_STEP)
        return True

    def run(self):
        self.start = self.world.elapsed
        sample = 0
        while self.world.elapsed - self.start < ROUTE_LIMIT:
            elapsed = self.world.elapsed - self.start
            if elapsed >= sample:
                p = self.player
                self.history.append([round(elapsed, 2), round(p.x, 2), round(p.temperature, 2), round(p.hunger, 2)])
                sample += 60
            self.take_cache()
            if not self.act():
                break
        return {
            "seconds": round(self.world.elapsed - self.start, 2), "distance": round(self.player.x, 2),
            "caches": self.caches, "took": self.taken, "skipped": self.skipped, "replaced": self.replaced,
            "food": self.food_eaten, "heat": self.heat_used, "fires": self.fires, "rest_seconds": self.rest,
            "temperature": round(self.player.temperature, 2), "hunger": round(self.player.hunger, 2),
            "first_downed": self.first_downed, "finished": self.world.elapsed - self.start >= ROUTE_LIMIT,
            "history": self.history, "actions": self.actions,
        }


def expedition(job):
    scenario, build, seed, pickup = job
    with TemporaryDirectory(prefix="cold-expedition-") as folder:
        storage = Storage(Path(folder) / "route.sqlite3")
        try:
            world = RouteWorld(storage, scenario, seed)
            result = Expedition(world, BUILDS[build], pickup).run()
        finally:
            storage.close()
    return {"scenario": scenario, "build": build, "seed": seed, "pickup": pickup, **result}


def combat(job):
    build, density, seed = job
    category, items = COMBAT[build]
    LOADOUTS.update(rifle=("rifle", "axe"), ice_fire=("ice_carbine", "flame_staff"),
                    fire_control=("handgun", "flame_staff"))
    GUN_RANGES.update(rifle=11, ice_fire=9, fire_control=8)
    run = run_match((Setup("open_field", "bold", category, density, seed, carried=items,
                           melee_followup=build in ("ice_fire", "fire_control")), False))
    return {"build": build, "density": density, "seed": seed, **run["summary"]}


def acquisition():
    settings = profile()
    counts = Counter()
    chests = buildings = 0
    for seed, x, y in itertools.product(RUNS, range(-14, 15), range(-14, 15)):
        if (x, y) == (0, 0):
            continue
        structures, interior = plan(seed, x, y, settings)
        buildings += bool(interior)
        for structure in structures:
            if structure.kind != "chest":
                continue
            chests += 1
            counts.update({item.kind for item in structure.slots if item})
    return [
        {"build": build, "item": kind, "chests_with_item": counts[kind], "chests": chests, "building_chunks": buildings}
        for build, kit in BUILDS.items() if build != "clutter"
        for kind in dict.fromkeys(kit) if kind not in {RATION, "wood", "lighter"}
    ]


def shelter():
    rows = []
    for fuel in (0, 1, 4):
        with TemporaryDirectory(prefix="cold-shelter-") as folder:
            storage = Storage(Path(folder) / "shelter.sqlite3")
            try:
                world = RouteWorld(storage, "deep_cold", RUNS[0])
                world.join(PLAYER)
                player = world.players[PLAYER]
                player.hunger = 0
                if fuel:
                    fire = place(world, "campfire")
                    light(world, fire, "lighter", fuel)
                start = world.elapsed
                at_20_minutes = None
                while world.elapsed - start < 30 * 60 and player.temperature >= 5:
                    world.tick(ROUTE_STEP)
                    if world.elapsed - start == 20 * 60:
                        at_20_minutes = round(player.temperature, 2)
                rows.append({"fuel": fuel, "seconds": world.elapsed - start, "temperature_at_20min": at_20_minutes,
                             "hunger": player.hunger, "food": 0, "ambient": world.ambient})
            finally:
                storage.close()
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("all", "route", "combat", "pressure", "packing", "acquisition", "shelter"), default="all")
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--output", type=Path, default=Path("replays/build-benchmark"))
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("jobs must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.suite in ("all", "acquisition"):
        write(args.output, "acquisition", acquisition())
    if args.suite in ("all", "shelter"):
        write(args.output, "shelter", shelter())
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        if args.suite in ("all", "route"):
            kits = [build for build in BUILDS if build != "clutter"]
            routes = list(itertools.product(("mild", "cold", "deep_cold"), kits, RUNS, ("smart",)))
            routes += list(itertools.product(("mild", "cold", "deep_cold"), ("rations", "balanced", "packed_fuel"), RUNS, ("greedy",)))
            routes += [("no_loot", build, RUNS[0], "smart") for build in kits]
            write(args.output, "route", list(executor.map(expedition, routes, chunksize=1)))
        if args.suite in ("all", "combat"):
            fights = list(itertools.product(COMBAT, (16, 24), RUNS))
            write(args.output, "combat", list(executor.map(combat, fights, chunksize=1)))
        if args.suite in ("all", "pressure"):
            builds = ("automatic", "auto_badge", "auto_armor", "auto_helmet", "auto_defense", "auto_badge_armor",
                      "rifle", "fire_control", "ice_fire")
            fights = itertools.product(builds, (32, 36), RUNS)
            write(args.output, "pressure", list(executor.map(combat, fights, chunksize=1)))
        if args.suite in ("all", "packing"):
            packing = list(itertools.product(("full_pack",), ("clutter",), RUNS, ("smart", "greedy")))
            write(args.output, "packing", list(executor.map(expedition, packing, chunksize=1)))


def write(output, name, rows):
    with (output / (name + ".json")).open("w", encoding="utf-8") as stream:
        json.dump(rows, stream, ensure_ascii=False, allow_nan=False)
    detail = [{key: value for key, value in row.items() if key not in {"history", "actions"}} for row in rows]
    with (output / (name + ".csv")).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(detail[0]))
        writer.writeheader()
        writer.writerows(detail)
    if "seconds" in rows[0]:
        print(name, len(rows), "runs", "median simulated seconds", median(row["seconds"] for row in rows), flush=True)
    else:
        print(name, len(rows), "rows", flush=True)


if __name__ == "__main__":
    main()
