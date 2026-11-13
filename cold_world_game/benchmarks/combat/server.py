import hmac
import json
import logging
import math
from pathlib import Path
import platform
import random
import threading
import time

from flask import abort, jsonify, request
import psutil
from werkzeug.serving import make_server

from cold_world_game import create_app
from cold_world_game.constants import BODY_RADIUS, MONSTER_SPAWN_CHANCES, MONSTER_XRAY_CHANCE
from cold_world_game.geometry import distance
from cold_world_game.models import Item, Monster, Player, Structure
from cold_world_game.wildlife import MONSTER_TYPES
from cold_world_game.wire import CompactSync, WireEncoder

from .metrics import Recorder, TimedLock, timed
from .control import formation, player_position


class Fixture:
    def __init__(self, world, config, recorder):
        self.world = world
        self.config = config
        self.recorder = recorder
        self.target = 0
        self.phase = 0
        self.started = time.monotonic()
        self.scenario = "open"
        self.population = 0
        self.waiting = {}
        self.cells = []
        self.cursor = 0
        self.random = random.Random(config["seed"])

    def center(self):
        return 60 * math.sin((time.monotonic() - self.started) / 90) if self.scenario == "march" else 0

    def reset(self, target, scenario):
        world = self.world
        self.target, self.scenario = target, scenario
        self.started = time.monotonic()
        self.phase += 1
        self.population = 0
        self.waiting.clear()
        self.random = random.Random(f'{self.config["seed"]}:{scenario}:{target}')
        spacing = BODY_RADIUS * 2 + .02
        self.cells = [(horizontal * spacing, vertical * spacing) for horizontal in range(-17, 18) for vertical in range(-9, 10) if math.hypot(horizontal * spacing, vertical * spacing) >= 3]
        self.random.shuffle(self.cells)
        self.cursor = 0
        with world.lock, world.transaction():
            world.touch()
            for structure in list(world.structures.values()):
                if abs(structure.x) <= 95 and abs(structure.y) <= 12:
                    world.remove_structure(structure)
            if scenario == "obstacles":
                for horizontal in (-8, -4, 4, 8):
                    for vertical in range(-7, 8):
                        if vertical not in (-3, 0, 3):
                            world.add_structure(Structure("fence" if vertical % 3 == 0 else "wall", horizontal, vertical))
            world.monsters.clear()
            world.projectiles.clear()
            world.ground.clear()
            world.shot_hits.clear()
            world.shot_impacts.clear()
            world._path_jobs.clear()
            world._path_queue.clear()
            world._velocities.clear()
            effects = ("axe", "rifle", "flame_staff", "shotgun", "ice_staff", "homing_missile", "coin_launcher", "rifle")
            for index in range(self.config["players"]):
                player = world.players[f"bench-{index:02d}"]
                player.x, player.y = player_position(index)
                player.temperature, player.hunger, player.money = 36, 10, 10000
                weapon = effects[index % len(effects)] if scenario == "effects" else "axe" if index % 2 == 0 else "rifle"
                player.inventory = [Item.create(weapon), Item.create("axe"), Item.create("rifle")] + [None] * 5 + [Item.create("fence"), Item.create("wood")]
                player.backpack = [None] * 30
                player.selected = 0
                if player.id in world.controls:
                    controls = world.controls[player.id]
                    controls.stop_attack()
                    controls.ui = False
                    controls.container = None
                    controls.seat = None
                    controls.move_x = controls.move_y = controls.velocity_x = controls.velocity_y = 0
                    controls.aim_target = None
                    controls.movement_epoch += 1
                    controls.teleport_epoch += 1
            self.sustain(initial=True)

    def sustain(self, initial=False):
        world = self.world
        started = time.perf_counter()
        for player in world.players.values():
            if player.temperature < 16 or player.hunger < 2:
                world.touch()
                player.temperature, player.hunger = 36, 10
                self.recorder.count("fixture_heals")
            for item in player.inventory:
                if item and item.ammo is not None and item.ammo < 50:
                    world.touch()
                    item.ammo = 10000
                if item and item.uses is not None and item.uses < 10:
                    world.touch()
                    item.uses = 1000
            if player.money < 20:
                world.touch()
                player.money = 10000
            if player.inventory[8] is None:
                world.touch()
                player.inventory[8] = Item.create("fence")
        center = self.center()
        for identifier, monster in list(world.monsters.items()):
            if abs(monster.x - center) > 22 or abs(monster.y) > 12:
                world.touch()
                world.monsters.pop(identifier)
                world._path_jobs.pop(identifier, None)
                self.recorder.count("fixture_retired_monsters")
        attempts = len(self.cells) * 3 if initial else min(128, max(32, (self.target - len(world.monsters)) * 4))
        chances = MONSTER_SPAWN_CHANCES["night"]
        for attempt in range(attempts if self.cells else 0):
            if len(world.monsters) >= self.target:
                break
            offset_x, offset_y = self.cells[self.cursor % len(self.cells)]
            self.cursor += 1
            position_x, position_y = center + offset_x, offset_y
            if not world.can_stand(position_x, position_y, monster_id="benchmark-spawn"):
                continue
            species = self.random.choices(list(chances), weights=list(chances.values()))[0]
            self.population += 1
            monster = Monster(position_x, position_y, id=f"benchm:{self.phase}:{self.population}", big=species == "big", fast=species == "fast", species=species if species not in {"big", "fast"} else "small", hp=MONSTER_TYPES[species]["hp"], xray=self.random.random() < MONSTER_XRAY_CHANCE)
            world.touch()
            world.monsters[monster.id] = monster
            self.recorder.count("fixture_spawned_monsters")
        now = time.monotonic()
        for identifier in list(self.waiting):
            monster = world.monsters.get(identifier)
            if monster is None or monster.target is None or monster.demolition:
                self.waiting.pop(identifier)
            elif monster.path or monster.next_plan > world.elapsed:
                self.recorder.observe("pathless_wait_ms", (now - self.waiting.pop(identifier)) * 1000)
        for monster in world.monsters.values():
            target = world.players.get(monster.target)
            if target and not monster.path and not monster.demolition and distance(monster, target) > 1.2 and monster.next_plan <= world.elapsed:
                self.waiting.setdefault(monster.id, now)
        self.recorder.observe("population", len(world.monsters))
        self.recorder.observe("standing_online", sum(world.players[identifier].temperature >= 5 for identifier in world.online))
        formation_errors = []
        for index in range(self.config["players"]):
            player = world.players[f"bench-{index:02d}"]
            goal = formation(index, self.scenario, now - self.started)
            formation_errors.append(math.hypot(player.x - goal[0], player.y - goal[1]))
        self.recorder.observe("formation_error_max_m", max(formation_errors, default=0))
        self.recorder.observe("fixture_ms", (time.perf_counter() - started) * 1000)


