import hashlib
import math
import random
from collections import deque

from .constants import CHUNK_SIZE, FOODS, IGNITERS, SOLID, WORLD_RADIUS
from .geometry import chunk
from .models import Item, Structure


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
        self.structures[structure.id] = structure
        self.tiles[structure.x, structure.y] = structure.id

    def remove_structure(self, structure):
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
        digest = hashlib.blake2b(f"{self.seed}:{chunk_x}:{chunk_y}".encode(), digest_size=16).digest()
        generator = random.Random(int.from_bytes(digest, "big"))
        center_x, center_y = chunk_x * CHUNK_SIZE, chunk_y * CHUNK_SIZE
        roll = generator.random()
        if (chunk_x, chunk_y) == (0, 0) or roll >= 0.9:
            objects, interior = self.building(generator, center_x, center_y)
            for structure in objects:
                self.add_structure(structure)
            if (chunk_x, chunk_y) == (0, 0):
                self.origin_region = interior
        elif roll >= 0.5:
            for tile_x in range(center_x - 7, center_x + 8):
                for tile_y in range(center_y - 7, center_y + 8):
                    if generator.random() < 0.1:
                        self.add_structure(Structure("tree", tile_x, tile_y))
        self.chunks.add((chunk_x, chunk_y))

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
            objects.extend(Structure("chest", tile_x, tile_y, slots=self.loot(generator)) for tile_x, tile_y in chest_positions)
            return objects, sorted(interior)
        raise RuntimeError("Unable to generate a reachable building")

    @staticmethod
    def loot(generator):
        items = []
        if generator.random() < 0.5:
            items.extend(Item.create("wood") for count in range(generator.randint(1, 5)))
        if generator.random() < 0.1:
            items.append(Item.create(generator.choices(["handgun", "shotgun", "rifle"], [0.7, 0.2, 0.1])[0]))
        if generator.random() < 0.3:
            items.extend(Item.create(generator.choice(list(FOODS))) for count in range(generator.randint(1, 5)))
        if generator.random() < 0.2:
            items.append(Item.create(generator.choice(list(IGNITERS))))
        slots = items + [None] * (30 - len(items))
        generator.shuffle(slots)
        return slots

    def origin_spawn_points(self):
        blocked = {(structure.x, structure.y) for structure in self.structures.values() if -7 <= structure.x <= 7 and -7 <= structure.y <= 7 and structure.kind in SOLID}
        boundary = [(tile_x, tile_y) for tile_x in range(-7, 8) for tile_y in range(-7, 8) if abs(tile_x) == 7 or abs(tile_y) == 7]
        reachable = flood(boundary, blocked, (-7, 7, -7, 7))
        return [point for point in self.origin_region if tuple(point) in reachable]
