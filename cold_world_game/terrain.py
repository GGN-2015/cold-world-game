import math
from collections import deque

from .constants import CHUNK_SIZE, TERRAIN_VERSION, WORLD_RADIUS
from .geometry import chunk
from .wildlife import SEATS


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
            if structure.kind in {"campfire", "fixed_heater"}:
                self._campfires[structure.id] = structure
            if hasattr(self, "invalidate_chunk"):
                self.invalidate_chunk(structure)
                if structure.kind in SEATS:
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
        self.touch_terrain()
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

    def origin_spawn_points(self):
        blocked = {(structure.x, structure.y) for structure in self.structures.values() if -7 <= structure.x <= 7 and -7 <= structure.y <= 7 and structure.solid and structure.kind != "door"}
        boundary = [(tile_x, tile_y) for tile_x in range(-7, 8) for tile_y in range(-7, 8) if abs(tile_x) == 7 or abs(tile_y) == 7]
        reachable = flood(boundary, blocked, (-7, 7, -7, 7))
        return [point for point in self.origin_region if tuple(point) in reachable]
