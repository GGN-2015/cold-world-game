import heapq
import math
import random
import secrets
import threading
import time
from collections import deque
from contextlib import contextmanager

from .actions import Actions, GameError
from .admin import Administration, admin_id
from .combat import Combat
from .constants import STARVATION_AMBIENT, STARVATION_HUNGER, STARVATION_TEMPERATURE, WORLD_START_HOUR
from .constants import BACKPACK_STACK_LIMITS, NAVIGATION_ITEMS, STACK_LIMITS, THROWABLE_WEAPONS
from .constants import GROUND_ITEM_UNSEEN_SECONDS
from .constants import AXE, BACKPACK_SLOTS, BODY_RADIUS, BODY_TEMPERATURE_RATES, BULLET_BLOCKERS, BURN_SECONDS, CHAINSAW_CHANCE, CHUNK_SIZE, DAY_SECONDS, DEFAULT_VIEWPORT, DEFIBRILLATOR_CHANCE, DRINKS, DROP_DISTANCE, EQUIPPED_ITEMS, EXPLOSIVE_WEAPONS, FAST_MONSTER_SPEED, FIRST_AID_KIT_CHANCE, FLAME_STAFF_CHANCE, FOODS, GRENADE_CHANCE, GUNS, HARVEST_TOOLS, GUN_MACHINE_CHANCE, HEALING_ITEMS, HOMING_MISSILE_CHANCE, HEAT_PATCH_CHANCE, ICE_STAFF, ICE_STAFF_CHANCE, IGNITERS, INVENTORY_SLOTS, ITEM_KINDS, KNOCKBACK, LANDMINE_CHANCE, MACHINE_OFFERS, MATCH_MACHINE_CHANCE, MAX_COINS, MELEE_WEAPONS, MONSTER_BULLET_BLOCKERS, MONSTER_COIN_DROPS, MONSTER_REST_HOURS, MONSTER_RISE_SECONDS, MONSTER_SPAWN_CHANCES, MONSTER_SPEED, NIGHT_MONSTER_HOURS, OPAQUE, PASSIVE_ITEMS, PICKUP_RADIUS, PIGGY_BANK_CHANCE, PLAYER_SPEED, READY_TO_EAT_FOODS, RECIPES, RETURN_ITEMS, RETURN_STAFF_CHANCE, REVIVAL_ITEMS, SEASONS, SEASON_DAYS, SEASON_OFFSETS, SHERIFF_BADGE_CHANCE, SMALL_MONSTER_FOOD_CHANCE, SMALL_MONSTER_FOOD_WEIGHTS, SOLID, SWIFTNESS_RING_CHANCE, TERRAIN_VERSION, TICK_RATE, VENDING_MACHINE_CHANCE, VENDING_OFFERS, VODKA_CHANCE
from .expansion import DURIAN_CHANCE, EXPANSION_CATEGORIES, EXPANSION_ITEMS, carried_modifier
from .room_machines import ROOM_MACHINES
from .geometry import chunk, circle_square, distance, segment_box, segment_tiles, tile
from .models import Controls, GroundItem, Item, Monster, Player, Projectile, encode, item_from, player_from, projectile_from, structure_from
from .monsters import Monsters
from .outdoors import Outdoors
from .wildlife import MONSTER_TYPES, OUTDOOR_FEATURES, SEATS
from .storage import WorldDelta
from .terrain import Terrain
from .terrain_stream import TerrainStream
from .procedural import plan
from .spatial import BodyIndex
from .publication import capture_entities, compose_snapshot
from .inventory import can_insert, insert_item, personal_storages


def tuples(value):
    return tuple(tuples(element) for element in value) if isinstance(value, list) else value


