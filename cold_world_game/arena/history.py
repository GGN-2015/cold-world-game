import json
import logging
import re
import sqlite3
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

from ..actions import GameError


DEFAULT_HISTORY_DIRECTORY = Path.home() / ".cold-world-arena" / "history"
LOGGER = logging.getLogger(__name__)
HISTORY_FORMAT_VERSION = 2


def stamp_facings(snapshot, facings):
    state = snapshot["state"]
    for entity in state["players"] + state["monsters"]:
        previous = facings.get(entity["id"], {"x": entity["x"], "y": entity["y"], "direction": "down"})
        horizontal = entity.get("velocity_x", entity["x"] - previous["x"])
        vertical = entity.get("velocity_y", entity["y"] - previous["y"])
        direction = previous["direction"]
        if not entity.get("downed") and not entity.get("sleeping") and entity.get("rising") is None and max(abs(horizontal), abs(vertical)) > 0.00001:
            horizontal_direction = "left" if horizontal < 0 else "right"
            vertical_direction = "up" if vertical < 0 else "down"
            near_diagonal = abs(abs(horizontal) - abs(vertical)) <= max(abs(horizontal), abs(vertical)) * 0.2
            if not near_diagonal or direction not in (horizontal_direction, vertical_direction):
                direction = horizontal_direction if abs(horizontal) > abs(vertical) else vertical_direction
        entity["facing"] = direction
        facings[entity["id"]] = {"x": entity["x"], "y": entity["y"], "direction": direction}


def upgrade_facings(path):
    connection = sqlite3.connect(path, timeout=30)
    try:
        connection.execute("BEGIN IMMEDIATE")
        metadata = read_metadata(connection)
        if metadata.get("format_version", 1) < HISTORY_FORMAT_VERSION:
            facings = {}
            cursor = connection.execute("SELECT number, payload FROM frames ORDER BY number")
            while rows := cursor.fetchmany(128):
                for number, payload in rows:
                    snapshot = json.loads(zlib.decompress(payload))
                    stamp_facings(snapshot, facings)
                    payload = zlib.compress(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), level=1)
                    connection.execute("UPDATE frames SET payload = ? WHERE number = ?", (payload, number))
            metadata["format_version"] = HISTORY_FORMAT_VERSION
            connection.execute("UPDATE metadata SET payload = ? WHERE singleton = 1", (json.dumps(metadata),))
        connection.commit()
    finally:
        connection.close()


def read_metadata(connection):
    return json.loads(connection.execute("SELECT payload FROM metadata WHERE singleton = 1").fetchone()[0])


def remove_record(path):
    for attempt in range(5):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05)


def finish_record(path, status):
    connection = sqlite3.connect(path)
    try:
        metadata = read_metadata(connection)
        metadata["status"] = status
        connection.execute("UPDATE metadata SET payload = ? WHERE singleton = 1", (json.dumps(metadata),))
        connection.commit()
    finally:
        connection.close()
    destination = path.with_name(path.name.replace(".recording.sqlite3", ".sqlite3"))
    for attempt in range(5):
        try:
            path.replace(destination)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05)


