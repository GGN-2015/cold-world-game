"""Portable replay archives and their shared server-side library."""

import gzip
import json
import logging
import math
import re
import shutil
import sqlite3
import uuid
import zlib
from contextlib import closing
from datetime import UTC, datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from .actions import GameError
from .constants import ITEM_CATALOG_VERSION, TERRAIN_VERSION

FORMAT = "cold-world-replay/2"
SEGMENT_SECONDS = 5
SOURCES = ("arena", "gameplay", "batch", "uploads")
MAX_UPLOAD = 128 * 1024 * 1024
MAX_SEGMENT_BYTES = 32 * 1024 * 1024
DEFAULT_DIRECTORY = Path("replays/library")
ID = re.compile(r"[a-f0-9]{32}")
LOGGER = logging.getLogger(__name__)


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def decode(archive, member, maximum):
    entry = archive.getinfo(member)
    if entry.file_size > maximum:
        raise ValueError("Replay entry is too large")
    return json.loads(archive.read(entry))


def valid_position(value):
    return type(value) in (int, float) and -1_000_000 <= value <= 1_000_000


def read_manifest(archive):
    meta = decode(archive, "manifest.json", 4 * 1024 * 1024)
    if (not isinstance(meta, dict) or meta.get("format") != FORMAT
            or type(meta.get("item_catalog_version")) is not int
            or not isinstance(meta.get("title"), str) or len(meta["title"]) > 160
            or not isinstance(meta.get("created_at"), str) or len(meta["created_at"]) > 40
            or not isinstance(meta.get("configuration"), dict)
            or meta.get("source") not in SOURCES or not isinstance(meta.get("segments"), list)
            or not meta["segments"] or len(meta["segments"]) > 20000
            or not isinstance(meta.get("duration"), (float, int)) or not math.isfinite(meta["duration"]) or meta["duration"] < 0):
        raise ValueError("Unsupported replay manifest")
    previous_end = -1
    for number, item in enumerate(meta["segments"]):
        if (not isinstance(item, dict) or item.get("number") != number
                or type(item.get("count")) is not int or not 1 <= item["count"] <= 500
                or not isinstance(item.get("start"), (int, float)) or not math.isfinite(item["start"])
                or not isinstance(item.get("end"), (int, float)) or not math.isfinite(item["end"])
                or not previous_end < item["start"] <= item["end"] <= meta["duration"]):
            raise ValueError("Invalid segment index")
        previous_end = item["end"]
    return meta


def segment_name(number):
    return f"frames/{number:05d}.json"


def read_segment(archive, entry):
    segment = decode(archive, segment_name(entry["number"]), MAX_SEGMENT_BYTES)
    if (not isinstance(segment, dict) or not isinstance(segment.get("terrain"), list)
            or not isinstance(segment.get("frames"), list) or len(segment["frames"]) != entry["count"]):
        raise ValueError("Invalid replay segment")
    previous = -1
    state = None
    for frame in segment["frames"]:
        if isinstance(frame, dict) and isinstance(frame.get("state"), dict):
            state = frame["state"]
        elif isinstance(frame, dict) and state is not None and isinstance(frame.get("changes"), dict):
            state = {**state, **frame["changes"]}
        else:
            raise ValueError("Missing replay snapshot")
        seconds = frame.get("seconds") if isinstance(frame, dict) else None
        terrain = frame.get("terrain") if isinstance(frame, dict) else None
        if (not isinstance(seconds, (int, float)) or not math.isfinite(seconds)
                or not previous < seconds <= entry["end"] or seconds < entry["start"]
                or type(terrain) is not int or not 0 <= terrain < len(segment["terrain"])
                or not isinstance(segment["terrain"][terrain], list) or not isinstance(state, dict)
                or not isinstance(state.get("you"), dict) or not isinstance(state.get("environment"), dict)
                or not isinstance(state.get("elapsed"), (int, float)) or not math.isfinite(state["elapsed"])
                or any(not isinstance(state.get(key), list) for key in ("players", "monsters", "projectiles", "ground", "events"))):
            raise ValueError("Invalid replay frame")
        if any(not valid_position(state["you"].get(key)) for key in ("x", "y")):
            raise ValueError("Invalid player position")
        previous = seconds
    if segment["frames"][0]["seconds"] != entry["start"] or previous != entry["end"]:
        raise ValueError("Invalid replay timestamps")
    return segment


