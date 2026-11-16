import hashlib
import json
from functools import lru_cache
from math import atan2, cos, floor, sin, tau

from . import constants as rules
from .biome_layout import BIOME_RING, add_biome_terrain
from .loot import CHEST_LOOT
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
    result = {"algorithm": 1, "version": rules.TERRAIN_VERSION, "size": rules.CHUNK_SIZE, "machines": machines, "outdoors": {kind: dict(definition) for kind, definition in OUTDOOR_FEATURES.items()}, "rare": [[kind, chance] for kind, chance in sorted(rare.items())], "foods": list(rules.COMMON_CHEST_FOODS), "igniters": list(rules.COMMON_CHEST_IGNITERS), "items": {kind: {"ammo": item.ammo, "uses": item.uses} for kind in sorted(rules.ITEM_KINDS - rules.CREATIVE_ITEMS.keys()) if (item := Item.create(kind))}}
    result["chest_gun_chance"] = rules.CHEST_GUN_CHANCE
    result["biome_ring"] = dict(BIOME_RING)
    result["biome_loot"] = {"chance": rules.BIOME_LOOT_CHANCE, "items": sorted(rules.BIOME_ITEMS)}
    result["extra_chest_loot"] = [[kind, settings] for kind, settings in rules.EXTRA_CHEST_LOOT.items()]
    result["quality_loot"] = {"chance": rules.QUALITY_LOOT_CHANCE, "items": list(rules.QUALITY_LOOT)}
    result["loot"] = CHEST_LOOT
    result["stack_limits"] = dict(rules.STACK_LIMITS)
    result["digest"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return result


def chunk_seed(seed, horizontal, vertical):
    return derive(seed, "chunk", horizontal, vertical)


def cell_seed(seed, horizontal, vertical, tile_x, tile_y):
    return derive(chunk_seed(seed, horizontal, vertical), "tile", tile_x, tile_y)


def chest_items(seed, horizontal, vertical, tile_x, tile_y, settings):
    base = cell_seed(seed, horizontal, vertical, tile_x, tile_y)
    if "loot" in settings:
        items = []
        limits = settings.get("stack_limits", {})
        for category in ("weapon", "consumable", "equipment"):
            for kind, chance, quantities in settings["loot"][category]:
                stream = RandomStream(derive(base, "loot", "ordinary:v1", kind))
                if stream.random() < chance:
                    count = stream.choice(quantities)
                    limit = limits.get(kind, 1)
                    items.extend((kind, min(limit, count - start)) for start in range(0, count, limit))
        slots = items + [None] * max(0, 30 - len(items))
        RandomStream(derive(base, "loot", "shuffle")).shuffle(slots)
        return chest_slots(horizontal, vertical, tile_x, tile_y, settings, slots)
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
    if quality := settings.get("quality_loot"):
        stream = RandomStream(derive(base, "loot", "quality:v1"))
        candidates = [kind for kind in quality["items"] if kind not in items]
        if candidates and stream.random() < quality["chance"]:
            items.append(stream.choice(candidates))
    slots = items + [None] * max(0, 30 - len(items))
    RandomStream(derive(base, "loot", "shuffle")).shuffle(slots)
    if loot := settings.get("biome_loot"):
        stream = RandomStream(derive(base, "loot", "biome-kit:v1"))
        empty = [index for index, kind in enumerate(slots) if kind is None]
        if empty and stream.random() < loot["chance"]:
            slots[stream.choice(empty)] = stream.choice(loot["items"])
    for kind, loot in settings.get("extra_chest_loot", ()):
        stream = RandomStream(derive(base, "loot", f"extra:{kind}:v1"))
        if stream.random() >= loot["chance"] or (loot.get("unique") and kind in slots):
            continue
        empty = [index for index, entry in enumerate(slots) if entry is None]
        for index in stream.sample(empty, min(len(empty), stream.randint(*loot["count"]))):
            slots[index] = kind
    return chest_slots(horizontal, vertical, tile_x, tile_y, settings, slots)


def chest_slots(horizontal, vertical, tile_x, tile_y, settings, slots):
    items = []
    for index, entry in enumerate(slots):
        if entry is None:
            items.append(None)
            continue
        kind, count = entry if isinstance(entry, tuple) else (entry, 1)
        items.append(Item(kind, id=f"ni:{horizontal}:{vertical}:{tile_x}:{tile_y}:{index}", count=count, **settings["items"][kind]))
    return items


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


@lru_cache(maxsize=8192)
def ring_inside(seed, horizontal, vertical, size, radius):
    # Bend the perimeter around connected houses so their exterior doors stay reachable.
    radius2 = radius**2
    if (horizontal * size)**2 + (vertical * size)**2 <= radius2:
        return True
    visited = {(horizontal, vertical)}
    pending = [(horizontal, vertical)]
    while pending:
        x, y = pending.pop()
        if RandomStream(chunk_seed(seed, x, y)).random() < .9:
            continue
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                point = x + dx, y + dy
                if point in visited:
                    continue
                if (point[0] * size)**2 + (point[1] * size)**2 <= radius2:
                    return True
                visited.add(point)
                pending.append(point)
    return False


@lru_cache(maxsize=8192)
def ring_boundary(seed, horizontal, vertical, size, radius):
    x, y = horizontal * size, vertical * size
    if ring_inside(seed, horizontal, vertical, size, radius):
        return frozenset()
    half = size // 2
    boundary = set()
    for sx in (-1, 1):
        if ring_inside(seed, horizontal + sx, vertical, size, radius):
            boundary.update((x + sx*half, y + offset) for offset in range(-half, half + 1))
        if ring_inside(seed, horizontal, vertical + sx, size, radius):
            boundary.update((x + offset, y + sx*half) for offset in range(-half, half + 1))
        for sy in (-1, 1):
            if ring_inside(seed, horizontal + sx, vertical + sy, size, radius):
                boundary.add((x + sx*half, y + sy*half))
    return frozenset(boundary)


@lru_cache(maxsize=512)
def gate_tiles(seed, size, radius, gates, index):
    step = tau / gates
    angle = RandomStream(derive(seed, "first_ring:v1")).random() * step + index * step
    tx, ty = floor(radius*cos(angle) + .5), floor(radius*sin(angle) + .5)
    cx, cy = (tx + size//2)//size, (ty + size//2)//size
    boundary = set().union(*(
        ring_boundary(seed, x, y, size, radius)
        for x in range(cx - 3, cx + 4)
        for y in range(cy - 3, cy + 4)
    ))
    if not boundary:
        return frozenset()
    anchor = min(boundary, key=lambda p: ((p[0]-tx)**2 + (p[1]-ty)**2, *p))
    gate = {
        (tx, ty) for tx in range(anchor[0] - 2, anchor[0] + 3)
        for ty in range(anchor[1] - 2, anchor[1] + 3)
        if (tx, ty) in boundary
    }
    linked = {anchor}
    pending = [anchor]
    for x, y in pending:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                point = x + dx, y + dy
                if point in gate and point not in linked:
                    linked.add(point)
                    pending.append(point)
    return frozenset(linked)


def add_ring(seed, horizontal, vertical, settings, objects):
    size = settings["size"]
    radius, gates = settings["ring"]["radius"], settings["ring"]["gates"]
    boundary = ring_boundary(seed, horizontal, vertical, size, radius)
    if not boundary:
        return objects
    step = tau / gates
    rotation = RandomStream(derive(seed, "first_ring:v1")).random() * step
    result = [entry for entry in objects if (entry.x, entry.y) not in boundary]
    for tx, ty in sorted(boundary):
        offset = (atan2(ty, tx) - rotation) / step
        index = floor(offset + .5)
        gate = abs(offset - index)*step < .075 and (tx, ty) in gate_tiles(seed, size, radius, gates, index % gates)
        result.append(Structure("ring_gate" if gate else "ring_wall", tx, ty))
    return result


def add_devices(horizontal, vertical, builder, center_x, center_y, objects, interior):
    for kind, starter in (("fixed_heater", (2, 0)), ("service_gun", (-2, 0))):
        stream = builder.feature_generator("service:" + kind + ":v1", horizontal, vertical)
        if stream.random() >= .018 and starter != (horizontal, vertical):
            continue
        occupied = {(entry.x, entry.y) for entry in objects} | set(interior)
        candidates = [
            (center_x + x, center_y + y)
            for x in range(-7, 8)
            for y in range(-7, 8)
            if max(abs(x), abs(y)) == 7
            and all(not (center_x + x + dx, center_y + y + dy) in occupied
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1))
        ]
        if candidates:
            objects.append(Structure(kind, *stream.choice(candidates), ammo=0 if kind == "service_gun" else None))


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
    if "ring" in settings:
        objects = add_ring(seed, horizontal, vertical, settings, objects)
    if "ring" in settings or "biome_ring" in settings:
        add_devices(horizontal, vertical, builder, center_x, center_y, objects, interior)
    if "biome_ring" in settings:
        objects = add_biome_terrain(seed, horizontal, vertical, settings, objects, interior)
    for structure in objects:
        structure.id = f"n:{horizontal}:{vertical}:{structure.x}:{structure.y}:{structure.kind}"
        if structure.kind == "chest":
            structure.slots = chest_items(seed, horizontal, vertical, structure.x, structure.y, settings)
    return objects, interior


def appearance(structure):
    state = {"id": structure.id, "kind": structure.kind, "x": structure.x, "y": structure.y, "lit": False, "monster_demolition": False}
    if structure.kind == "door":
        state["door_open"] = structure.door_open
    if structure.kind in {"cable_station", "street_lamp", "bridge_pier"}:
        state["repaired"] = structure.repaired
    if structure.on_floor:
        state["on_floor"] = True
    return state