class World(Administration, Outdoors, Actions, Combat, Monsters, TerrainStream, Terrain):
    def __init__(self, storage, seed=None, admin=None):
        self.admin = admin_id(admin)
        self.storage = storage
        self.lock = threading.RLock()
        self.online = set()
        self.controls = {}
        self.fault = None
        self._backup = None
        self._runtime_backup = None
        self._in_transaction = False
        self._structure_undo = {}
        self._dirty_structures = {}
        self._terrain_dirty = True
        self._campfires = {}
        self._landmines = {}
        self._mine_triggers = set()
        self._structure_order = {}
        self._next_structure_order = 0
        self.events = deque(maxlen=256)
        self.event_sequence = 0
        self._pending_events = []
        self._path_cursor = None
        self._path_jobs = {}
        self._path_queue = deque()
        self._velocities = {}
        self._body_index = None
        self._persistence = None
        self._save_generation = 0
        self.init_terrain_stream()
        self._seats_by_chunk = {}
        state = storage.load()
        if state:
            self.restore(state)
        else:
            self.seed = seed if seed is not None else secrets.randbits(63)
            self.random = random.Random(self.seed)
            self.elapsed = DAY_SECONDS * WORLD_START_HOUR / 24
            self.tick_number = 0
            self.chunks = set()
            self.structures = {}
            self.tiles = {}
            self.origin_region = []
            self.players = {}
            self.monsters = {}
            self.projectiles = {}
            self.ground = {}
            self.shot_hits = {}
            self.shot_impacts = {}
            self.chunk_versions = {}
            self.ensure_terrain(0, 0)
            self.save_changes()
        self.navigation_bootstrap()
        self.next_save = self.elapsed + 2

    def export(self):
        return {**self.export_metadata(), "materialized": True, "structures": [encode(value) for value in self.structures.values()]}

    def export_terrain(self):
        chunks = sorted(self.chunks)
        return {
            "chunks": chunks,
            "chunk_versions": [[*point, self.chunk_versions.get(point, 1)] for point in chunks],
            "origin_region": list(self.origin_region),
            "generation_profiles": self.generation_profiles,
        }

    def export_metadata(self, terrain=True):
        random_state = self.random.getstate()
        return {
            **(self.export_terrain() if terrain else {}),
            "seed": self.seed,
            "terrain_format": 1,
            "random": [random_state[0], list(random_state[1]), random_state[2]],
            "elapsed": self.elapsed,
            "tick_number": self.tick_number,
            "players": [encode(value) for value in self.players.values()],
            "monsters": [encode(value) for value in self.monsters.values()],
            "projectiles": [encode(value) for value in self.projectiles.values()],
            "ground": [encode(value) for value in self.ground.values()],
            "shot_hits": {shot: sorted(players) for shot, players in self.shot_hits.items()},
            "shot_impacts": {shot: sorted(monsters) for shot, monsters in self.shot_impacts.items()},
        }

    def restore(self, state):
        self._mine_triggers = set()
        self._path_jobs = {}
        self._path_queue = deque()
        self.seed = state["seed"]
        self.generation_profiles = state.get("generation_profiles", self.generation_profiles)
        self._chunk_views.clear()
        self._baseline_views.clear()
        self.random = random.Random()
        self.random.setstate(tuples(state["random"]))
        self.elapsed = state["elapsed"]
        self.tick_number = state["tick_number"]
        if "chunks" in state:
            self.chunks = {tuple(point) for point in state["chunks"]}
            versions = {(chunk_x, chunk_y): version for chunk_x, chunk_y, version in state.get("chunk_versions", [])}
            self.chunk_versions = {point: versions.get(point, 1) for point in self.chunks}
            self.origin_region = [tuple(point) for point in state["origin_region"]]
            self._natural_geometry = {point: value for point, value in self._natural_geometry.items() if point in self.chunks}
        if "structures" in state:
            self.structures = {}
            self._natural_geometry = {}
            if state.get("terrain_format") == 1:
                for point, version in sorted(self.chunk_versions.items()):
                    if version >= 18:
                        objects, interior = plan(self.seed, *point, self.terrain_profile(version))
                        self.remember_baseline(point, objects)
                        if not state.get("materialized"):
                            self.structures.update((structure.id, structure) for structure in objects)
            for values in state["structures"]:
                if values.get("deleted"):
                    self.structures.pop(values["id"], None)
                else:
                    self.structures[values["id"]] = structure_from(values)
            self.tiles = {(value.x, value.y): value.id for value in self.structures.values()}
            self._campfires = {value.id: value for value in self.structures.values() if value.kind == "campfire"}
            self._landmines = {value.id: value for value in self.structures.values() if value.kind == "landmine"}
            self._seats_by_chunk = {}
            for structure in self.structures.values():
                if structure.kind in SEATS:
                    self._seats_by_chunk.setdefault((chunk(structure.x), chunk(structure.y)), set()).add(structure.id)
            self._structure_order = {identifier: index for index, identifier in enumerate(self.structures)}
            self._next_structure_order = len(self.structures)
            self._dirty_structures = {}
            self._terrain_dirty = False
        self.players = {values["id"]: player_from(values) for values in state["players"]}
        self.monsters = {values["id"]: Monster(**values) for values in state["monsters"]}
        self.projectiles = {values["id"]: projectile_from(values) for values in state["projectiles"]}
        self.ground = {values["id"]: GroundItem(**{**values, "item": item_from(values["item"])}) for values in state["ground"]}
        self.shot_hits = {shot: set(players) for shot, players in state["shot_hits"].items()}
        self.shot_impacts = {shot: set(monsters) for shot, monsters in state.get("shot_impacts", {}).items()}

    def touch(self):
        if self._backup is None:
            self._backup = self.export_metadata(terrain=False)
            self._runtime_backup = (set(self.online), {identifier: Controls(**{**vars(controls), "ghost_monsters": set(controls.ghost_monsters)}) for identifier, controls in self.controls.items()})

    def touch_terrain(self):
        if self._in_transaction:
            self.touch()
            if "chunks" not in self._backup:
                self._backup.update(self.export_terrain())
        self._terrain_dirty = True

    def record_structure(self, identifier, checkpoint=False):
        if self._in_transaction:
            if checkpoint:
                self.touch()
            if identifier not in self._structure_undo:
                original = self.structures.get(identifier)
                self._structure_undo[identifier] = (structure_from(encode(original)) if original else None, self._structure_order.get(identifier))
        self._dirty_structures.setdefault(identifier, None)

    def save_changes(self):
        if self._persistence is not None:
            self._persistence.changed()
            self._persistence.request()
            return
        batch = self.capture_save(clear=False)
        self.storage.save(batch)
        self._dirty_structures.clear()
        self._terrain_dirty = False
        self.finish_save(batch)

    def capture_save(self, clear=True):
        changed, removed = self.sparse_changes()
        metadata = self.export_metadata(terrain=False)
        if self._terrain_dirty:
            metadata.update(self.export_terrain())
        if clear:
            self._dirty_structures.clear()
            self._terrain_dirty = False
        return WorldDelta(metadata, changed, removed)

    def finish_save(self, batch):
        for identifier in batch.removed:
            if identifier not in self.structures and identifier not in self._dirty_structures:
                self._structure_order.pop(identifier, None)

    @contextmanager
    def transaction(self):
        self._pending_events = []
        self._in_transaction = True
        self._structure_undo = {}
        dirty_before = dict(self._dirty_structures)
        terrain_before = self._terrain_dirty
        try:
            yield
            if self._backup is not None and self._persistence is None:
                self.save_changes()
                self.next_save = self.elapsed + 2
            if self._persistence is not None:
                self._persistence.changed()
            for event in self._pending_events:
                self.event_sequence += 1
                self.events.append({**event, "id": self.event_sequence})
        except BaseException as error:
            if self._backup is not None:
                self.restore(self._backup)
                self.online, self.controls = self._runtime_backup
                self._in_transaction = False
                for identifier, (original, order) in self._structure_undo.items():
                    current = self.structures.get(identifier)
                    if current:
                        self.remove_structure(current)
                    if original:
                        self.add_structure(original)
                        self._structure_order[identifier] = order
                    else:
                        self._structure_order.pop(identifier, None)
                self.structures = dict(sorted(self.structures.items(), key=lambda entry: self._structure_order[entry[0]]))
                self._dirty_structures = dirty_before
                self._terrain_dirty = terrain_before
            if not isinstance(error, GameError):
                self.fault = "Storage or simulation failure; restart the server after checking its log"
            raise
        finally:
            self._backup = None
            self._runtime_backup = None
            self._pending_events = []
            self._in_transaction = False
            self._structure_undo = {}

    def emit_event(self, event_type, actor, kind, x, y, **details):
        self._pending_events.append({"type": event_type, "actor": actor, "kind": kind, "x": x, "y": y, "time": self.elapsed, **details})

    def join(self, player_id, client_movement=False):
        if not isinstance(player_id, str) or not player_id.strip() or len(player_id) > 64 or not player_id.isprintable():
            raise GameError("invalid_id", "Player ID must contain 1-64 printable characters")
        with self.lock, self.transaction():
            self.check_healthy()
            if player_id in self.online:
                raise GameError("id_in_use", "This player ID is already connected")
            self.touch()
            if not self.online:
                self.last_real = time.monotonic()
            player = self.players.get(player_id)
            if player is None:
                points = self.origin_spawn_points()
                self.event_random("player-spawn", player_id).shuffle(points)
                position = next((point for point in points if self.can_stand(*point, player_id=player_id)), None)
                if position is None:
                    raise GameError("spawn_blocked", "No safe spawn position is currently available")
                player = Player(player_id, *position)
                player.inventory[:3] = [Item.create("handgun"), Item.create("axe"), Item.create("lighter")]
                self.players[player_id] = player
            elif ((structure := self.structure_at(tile(player.x), tile(player.y))) is not None and structure.kind in SEATS) or not self.can_stand(player.x, player.y, player_id=player_id, ignore_monsters=player.temperature < 5):
                position = self.return_destination(player.x, player.y)
                player.x, player.y = position
            if player.offline_since is not None:
                player.next_shot = self.elapsed + max(0, player.next_shot - player.offline_since)
                player.next_axe_attack = self.elapsed + max(0, player.next_axe_attack - player.offline_since)
                player.offline_since = None
            player.last_login_at = time.time()
            self.online.add(player_id)
            self.controls[player_id] = Controls(aim_x=player.x + 1, aim_y=player.y, last_input=time.monotonic(), client_movement=client_movement)
            for monster in self.monsters.values():
                if monster.target not in self.online or self.players[monster.target].temperature < 5:
                    self.clear_target(monster)
            return self.snapshot(player_id)

    def leave(self, player_id):
        with self.lock:
            if player_id not in self.online:
                return
            if self.fault:
                self.online.remove(player_id)
                self.controls.pop(player_id, None)
                self.players[player_id].offline_since = self.elapsed
                if self._persistence is not None:
                    self._persistence.changed()
                    if not self.online:
                        self._persistence.request()
                return
            with self.transaction():
                self.touch()
                for projectile in self.projectiles.values():
                    if projectile.kind == "bullet" and (projectile.range_player == player_id or (not projectile.hostile and projectile.owner == player_id)):
                        projectile.remaining = self.projectile_range(projectile)
                self.online.remove(player_id)
                self.controls.pop(player_id, None)
                for monster in self.monsters.values():
                    if monster.target == player_id:
                        self.clear_target(monster)
            if not self.online and self._persistence is not None:
                self._persistence.request()

    def player_roster(self):
        with self.lock:
            players = sorted(self.players.values(), key=lambda player: (player.id not in self.online, 0 if player.id in self.online else -(player.last_login_at or 0), player.id.casefold(), player.id))
            return {
                "server_time": time.time(),
                "players": [{"id": player.id, "online": player.id in self.online, "hunger": player.hunger, "temperature": player.temperature, "money": player.money, "last_login_at": player.last_login_at} for player in players],
            }

    def check_healthy(self):
        if self.fault:
            raise GameError("server_paused", self.fault)

    def execute(self, player_id, command):
        with self.lock, self.transaction():
            self.check_healthy()
            if player_id not in self.online:
                raise GameError("not_connected", "Join before sending commands")
            if not isinstance(command, dict):
                raise GameError("invalid_command", "Command must be an object")
            result = self.action(self.players[player_id], self.controls[player_id], command)
            self.detonate_mines()
            return result

    def tick(self, seconds):
        with self.lock:
            if not self.online or self.fault:
                return
            with self.transaction():
                self.elapsed += seconds
                self.tick_number += 1
                self.update_fires(seconds)
                for player_id in list(self.online):
                    player, controls = self.players[player_id], self.controls[player_id]
                    if self.input_expired(controls):
                        controls.move_x = controls.move_y = 0.0
                        controls.velocity_x = controls.velocity_y = 0.0
                        controls.stop_attack()
                    self.update_player(player, controls, seconds)
                previous_monsters = {identifier: (monster.x, monster.y) for identifier, monster in self.monsters.items()}
                self.update_burning()
                self.update_impalement()
                self.detonate_mines()
                self.update_monsters(seconds)
                self.detonate_mines()
                self._velocities = {identifier: ((monster.x - previous_monsters[identifier][0]) / seconds, (monster.y - previous_monsters[identifier][1]) / seconds) for identifier, monster in self.monsters.items() if identifier in previous_monsters and seconds > 0}
                self.update_projectiles(seconds)
                for player_id in list(self.online):
                    player, controls = self.players[player_id], self.controls[player_id]
                    self.update_player_attack(player, controls, seconds)
                    self.pickup(player)
                    self.validate_container(player, controls)
                self.update_ground_items()
                self.detonate_mines()
                self.spawn_monster()
                if self._persistence is None and self.elapsed >= self.next_save and self._backup is None:
                    self.touch()

    def input_expired(self, controls):
        return time.monotonic() - controls.last_input > 1

    @contextmanager
    def monster_collisions(self):
        previous = self._body_index
        if previous is None:
            self._body_index = BodyIndex(self.monsters.values())
        try:
            yield
        finally:
            self._body_index = previous

    def nearby_monsters(self, left, top, right, bottom):
        bodies = self._body_index.query(left, top, right, bottom) if self._body_index is not None else self.monsters.values()
        return (body for body in bodies if self.monsters.get(body.id) is body and left <= body.x <= right and top <= body.y <= bottom)

    def can_stand(self, x, y, player_id=None, monster_id=None, ignore_monsters=False, ignore_structure=None):
        if any(not self.generated(corner_x, corner_y) for corner_x in (x - BODY_RADIUS, x + BODY_RADIUS) for corner_y in (y - BODY_RADIUS, y + BODY_RADIUS)):
            return False
        for tile_x in range(tile(x - BODY_RADIUS - 0.5), tile(x + BODY_RADIUS + 0.5) + 1):
            for tile_y in range(tile(y - BODY_RADIUS - 0.5), tile(y + BODY_RADIUS + 0.5) + 1):
                structure = self.structure_at(tile_x, tile_y)
                if structure and structure.id != ignore_structure and structure.kind in SOLID and circle_square(x, y, tile_x, tile_y):
                    return False
        if not ignore_monsters:
            ghost = self.controls[player_id].ghost_monsters if player_id in self.controls else set()
            for monster in self.nearby_monsters(x - BODY_RADIUS * 2, y - BODY_RADIUS * 2, x + BODY_RADIUS * 2, y + BODY_RADIUS * 2):
                if monster.id != monster_id and monster.id not in ghost and not self.allows_player_overlap(monster, player_id) and math.hypot(x - monster.x, y - monster.y) < BODY_RADIUS * 2 - 1e-9:
                    return False
        if monster_id is not None:
            moving_monster = self.monsters.get(monster_id)
            for other_id in self.online:
                player = self.players[other_id]
                if player.temperature >= 5 and monster_id not in self.controls[other_id].ghost_monsters and not (moving_monster and self.allows_player_overlap(moving_monster, other_id)) and math.hypot(x - player.x, y - player.y) < BODY_RADIUS * 2 - 1e-9:
                    return False
        return True

    def move_body(self, body, delta_x, delta_y, player_id=None, monster_id=None):
        steps = max(1, math.ceil(math.hypot(delta_x, delta_y) / 0.15))
        moved = False
        for step in range(steps):
            arguments = {"player_id": player_id, "monster_id": monster_id, "ignore_monsters": player_id is not None and body.temperature < 5}
            if self.can_stand(body.x + delta_x / steps, body.y + delta_y / steps, **arguments):
                body.x += delta_x / steps
                body.y += delta_y / steps
                moved = True
            else:
                if delta_x and self.can_stand(body.x + delta_x / steps, body.y, **arguments):
                    body.x += delta_x / steps
                    moved = True
                if delta_y and self.can_stand(body.x, body.y + delta_y / steps, **arguments):
                    body.y += delta_y / steps
                    moved = True
            if monster_id is not None:
                if self._body_index is not None:
                    self._body_index.update(body)
                self.collect_mine(body)
        return moved

    def visible(self, start_x, start_y, end_x, end_y, ignore=None):
        for structure in self.nearby_structures(start_x, start_y, end_x, end_y):
            if structure.id != ignore and structure.kind in OPAQUE and segment_box(start_x, start_y, end_x, end_y, structure.x, structure.y) is not None:
                return False
        return True

    def nearby_structures(self, start_x, start_y, end_x, end_y):
        for point in segment_tiles(start_x, start_y, end_x, end_y):
            identifier = self.tiles.get(point)
            if identifier is not None:
                yield self.structures[identifier]

    def nearest_walkable(self, player):
        center_x, center_y = tile(player.x), tile(player.y)
        candidates = [(center_x + offset_x, center_y + offset_y) for offset_x in range(-30, 31) for offset_y in range(-30, 31)]
        candidates.sort(key=lambda point: (point[0] - player.x) ** 2 + (point[1] - player.y) ** 2)
        return next((point for point in candidates if (self.structure_at(*point) is None or self.structure_at(*point).kind not in SEATS) and self.can_stand(*point, player_id=player.id, ignore_monsters=player.temperature < 5)), None)

    def return_destination(self, center_x=0.0, center_y=0.0):
        half = CHUNK_SIZE // 2
        center_chunk = (chunk(center_x), chunk(center_y))
        pending = [(0, *center_chunk)]
        queued = {center_chunk}
        monster_tiles = {(tile(monster.x), tile(monster.y)) for monster in self.monsters.values()}
        best = None
        while pending:
            lower_bound, chunk_x, chunk_y = heapq.heappop(pending)
            if best is not None and lower_bound > best[0]:
                break
            self.generate_chunk(chunk_x, chunk_y)
            candidates = sorted(((horizontal - center_x) ** 2 + (vertical - center_y) ** 2, horizontal, vertical) for horizontal in range(chunk_x * CHUNK_SIZE - half, chunk_x * CHUNK_SIZE + half + 1) for vertical in range(chunk_y * CHUNK_SIZE - half, chunk_y * CHUNK_SIZE + half + 1))
            for origin_distance, horizontal, vertical in candidates:
                if best is not None and origin_distance > best[0]:
                    break
                structure = self.structure_at(horizontal, vertical)
                if (horizontal, vertical) in monster_tiles or (structure and structure.kind not in {"floor", "landmine"}) or not self.can_stand(horizontal, vertical):
                    continue
                safety = min(((horizontal - monster_x) ** 2 + (vertical - monster_y) ** 2 for monster_x, monster_y in monster_tiles), default=math.inf)
                candidate = (origin_distance, -safety, horizontal, vertical)
                if best is None or candidate < best:
                    best = candidate
            for offset_x, offset_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor = (chunk_x + offset_x, chunk_y + offset_y)
                if neighbor not in queued:
                    queued.add(neighbor)
                    nearest_distance = sum(max(0, abs(coordinate * CHUNK_SIZE - center) - half) ** 2 for coordinate, center in zip(neighbor, (center_x, center_y)))
                    heapq.heappush(pending, (nearest_distance, *neighbor))
        return best[2], best[3]

    def environment(self):
        day = int(self.elapsed // DAY_SECONDS)
        season = (day // SEASON_DAYS) % len(SEASONS)
        hour = (self.elapsed % DAY_SECONDS) / 60
        spring = -20 + hour * (20 / 12) if hour <= 12 else 20 - hour * (20 / 12)
        return {"year": day // (SEASON_DAYS * len(SEASONS)) + 1, "season": SEASONS[season], "day": day % SEASON_DAYS + 1, "hour": hour, "ambient_temperature": spring + SEASON_OFFSETS[season]}

    def temperature_at(self, player):
        if player.hunger <= STARVATION_HUNGER and player.temperature > STARVATION_TEMPERATURE:
            return STARVATION_AMBIENT
        if player.excitement_remaining > 0:
            return DRINKS["vodka"]["felt_temperature"]
        return self.actual_temperature_at(player) + carried_modifier(player, "ambient_bonus", 0.0)

    def actual_temperature_at(self, player):
        nearest = min((abs(tile(player.x) - fire.x) + abs(tile(player.y) - fire.y) for fire in self._campfires.values() if fire.lit), default=math.inf)
        return next((temperature for radius, temperature in ((3, 30), (6, 20), (9, 10)) if 1 <= nearest <= radius), self.environment()["ambient_temperature"])

    def update_fires(self, seconds):
        for fire in self._campfires.values():
            if not fire.lit:
                continue
            self.record_structure(fire.id)
            remaining = fire.burn_remaining - seconds
            if remaining <= 0:
                self.touch()
                while remaining <= 0 and fire.fuel > 0:
                    fire.fuel -= 1
                    remaining += BURN_SECONDS
                fire.burn_remaining = max(0, remaining)
            else:
                fire.burn_remaining = remaining

    @staticmethod
    def player_speed(player):
        if player.temperature < 5:
            return 0.0
        item = player.inventory[player.selected]
        multiplier = EQUIPPED_ITEMS.get(item.kind, {}).get("speed_multiplier", 1) if item else 1
        return PLAYER_SPEED * (0.5 if player.temperature < 18 else 1) * (0.5 if player.hunger <= 0 else 1) * multiplier

    @staticmethod
    def body_temperature_rate(ambient):
        return next((rate for minimum, rate in BODY_TEMPERATURE_RATES if ambient >= minimum), -10)

    def change_body_temperature(self, player, ambient, seconds):
        starving = player.hunger <= STARVATION_HUNGER
        if starving and player.temperature > STARVATION_TEMPERATURE:
            rate = self.body_temperature_rate(STARVATION_AMBIENT)
            cooling_seconds = min(seconds, (player.temperature - STARVATION_TEMPERATURE) * 60 / -rate)
            player.temperature = max(STARVATION_TEMPERATURE, player.temperature + rate * cooling_seconds / 60)
            seconds -= cooling_seconds
        if seconds > 0:
            ceiling = STARVATION_TEMPERATURE if starving else 36.0
            player.temperature = max(0.0, min(ceiling, player.temperature + self.body_temperature_rate(ambient) * seconds / 60))

    def drain_hunger(self, player, seconds):
        player.hunger = max(0.0, player.hunger - seconds / 60 * carried_modifier(player, "hunger_drain_multiplier", minimum=True))

    def update_player(self, player, controls, seconds):
        previous_temperature = player.temperature
        excited_seconds = min(seconds, player.excitement_remaining)
        if excited_seconds > 0:
            self.change_body_temperature(player, DRINKS["vodka"]["felt_temperature"], excited_seconds)
            player.excitement_remaining = max(0.0, player.excitement_remaining - seconds)
        if seconds > excited_seconds:
            ambient = self.actual_temperature_at(player) + carried_modifier(player, "ambient_bonus", 0.0)
            self.change_body_temperature(player, ambient, seconds - excited_seconds)
        self.drain_hunger(player, seconds)
        if (previous_temperature < 5) != (player.temperature < 5):
            controls.movement_epoch += 1
        if player.temperature < 5:
            controls.seat = None
            item = player.inventory[player.selected]
            if item is None or item.kind not in HEALING_ITEMS and item.kind not in RETURN_ITEMS and item.kind not in DRINKS:
                controls.stop_attack()
            controls.ghost_monsters.update(monster.id for monster in self.monsters.values() if distance(player, monster) < BODY_RADIUS * 2)
        elif previous_temperature < 5:
            controls.ghost_monsters.update(monster.id for monster in self.monsters.values() if distance(player, monster) < BODY_RADIUS * 2)
        controls.ghost_monsters.intersection_update(monster.id for monster in self.monsters.values() if distance(player, monster) < BODY_RADIUS * 2)
        if player.temperature >= 5:
            speed = self.player_speed(player)
            self.ensure_terrain(player.x, player.y)
            if not controls.client_movement:
                previous_x, previous_y = player.x, player.y
                self.move_body(player, controls.move_x * speed * seconds, controls.move_y * speed * seconds, player_id=player.id)
                controls.velocity_x = (player.x - previous_x) / seconds if seconds > 0 else 0.0
                controls.velocity_y = (player.y - previous_y) / seconds if seconds > 0 else 0.0
                self.ensure_terrain(player.x, player.y)
        else:
            controls.velocity_x = controls.velocity_y = 0.0

    def update_ground_items(self):
        viewers = [(self.players[identifier], self.controls[identifier]) for identifier in sorted(self.online)]
        for identifier, ground in list(self.ground.items()):
            seen = any(abs(ground.x - player.x) <= min(20, controls.view_width / 2 + 0.285) and abs(ground.y - player.y) <= min(13, controls.view_height / 2 + 0.33) for player, controls in viewers)
            if seen:
                if ground.unseen_since is not None:
                    self.touch()
                    ground.unseen_since = None
            elif ground.unseen_since is None:
                self.touch()
                ground.unseen_since = self.elapsed
            elif self.elapsed - ground.unseen_since + 1e-9 >= GROUND_ITEM_UNSEEN_SECONDS:
                self.touch()
                del self.ground[identifier]

    def pickup(self, player):
        storages = personal_storages(player, ("inventory", "backpack"))
        radius = PICKUP_RADIUS + carried_modifier(player, "pickup_radius_bonus", 0.0)
        for ground_id, ground in list(self.ground.items()):
            if distance(player, ground) <= radius and self.visible(player.x, player.y, ground.x, ground.y) and not (ground.dropped_by == player.id and self.elapsed < ground.immune_until):
                if ground.item.kind != "coin" and not can_insert(storages, ground.item):
                    continue
                self.touch()
                if ground.item.kind == "coin":
                    player.money += ground.item.count
                else:
                    insert_item(storages, ground.item)
                del self.ground[ground_id]

    def snapshot(self, player_id, procedural=False):
        with self.lock:
            shared = capture_entities(self)
            viewer = self.snapshot_view(player_id, procedural)
        return compose_snapshot(shared, viewer)

    def snapshot_view(self, player_id, procedural=False, demolitions=None):
        with self.lock:
            player = self.players[player_id]
            structures = []
            if demolitions is None:
                demolitions = self.active_demolitions()
            for horizontal in range(math.ceil(player.x - 20), math.floor(player.x + 20) + 1) if not procedural else ():
                for vertical in range(math.ceil(player.y - 13), math.floor(player.y + 13) + 1):
                    structure = self.structure_at(horizontal, vertical)
                    if structure:
                        structures.append({"id": structure.id, "kind": structure.kind, "x": structure.x, "y": structure.y, "lit": structure.lit, "monster_demolition": structure.id in demolitions})
            controls = self.controls[player_id]
            seat = self.seated_structure(controls)
            occupants = {control.seat: identifier for identifier, control in self.controls.items() if control.seat}
            for structure in structures:
                if structure["kind"] in SEATS:
                    structure["occupant"] = occupants.get(structure["id"])
                    structure["ammo"] = self.structures[structure["id"]].ammo
            container = self.structures.get(controls.container)
            visible_chunks = [(horizontal, vertical) for horizontal in range(math.ceil((player.x - 30) / CHUNK_SIZE), math.floor((player.x + 30) / CHUNK_SIZE) + 1) for vertical in range(math.ceil((player.y - 24) / CHUNK_SIZE), math.floor((player.y + 24) / CHUNK_SIZE) + 1) if (horizontal, vertical) in self.chunks]
            return {
                "movement": {"mode": "client" if controls.client_movement else "server", "epoch": controls.movement_epoch, "teleport_epoch": controls.teleport_epoch},
                "you": {**encode(player), "seated": seat.kind if seat else None, "seat_id": controls.seat, "tile": [tile(player.x), tile(player.y)], "offset": [player.x - tile(player.x), player.y - tile(player.y)], "ambient_temperature": self.temperature_at(player), "downed": player.temperature < 5, "is_admin": self.admin is not None and player.id == self.admin},
                "structures": structures,
                **({"structure_states": self.structure_states(player, demolitions)} if procedural else {}),
                "chunks": sorted(visible_chunks),
                "container": encode(container) if container else None,
                "interaction": {"target": controls.target, "progress": controls.progress, "ui_open": controls.ui},
            }

    @staticmethod
    def catalog():
        return {"stack_limits": STACK_LIMITS, "backpack_stack_limits": BACKPACK_STACK_LIMITS, "navigation_items": NAVIGATION_ITEMS, "tick_rate": TICK_RATE, "chunk_size": CHUNK_SIZE, "radius": BODY_RADIUS, "recipes": RECIPES, "vending_offers": VENDING_OFFERS, "machine_offers": MACHINE_OFFERS, "room_machines": {kind: {"chance": definition["chance"]} for kind, definition in ROOM_MACHINES.items()}, "currency": {"item": "coin", "player_field": "money", "uses_slots": False, "shared_bank": "piggy_bank", "bank_balance_field": "balance", "max_coins": MAX_COINS}, "body_temperature_rates": BODY_TEMPERATURE_RATES, "monster_coin_drops": MONSTER_COIN_DROPS, "monster_food_drops": {"small": {"chance": SMALL_MONSTER_FOOD_CHANCE, "weights": SMALL_MONSTER_FOOD_WEIGHTS}}, "monster_spawning": {"night_start": NIGHT_MONSTER_HOURS[0], "night_end": NIGHT_MONSTER_HOURS[1], **MONSTER_SPAWN_CHANCES}, "monster_activity": {"rest_start": MONSTER_REST_HOURS[0], "rest_end": MONSTER_REST_HOURS[1], "rise_seconds": MONSTER_RISE_SECONDS}, "terrain": {"version": TERRAIN_VERSION, "vending_machine_chance": VENDING_MACHINE_CHANCE, "match_machine_chance": MATCH_MACHINE_CHANCE, "chest_first_aid_kit_chance": FIRST_AID_KIT_CHANCE, "chest_return_staff_chance": RETURN_STAFF_CHANCE, "chest_ice_staff_chance": ICE_STAFF_CHANCE, "gun_machine_chance": GUN_MACHINE_CHANCE, "chest_grenade_chance": GRENADE_CHANCE, "chest_flame_staff_chance": FLAME_STAFF_CHANCE, "chest_defibrillator_chance": DEFIBRILLATOR_CHANCE, "piggy_bank_chance": PIGGY_BANK_CHANCE, "chest_heat_patch_chance": HEAT_PATCH_CHANCE, "chest_sheriff_badge_chance": SHERIFF_BADGE_CHANCE, "chest_vodka_chance": VODKA_CHANCE, "chest_swiftness_ring_chance": SWIFTNESS_RING_CHANCE, "chest_homing_missile_chance": HOMING_MISSILE_CHANCE, "chest_chainsaw_chance": CHAINSAW_CHANCE, "chest_landmine_chance": LANDMINE_CHANCE, "chest_durian_chance": DURIAN_CHANCE, "room_machine_chances": {kind: definition["chance"] for kind, definition in ROOM_MACHINES.items()}, "chest_expansion_chances": {kind: value["chance"] for kind, value in EXPANSION_ITEMS.items()}, "unexplored_uses_latest": True}, "axe": AXE, "melee_weapons": MELEE_WEAPONS, "harvest_tools": HARVEST_TOOLS, "explosive_weapons": EXPLOSIVE_WEAPONS, "throwable_weapons": THROWABLE_WEAPONS, "guns": GUNS, "projectiles": {"piercing": True, "range": "viewport_half_diagonal", "default_viewport": list(DEFAULT_VIEWPORT), "blockers": sorted(BULLET_BLOCKERS), "monster_blockers": sorted(MONSTER_BULLET_BLOCKERS)}, "drinks": DRINKS, "passive_items": PASSIVE_ITEMS, "equipped_items": EQUIPPED_ITEMS, "ready_to_eat_foods": sorted(READY_TO_EAT_FOODS), "healing_items": HEALING_ITEMS, "revival_items": REVIVAL_ITEMS, "return_items": RETURN_ITEMS, "foods": FOODS, "igniters": IGNITERS, "items": sorted(ITEM_KINDS), "expansion_items": {kind: {"category": EXPANSION_CATEGORIES[value["mechanic"]], "group": value["group"], "chance": value["chance"]} for kind, value in EXPANSION_ITEMS.items()}, "day_seconds": DAY_SECONDS, "season_days": SEASON_DAYS, "movement": {"player_speed": PLAYER_SPEED, "monster_speed": MONSTER_SPEED, "fast_monster_speed": FAST_MONSTER_SPEED, "frozen_speed_scale": ICE_STAFF["speed_scale"]}, "knockback": KNOCKBACK, "storage": {"inventory_slots": INVENTORY_SLOTS, "backpack_slots": BACKPACK_SLOTS, "drop_distance": DROP_DISTANCE, "pickup_radius": PICKUP_RADIUS}, "monster_types": MONSTER_TYPES, "outdoor_features": OUTDOOR_FEATURES, "protocol": 1}

    def close(self, save=True):
        with self.lock:
            try:
                if save and not self.fault:
                    self.save_changes()
            finally:
                self.storage.close()