class ReplayWriter:
    def __init__(self, library, source, title, configuration=None, *, identifier=None, created_at=None):
        from . import __version__

        self.id = identifier or uuid.uuid4().hex
        self.path = library.directory / source / f"{self.id}.replay"
        self.temporary = self.path.with_suffix(f".{uuid.uuid4().hex}.partial")
        self.archive = ZipFile(self.temporary, "w", compression=ZIP_DEFLATED, compresslevel=3)
        self.meta = {"format": FORMAT, "id": self.id, "source": source, "title": title[:160],
                     "created_at": created_at or datetime.now(UTC).isoformat(),
                     "game_version": __version__, "item_catalog_version": ITEM_CATALOG_VERSION, "terrain_version": TERRAIN_VERSION,
                     "configuration": configuration or {}, "segments": []}
        self.frames = []
        self.terrain = []
        self.pending = []
        self.latest = -1
        self.previous = None
        self.facings = {}

    def note(self, note):
        self.pending.append(note)

    def append(self, seconds, state, **metadata):
        if seconds <= self.latest:
            if not self.pending:
                return
            seconds = round(self.latest + .001, 6)
        if self.frames and (seconds - self.segment_start >= SEGMENT_SECONDS or len(self.frames) >= 500):
            self.flush()
        world = {name: value for name, value in state.items()
                 if name not in {"structures", "interaction_target", "terrain_geometry", "movement"}}
        world["you"] = {name: value for name, value in state["you"].items()
                        if name not in {"is_admin", "last_login_at", "offline_since"}}
        facings = self.facings
        self.facings = {}
        for group in ("players", "monsters"):
            world[group] = []
            for entity in state[group]:
                old_x, old_y, direction = facings.get(entity["id"], (entity["x"], entity["y"], "down"))
                dx = entity.get("velocity_x", entity["x"] - old_x)
                dy = entity.get("velocity_y", entity["y"] - old_y)
                if max(abs(dx), abs(dy)) > 1e-5 and not entity.get("downed") and not entity.get("sleeping"):
                    direction = ("left" if dx < 0 else "right") if abs(dx) > abs(dy) else ("up" if dy < 0 else "down")
                direction = entity.get("facing", direction)
                world[group].append({**entity, "facing": direction})
                self.facings[entity["id"]] = entity["x"], entity["y"], direction
        structures = dumps(state["structures"])
        if not self.terrain or self.terrain[-1] != structures:
            self.terrain.append(structures)
        frame = {"seconds": seconds, "terrain": len(self.terrain) - 1, **metadata}
        if self.previous is None or self.previous.keys() != world.keys():
            frame["state"] = world
        else:
            frame["changes"] = {key: value for key, value in world.items() if self.previous[key] != value}
        self.previous = world
        if self.pending:
            frame["notes"] = self.pending
            self.pending = []
        self.frames.append(dumps(frame))
        # Keep the time bound separately from serialized snapshots.
        if len(self.frames) == 1:
            self.segment_start = seconds
        self.latest = seconds

    def flush(self):
        if not self.frames:
            return
        number = len(self.meta["segments"])
        payload = '{"terrain":[' + ",".join(self.terrain) + '],"frames":[' + ",".join(self.frames) + "]}"
        self.archive.writestr(segment_name(number), payload)
        self.meta["segments"].append({"number": number, "start": self.segment_start,
                                      "end": self.latest, "count": len(self.frames)})
        self.frames.clear()
        self.terrain.clear()
        self.previous = None

    def discard(self):
        try:
            if self.archive is not None:
                self.archive.close()
        finally:
            self.archive = None
            self.temporary.unlink(missing_ok=True)

    def finish(self, status, **result):
        if self.archive is None:
            return
        archive = self.archive
        try:
            self.flush()
            if self.meta["segments"]:
                self.meta.update(status=status, duration=self.latest, result=result)
                archive.writestr("manifest.json", dumps(self.meta))
            archive.close()
            if self.meta["segments"]:
                self.temporary.replace(self.path)
            else:
                self.temporary.unlink(missing_ok=True)
        except BaseException:
            archive.close()
            self.temporary.unlink(missing_ok=True)
            raise
        finally:
            self.archive = None


