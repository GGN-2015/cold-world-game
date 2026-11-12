import hashlib
import math
import random
from collections import deque

from .constants import CHUNK_SIZE, COMMON_CHEST_FOODS, COMMON_CHEST_IGNITERS, CONTAINERS, DEFIBRILLATOR_CHANCE, FIRST_AID_KIT_CHANCE, FLAME_STAFF_CHANCE, FOODS, GRENADE_CHANCE, GUN_MACHINE_CHANCE, HEAT_PATCH_CHANCE, HOMING_MISSILE_CHANCE, ICE_STAFF_CHANCE, IGNITERS, MATCH_MACHINE_CHANCE, PIGGY_BANK_CHANCE, RARE_CHEST_ITEMS, RETURN_STAFF_CHANCE, SHERIFF_BADGE_CHANCE, SOLID, SWIFTNESS_RING_CHANCE, TERRAIN_VERSION, VENDING_MACHINE_CHANCE, VODKA_CHANCE, WORLD_RADIUS
from .geometry import chunk
from .models import Item, Structure
from .room_machines import ROOM_MACHINES
from .wildlife import OUTDOOR_FEATURES


def flood(start_points, blocked, bounds):
    minimum_x, maximum_x, minimum_y, maximum_y = bounds
    visited = {point for point in start_points if point not in blocked}
    pending = deque(visited)
    while pending:
        current_x, current_y = pending.popleft()
        for offset_x, offset_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            point = current_x + offset_x, current_y + offset_y
            if minimum_x <= point[0] <= maximum_x and minimum_y <= point[1] <= maximum_y and point not in blocked and point not in visited:
                visited.add(point)
                pending.append(point)
    return visited


