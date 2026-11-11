import copy
import heapq
import math
import random
import secrets
import threading
import time
from collections import deque
from contextlib import contextmanager

from .actions import Actions, GameError
from .combat import Combat
from .constants import AXE, BACKPACK_SLOTS, BODY_RADIUS, BULLET_BLOCKERS, BURN_SECONDS, CHUNK_SIZE, DAY_SECONDS, DEFAULT_VIEWPORT, DROP_DISTANCE, FAST_MONSTER_SPEED, FIRST_AID_KIT_CHANCE, FOODS, GUNS, HEALING_ITEMS, IGNITERS, INVENTORY_SLOTS, ITEM_KINDS, KNOCKBACK, MACHINE_OFFERS, MATCH_MACHINE_CHANCE, MONSTER_COIN_DROPS, MONSTER_SPAWN_CHANCES, MONSTER_SPEED, NIGHT_MONSTER_HOURS, OPAQUE, PICKUP_RADIUS, PLAYER_SPEED, RECIPES, RETURN_ITEMS, RETURN_STAFF_CHANCE, SEASON_DAYS, SEASON_OFFSETS, SEASONS, SOLID, TERRAIN_VERSION, TICK_RATE, VENDING_MACHINE_CHANCE, VENDING_OFFERS
from .geometry import circle_square, distance, segment_box, tile
from .models import Controls, GroundItem, Item, Monster, Player, Projectile, encode, item_from, player_from, structure_from
from .monsters import Monsters
from .terrain import Terrain


def tuples(value):
    return tuple(tuples(element) for element in value) if isinstance(value, list) else value