class ReplayLibrary:
    def __init__(self, directory=None):
        self.directory = Path(directory or DEFAULT_DIRECTORY).expanduser().resolve()
        for source in SOURCES:
            (self.directory / source).mkdir(parents=True, exist_ok=True)

    def path(self, identifier):
        if not ID.fullmatch(identifier):
            raise FileNotFoundError(identifier)
        for source in SOURCES:
            path = self.directory / source / f"{identifier}.replay"
            if path.is_file():
                return path
        raise FileNotFoundError(identifier)

    @staticmethod
    def metadata(path):
        with ZipFile(path) as archive:
            return {**read_manifest(archive), "id": path.stem, "location": path.parent.name}

    def list(self):
        entries = []
        for source in SOURCES:
            for path in (self.directory / source).glob("*.replay"):
                if not ID.fullmatch(path.stem):
                    continue
                try:
                    entries.append(self.metadata(path))
                except (OSError, ValueError, KeyError, BadZipFile):
                    LOGGER.warning("Skipping unreadable replay %s", path.name)
        return sorted(entries, key=lambda item: (item["created_at"], item["id"]), reverse=True)

    def upload(self, stream, filename):
        identifier = uuid.uuid4().hex
        temporary = self.directory / "uploads" / f".{identifier}.upload"
        try:
            with temporary.open("xb") as file:
                shutil.copyfileobj(stream, file)
            with temporary.open("rb") as file:
                magic = file.read(4)
            if magic != b"PK\x03\x04":
                return self.import_gameplay(temporary, Path(filename).name, magic.startswith(b"\x1f\x8b"))
            with ZipFile(temporary) as archive:
                meta = read_manifest(archive)
                if sum(entry.file_size for entry in archive.infolist()) > 768 * 1024 * 1024:
                    raise ValueError("Uncompressed replay exceeds the upload limit")
                for entry in meta["segments"]:
                    read_segment(archive, entry)
            final = temporary.with_name(f"{identifier}.replay")
            temporary.replace(final)
            return self.metadata(final)
        finally:
            temporary.unlink(missing_ok=True)

    def import_gameplay(self, path, title, compressed):
        opener = gzip.open if compressed else open
        with opener(path, "rb") as stream:
            raw = stream.read(256 * 1024 * 1024 + 1)
        if len(raw) > 256 * 1024 * 1024:
            raise ValueError("Uncompressed replay exceeds the upload limit")
        old = json.loads(raw)
        if old.get("format") != "cold-world-replay/1" or old.get("item_catalog_version") != ITEM_CATALOG_VERSION:
            raise ValueError("Unsupported recording")
        writer = ReplayWriter(self, "uploads", title, {"imported_from": "gameplay"})
        writer.meta["game_version"] = old.get("game_version")
        try:
            for frame in old["frames"]:
                seconds = frame["seconds"]
                if not isinstance(seconds, (float, int)) or not math.isfinite(seconds) or seconds <= writer.latest:
                    raise ValueError("Invalid replay timestamps")
                state = {**frame["state"], "structures": old["terrain"][frame["terrain"]]}
                if any(not isinstance(state.get(key), list) for key in ("players", "monsters", "projectiles", "ground", "events", "structures")):
                    raise ValueError("Invalid replay frame")
                writer.append(seconds, state)
            if writer.latest < 0:
                raise ValueError("Empty recording")
            writer.finish("imported")
            with ZipFile(writer.path) as archive:
                for entry in read_manifest(archive)["segments"]:
                    read_segment(archive, entry)
            return self.metadata(writer.path)
        except BaseException:
            if writer.archive is not None:
                writer.archive.close()
            writer.path.unlink(missing_ok=True)
            writer.temporary.unlink(missing_ok=True)
            raise

    def import_arena(self, directory):
        for path in Path(directory).expanduser().glob("*.sqlite3"):
            if not ID.fullmatch(path.stem) or (self.directory / "arena" / f"{path.stem}.replay").exists():
                continue
            writer = None
            try:
                with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
                    meta = json.loads(connection.execute("SELECT payload FROM metadata WHERE singleton=1").fetchone()[0])
                    config = meta.get("config") or {}
                    writer = ReplayWriter(self, "arena", config.get("weapon") or "Arena", config,
                                          identifier=path.stem, created_at=meta.get("created_at"))
                    writer.meta["game_version"] = meta.get("game_version")
                    for (payload,) in connection.execute("SELECT payload FROM frames ORDER BY number"):
                        frame = json.loads(zlib.decompress(payload))
                        writer.append(frame["seconds"], frame["state"], aim=frame.get("aim"), decision=frame.get("decision"))
                    writer.finish(meta.get("status", "imported"), kills=meta.get("kills"), spawned=meta.get("spawned"))
            except (ValueError, KeyError, TypeError, OSError, sqlite3.Error, zlib.error):
                LOGGER.warning("Could not import arena replay %s", path.name, exc_info=True)
                if writer and writer.archive is not None:
                    writer.archive.close()
                    writer.temporary.unlink(missing_ok=True)


