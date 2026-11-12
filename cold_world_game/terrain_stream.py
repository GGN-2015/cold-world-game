from collections import OrderedDict, deque
import hashlib
import json
import secrets

from .constants import CHUNK_SIZE, TERRAIN_VERSION
from .geometry import chunk
from .models import encode
from .procedural import appearance, derive, plan, profile, RandomStream


class TerrainStream:
    def init_terrain_stream(self):
        self.generation_profiles = {}
        self.terrain_session = secrets.token_hex(12)
        self._chunk_revisions = {}
        self._chunk_views = OrderedDict()
        self._baseline_views = OrderedDict()
        self._natural_geometry = {}
        self._terrain_serial = 0
        self._chunk_changes = {}

    def terrain_profile(self, version=TERRAIN_VERSION):
        key = str(version)
        if key not in self.generation_profiles:
            if version != TERRAIN_VERSION:
                raise ValueError("Missing procedural generation profile")
            self.generation_profiles = {**self.generation_profiles, key: profile()}
        return self.generation_profiles[key]

    def invalidate_chunk(self, structure, removed=False):
        point = chunk(structure.x), chunk(structure.y)
        previous = self._chunk_revisions.get(point, 0)
        self._terrain_serial += 1
        self._chunk_revisions[point] = self._terrain_serial
        self._chunk_views.pop(point, None)
        if not getattr(self, "_stream_generating", False):
            self._chunk_changes.setdefault(point, deque(maxlen=128)).append((self._terrain_serial, None if removed else appearance(structure), structure.id, previous))

    def baseline(self, horizontal, vertical):
        point = horizontal, vertical
        if point not in self._baseline_views:
            objects, interior = plan(self.seed, horizontal, vertical, self.terrain_profile(self.chunk_versions[point]))
            self._baseline_views[point] = {structure.id: encode(structure) for structure in objects}
            if len(self._baseline_views) > 64:
                self._baseline_views.popitem(last=False)
        self._baseline_views.move_to_end(point)
        return self._baseline_views[point]

    def remember_baseline(self, point, structures):
        ordered = sorted(structures, key=lambda structure: structure.id)
        content = [[structure.id, structure.kind, structure.x, structure.y] for structure in ordered]
        fingerprint = hashlib.md5(json.dumps(content, separators=(",", ":")).encode(), usedforsecurity=False).hexdigest()
        self._natural_geometry[point] = fingerprint, frozenset(structure.id for structure in ordered)

    def sparse_changes(self):
        changed, removed = {}, set()
        for identifier in self._dirty_structures:
            structure = self.structures.get(identifier)
            if identifier.startswith("n:"):
                if structure is None:
                    changed[identifier] = {"id": identifier, "deleted": True}
                elif encode(structure) == self.baseline(chunk(structure.x), chunk(structure.y)).get(identifier):
                    removed.add(identifier)
                else:
                    changed[identifier] = encode(structure)
            elif structure is None:
                removed.add(identifier)
            else:
                changed[identifier] = encode(structure)
        return changed, removed

    def chunk_view(self, point):
        if point in self._chunk_views:
            self._chunk_views.move_to_end(point)
            return self._chunk_views[point]
        horizontal, vertical = point
        records = []
        for tile_x in range(horizontal * CHUNK_SIZE - 7, horizontal * CHUNK_SIZE + 8):
            for tile_y in range(vertical * CHUNK_SIZE - 7, vertical * CHUNK_SIZE + 8):
                structure = self.structure_at(tile_x, tile_y)
                if structure:
                    records.append(appearance(structure))
        version = self.chunk_versions.get(point, 1)
        if version >= 18:
            fingerprint, baseline = self._natural_geometry[point]
            current = {record["id"]: record for record in records}
            records = [record for record in records if record["id"] not in baseline]
            deleted = sorted(baseline - current.keys())
        else:
            deleted = []
            fingerprint = None
        result = {"id": f"{horizontal},{vertical}", "x": horizontal, "y": vertical, "version": version, "revision": self._chunk_revisions.get(point, 0), "hash": fingerprint, "add": records, "remove": deleted}
        self._chunk_views[point] = result
        if len(self._chunk_views) > 256:
            self._chunk_views.popitem(last=False)
        return result

    def terrain_bootstrap(self):
        self.terrain_profile()
        return {"session": self.terrain_session, "seed": str(self.seed), "profiles": self.generation_profiles}

    def terrain_updates(self, player_id, previous):
        player = self.players[player_id]
        center_x, center_y = chunk(player.x), chunk(player.y)
        points = {(center_x + offset_x, center_y + offset_y) for offset_x in range(-2, 3) for offset_y in range(-2, 3)} & self.chunks
        current = {point: self._chunk_revisions.get(point, 0) for point in points}
        updates = []
        for point in sorted(points):
            if previous.get(point) == current[point]:
                continue
            history = self._chunk_changes.get(point)
            if point in previous and history and history[0][3] <= previous[point]:
                added, removed = {}, set()
                for revision, record, identifier, before in history:
                    if revision <= previous[point]:
                        continue
                    if record is None:
                        added.pop(identifier, None)
                        removed.add(identifier)
                    else:
                        removed.discard(identifier)
                        added[identifier] = record
                updates.append({"id": f"{point[0]},{point[1]}", "revision": current[point], "patch": True, "add": list(added.values()), "remove": sorted(removed)})
            else:
                updates.append(self.chunk_view(point))
        return {"add": updates, "remove": [f"{horizontal},{vertical}" for horizontal, vertical in sorted(previous.keys() - points)]}, current

    def structure_states(self, player):
        nearby = {(chunk(player.x) + horizontal, chunk(player.y) + vertical) for horizontal in range(-2, 3) for vertical in range(-2, 3)}
        states = {structure.id: {"id": structure.id, "lit": True} for structure in self._campfires.values() if structure.lit and abs(structure.x-player.x)<=38 and abs(structure.y-player.y)<=38}
        for player_id, controls in self.controls.items():
            seat = self.structures.get(controls.seat)
            if seat and (chunk(seat.x), chunk(seat.y)) in nearby:
                states.setdefault(seat.id, {"id": seat.id})["occupant"] = player_id
        for horizontal in range(chunk(player.x)-2, chunk(player.x)+3):
            for vertical in range(chunk(player.y)-2, chunk(player.y)+3):
                for identifier in self._seats_by_chunk.get((horizontal, vertical), ()):
                    seat = self.structures[identifier]
                    states.setdefault(identifier, {"id": identifier, "occupant": None})["ammo"] = seat.ammo
        for monster in self.monsters.values():
            target = self.structures.get(monster.demolition)
            if target and (chunk(target.x), chunk(target.y)) in nearby and not self.monster_inactive(monster):
                states.setdefault(monster.demolition, {"id": monster.demolition})["monster_demolition"] = True
        return sorted(states.values(), key=lambda value: value["id"])

    def event_random(self, system, entity="world"):
        return RandomStream(derive(self.seed, "simulation", self.tick_number, system, entity))
