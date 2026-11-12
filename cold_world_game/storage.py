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
    def unpack(parts, sparse=False):
        structures = parts.get("structures")
        if not isinstance(structures, list) or not all(isinstance(identifier, str) for identifier in structures):
            return parts
        if sparse:
            records = {name.removeprefix("structure:"): value for name, value in parts.items() if name.startswith("structure:")}
            ordered = [records.pop(identifier) for identifier in structures if identifier in records]
            ordered.extend(records.values())
        else:
            ordered = [parts["structure:" + identifier] for identifier in structures]
        return {**{name: value for name, value in parts.items() if not name.startswith("structure:")}, "structures": ordered}

    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file_lock = FileLock(str(self.path) + ".lock")
        self.file_lock.acquire(timeout=0)
        self.connection = None
        self._version = None
        self._state = None
        self._migrate_parts = False
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
        record = self.connection.execute("SELECT version, payload FROM world WHERE singleton=1").fetchone()
        if record is None:
            self._version = None
            self._state = {}
            self._migrate_parts = False
            return None
        if record[0] not in (1, 2, 3, 4):
            raise ValueError(f"Unsupported save version: {record[0]}")
        state = self.parts(json.loads(record[1])) if record[0] == 1 else {name: json.loads(payload) for name, payload in self.connection.execute("SELECT name, payload FROM world_parts ORDER BY rowid")}
        if record[0] == 2:
            normalized = self.parts(state)
            self._migrate_parts = normalized is not state
            state = normalized
        else:
            self._migrate_parts = False
        self._version = record[0]
        self._state = copy.deepcopy(state)
        return self.unpack(state, sparse=record[0] >= 3)

    def save(self, state: dict) -> None:
        if self._state is None:
            self.load()
        migrate = self._version in (None, 1) or self._migrate_parts
        if isinstance(state, WorldDelta):
            values = {**state, **{"structure:" + identifier: value for identifier, value in state.structures.items()}}
            removed = {"structure:" + identifier for identifier in state.removed}
            if migrate:
                values = {**self._state, **values}
                for name in removed:
                    values.pop(name, None)
                values.setdefault("structures", list(state.structures))
        else:
            values = self.parts(state)
            removed = self._state.keys() - values.keys()
        changed = {name: json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) for name, value in values.items() if migrate or name not in self._state or value != self._state[name]}
        version = 4 if values.get("terrain_format", self._state.get("terrain_format")) == 1 else 3
        if not changed and not removed and self._version == version:
            return
        saved = {name: json.loads(payload) for name, payload in changed.items()}
        with self.connection:
            if migrate:
                self.connection.execute("DELETE FROM world_parts")
            if self._version != version:
                self.connection.execute("INSERT INTO world(singleton, version, payload) VALUES(1, ?, '{}') ON CONFLICT(singleton) DO UPDATE SET version=excluded.version, payload='{}'", (version,))
            self.connection.executemany("INSERT INTO world_parts(name, payload) VALUES(?, ?) ON CONFLICT(name) DO UPDATE SET payload=excluded.payload", changed.items())
            self.connection.executemany("DELETE FROM world_parts WHERE name=?", [(name,) for name in removed])
        self._state.update(saved)
        for name in removed:
            self._state.pop(name, None)
        self._version = version
        self._migrate_parts = False

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        self.file_lock.release()