class GameplayCapture:
    """Record the authoritative local view of one connected player."""

    def __init__(self, library, world, player_id):
        self.library = library
        self.world = world
        self.player_id = player_id
        self.writer = None

    def command(self, command):
        try:
            if command["type"] == "record_start":
                if self.writer is None:
                    self.writer = ReplayWriter(self.library, "gameplay", self.player_id, {"player": self.player_id})
                    self.started = None
                    self.append()
                return {"id": self.writer.id}
            if self.writer is None:
                raise GameError("replay_not_recording", "No recording is active")
            self.append()
            writer = self.writer
            writer.finish("completed")
            self.writer = None
            return {"id": writer.id}
        except (OSError, ValueError) as error:
            self.failed()
            raise GameError("replay_file", "The server could not save the recording") from error

    def operation(self, command, result, error=None):
        kind = command.get("type")
        if self.writer is None or not isinstance(kind, str) or kind not in {
            "attack", "select", "reload", "craft", "transfer", "take_all", "drop", "place",
            "open", "close", "sort_backpack", "copy_scroll", "trade", "bank", "sit", "toggle_door", "light",
        }:
            return
        fields = ("type", "pressed", "slot", "kind", "target", "id", "item_id", "x", "y", "from", "to", "count")
        self.writer.note({"type": "operation", "tick": self.world.tick_number,
                          "command": {key: command[key] for key in fields if key in command},
                          "accepted": error is None and (not isinstance(result, dict) or result.get("accepted") is not False),
                          "result": result, "error": error})

    def append(self):
        with self.world.lock:
            snapshot = self.world.snapshot(self.player_id)
            controls = self.world.controls[self.player_id]
            aim = [controls.aim_x, controls.aim_y]
        if self.started is None:
            self.started = snapshot["elapsed"]
        self.writer.append(round(snapshot["elapsed"] - self.started, 6), snapshot, aim=aim)

    def capture(self):
        if self.writer is None:
            return
        try:
            self.append()
        except (OSError, ValueError):
            self.failed()

    def disconnect(self):
        self.capture()
        if self.writer is not None:
            try:
                self.writer.finish("disconnected")
                self.writer = None
            except (OSError, ValueError):
                self.failed()

    def failed(self):
        LOGGER.exception("Could not record gameplay for %s", self.player_id)
        writer, self.writer = self.writer, None
        if writer:
            try:
                writer.discard()
            except OSError:
                LOGGER.exception("Could not discard incomplete recording %s", writer.id)
