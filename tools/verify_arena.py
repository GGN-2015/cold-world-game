"""Verify combat mechanics, live edits and the shared replay library."""

from contextlib import closing
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from cold_world_game.actions import GameError
from cold_world_game.app import create_app
from cold_world_game.arena.server import create_arena_app
from cold_world_game.arena.simulation import (
    FINISHED_STATUSES,
    WAVES,
    Simulation,
    validate_config,
)
from cold_world_game.constants import GUNS, MELEE_WEAPONS
from cold_world_game.models import Projectile
from cold_world_game.replay_batch import run_document
from cold_world_game.replays import GameplayCapture, ReplayWriter


def complete(fight):
    for _ in range(902):
        if fight.status in FINISHED_STATUSES:
            return fight.snapshot()
        fight.step()
    raise AssertionError("fight exceeded its time limit")


def check_fights():
    for intensity, kinds in WAVES.items():
        config = {"weapon": "handgun", "intensity": intensity}
        with closing(Simulation(config)) as first, closing(Simulation(config)) as second:
            player = first.world.players[first.player_id]
            assert player.inventory[0].ammo == GUNS["handgun"]["ammo"]
            assert all(item is None for item in player.inventory[1:] + player.backpack)
            assert tuple(monster.kind for monster in first.world.monsters.values()) == kinds
            a, b = complete(first), complete(second)
            assert (a["kills"], a["seconds"], a["status"]) == (b["kills"], b["seconds"], b["status"])
            assert a["kills"] + a["alive"] == a["spawned"] == len(kinds)

    try:
        validate_config({"weapon": "storm_smg", "intensity": "low"})
    except GameError as error:
        assert error.code == "arena_config"
    else:
        raise AssertionError("retired weapon accepted")


def check_last_shot():
    with closing(Simulation({"weapon": "handgun", "intensity": "low"})) as fight:
        player = fight.world.players[fight.player_id]
        player.inventory[0].ammo = 1
        next(iter(fight.world.monsters.values())).hp = 2
        fight.step()
        assert player.inventory[0].ammo == 0
        assert fight.status == "running"
        assert complete(fight)["status"] == "cleared"


def check_dodge():
    with closing(Simulation({"weapon": "handgun", "intensity": "low"})) as fight:
        fight.world.monsters.clear()
        shot = Projectile(-2, 0, 8, 0, 16, 1, "monster", hostile=True)
        fight.world.projectiles[shot.id] = shot
        fight.step()
        assert fight.ai.decision == "dodge"
        assert abs(fight.world.controls[fight.player_id].move_y) > .5


def check_history(path):
    replay_dir = path / "replays"
    app = create_arena_app(password="test", replay_dir=replay_dir)
    client = app.test_client()
    library = app.extensions["cold_world_arena"].library
    headers = {"X-Replay-Password": "test"}
    with closing(Simulation({"weapon": "axe", "intensity": "none", "editable": True})) as fight:
        writer = ReplayWriter(library, "arena", "axe", fight.config)
        fight.capture(writer)
        player = fight.world.players[fight.player_id]
        axe = player.inventory[0]
        reach = fight.world.melee_reach(player, axe, MELEE_WEAPONS["axe"])
        commands = (
            {"action": "equip", "storage": "backpack", "kind": "axe_handle", "slot": 0},
            {"action": "player", "hunger": 7, "temperature": 31, "x": 1.0, "y": 0.0},
            {"action": "tile", "kind": "wall", "x": 3, "y": 0},
            {"action": "spawn", "kind": "small", "count": 2},
            {"action": "spawning", "kind": "small", "count": 1, "cap": 3, "interval": .5},
            {"action": "strategy", "strategy": "kite"},
        )
        for command in commands:
            fight.apply(writer, command)
            fight.capture(writer)
        assert fight.world.melee_reach(player, axe, MELEE_WEAPONS["axe"]) > reach
        assert (player.x, player.y, player.hunger, player.temperature) == (1, 0, 7, 31)
        assert fight.world.structure_at(3, 0).kind == "wall"
        assert len(fight.world.monsters) == 2
        fight.step()
        assert fight.world.tick_number == 0
        fight.apply(writer, {"action": "resume"})
        for _ in range(12):
            fight.step()
        assert fight.spawned == 3
        fight.apply(writer, {"action": "clear"})
        fight.apply(writer, {"action": "stop"})
        fight.capture(writer)
        writer.finish(fight.status)
    replay = f"/api/replays/{writer.id}"
    assert client.get(replay).status_code == 403
    assert client.get(replay, headers=headers).json["status"] == "stopped"
    frames = client.get(replay + "/segments/0", headers=headers).json["frames"]
    assert frames[0]["state"] and "changes" in frames[1]
    assert any(note["type"] == "wave" for frame in frames for note in frame.get("notes", []))
    assert client.get("/replay/").status_code == 200
    download = client.get(replay + "/download", headers=headers)
    with download:
        reply = client.post("/api/replays/upload", data={"file": (BytesIO(download.data), "arena.replay")}, headers=headers)
    assert reply.status_code == 201 and reply.json["location"] == "uploads" and reply.json["source"] == "arena"
    assert client.post("/api/replays/upload", data={"file": (BytesIO(b"[]"), "broken.replay")}, headers=headers).status_code == 422
    assert client.get(replay, headers={**headers, "Origin": "https://example.test"}).status_code == 403

    game = create_app(password="test", save_path=path / "save", seed=45, start_engine=False, replay_dir=replay_dir)
    server = game.extensions["cold_world_game"]
    try:
        game_client = game.test_client()
        assert game_client.get("/").status_code == 200
        assert game_client.get("/arena/").status_code == 200
        assert game_client.get("/replay/").status_code == 200
        arena_info = game_client.get("/api/arena/info").json
        assert arena_info["password_required"] and arena_info["max_sessions"] == 4
        assert "guns" in game_client.get("/api/info").json
        assert game_client.get("/api/server").json["arena_websocket"] == "/ws/arena"
        assert game_client.get("/api/replays").status_code == 403
        assert game_client.get(replay, headers=headers).json["source"] == "arena"
        assert game.extensions["cold_world_arena"].library.directory == replay_dir.resolve()
        server.world.join("tester")
        capture = GameplayCapture(library, server.world, "tester")
        record_id = capture.command({"type": "record_start"})["id"]
        capture.capture()
        assert capture.command({"type": "record_stop"})["id"] == record_id
        capture.command({"type": "record_start"})
        capture.disconnect()
        summaries = list(run_document({"name": "Smoke", "runs": [
            {"title": "Move east", "duration": 6, "script": [{"at": 0, "command": {"type": "input", "move": [1, 0]}}]},
            {"title": "Arena edit", "mode": "arena", "weapon": "handgun", "intensity": "none", "duration": 1},
        ]}, library))
        assert summaries[0]["result"]["x"] > 0
        assert len(client.get(f"/api/replays/{summaries[0]['id']}", headers=headers).json["segments"]) == 2
        records = {entry["id"]: entry for entry in game_client.get("/api/replays", headers=headers).json["records"]}
        assert {"arena", "batch", "gameplay", "uploads"} <= {entry["location"] for entry in records.values()}
        assert records[record_id]["status"] == "completed"
        assert any(entry["status"] == "disconnected" for entry in records.values())
    finally:
        server.close()


if __name__ == "__main__":
    check_fights()
    check_last_shot()
    check_dodge()
    with TemporaryDirectory() as temporary:
        check_history(Path(temporary))
    print("Passed arena combat, editing, batch and gameplay captures, and the shared playback/upload API.")
