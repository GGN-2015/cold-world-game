import copy
import json
import sqlite3
from pathlib import Path

from filelock import FileLock


class WorldDelta(dict):
    def __init__(self, metadata, structures, removed):
        super().__init__(metadata)
        self.structures = structures
        self.removed = removed


class Storage:
    version = 4

    @staticmethod
    def parts(state):
        structures = state.get("structures")
        if not isinstance(structures, list) or not all(isinstance(value, dict) and isinstance(value.get("id"), str) for value in structures):
            return state
        identifiers = [value["id"] for value in structures]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Duplicate structure IDs in save")
        if state.get("materialized") and state.get("terrain_format") == 1:
            from .models import encode
            from .procedural import plan
            records = {value["id"]: value for value in structures}
            for horizontal, vertical, version in state.get("chunk_versions", []):
                if version < 18:
                    continue
                objects, interior = plan(state["seed"], horizontal, vertical, state["generation_profiles"][str(version)])
                for structure in objects:
                    original = records.get(structure.id)
                    if original is None:
                        records[structure.id] = {"id": structure.id, "deleted": True}
                    elif original == encode(structure):
                        records.pop(structure.id)
            structures = list(records.values())
            identifiers = list(records)
            state = {name: value for name, value in state.items() if name != "materialized"}
        return {**state, "structures": identifiers, **{"structure:" + value["id"]: value for value in structures}}

    @staticmethod
    def unpack(parts):
        structures = parts.get("structures")
        if not isinstance(structures, list) or not all(isinstance(identifier, str) for identifier in structures):
            return parts
        records = {name.removeprefix("structure:"): value for name, value in parts.items() if name.startswith("structure:")}
        ordered = [records.pop(identifier) for identifier in structures if identifier in records]
        ordered.extend(records.values())
        return {**{name: value for name, value in parts.items() if not name.startswith("structure:")}, "structures": ordered}

    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file_lock = FileLock(str(self.path) + ".lock")
        self.file_lock.acquire(timeout=0)
        self.connection = None
        self._version = None
        self._state = None
        try:
            self.connection = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute("CREATE TABLE IF NOT EXISTS world (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL, payload TEXT NOT NULL)")
            self.connection.execute("CREATE TABLE IF NOT EXISTS world_parts (name TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            self.connection.commit()
        except BaseException:
            self.close()
            raise

    def load(self) -> dict | None:
        record = self.connection.execute("SELECT version FROM world WHERE singleton=1").fetchone()
        if record is None:
            self._version = None
            self._state = {}
            return None
        if record[0] != self.version:
            raise ValueError(f"Unsupported save version {record[0]}. Use a new save path.")
        state = {name: json.loads(payload) for name, payload in self.connection.execute("SELECT name, payload FROM world_parts ORDER BY rowid")}
        self._version = record[0]
        self._state = copy.deepcopy(state)
        return self.unpack(state)

    def save(self, state: dict) -> None:
        if self._state is None:
            self.load()
        if isinstance(state, WorldDelta):
            values = {**state, **{"structure:" + identifier: value for identifier, value in state.structures.items()}}
            removed = {"structure:" + identifier for identifier in state.removed}
            if self._version is None:
                values.setdefault("structures", list(state.structures))
        else:
            values = self.parts(state)
            removed = self._state.keys() - values.keys()
        changed = {name: json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) for name, value in values.items() if name not in self._state or value != self._state[name]}
        if not changed and not removed and self._version is not None:
            return
        saved = {name: json.loads(payload) for name, payload in changed.items()}
        with self.connection:
            if self._version is None:
                self.connection.execute("INSERT INTO world(singleton, version, payload) VALUES(1, ?, '{}')", (self.version,))
            self.connection.executemany("INSERT INTO world_parts(name, payload) VALUES(?, ?) ON CONFLICT(name) DO UPDATE SET payload=excluded.payload", changed.items())
            self.connection.executemany("DELETE FROM world_parts WHERE name=?", [(name,) for name in removed])
        self._state.update(saved)
        for name in removed:
            self._state.pop(name, None)
        self._version = self.version

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        self.file_lock.release()
