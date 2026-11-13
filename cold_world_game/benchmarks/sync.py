import base64
import json
import math
from pathlib import Path
import statistics
import tempfile
import time

from cold_world_game import create_app
from cold_world_game.models import Controls, Item, Monster, Player
from cold_world_game.sync import state_delta
from cold_world_game.wire import CompactSync


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def summary(values):
    ordered = sorted(values)
    return {"mean_ms": statistics.mean(values), "p95_ms": ordered[min(len(ordered) - 1, int(len(ordered) * .95))], "samples": len(values)}


def benchmark(players=16, radius=20, frames=300, capture_path=None):
    with tempfile.TemporaryDirectory(prefix="cold-world-sync-benchmark-") as folder:
        runtime = create_app(password="benchmark-only", save_path=folder, seed=43, start_engine=False).extensions["cold_world_game"]
        try:
            world = runtime.world
            for horizontal in range(-radius, radius + 1):
                for vertical in range(-radius, radius + 1):
                    world.generate_chunk(horizontal, vertical)
            with world.transaction():
                world.touch()
                for structure in list(world.structures.values()):
                    if abs(structure.x) < 23 and abs(structure.y) < 23:
                        world.remove_structure(structure)
            world.players = {f"benchmark-{index}": Player(f"benchmark-{index}", (index % 4 - 1.5) * 4, (index // 4 - 1.5) * 4) for index in range(players)}
            world.controls = {identifier: Controls() for identifier in world.players}
            world.online = set(world.players)
            for index, player in enumerate(world.players.values()):
                player.inventory = [Item.create("rifle" if index % 2 == 0 else "axe"), Item.create("axe")] + [Item.create("fence" if slot % 2 == 0 else "wall") for slot in range(8)]
                if player.inventory[0].ammo is not None:
                    player.inventory[0].ammo = 10000
            population = 0

            def populate():
                nonlocal population
                while len(world.monsters) < 70:
                    index = population
                    population += 1
                    angle, reach = index * 2.3999632297, 9 + index % 6
                    monster = Monster(math.cos(angle) * reach, math.sin(angle) * reach, id=f"m:{index}", big=index % 10 == 0, fast=index % 10 == 1, hp=50 if index % 10 == 0 else 10)
                    world.monsters[monster.id] = monster

            world.spawn_monster = populate
            populate()
            compact = {identifier: CompactSync() for identifier in world.players}
            previous = {}
            subscriptions = {}
            wire = {"json_delta": 0, "compact": 0}
            samples = {name: [] for name in wire}
            capture = {"messages": []}
            for frame in range(frames):
                for player in world.players.values():
                    controls = world.controls[player.id]
                    controls.last_input = time.monotonic()
                    controls.held = controls.pending_shot = True
                    target = min(world.monsters.values(), key=lambda monster: (monster.x - player.x) ** 2 + (monster.y - player.y) ** 2)
                    controls.aim_x, controls.aim_y = target.x, target.y
                    player.temperature = max(16, player.temperature)
                world.tick(.05)
                if frame % 2:
                    continue
                for identifier in world.players:
                    state = world.snapshot(identifier, procedural=True)
                    terrain, subscriptions[identifier] = world.terrain_updates(identifier, subscriptions.get(identifier, {}))
                    channel = compact[identifier]
                    if identifier not in previous:
                        roster = world.player_roster()
                        message = {"type": "welcome", "state_revision": 0, "state": state, "terrain": terrain, "terrain_config": world.terrain_bootstrap(), "roster": roster}
                        wire["json_delta"] += len(json_bytes(message))
                        message = {**message, "state": channel.welcome(state), "wire_config": channel.encoder.config(), "roster": channel.reset_roster(roster)}
                        wire["compact"] += len(json_bytes(message))
                        if identifier == "benchmark-0":
                            capture["welcome"] = message
                    else:
                        for mode in (("json_delta", "compact") if frame % 4 else ("compact", "json_delta")):
                            began = time.perf_counter()
                            message = state_delta(previous[identifier], state, frame // 2 - 1) if mode == "json_delta" else channel.delta(state)
                            if terrain["add"] or terrain["remove"]:
                                message["terrain"] = terrain
                            encoded = json_bytes(message) if mode == "json_delta" else channel.encoder.encode(message)
                            samples[mode].append((time.perf_counter() - began) * 1000)
                            wire[mode] += len(encoded)
                            if capture_path and mode == "compact" and identifier == "benchmark-0":
                                capture["messages"].append({"binary": base64.b64encode(encoded).decode(), "message": message, "projectiles": state["projectiles"]})
                    previous[identifier] = state
                    if frame and frame % 20 == 0:
                        roster = world.player_roster()
                        wire["json_delta"] += len(json_bytes({"type": "roster", **roster}))
                        delta = channel.roster_delta(roster)
                        if delta:
                            encoded = channel.encoder.encode(delta)
                            wire["compact"] += len(encoded)
                            if capture_path and identifier == "benchmark-0":
                                capture["messages"].append({"binary": base64.b64encode(encoded).decode(), "message": delta})
            if capture_path:
                Path(capture_path).write_text(json.dumps(capture, ensure_ascii=False), encoding="utf-8")
            return {
                "scenario": {"players": players, "monsters": 70, "chunks": len(world.chunks), "structures": len(world.structures), "frames": frames, "game_seconds": frames * .05, "seed": 43},
                **{name: {**summary(samples[name]), "wire_bytes": wire[name]} for name in wire},
                "scope": "Identical authoritative combat frames, paired per-client protocol encoding; includes welcome, terrain and roster. Excludes snapshot construction, lock queueing, browser rendering, TCP and TLS. Fixture replenishes monsters, ammunition and warmth for sustained load.",
            }
        finally:
            runtime.close()


def configure_parser(parser):
    parser.add_argument("--players", type=int, default=16, choices=range(1, 65), metavar="1..64")
    parser.add_argument("--radius", type=int, default=20, choices=range(8, 41), metavar="8..40")
    parser.add_argument("--frames", type=int, default=300, choices=range(40, 1201), metavar="40..1200")
    parser.add_argument("--capture", type=Path)


def run(arguments, command):
    print(json.dumps(benchmark(arguments.players, arguments.radius, arguments.frames, arguments.capture), ensure_ascii=False, indent=2))
    return 0