def run_worker(config_path):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app = create_app(password=config["password"], save_path=config["save_path"], seed=config["seed"], start_engine=False)
    runtime = app.extensions["cold_world_game"]
    world = runtime.world
    recorder = Recorder()
    runtime.observe = recorder.observe
    world.lock = TimedLock(world.lock, recorder)
    fixture = Fixture(world, config, recorder)
    for horizontal in range(-config["radius"], config["radius"] + 1):
        for vertical in range(-config["radius"], config["radius"] + 1):
            world.generate_chunk(horizontal, vertical)
    world.elapsed = 21 * 60
    for index in range(config["players"]):
        identifier = f"bench-{index:02d}"
        world.players[identifier] = Player(identifier, *player_position(index))
    world.save_changes()
    fixture.reset(0, "open")
    world.spawn_monster = fixture.sustain
    world.monster_activity = lambda: (False, None)
    original_event = world.emit_event

    def event(kind, *arguments, **keywords):
        recorder.count("event_" + kind)
        if kind == "hurt" and keywords.get("source") in world.players:
            recorder.count("friendly_fire_hits")
        return original_event(kind, *arguments, **keywords)

    world.emit_event = event
    for name in ("update_monsters", "update_projectiles", "update_burning", "save_changes", "snapshot", "export_metadata"):
        timed(world, name, recorder)
    timed(world.storage, "save", recorder, "sqlite_save_ms")
    timed(runtime, "execute", recorder, "command_ms")
    timed(CompactSync, "delta", recorder, "delta_ms")
    timed(WireEncoder, "encode", recorder, "encode_ms")
    timed(world, "tick", recorder, "tick_ms")
    measured_tick = world.tick

    def tick(seconds):
        measured_tick(seconds)
        recorder.tick()

    world.tick = tick
    process = psutil.Process()
    process.cpu_percent()
    http = make_server("127.0.0.1", 0, app, threaded=True)
    http.daemon_threads = True

    @app.before_request
    def protect_control():
        if request.path.startswith("/__benchmark/") and not hmac.compare_digest(request.headers.get("X-Benchmark-Token", ""), config["token"]):
            abort(403)

    @app.post("/__benchmark/reset")
    def reset():
        recorder.active = False
        values = request.get_json()
        fixture.reset(values["target"], values["scenario"])
        return jsonify(ok=True, target=fixture.target, center=fixture.center(), started=fixture.started, epochs={identifier: controls.teleport_epoch for identifier, controls in world.controls.items()})

    @app.post("/__benchmark/measure")
    def measure():
        with world.lock:
            recorder.active = False
            recorder.reset()
            fixture.waiting.clear()
            recorder.active = True
            process.cpu_percent()
        return jsonify(ok=True)

    @app.post("/__benchmark/stop-measure")
    def stop_measure():
        with world.lock:
            recorder.stop()
        return jsonify(ok=True)

    @app.get("/__benchmark/stats")
    def stats():
        cpu = process.cpu_percent()
        rss = process.memory_info().rss / 1024 ** 2
        recorder.observe("process_cpu_percent", cpu)
        recorder.observe("rss_mib", rss)
        persistence = runtime.persistence.status() if runtime.persistence else {"mode": "synchronous"}
        recorder.observe("unsaved_age_seconds", persistence.get("unsaved_seconds", 0))
        recorder.observe("save_failures", persistence.get("failures", 0))
        with world.lock:
            details = {"online": len(world.online), "fault": world.fault, "population": len(world.monsters), "structures": len(world.structures), "chunks": len(world.chunks), "center": fixture.center(), "path_jobs": len(world._path_jobs), "oldest_pathless_wait_ms": max(((time.monotonic() - since) * 1000 for since in fixture.waiting.values()), default=0), "database_bytes": sum(path.stat().st_size for path in world.storage.path.parent.glob("world.sqlite3*") if path.is_file())}
        return jsonify(**details, persistence=persistence, metrics=recorder.report(), cpu_percent=cpu, rss_mib=rss)

    @app.post("/__benchmark/shutdown")
    def shutdown():
        threading.Thread(target=http.shutdown, daemon=True).start()
        return jsonify(ok=True)

    ready = {"port": http.server_port, "seed": world.seed, "chunks": len(world.chunks), "structures": len(world.structures), "python": platform.python_version(), "platform": platform.platform(), "cpu": platform.processor(), "logical_cpus": psutil.cpu_count(), "memory_mib": psutil.virtual_memory().total / 1024 ** 2}
    runtime.start()
    ready["persistence"] = runtime.persistence.status()
    ready["state_publication_hz"] = 10
    Path(config["ready_path"]).write_text(json.dumps(ready), encoding="utf-8")
    try:
        http.serve_forever(poll_interval=.1)
    finally:
        http.server_close()
        runtime.close()
