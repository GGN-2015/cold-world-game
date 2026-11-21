"""Run authored replay scenarios in an isolated, authoritative world."""

import argparse
import importlib
import json
import math
from itertools import count
from pathlib import Path

from .actions import GameError
from .arena.simulation import FINISHED_STATUSES, ArenaStorage, Simulation, number
from .constants import TICK_RATE
from .models import identifier_scope
from .replays import ReplayLibrary, ReplayWriter
from .world import World

PLAYER_ID = "batch-ai"
COMMANDS = frozenset({"input", "stop", "attack", "reload", "select", "open", "close", "take_all", "transfer",
                      "craft", "copy_scroll", "trade", "bank", "place", "drop", "toggle_door", "sit", "light",
                      "sort_backpack", "dismantle_container", "ui"})


class BatchWorld(World):
    """Expire input in simulation time, matching the live game's one-second timeout."""

    last_input_tick = -2 * TICK_RATE

    def input_expired(self, controls):
        return self.tick_number - self.last_input_tick > TICK_RATE

    def action(self, player, controls, command):
        result = super().action(player, controls, command)
        if command["type"] in ("input", "attack"):
            self.last_input_tick = self.tick_number
        return result


def configure_parser(parser):
    parser.add_argument("scenarios", type=Path, help="JSON batch description")
    parser.add_argument("--replay-dir", help="Shared replay library (default: replays/library)")


def load_policy(reference):
    if not isinstance(reference, str) or ":" not in reference:
        raise ValueError("policy must identify a local Python module:function")
    module, function = reference.rsplit(":", 1)
    policy = getattr(importlib.import_module(module), function)
    if not callable(policy):
        raise TypeError("policy must be callable")
    return policy


def validate_schedule(value, duration):
    if not isinstance(value, list):
        raise TypeError("script must be an array")
    schedule = []
    for entry in value:
        if not isinstance(entry, dict) or not isinstance(entry.get("command"), dict):
            raise TypeError("Each script entry must contain a command object")
        at = number(entry.get("at"), 0, duration)
        reason = entry.get("reason", "")
        if not isinstance(reason, str):
            raise TypeError("Script reason must be a string")
        schedule.append((math.ceil(at * TICK_RATE - 1e-9), entry["command"], reason))
    return sorted(schedule, key=lambda item: item[0])


def command_result(world, writer, command, reason):
    kind = command.get("type")
    note = {"type": "operation", "tick": world.tick_number, "command": command, "reason": reason}
    try:
        if not isinstance(kind, str) or kind not in COMMANDS:
            raise GameError("unknown_command", "Command is unavailable in batch scenarios")
        result = world.execute(PLAYER_ID, command)
        note.update(result=result, accepted=not isinstance(result, dict) or result.get("accepted") is not False)
    except GameError as error:
        note.update(accepted=False, error=error.code)
    writer.note(note)
    return {key: value for key, value in note.items() if key in {"command", "result", "accepted", "error"}}


