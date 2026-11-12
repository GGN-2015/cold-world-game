import argparse
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cold_world_game import create_app
from cold_world_game.models import Controls, Monster, Player
from cold_world_game.storage import Storage
from cold_world_game.sync import state_delta


def encoded(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


def summary(values):
    ordered = sorted(values)
    return {"mean_ms": statistics.mean(values), "p95_ms": ordered[min(len(ordered) - 1, int(len(ordered) * .95))], "samples": len(values)}


def benchmark(players, radius, steps):
    with tempfile.TemporaryDirectory(prefix="cold-world-terrain-benchmark-") as folder:
        runtime = create_app(password="benchmark-only", save_path=folder, seed=43, start_engine=False).extensions["cold_world_game"]
        try:
            world = runtime.world
            for horizontal in range(-radius, radius + 1):
                for vertical in range(-radius, radius + 1):
                    world.generate_chunk(horizontal, vertical)
            world.players = {f"benchmark-{index}": Player(f"benchmark-{index}", 0, 0) for index in range(players)}
            world.controls = {identifier: Controls() for identifier in world.players}
            world.online = set(world.players)
            world.monsters = {f"monster-{index}": Monster(index % 10 - 5, index // 10 - 3, id=f"monster-{index}") for index in range(70)}
            world.save_changes()
            world.storage.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            sparse_size = world.storage.path.stat().st_size
            sparse_rows = world.storage.connection.execute("SELECT count(*) FROM world_parts WHERE name LIKE 'structure:%'").fetchone()[0]
            materialized = world.export()
            materialized["terrain_format"] = 0
            materialized.pop("materialized")
            materialized.pop("generation_profiles")
            storage = Storage(Path(folder) / "materialized.sqlite3")
            try:
                storage.save(materialized)
                storage.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                full_size = storage.path.stat().st_size
            finally:
                storage.close()
            previous = {False: {}, True: {}}
            subscriptions = {}
            samples = {False: [], True: []}
            wire = {False: 0, True: 0}
            terrain_wire = {False: 0, True: 0}
            travel = min(90, (radius - 3) * 15)
            for step in range(steps):
                world.elapsed = step * .1
                for index, player in enumerate(world.players.values()):
                    player.x = -travel + step * travel * 2 / max(1, steps - 1)
                    player.y = (index % 4 - 1.5) * 8
                    for procedural in ((False, True) if step % 2 else (True, False)):
                        began = time.perf_counter()
                        state = world.snapshot(player.id, procedural=procedural)
                        message = state_delta(previous[procedural][player.id], state, step) if player.id in previous[procedural] else {"type": "welcome", "state": state}
                        if procedural:
                            changes, subscriptions[player.id] = world.terrain_updates(player.id, subscriptions.get(player.id, {}))
                            if changes["add"] or changes["remove"]:
                                message["terrain"] = changes
                            if step == 0:
                                message["terrain_config"] = world.terrain_bootstrap()
                            terrain_size = encoded(changes) if changes["add"] or changes["remove"] else 0
                            if step == 0:
                                terrain_size += encoded(message["terrain_config"])
                        else:
                            structures = message.get("entities", {}).get("structures", {}) if step else state["structures"]
                            terrain_size = encoded(structures) if structures else 0
                        size = encoded(message)
                        samples[procedural].append((time.perf_counter() - began) * 1000)
                        wire[procedural] += size
                        terrain_wire[procedural] += terrain_size
                        previous[procedural][player.id] = state
            return {
                "scenario": {"players": players, "monsters": 70, "chunks": len(world.chunks), "structures": len(world.structures), "steps": steps, "route_meters": travel * 2, "seed": 43},
                "materialized": {**summary(samples[False]), "wire_bytes": wire[False], "terrain_bytes": terrain_wire[False], "database_bytes": full_size},
                "procedural": {**summary(samples[True]), "wire_bytes": wire[True], "terrain_bytes": terrain_wire[True], "database_bytes": sparse_size, "structure_rows": sparse_rows},
                "scope": "Serial snapshot, delta and JSON processing replay on identical terrain; not a browser FPS or network latency test. Both paths exclude world-lock queueing.",
            }
        finally:
            runtime.close()


def main():
    parser = argparse.ArgumentParser(description="Compare both terrain protocols on a disposable deterministic world.")
    parser.add_argument("--players", type=int, default=16, choices=range(1, 65), metavar="1..64")
    parser.add_argument("--radius", type=int, default=20, choices=range(8, 41), metavar="8..40")
    parser.add_argument("--steps", type=int, default=120, choices=range(2, 1001), metavar="2..1000")
    arguments = parser.parse_args()
    print(json.dumps(benchmark(arguments.players, arguments.radius, arguments.steps), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
