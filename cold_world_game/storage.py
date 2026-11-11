import copy
import json
import sqlite3
from pathlib import Path

from filelock import FileLock


class Storage:
    @staticmethod
    def parts(state):
        structures = state.get("structures")
        if not isinstance(structures, list) or not all(isinstance(value, dict) and isinstance(value.get("id"), str) for value in structures):
            return state
        identifiers = [value["id"] for value in structures]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Duplicate structure IDs in save")
        return {**state, "structures": identifiers, **{"structure:" + value["id"]: value for value in structures}}

    @staticmethod
    def unpack(parts):
        structures = parts.get("structures")
        if not isinstance(structures, list) or not all(isinstance(identifier, str) for identifier in structures):
            return parts
        return {**{name: value for name, value in parts.items() if not name.startswith("structure:")}, "structures": [parts["structure:" + identifier] for identifier in structures]}

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
        record = self.connection.execute("SELECT version, payload FROM world WHERE singleton=1").fetchone()
        if record is None:
            self._version = None
            self._state = {}
            return None
        if record[0] not in (1, 2):
            raise ValueError(f"Unsupported save version: {record[0]}")
        state = json.loads(record[1]) if record[0] == 1 else {name: json.loads(payload) for name, payload in self.connection.execute("SELECT name, payload FROM world_parts")}
        self._version = record[0]
        self._state = copy.deepcopy(state)
        return self.unpack(state) if record[0] == 2 else state

    def save(self, state: dict) -> None:
        if self._state is None:
            self.load()
        state = self.parts(state)
        changed = {name: json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) for name, value in state.items() if self._version != 2 or name not in self._state or value != self._state[name]}
        removed = self._state.keys() - state.keys()
        if not changed and not removed and self._version == 2:
            return
        saved = {name: json.loads(payload) for name, payload in changed.items()}
        with self.connection:
            if self._version != 2:
                self.connection.execute("DELETE FROM world_parts")
                self.connection.execute("INSERT INTO world(singleton, version, payload) VALUES(1, 2, '{}') ON CONFLICT(singleton) DO UPDATE SET version=2, payload='{}'")
            self.connection.executemany("INSERT INTO world_parts(name, payload) VALUES(?, ?) ON CONFLICT(name) DO UPDATE SET payload=excluded.payload", changed.items())
            self.connection.executemany("DELETE FROM world_parts WHERE name=?", [(name,) for name in removed])
        self._state.update(saved)
        for name in removed:
            self._state.pop(name, None)
        self._version = 2

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        self.file_lock.release()