def survival(config, writer, schedule):
    identifiers = count(1)
    seed = config["seed"]
    policy = load_policy(config["policy"]) if config.get("policy") else None
    every = max(1, round(number(config.get("policy_every", .25), .05, 60) * TICK_RATE))
    if type(config.get("stop_on_downed", True)) is not bool:
        raise ValueError("stop_on_downed must be true or false")
    with identifier_scope(lambda: f"batch:{next(identifiers)}"):
        world = BatchWorld(ArenaStorage(), seed=seed)
        world.next_save = math.inf
        last_results = []
        commands = failures = 0
        try:
            world.join(PLAYER_ID)
            position = 0
            limit = config["duration"] * TICK_RATE
            while True:
                tick = world.tick_number
                stop = tick == limit or config.get("stop_on_downed", True) and world.players[PLAYER_ID].temperature < 5
                outputs = []
                while position < len(schedule) and schedule[position][0] <= tick:
                    _, command, reason = schedule[position]
                    outputs.append((command, reason))
                    position += 1
                if policy and not stop and tick % every == 0:
                    items = policy({"seconds": tick / TICK_RATE, "state": world.snapshot(PLAYER_ID),
                                    "previous_results": last_results})
                    if not isinstance(items, (tuple, list)) or len(items) > 32:
                        raise ValueError("Policy must return at most 32 commands per call")
                    for item in items:
                        if not isinstance(item, dict) or not isinstance(item.get("command"), dict) or not isinstance(item.get("reason", ""), str):
                            raise TypeError("Policy entries must contain a command object and optional reason")
                        outputs.append((item["command"], item.get("reason", "")))
                if outputs:
                    last_results = [command_result(world, writer, command, reason) for command, reason in outputs]
                    commands += len(last_results)
                    failures += sum(not result["accepted"] for result in last_results)
                player = world.players[PLAYER_ID]
                if tick % 4 == 0 or stop or outputs:
                    controls = world.controls[PLAYER_ID]
                    writer.append(tick / TICK_RATE, world.snapshot(PLAYER_ID), aim=[controls.aim_x, controls.aim_y])
                if stop:
                    return ("downed" if player.temperature < 5 else "completed",
                            {"commands": commands, "rejected": failures, "x": round(player.x, 2), "y": round(player.y, 2),
                             "distance": round(math.hypot(player.x, player.y), 2), "temperature": player.temperature,
                             "hunger": player.hunger})
                world.tick(1 / TICK_RATE)
        finally:
            world.close(save=False)


def trial(config, writer, schedule):
    trial_config = {key: config[key] for key in ("seed", "duration", "weapon", "intensity", "strategy", "terrain", "setup") if key in config}
    fight = Simulation({**trial_config, "editable": True})
    fight.control({"action": "resume"})
    position = 0
    try:
        fight.capture(writer)
        if fight.config["setup"]:
            fight.restore_opening(writer)
            fight.capture(writer)
        while fight.status == "running":
            while position < len(schedule) and schedule[position][0] <= fight.world.tick_number:
                _, command, reason = schedule[position]
                position += 1
                if reason:
                    writer.note({"type": "decision", "decision": reason})
                try:
                    fight.apply(writer, command)
                except GameError:
                    pass
                fight.capture(writer)
                if fight.status in FINISHED_STATUSES:
                    break
            if fight.status == "running":
                fight.step()
                if fight.world.tick_number % 4 == 0 or fight.status != "running":
                    fight.capture(writer)
        return ("downed" if fight.status == "paused" and fight.world.players[fight.player_id].temperature < 5 else fight.status,
                {"kills": fight.kills, "spawned": fight.spawned})
    finally:
        fight.close()


def run_document(document, library):
    if not isinstance(document, dict) or not isinstance(document.get("runs"), list) or not document["runs"]:
        raise ValueError("Batch JSON must contain a nonempty runs array")
    name = document.get("name", "Batch")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Batch name must be text")
    for index, entry in enumerate(document["runs"], 1):
        if not isinstance(entry, dict):
            raise TypeError("Each run must be an object")
        mode, title = entry.get("mode", "survival"), entry.get("title", f"Run {index}")
        if mode not in ("arena", "survival") or not isinstance(title, str) or not title.strip():
            raise ValueError("A run needs a title and a supported mode")
        duration = number(entry.get("duration", 45), 1, 3600 if mode == "arena" else 28800, integer=True)
        seed = number(entry.get("seed", 45), 0, 2 ** 32 - 1, integer=True)
        schedule = validate_schedule(entry.get("script", []), duration)
        config = {**entry, "mode": mode, "duration": duration, "seed": seed, "batch": name}
        writer = ReplayWriter(library, "batch", title, config)
        try:
            status, result = (trial if mode == "arena" else survival)(config, writer, schedule)
            writer.finish(status, **result)
        except BaseException:
            writer.discard()
            raise
        yield {"id": writer.id, "title": title, "status": status, "result": result, "path": str(writer.path)}


def run(options, parser: argparse.ArgumentParser):
    try:
        document = json.loads(options.scenarios.read_text(encoding="utf-8-sig"))
        for result in run_document(document, ReplayLibrary(options.replay_dir)):
            print(json.dumps(result, ensure_ascii=True), flush=True)
    except (GameError, OSError, ValueError, TypeError, ImportError, AttributeError) as error:
        parser.exit(1, f"Batch failed: {error}\n")
    return 0
