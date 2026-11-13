import math
import time

from .constants import EXPLOSIVE_WEAPONS
from .models import encode
from .wildlife import MONSTER_TYPES


def capture_entities(world):
    resting, rising = world.monster_activity()
    players = []
    covered = set()
    for identifier in sorted(world.online):
        player, controls = world.players[identifier], world.controls[identifier]
        covered.update((horizontal, vertical) for horizontal in range(math.floor((player.x - 22) / 22), math.floor((player.x + 22) / 22) + 1) for vertical in range(math.floor((player.y - 15) / 15), math.floor((player.y + 15) / 15) + 1))
        seat = world.structures.get(controls.seat)
        players.append({"id": player.id, "x": player.x, "y": player.y, "temperature": player.temperature, "hunger": player.hunger, "downed": player.temperature < 5, "move_speed": world.player_speed(player), "velocity_x": controls.velocity_x, "velocity_y": controls.velocity_y, "teleport_epoch": controls.teleport_epoch, "seated": seat.kind if seat else None, "seat_direction": (round(math.atan2(controls.aim_y - player.y, controls.aim_x - player.x) / (math.pi / 4)) + 8) % 8 if controls.seat else 0})
    nearby = lambda entity: (math.floor(entity.x / 22), math.floor(entity.y / 15)) in covered
    projectiles = (projectile for projectile in world.projectiles.values() if nearby(projectile) or (projectile.kind in EXPLOSIVE_WEAPONS and (math.floor(projectile.target_x / 22), math.floor(projectile.target_y / 15)) in covered))
    return {
        "tick": world.tick_number,
        "elapsed": world.elapsed,
        "paused": not world.online or world.fault is not None,
        "fault": world.fault,
        "environment": world.environment(),
        "event_sequence": world.event_sequence,
        "players": players,
        "monsters": [{"id": monster.id, "x": monster.x, "y": monster.y, "big": monster.big, "fast": monster.fast, "species": monster.kind, "max_hp": MONSTER_TYPES[monster.kind]["hp"], "move_speed": monster.speed, "hp": monster.hp, "frozen_until": monster.frozen_until, "burning_until": monster.burning_until, "sleeping": (monster.big or monster.fast) and resting, "rising": rising if monster.big else None, "demolition": monster.demolition, "overlap_player": monster.overlap_player, "velocity_x": world._velocities.get(monster.id, (0.0, 0.0))[0], "velocity_y": world._velocities.get(monster.id, (0.0, 0.0))[1]} for monster in world.monsters.values() if nearby(monster)],
        "projectiles": [encode(projectile) for projectile in projectiles],
        "ground": [encode(ground) for ground in world.ground.values() if nearby(ground)],
        "events": [event for event in world.events if world.elapsed - event["time"] <= 1.5],
    }


def compose_snapshot(shared, viewer):
    player = viewer["you"]
    horizontal, vertical = player["x"], player["y"]
    nearby = lambda record: abs(record["x"] - horizontal) <= 20 and abs(record["y"] - vertical) <= 13
    return {
        **shared,
        **viewer,
        "players": [record for record in shared["players"] if nearby(record)],
        "monsters": [record for record in shared["monsters"] if nearby(record)],
        "ground": [record for record in shared["ground"] if nearby(record)],
        "events": [record for record in shared["events"] if nearby(record)],
        "projectiles": [record for record in shared["projectiles"] if (abs(record["x"] - horizontal) <= 22 and abs(record["y"] - vertical) <= 15) or (record["kind"] in EXPLOSIVE_WEAPONS and abs(record["target_x"] - horizontal) <= 22 and abs(record["target_y"] - vertical) <= 15)],
    }


def terrain_delta(captured, previous):
    current = {point: record[0]["revision"] for point, record in captured.items()}
    updates = []
    for point in sorted(captured):
        if previous.get(point) == current[point]:
            continue
        view, history = captured[point]
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
            updates.append({"id": view["id"], "revision": current[point], "patch": True, "add": list(added.values()), "remove": sorted(removed)})
        else:
            updates.append(view)
    return {"add": updates, "remove": [f"{horizontal},{vertical}" for horizontal, vertical in sorted(previous.keys() - captured.keys())]}, current


class StatePublisher:
    def __init__(self, server):
        self.server = server
        self.subscriptions = {}
        self.sequences = {}
        self.frames = {}
        self.roster = None
        self.next_roster = 0.0
        self.generation = 0

    def subscribe(self, player_id, procedural):
        with self.server.world.lock:
            self.generation += 1
            self.subscriptions[player_id] = (procedural, self.generation)
            self.sequences[player_id] = 0
            self.frames.pop(player_id, None)

    def unsubscribe(self, player_id):
        with self.server.world.lock:
            self.subscriptions.pop(player_id, None)
            self.sequences.pop(player_id, None)
            self.frames.pop(player_id, None)

    def publish(self):
        world = self.server.world
        started = time.perf_counter()
        with world.lock:
            captured_at = time.monotonic()
            active = [(identifier, procedural) for identifier, procedural in self.subscriptions.items() if identifier in world.online]
            shared = capture_entities(world) if active else None
            demolitions = world.active_demolitions() if active else ()
            viewers, terrain = {}, {}
            for identifier, (procedural, generation) in active:
                view = world.snapshot_view(identifier, procedural=procedural, demolitions=demolitions)
                view["command_sequence"] = self.sequences.get(identifier, 0)
                chunks = {}
                if procedural:
                    for point in world.terrain_points(identifier):
                        if point not in terrain:
                            terrain[point] = (world.chunk_view(point), tuple(world._chunk_changes.get(point, ())))
                        chunks[point] = terrain[point]
                viewers[identifier] = (view, chunks)
            now = time.monotonic()
            if now >= self.next_roster:
                self.roster = world.player_roster()
                self.next_roster = now + 1
        self.server.observe("publication_capture_ms", (time.perf_counter() - started) * 1000)
        frames = {identifier: (compose_snapshot(shared, view), chunks, captured_at) for identifier, (view, chunks) in viewers.items()}
        with world.lock:
            captured_subscriptions = dict(active)
            self.frames = {identifier: frame for identifier, frame in frames.items() if self.subscriptions.get(identifier) == captured_subscriptions[identifier]}
        self.server.observe("publication_ms", (time.perf_counter() - started) * 1000)

    def snapshot(self, player_id, procedural, previous):
        with self.server.world.lock:
            frame = self.frames.get(player_id)
            if frame is None:
                world = self.server.world
                state = world.snapshot(player_id, procedural=procedural)
                state["command_sequence"] = self.sequences.get(player_id, 0)
                changes, current = world.terrain_updates(player_id, previous) if procedural else ({"add": [], "remove": []}, previous)
                return state, changes, current, time.monotonic()
        state, captured, captured_at = frame
        changes, current = terrain_delta(captured, previous) if procedural else ({"add": [], "remove": []}, previous)
        return state, changes, current, captured_at