class World(Actions, Combat, Monsters, Terrain):
    def __init__(self, storage, seed=None):
        self.storage = storage
        self.lock = threading.RLock()
        self.online = set()
        self.controls = {}
        self.fault = None
        self._backup = None
        self._runtime_backup = None
        self.events = deque(maxlen=256)
        self.event_sequence = 0
        self._pending_events = []
        self._path_cursor = None
        self._path_jobs = {}
        self._path_queue = deque()
        self._velocities = {}
        state = storage.load()
        if state:
            self.restore(state)
        else:
            self.seed = seed if seed is not None else secrets.randbits(63)
            self.random = random.Random(self.seed)
            self.elapsed = 0.0
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
            self.storage.save(self.export())
        self.next_save = self.elapsed + 2

    def export(self):
        return {
            "seed": self.seed,
            "random": self.random.getstate(),
            "elapsed": self.elapsed,
            "tick_number": self.tick_number,
            "chunks": sorted(self.chunks),
            "chunk_versions": [[*point, self.chunk_versions.get(point, 1)] for point in sorted(self.chunks)],
            "origin_region": self.origin_region,
            "structures": [encode(value) for value in self.structures.values()],
            "players": [encode(value) for value in self.players.values()],
            "monsters": [encode(value) for value in self.monsters.values()],
            "projectiles": [encode(value) for value in self.projectiles.values()],
            "ground": [encode(value) for value in self.ground.values()],
            "shot_hits": {shot: sorted(players) for shot, players in self.shot_hits.items()},
            "shot_impacts": {shot: sorted(monsters) for shot, monsters in self.shot_impacts.items()},
        }

    def restore(self, state):
        self._path_jobs = {}
        self._path_queue = deque()
        self.seed = state["seed"]
        self.random = random.Random()
        self.random.setstate(tuples(state["random"]))
        self.elapsed = state["elapsed"]
        self.tick_number = state["tick_number"]
        self.chunks = {tuple(point) for point in state["chunks"]}
        versions = {(chunk_x, chunk_y): version for chunk_x, chunk_y, version in state.get("chunk_versions", [])}
        self.chunk_versions = {point: versions.get(point, 1) for point in self.chunks}
        self.origin_region = [tuple(point) for point in state["origin_region"]]
        self.structures = {values["id"]: structure_from(values) for values in state["structures"]}
        self.tiles = {(value.x, value.y): value.id for value in self.structures.values()}
        self.players = {values["id"]: player_from(values) for values in state["players"]}
        self.monsters = {values["id"]: Monster(**values) for values in state["monsters"]}
        self.projectiles = {values["id"]: Projectile(**values) for values in state["projectiles"]}
        self.ground = {values["id"]: GroundItem(**{**values, "item": item_from(values["item"])}) for values in state["ground"]}
        self.shot_hits = {shot: set(players) for shot, players in state["shot_hits"].items()}
        self.shot_impacts = {shot: set(monsters) for shot, monsters in state.get("shot_impacts", {}).items()}

    def touch(self):
        if self._backup is None:
            self._backup = self.export()
            self._runtime_backup = (set(self.online), copy.deepcopy(self.controls))

    @contextmanager
    def transaction(self):
        self._pending_events = []
        try:
            yield
            if self._backup is not None:
                self.storage.save(self.export())
                self.next_save = self.elapsed + 2
            for event in self._pending_events:
                self.event_sequence += 1
                self.events.append({**event, "id": self.event_sequence})
        except BaseException as error:
            if self._backup is not None:
                self.restore(self._backup)
                self.online, self.controls = self._runtime_backup
            if not isinstance(error, GameError):
                self.fault = "Storage or simulation failure; restart the server after checking its log"
            raise
        finally:
            self._backup = None
            self._runtime_backup = None
            self._pending_events = []

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
                self.random.shuffle(points)
                position = next((point for point in points if self.can_stand(*point, player_id=player_id)), None)
                if position is None:
                    raise GameError("spawn_blocked", "No safe spawn position is currently available")
                player = Player(player_id, *position)
                player.inventory[:3] = [Item.create("handgun"), Item.create("axe"), Item.create("lighter")]
                self.players[player_id] = player
            elif not self.can_stand(player.x, player.y, player_id=player_id, ignore_monsters=player.temperature < 5):
                position = self.nearest_walkable(player)
                if position is None:
                    raise GameError("spawn_blocked", "No nearby walkable reconnect position")
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
                return
            with self.transaction():
                self.touch()
                for projectile in self.projectiles.values():
                    if projectile.range_player == player_id or (not projectile.hostile and projectile.owner == player_id):
                        projectile.remaining = self.projectile_range(projectile)
                self.online.remove(player_id)
                self.controls.pop(player_id, None)
                for monster in self.monsters.values():
                    if monster.target == player_id:
                        self.clear_target(monster)

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
            return self.action(self.players[player_id], self.controls[player_id], command)

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
                    if time.monotonic() - controls.last_input > 1:
                        controls.move_x = controls.move_y = 0.0
                        controls.velocity_x = controls.velocity_y = 0.0
                        controls.stop_attack()
                    self.update_player(player, controls, seconds)
                previous_monsters = {identifier: (monster.x, monster.y) for identifier, monster in self.monsters.items()}
                self.update_monsters(seconds)
                self._velocities = {identifier: ((monster.x - previous_monsters[identifier][0]) / seconds, (monster.y - previous_monsters[identifier][1]) / seconds) for identifier, monster in self.monsters.items() if identifier in previous_monsters and seconds > 0}
                self.update_projectiles(seconds)
                for player_id in list(self.online):
                    player, controls = self.players[player_id], self.controls[player_id]
                    self.update_player_attack(player, controls, seconds)
                    self.pickup(player)
                    self.validate_container(player, controls)
                self.spawn_monster()
                if self.elapsed >= self.next_save and self._backup is None:
                    self.touch()

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
            for monster in self.monsters.values():
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
        return moved

    def visible(self, start_x, start_y, end_x, end_y, ignore=None):
        for structure in self.nearby_structures(start_x, start_y, end_x, end_y):
            if structure.id != ignore and structure.kind in OPAQUE and segment_box(start_x, start_y, end_x, end_y, structure.x, structure.y) is not None:
                return False
        return True

    def nearby_structures(self, start_x, start_y, end_x, end_y):
        first_x, first_y = tile(start_x), tile(start_y)
        last_x, last_y = tile(end_x), tile(end_y)
        width, height = abs(last_x - first_x) + 3, abs(last_y - first_y) + 3
        if width * height > (width + height) * 5:
            direction_x = (end_x > start_x) - (end_x < start_x)
            direction_y = (end_y > start_y) - (end_y < start_y)
            step_x = 1 / abs(end_x - start_x) if direction_x else math.inf
            step_y = 1 / abs(end_y - start_y) if direction_y else math.inf
            next_x = ((first_x + direction_x * 0.5) - start_x) / (end_x - start_x) if direction_x else math.inf
            next_y = ((first_y + direction_y * 0.5) - start_y) / (end_y - start_y) if direction_y else math.inf
            visited = set()
            current_x, current_y = first_x, first_y
            while True:
                for offset_x in (-1, 0, 1):
                    for offset_y in (-1, 0, 1):
                        point = current_x + offset_x, current_y + offset_y
                        if point not in visited:
                            visited.add(point)
                            structure = self.structure_at(*point)
                            if structure:
                                yield structure
                if (current_x, current_y) == (last_x, last_y):
                    return
                if current_x == last_x:
                    next_x = math.inf
                if current_y == last_y:
                    next_y = math.inf
                if next_x < next_y:
                    current_x += direction_x
                    next_x += step_x
                else:
                    current_y += direction_y
                    next_y += step_y
        for tile_x in range(tile(min(start_x, end_x)) - 1, tile(max(start_x, end_x)) + 2):
            for tile_y in range(tile(min(start_y, end_y)) - 1, tile(max(start_y, end_y)) + 2):
                structure = self.structure_at(tile_x, tile_y)
                if structure:
                    yield structure

    def nearest_walkable(self, player):
        center_x, center_y = tile(player.x), tile(player.y)
        candidates = [(center_x + offset_x, center_y + offset_y) for offset_x in range(-30, 31) for offset_y in range(-30, 31)]
        candidates.sort(key=lambda point: (point[0] - player.x) ** 2 + (point[1] - player.y) ** 2)
        return next((point for point in candidates if self.can_stand(*point, player_id=player.id, ignore_monsters=player.temperature < 5)), None)

    def return_destination(self):
        half = CHUNK_SIZE // 2
        pending = [(0, 0, 0)]
        queued = {(0, 0)}
        monster_tiles = {(tile(monster.x), tile(monster.y)) for monster in self.monsters.values()}
        best = None
        while pending:
            lower_bound, chunk_x, chunk_y = heapq.heappop(pending)
            if best is not None and lower_bound > best[0]:
                break
            self.generate_chunk(chunk_x, chunk_y)
            candidates = sorted((horizontal ** 2 + vertical ** 2, horizontal, vertical) for horizontal in range(chunk_x * CHUNK_SIZE - half, chunk_x * CHUNK_SIZE + half + 1) for vertical in range(chunk_y * CHUNK_SIZE - half, chunk_y * CHUNK_SIZE + half + 1))
            for origin_distance, horizontal, vertical in candidates:
                if best is not None and origin_distance > best[0]:
                    break
                if (horizontal, vertical) in monster_tiles or self.structure_at(horizontal, vertical) or not self.can_stand(horizontal, vertical):
                    continue
                safety = min(((horizontal - monster_x) ** 2 + (vertical - monster_y) ** 2 for monster_x, monster_y in monster_tiles), default=math.inf)
                candidate = (origin_distance, -safety, horizontal, vertical)
                if best is None or candidate < best:
                    best = candidate
            for offset_x, offset_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor = (chunk_x + offset_x, chunk_y + offset_y)
                if neighbor not in queued:
                    queued.add(neighbor)
                    nearest_distance = sum(max(0, abs(coordinate * CHUNK_SIZE) - half) ** 2 for coordinate in neighbor)
                    heapq.heappush(pending, (nearest_distance, *neighbor))
        return best[2], best[3]

    def environment(self):
        day = int(self.elapsed // DAY_SECONDS)
        season = (day // SEASON_DAYS) % len(SEASONS)
        hour = (self.elapsed % DAY_SECONDS) / 60
        spring = -20 + hour * (20 / 12) if hour <= 12 else 20 - hour * (20 / 12)
        return {"year": day // (SEASON_DAYS * len(SEASONS)) + 1, "season": SEASONS[season], "day": day % SEASON_DAYS + 1, "hour": hour, "ambient_temperature": spring + SEASON_OFFSETS[season]}

    def temperature_at(self, player):
        nearest = min((abs(tile(player.x) - fire.x) + abs(tile(player.y) - fire.y) for fire in self.structures.values() if fire.kind == "campfire" and fire.lit), default=math.inf)
        return next((temperature for radius, temperature in ((3, 30), (6, 20), (9, 10)) if 1 <= nearest <= radius), self.environment()["ambient_temperature"])

    def update_fires(self, seconds):
        for fire in self.structures.values():
            if fire.kind != "campfire" or not fire.lit:
                continue
            remaining = fire.burn_remaining - seconds
            if remaining <= 0:
                self.touch()
                while remaining <= 0 and fire.fuel > 0:
                    fire.fuel -= 1
                    remaining += BURN_SECONDS
                fire.burn_remaining = max(0, remaining)
            else:
                fire.burn_remaining = remaining

    def update_player(self, player, controls, seconds):
        previous_temperature = player.temperature
        ambient = self.temperature_at(player)
        rate = 10 if ambient >= 20 else 0 if ambient >= 10 else -1 if ambient >= 0 else -2 if ambient >= -10 else -5 if ambient >= -20 else -10
        player.temperature = max(0.0, min(36.0, player.temperature + rate * seconds / 60))
        player.hunger = max(0.0, player.hunger - seconds / 60)
        if (previous_temperature < 5) != (player.temperature < 5):
            controls.movement_epoch += 1
        if player.temperature < 5:
            item = player.inventory[player.selected]
            if item is None or item.kind not in HEALING_ITEMS and item.kind not in RETURN_ITEMS:
                controls.stop_attack()
            controls.ghost_monsters.update(monster.id for monster in self.monsters.values() if distance(player, monster) < BODY_RADIUS * 2)
        elif previous_temperature < 5:
            controls.ghost_monsters.update(monster.id for monster in self.monsters.values() if distance(player, monster) < BODY_RADIUS * 2)
        controls.ghost_monsters.intersection_update(monster.id for monster in self.monsters.values() if distance(player, monster) < BODY_RADIUS * 2)
        if player.temperature >= 5:
            speed = PLAYER_SPEED * (0.5 if player.temperature < 18 else 1) * (0.5 if player.hunger == 0 else 1)
            self.ensure_terrain(player.x, player.y)
            if not controls.client_movement:
                previous_x, previous_y = player.x, player.y
                self.move_body(player, controls.move_x * speed * seconds, controls.move_y * speed * seconds, player_id=player.id)
                controls.velocity_x = (player.x - previous_x) / seconds if seconds > 0 else 0.0
                controls.velocity_y = (player.y - previous_y) / seconds if seconds > 0 else 0.0
                self.ensure_terrain(player.x, player.y)
        else:
            controls.velocity_x = controls.velocity_y = 0.0

    def pickup(self, player):
        has_space = None in player.backpack
        for ground_id, ground in list(self.ground.items()):
            if ground.item.kind != "coin" and not has_space:
                continue
            if distance(player, ground) <= PICKUP_RADIUS and self.visible(player.x, player.y, ground.x, ground.y) and not (ground.dropped_by == player.id and self.elapsed < ground.immune_until):
                self.touch()
                if ground.item.kind == "coin":
                    player.money += 1
                else:
                    player.backpack[player.backpack.index(None)] = ground.item
                    has_space = None in player.backpack
                del self.ground[ground_id]

    def snapshot(self, player_id):
        with self.lock:
            player = self.players[player_id]
            structures = []
            demolitions = {monster.demolition for monster in self.monsters.values() if monster.demolition}
            for horizontal in range(math.ceil(player.x - 20), math.floor(player.x + 20) + 1):
                for vertical in range(math.ceil(player.y - 13), math.floor(player.y + 13) + 1):
                    structure = self.structure_at(horizontal, vertical)
                    if structure:
                        structures.append({"id": structure.id, "kind": structure.kind, "x": structure.x, "y": structure.y, "lit": structure.lit, "monster_demolition": structure.id in demolitions})
            controls = self.controls[player_id]
            container = self.structures.get(controls.container)
            visible_chunks = [(horizontal, vertical) for horizontal in range(math.ceil((player.x - 30) / CHUNK_SIZE), math.floor((player.x + 30) / CHUNK_SIZE) + 1) for vertical in range(math.ceil((player.y - 24) / CHUNK_SIZE), math.floor((player.y + 24) / CHUNK_SIZE) + 1) if (horizontal, vertical) in self.chunks]
            return {
                "tick": self.tick_number,
                "elapsed": self.elapsed,
                "paused": not self.online or self.fault is not None,
                "fault": self.fault,
                "movement": {"mode": "client" if controls.client_movement else "server", "epoch": controls.movement_epoch, "teleport_epoch": controls.teleport_epoch},
                "environment": self.environment(),
                "you": {**encode(player), "tile": [tile(player.x), tile(player.y)], "offset": [player.x - tile(player.x), player.y - tile(player.y)], "ambient_temperature": self.temperature_at(player), "downed": player.temperature < 5},
                "players": [{"id": other.id, "x": other.x, "y": other.y, "temperature": other.temperature, "hunger": other.hunger, "downed": other.temperature < 5, "velocity_x": self.controls[other_id].velocity_x, "velocity_y": self.controls[other_id].velocity_y, "teleport_epoch": self.controls[other_id].teleport_epoch} for other_id in sorted(self.online) if (other := self.players[other_id]) and abs(other.x - player.x) <= 20 and abs(other.y - player.y) <= 13],
                "structures": structures,
                "chunks": sorted(visible_chunks),
                "monsters": [{"id": monster.id, "x": monster.x, "y": monster.y, "big": monster.big, "fast": monster.fast, "hp": monster.hp, "demolition": monster.demolition, "overlap_player": monster.overlap_player, "velocity_x": self._velocities.get(monster.id, (0.0, 0.0))[0], "velocity_y": self._velocities.get(monster.id, (0.0, 0.0))[1]} for monster in self.monsters.values() if abs(monster.x - player.x) <= 20 and abs(monster.y - player.y) <= 13],
                "projectiles": [encode(projectile) for projectile in self.projectiles.values() if abs(projectile.x - player.x) <= 22 and abs(projectile.y - player.y) <= 15],
                "ground": [encode(ground) for ground in self.ground.values() if abs(ground.x - player.x) <= 20 and abs(ground.y - player.y) <= 13],
                "container": encode(container) if container else None,
                "interaction": {"target": controls.target, "progress": controls.progress, "ui_open": controls.ui},
                "event_sequence": self.event_sequence,
                "events": [event for event in self.events if self.elapsed - event["time"] <= 1.5 and abs(event["x"] - player.x) <= 20 and abs(event["y"] - player.y) <= 13],
            }

    @staticmethod
    def catalog():
        return {"tick_rate": TICK_RATE, "chunk_size": CHUNK_SIZE, "radius": BODY_RADIUS, "recipes": RECIPES, "vending_offers": VENDING_OFFERS, "machine_offers": MACHINE_OFFERS, "currency": {"item": "coin", "player_field": "money", "uses_slots": False}, "monster_coin_drops": MONSTER_COIN_DROPS, "monster_spawning": {"night_start": NIGHT_MONSTER_HOURS[0], "night_end": NIGHT_MONSTER_HOURS[1], **MONSTER_SPAWN_CHANCES}, "terrain": {"version": TERRAIN_VERSION, "vending_machine_chance": VENDING_MACHINE_CHANCE, "match_machine_chance": MATCH_MACHINE_CHANCE, "chest_first_aid_kit_chance": FIRST_AID_KIT_CHANCE, "chest_return_staff_chance": RETURN_STAFF_CHANCE, "unexplored_uses_latest": True}, "axe": AXE, "guns": GUNS, "projectiles": {"piercing": True, "range": "viewport_half_diagonal", "default_viewport": list(DEFAULT_VIEWPORT), "blockers": sorted(BULLET_BLOCKERS)}, "healing_items": HEALING_ITEMS, "return_items": RETURN_ITEMS, "foods": FOODS, "igniters": IGNITERS, "items": sorted(ITEM_KINDS), "day_seconds": DAY_SECONDS, "season_days": SEASON_DAYS, "movement": {"player_speed": PLAYER_SPEED, "monster_speed": MONSTER_SPEED, "fast_monster_speed": FAST_MONSTER_SPEED}, "knockback": KNOCKBACK, "storage": {"inventory_slots": INVENTORY_SLOTS, "backpack_slots": BACKPACK_SLOTS, "drop_distance": DROP_DISTANCE, "pickup_radius": PICKUP_RADIUS}, "protocol": 1}

    def close(self):
        with self.lock:
            try:
                if not self.fault:
                    self.storage.save(self.export())
            finally:
                self.storage.close()
