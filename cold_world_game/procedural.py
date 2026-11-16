import hashlib
import json

from . import constants as rules
from .models import Item, Structure
from .room_machines import ROOM_MACHINES
from .wildlife import OUTDOOR_FEATURES
from .terrain import flood


MASK = 0xFFFFFFFF


def seed_words(text):
    digest = hashlib.md5(text.encode("utf-8"), usedforsecurity=False).digest()
    return [int.from_bytes(digest[offset:offset + 4], "little") for offset in range(0, 16, 4)]


def derive(*parts):
    content = json.dumps([str(part) for part in parts], ensure_ascii=False, separators=(",", ":"))
    return hashlib.md5(content.encode("utf-8"), usedforsecurity=False).hexdigest()


class RandomStream:
    def __init__(self, seed):
        self.words = seed_words(seed)
        for warmup in range(12):
            self.random()

    def random(self):
        first, second, third, fourth = self.words
        total = (first + second + fourth) & MASK
        self.words = [second ^ (second >> 9), (third + (third << 3)) & MASK, (((third << 21) | (third >> 11)) + total) & MASK, (fourth + 1) & MASK]
        return total / 4294967296

    def randint(self, lower, upper):
        return lower + int(self.random() * (upper - lower + 1))

    def choice(self, values):
        return values[self.randint(0, len(values) - 1)]

    def uniform(self, lower, upper):
        return lower + (upper - lower) * self.random()

    def choices(self, values, weights, count=1):
        result = []
        for index in range(count):
            target = self.random() * sum(weights)
            cumulative = 0
            for value, weight in zip(values, weights):
                cumulative += weight
                if target < cumulative:
                    result.append(value)
                    break
        return result

    def shuffle(self, values):
        for index in range(len(values) - 1, 0, -1):
            other = self.randint(0, index)
            values[index], values[other] = values[other], values[index]

    def sample(self, values, count):
        values = list(values)
        self.shuffle(values)
        return values[:count]


