import json
import sqlite3
from pathlib import Path

from filelock import FileLock


class Storage:
    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file_lock = FileLock(str(self.path) + ".lock")
        self.file_lock.acquire(timeout=0)
        self.connection = None
        try:
            self.connection = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute("CREATE TABLE IF NOT EXISTS world (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL, payload TEXT NOT NULL)")
            self.connection.commit()
        except BaseException:
            self.close()
            raise

    def load(self) -> dict | None:
        record = self.connection.execute("SELECT version, payload FROM world WHERE singleton=1").fetchone()
        if record is None:
            return None
        if record[0] != 1:
            raise ValueError(f"Unsupported save version: {record[0]}")
        return json.loads(record[1])

    def save(self, state: dict) -> None:
        payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        with self.connection:
            self.connection.execute(
                "INSERT INTO world(singleton, version, payload) VALUES(1, 1, ?) ON CONFLICT(singleton) DO UPDATE SET version=excluded.version, payload=excluded.payload",
                (payload,),
            )

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        self.file_lock.release()