class Terrain:
    def generated(self, x, y):
        return (chunk(x), chunk(y)) in self.chunks

    def add_structure(self, structure):
        if hasattr(self, "record_structure"):
            self.record_structure(structure.id, checkpoint=True)
            if structure.id not in self._structure_order:
                self._structure_order[structure.id] = self._next_structure_order
                self._next_structure_order += 1
            self._campfires.pop(structure.id, None)
            self._landmines.pop(structure.id, None)
            if structure.kind == "landmine":
                self._landmines[structure.id] = structure
            if structure.kind == "campfire":
                self._campfires[structure.id] = structure
            if hasattr(self, "invalidate_chunk"):
                self.invalidate_chunk(structure)
                if structure.kind in OUTDOOR_FEATURES:
                    self._seats_by_chunk.setdefault((chunk(structure.x), chunk(structure.y)), set()).add(structure.id)
        self._terrain_revision = getattr(self, "_terrain_revision", 0) + 1
        self.structures[structure.id] = structure
        self.tiles[structure.x, structure.y] = structure.id

    def remove_structure(self, structure):
        if hasattr(self, "record_structure"):
            self.record_structure(structure.id, checkpoint=True)
            self._campfires.pop(structure.id, None)
            self._landmines.pop(structure.id, None)
            if hasattr(self, "invalidate_chunk"):
                self.invalidate_chunk(structure, removed=True)
                self._seats_by_chunk.get((chunk(structure.x), chunk(structure.y)), set()).discard(structure.id)
        self._terrain_revision = getattr(self, "_terrain_revision", 0) + 1
        self.structures.pop(structure.id, None)
        self.tiles.pop((structure.x, structure.y), None)

    def structure_at(self, x, y):
        return self.structures.get(self.tiles.get((x, y)))

    def ensure_terrain(self, x, y):
        changed = False
        for chunk_x in range(math.ceil((x - WORLD_RADIUS) / CHUNK_SIZE), math.floor((x + WORLD_RADIUS) / CHUNK_SIZE) + 1):
            for chunk_y in range(math.ceil((y - WORLD_RADIUS) / CHUNK_SIZE), math.floor((y + WORLD_RADIUS) / CHUNK_SIZE) + 1):
                if (chunk_x, chunk_y) not in self.chunks and math.hypot(chunk_x * CHUNK_SIZE - x, chunk_y * CHUNK_SIZE - y) <= WORLD_RADIUS:
                    self.generate_chunk(chunk_x, chunk_y)
                    changed = True
        return changed

    def generate_chunk(self, chunk_x, chunk_y):
        if (chunk_x, chunk_y) in self.chunks:
            return
        if hasattr(self, "touch_terrain"):
            self.touch_terrain()
        if hasattr(self, "terrain_profile"):
            from .procedural import plan
            objects, interior = plan(self.seed, chunk_x, chunk_y, self.terrain_profile())
            self.remember_baseline((chunk_x, chunk_y), objects)
            self._stream_generating = True
            try:
                for structure in objects:
                    self.add_structure(structure)
                    self._dirty_structures.pop(structure.id, None)
            finally:
                self._stream_generating = False
            if (chunk_x, chunk_y) == (0, 0):
                self.origin_region = interior
            self.chunks.add((chunk_x, chunk_y))
            self.chunk_versions[chunk_x, chunk_y] = TERRAIN_VERSION
            return
        digest = hashlib.blake2b(f"{self.seed}:{chunk_x}:{chunk_y}".encode(), digest_size=16).digest()
        generator = random.Random(int.from_bytes(digest, "big"))
        center_x, center_y = chunk_x * CHUNK_SIZE, chunk_y * CHUNK_SIZE
        roll = generator.random()
        if (chunk_x, chunk_y) == (0, 0) or roll >= 0.9:
            objects, interior = self.building(generator, center_x, center_y)
            self.populate_vending_machine(objects, interior, chunk_x, chunk_y)
            self.populate_match_machine(objects, interior, chunk_x, chunk_y)
            self.populate_machine(objects, interior, chunk_x, chunk_y, "gun_machine", "gun_machine:v1", GUN_MACHINE_CHANCE)
            self.populate_machine(objects, interior, chunk_x, chunk_y, "piggy_bank", "piggy_bank:v1", PIGGY_BANK_CHANCE)
            for kind, definition in ROOM_MACHINES.items():
                self.populate_machine(objects, interior, chunk_x, chunk_y, kind, f"room_machine:{kind}:v1", definition["chance"], preserve_paths=True)
            for structure in objects:
                self.add_structure(structure)
            if (chunk_x, chunk_y) == (0, 0):
                self.origin_region = interior
        elif roll >= 0.5:
            for tile_x in range(center_x - 7, center_x + 8):
                for tile_y in range(center_y - 7, center_y + 8):
                    if generator.random() < 0.1:
                        self.add_structure(Structure("tree", tile_x, tile_y))
        else:
            for kind, settings in OUTDOOR_FEATURES.items():
                feature = self.feature_generator(settings["stream"], chunk_x, chunk_y)
                if feature.random() < settings["chance"]:
                    candidates = [(center_x + horizontal, center_y + vertical) for horizontal in range(-6, 7) for vertical in range(-6, 7) if self.structure_at(center_x + horizontal, center_y + vertical) is None]
                    if candidates:
                        position = feature.choice(candidates)
                        self.add_structure(Structure(kind, *position, ammo=settings.get("ammo")))
        self.chunks.add((chunk_x, chunk_y))
        self.chunk_versions[chunk_x, chunk_y] = TERRAIN_VERSION

    def feature_generator(self, feature, chunk_x, chunk_y):
        digest = hashlib.blake2b(f"{self.seed}:{feature}:{chunk_x}:{chunk_y}".encode(), digest_size=16).digest()
        return random.Random(int.from_bytes(digest, "big"))

    def populate_vending_machine(self, objects, interior, chunk_x, chunk_y):
        self.populate_machine(objects, interior, chunk_x, chunk_y, "vending_machine", "vending_machine:v1", VENDING_MACHINE_CHANCE)

    def populate_match_machine(self, objects, interior, chunk_x, chunk_y):
        self.populate_machine(objects, interior, chunk_x, chunk_y, "match_machine", "match_machine:v1", MATCH_MACHINE_CHANCE)

    def populate_machine(self, objects, interior, chunk_x, chunk_y, kind, feature, chance, preserve_paths=False):
        generator = self.feature_generator(feature, chunk_x, chunk_y)
        if generator.random() >= chance:
            return
        center_x, center_y = chunk_x * CHUNK_SIZE, chunk_y * CHUNK_SIZE
        bounds = center_x - 8, center_x + 8, center_y - 8, center_y + 8
        blocked = {(structure.x, structure.y) for structure in objects if structure.kind in SOLID}
        containers = [(structure.x, structure.y) for structure in objects if structure.kind in CONTAINERS]
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
            objects.extend(Structure("chest", tile_x, tile_y, slots=self.loot(generator, self.feature_generator(f"chest_first_aid_kit:v1:{tile_x}:{tile_y}", chunk(center_x), chunk(center_y)), self.feature_generator(f"chest_return_staff:v1:{tile_x}:{tile_y}", chunk(center_x), chunk(center_y)), self.feature_generator(f"chest_ice_staff:v1:{tile_x}:{tile_y}", chunk(center_x), chunk(center_y)), self.feature_generator(f"chest_grenade:v1:{tile_x}:{tile_y}", chunk(center_x), chunk(center_y)), self.feature_generator(f"chest_flame_staff:v1:{tile_x}:{tile_y}", chunk(center_x), chunk(center_y)), self.feature_generator(f"chest_defibrillator:v1:{tile_x}:{tile_y}", chunk(center_x), chunk(center_y)), self.feature_generator(f"chest_heat_patch:v1:{tile_x}:{tile_y}", chunk(center_x), chunk(center_y)), self.feature_generator(f"chest_sheriff_badge:v1:{tile_x}:{tile_y}", chunk(center_x), chunk(center_y)), self.feature_generator(f"chest_vodka:v1:{tile_x}:{tile_y}", chunk(center_x), chunk(center_y)), self.feature_generator(f"chest_swiftness_ring:v1:{tile_x}:{tile_y}", chunk(center_x), chunk(center_y)), self.feature_generator(f"chest_homing_missile:v1:{tile_x}:{tile_y}", chunk(center_x), chunk(center_y)), {kind: self.feature_generator(f"chest_{kind}:v1:{tile_x}:{tile_y}", chunk(center_x), chunk(center_y)) for kind in RARE_CHEST_ITEMS})) for tile_x, tile_y in chest_positions)
            return objects, sorted(interior)
        raise RuntimeError("Unable to generate a reachable building")

    @staticmethod
    def loot(generator, first_aid_generator=None, return_staff_generator=None, ice_staff_generator=None, grenade_generator=None, flame_staff_generator=None, defibrillator_generator=None, heat_patch_generator=None, sheriff_badge_generator=None, vodka_generator=None, swiftness_ring_generator=None, homing_missile_generator=None, rare_generators=None):
        items = []
        if generator.random() < 0.5:
            items.extend(Item.create("wood") for count in range(generator.randint(1, 5)))
        if generator.random() < 0.1:
            items.append(Item.create(generator.choices(["handgun", "shotgun", "rifle"], [0.7, 0.2, 0.1])[0]))
        if generator.random() < 0.3:
            items.extend(Item.create(generator.choice(COMMON_CHEST_FOODS)) for count in range(generator.randint(1, 5)))
        if generator.random() < 0.2:
            items.append(Item.create(generator.choice(COMMON_CHEST_IGNITERS)))
        if first_aid_generator is not None and first_aid_generator.random() < FIRST_AID_KIT_CHANCE:
            items.append(Item.create("first_aid_kit"))
        if return_staff_generator is not None and return_staff_generator.random() < RETURN_STAFF_CHANCE:
            items.append(Item.create("return_staff"))
        if ice_staff_generator is not None and ice_staff_generator.random() < ICE_STAFF_CHANCE:
            items.append(Item.create("ice_staff"))
        if grenade_generator is not None and grenade_generator.random() < GRENADE_CHANCE:
            items.append(Item.create("grenade"))
        if flame_staff_generator is not None and flame_staff_generator.random() < FLAME_STAFF_CHANCE:
            items.append(Item.create("flame_staff"))
        if defibrillator_generator is not None and defibrillator_generator.random() < DEFIBRILLATOR_CHANCE:
            items.append(Item.create("defibrillator"))
        if heat_patch_generator is not None and heat_patch_generator.random() < HEAT_PATCH_CHANCE:
            items.append(Item.create("heat_patch"))
        if sheriff_badge_generator is not None and sheriff_badge_generator.random() < SHERIFF_BADGE_CHANCE:
            items.append(Item.create("sheriff_badge"))
        if vodka_generator is not None and vodka_generator.random() < VODKA_CHANCE:
            items.append(Item.create("vodka"))
        if swiftness_ring_generator is not None and swiftness_ring_generator.random() < SWIFTNESS_RING_CHANCE:
            items.append(Item.create("swiftness_ring"))
        if homing_missile_generator is not None and homing_missile_generator.random() < HOMING_MISSILE_CHANCE:
            items.append(Item.create("homing_missile"))
        for kind, rare_generator in (rare_generators or {}).items():
            if rare_generator.random() < RARE_CHEST_ITEMS[kind]:
                items.append(Item.create(kind))
        slots = items + [None] * max(0, 30 - len(items))
        generator.shuffle(slots)
        return slots

    def origin_spawn_points(self):
        blocked = {(structure.x, structure.y) for structure in self.structures.values() if -7 <= structure.x <= 7 and -7 <= structure.y <= 7 and structure.kind in SOLID}
        boundary = [(tile_x, tile_y) for tile_x in range(-7, 8) for tile_y in range(-7, 8) if abs(tile_x) == 7 or abs(tile_y) == 7]
        reachable = flood(boundary, blocked, (-7, 7, -7, 7))
        return [point for point in self.origin_region if tuple(point) in reachable]