def profile():
    rare = dict(rules.RARE_CHEST_ITEMS)
    for kind in ("first_aid_kit", "return_staff", "ice_staff", "grenade", "flame_staff", "defibrillator", "heat_patch", "sheriff_badge", "vodka", "swiftness_ring", "homing_missile"):
        rare[kind] = getattr(rules, kind.upper() + "_CHANCE")
    machines = [[kind, stream, chance] for kind, stream, chance in (
        ("vending_machine", "vending_machine:v1", rules.VENDING_MACHINE_CHANCE),
        ("match_machine", "match_machine:v1", rules.MATCH_MACHINE_CHANCE),
        ("gun_machine", "gun_machine:v1", rules.GUN_MACHINE_CHANCE),
        ("piggy_bank", "piggy_bank:v1", rules.PIGGY_BANK_CHANCE),
    )]
    machines.extend([kind, "room_machine:" + kind + ":v1", definition["chance"]] for kind, definition in ROOM_MACHINES.items())
    result = {"algorithm": 1, "version": rules.TERRAIN_VERSION, "size": rules.CHUNK_SIZE, "machines": machines, "outdoors": {kind: dict(definition) for kind, definition in OUTDOOR_FEATURES.items()}, "rare": [[kind, chance] for kind, chance in sorted(rare.items())], "foods": list(rules.COMMON_CHEST_FOODS), "igniters": list(rules.COMMON_CHEST_IGNITERS), "items": {kind: {"ammo": item.ammo, "uses": item.uses} for kind in sorted(rules.ITEM_KINDS) if (item := Item.create(kind))}}
    result["chest_gun_chance"] = rules.CHEST_GUN_CHANCE
    result["digest"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return result


def chunk_seed(seed, horizontal, vertical):
    return derive(seed, "chunk", horizontal, vertical)


def cell_seed(seed, horizontal, vertical, tile_x, tile_y):
    return derive(chunk_seed(seed, horizontal, vertical), "tile", tile_x, tile_y)


def chest_items(seed, horizontal, vertical, tile_x, tile_y, settings):
    base = cell_seed(seed, horizontal, vertical, tile_x, tile_y)
    items = []
    for name, chance in (("wood", .5), ("gun", settings.get("chest_gun_chance", .1)), ("food", .3), ("igniter", .2)):
        stream = RandomStream(derive(base, "loot", name))
        if stream.random() >= chance:
            continue
        if name == "wood":
            items.extend(["wood"] * stream.randint(1, 5))
        elif name == "gun":
            roll = stream.random()
            items.append("handgun" if roll < .7 else "shotgun" if roll < .9 else "rifle")
        elif name == "food":
            items.extend(stream.choice(settings["foods"]) for count in range(stream.randint(1, 5)))
        else:
            items.append(stream.choice(settings["igniters"]))
    for kind, chance in settings["rare"]:
        if RandomStream(derive(base, "loot", kind)).random() < chance:
            items.append(kind)
    slots = items + [None] * max(0, 30 - len(items))
    RandomStream(derive(base, "loot", "shuffle")).shuffle(slots)
    return [Item(kind, id=f"ni:{horizontal}:{vertical}:{tile_x}:{tile_y}:{index}", **settings["items"][kind]) if kind else None for index, kind in enumerate(slots)]


class LayoutV1:
    def __init__(self, seed):
        self.seed = seed

    def feature_generator(self, feature, chunk_x, chunk_y):
        return RandomStream(derive(chunk_seed(self.seed, chunk_x, chunk_y), "feature", feature))

    def populate_machine(self, objects, interior, chunk_x, chunk_y, kind, feature, chance, preserve_paths=True):
        generator = self.feature_generator(feature, chunk_x, chunk_y)
        if generator.random() >= chance:
            return
        center_x, center_y = chunk_x * 15, chunk_y * 15
        bounds = center_x - 8, center_x + 8, center_y - 8, center_y + 8
        blocked = {(structure.x, structure.y) for structure in objects}
        containers = [(structure.x, structure.y) for structure in objects if structure.kind != "wall"]
        interior = set(interior)
        protected = interior & flood([(bounds[0], bounds[2])], blocked, bounds) if preserve_paths else set()
        passages = {position for position in interior if any((position[0] + offset_x, position[1] + offset_y) not in interior and (position[0] + offset_x, position[1] + offset_y) not in blocked for offset_x, offset_y in ((1, 0), (-1, 0), (0, 1), (0, -1)))} if preserve_paths else set()
        candidates = sorted(set(interior) - blocked)
        generator.shuffle(candidates)
        for position in candidates:
            if position in passages:
                continue
            if any(max(abs(position[0] - target[0]), abs(position[1] - target[1])) <= 1 for target in containers):
                continue
            reachable = flood([(bounds[0], bounds[2])], blocked | {position}, bounds)
            if preserve_paths and not (protected - {position}) <= reachable:
                continue
            if not (set(interior) & reachable) or any(not any((target[0] + offset_x, target[1] + offset_y) in reachable for offset_x, offset_y in ((1, 0), (-1, 0), (0, 1), (0, -1))) for target in [*containers, position]):
                continue
            objects.append(Structure(kind, *position))
            return

    def building(self, generator, center_x, center_y):
        for attempt in range(100):
            width, height = generator.randint(7, 13), generator.randint(7, 13)
            left = center_x + generator.randint(-6, 7 - width)
            bottom = center_y + generator.randint(-6, 7 - height)
            right, top = left + width - 1, bottom + height - 1
            perimeter = {(tile_x, tile_y) for tile_x in range(left, right + 1) for tile_y in range(bottom, top + 1) if tile_x in (left, right) or tile_y in (bottom, top)}
            for edge in generator.sample(range(4), generator.randint(1, 2)):
                opening = generator.randint(1, 2)
                if edge < 2:
                    start = generator.randint(left + 1, right - opening)
                    perimeter.difference_update((start + offset, bottom if edge == 0 else top) for offset in range(opening))
                else:
                    start = generator.randint(bottom + 1, top - opening)
                    perimeter.difference_update((left if edge == 2 else right, start + offset) for offset in range(opening))
            interior = {(tile_x, tile_y) for tile_x in range(left + 1, right) for tile_y in range(bottom + 1, top)}
            pillar_count = min(5, max(1, len(interior) // 20))
            pillars = set(generator.sample(sorted(interior), pillar_count))
            chest_positions = []
            candidates = sorted(interior - pillars)
            generator.shuffle(candidates)
            desired = generator.randint(1, 2)
            for position in candidates:
                if all(max(abs(position[0] - other[0]), abs(position[1] - other[1])) > 1 for other in chest_positions):
                    chest_positions.append(position)
                    if len(chest_positions) == desired:
                        break
            if len(chest_positions) != desired:
                continue
            blocked = perimeter | pillars | set(chest_positions)
            reachable = flood([(left - 1, bottom - 1)], blocked, (left - 1, right + 1, bottom - 1, top + 1))
            if not (interior & reachable) or any(not any((position[0] + offset_x, position[1] + offset_y) in reachable for offset_x, offset_y in ((1, 0), (-1, 0), (0, 1), (0, -1))) for position in chest_positions):
                continue
            objects = [Structure("wall", tile_x, tile_y) for tile_x, tile_y in sorted(perimeter | pillars)]
            objects.extend(Structure("chest", tile_x, tile_y, slots=[]) for tile_x, tile_y in chest_positions)
            return objects, sorted(interior)
        raise RuntimeError("Unable to generate a reachable building")


def plan(seed, horizontal, vertical, settings):
    if settings["algorithm"] != 1:
        raise ValueError("Unsupported procedural terrain algorithm")
    builder = LayoutV1(seed)
    stream = RandomStream(chunk_seed(seed, horizontal, vertical))
    center_x, center_y = horizontal * settings["size"], vertical * settings["size"]
    roll = stream.random()
    interior = []
    if (horizontal, vertical) == (0, 0) or roll >= .9:
        objects, interior = builder.building(stream, center_x, center_y)
        for kind, feature, chance in settings["machines"]:
            builder.populate_machine(objects, interior, horizontal, vertical, kind, feature, chance, preserve_paths=True)
    elif roll >= .5:
        objects = [Structure("tree", tile_x, tile_y) for tile_x in range(center_x - 7, center_x + 8) for tile_y in range(center_y - 7, center_y + 8) if int(derive(cell_seed(seed, horizontal, vertical, tile_x, tile_y), "tree")[:8], 16) / 4294967296 < .1]
    else:
        objects = []
        for kind, definition in settings["outdoors"].items():
            feature = builder.feature_generator(definition["stream"], horizontal, vertical)
            if feature.random() < definition["chance"]:
                occupied = {(structure.x, structure.y) for structure in objects}
                candidates = [(center_x + offset_x, center_y + offset_y) for offset_x in range(-6, 7) for offset_y in range(-6, 7) if (center_x + offset_x, center_y + offset_y) not in occupied]
                if settings["version"] >= 22 and kind == "mounted_gun":
                    candidates = [position for position in candidates if (position[0] + 1, position[1]) not in occupied]
                if candidates:
                    objects.append(Structure(kind, *feature.choice(candidates), ammo=definition.get("ammo")))
    for structure in objects:
        structure.id = f"n:{horizontal}:{vertical}:{structure.x}:{structure.y}:{structure.kind}"
        if structure.kind == "chest":
            structure.slots = chest_items(seed, horizontal, vertical, structure.x, structure.y, settings)
    return objects, interior


def appearance(structure):
    return {"id": structure.id, "kind": structure.kind, "x": structure.x, "y": structure.y, "lit": False, "monster_demolition": False}