class HistoryWriter:
    def __init__(self, directory, identifier, simulation):
        self.path = Path(directory) / f"{identifier}.recording.sqlite3"
        self.connection = sqlite3.connect(self.path)
        self.connection.executescript("CREATE TABLE metadata (singleton INTEGER PRIMARY KEY, payload TEXT NOT NULL); CREATE TABLE catalog (singleton INTEGER PRIMARY KEY, payload TEXT NOT NULL); CREATE TABLE frames (number INTEGER PRIMARY KEY, tick INTEGER UNIQUE NOT NULL, payload BLOB NOT NULL);")
        self.metadata = {"id": identifier, "format_version": HISTORY_FORMAT_VERSION, "created_at": datetime.now(timezone.utc).isoformat(),
                         "config": simulation.config, "ai_version": simulation.ai.version, "status": "running", "frame_count": 0, "seconds": 0, "kills": 0}
        self.connection.execute("INSERT INTO metadata VALUES (1, ?)", (json.dumps(self.metadata),))
        self.connection.execute("INSERT INTO catalog VALUES (1, ?)", (json.dumps(simulation.world.catalog()),))
        self.connection.commit()
        self.last_tick = None
        self.facings = {}

    def append(self, snapshot):
        tick = snapshot["state"]["tick"]
        if tick != self.last_tick:
            self.metadata["frame_count"] += 1
            self.last_tick = tick
        snapshot["run_id"] = self.metadata["id"]
        snapshot["frame"] = self.metadata["frame_count"] - 1
        stamp_facings(snapshot, self.facings)
        payload = zlib.compress(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), level=1)
        self.connection.execute("INSERT OR REPLACE INTO frames VALUES (?, ?, ?)", (snapshot["frame"], tick, payload))
        self.metadata.update(status=snapshot["status"], seconds=snapshot["seconds"], kills=snapshot["kills"], spawned=snapshot["spawned"])
        self.connection.execute("UPDATE metadata SET payload = ? WHERE singleton = 1", (json.dumps(self.metadata),))
        self.connection.commit()
        return snapshot

    def close(self, status):
        self.connection.close()
        finish_record(self.path, status)


class HistoryStore:
    def __init__(self, directory=None):
        self.directory = Path(directory or DEFAULT_HISTORY_DIRECTORY).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(self.directory / ".server.lock", thread_local=False)
        self.lock.acquire(timeout=0)
        for path in self.directory.glob("*.recording.sqlite3"):
            try:
                finish_record(path, "interrupted")
            except (sqlite3.Error, ValueError, OSError, TypeError):
                LOGGER.exception("Could not recover arena record %s", path.name)

    def path(self, identifier):
        if not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise GameError("arena_history_missing", "History record not found")
        for suffix in (".sqlite3", ".recording.sqlite3"):
            path = self.directory / (identifier + suffix)
            if path.is_file():
                return path
        raise GameError("arena_history_missing", "History record not found")

    def read(self, identifier, start=None, limit=1):
        path = self.path(identifier)
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            metadata = read_metadata(connection)
            if metadata.get("format_version", 1) < HISTORY_FORMAT_VERSION:
                connection.close()
                upgrade_facings(path)
                connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
                metadata = read_metadata(connection)
            if start is None:
                metadata["catalog"] = json.loads(connection.execute("SELECT payload FROM catalog WHERE singleton = 1").fetchone()[0])
                return metadata
            rows = connection.execute("SELECT payload FROM frames WHERE number >= ? ORDER BY number LIMIT ?", (start, limit)).fetchall()
            return {"frames": [json.loads(zlib.decompress(row[0])) for row in rows], "frame_count": metadata["frame_count"]}
        finally:
            connection.close()

    def list(self):
        records = []
        for path in self.directory.glob("*.sqlite3"):
            if ".recording." in path.name:
                continue
            connection = None
            try:
                connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
                records.append(read_metadata(connection))
            except (sqlite3.Error, ValueError, OSError, TypeError):
                LOGGER.warning("Skipping unreadable arena record %s", path.name)
            finally:
                if connection is not None:
                    connection.close()
        return sorted(records, key=lambda record: record["created_at"], reverse=True)

    def delete(self, identifier):
        path = self.path(identifier)
        if ".recording." in path.name:
            raise GameError("arena_history_active", "An active recording cannot be deleted")
        remove_record(path)

    def delete_all(self):
        deleted = []
        for path in self.directory.glob("*.sqlite3"):
            if not re.fullmatch(r"[a-f0-9]{32}", path.stem) or not path.is_file():
                continue
            remove_record(path)
            deleted.append(path.stem)
        return deleted

    def close(self):
        self.lock.release()
