import json
import logging
import secrets
import threading
import time
from pathlib import Path

from .constants import TICK_RATE
from .admin import admin_id
from .storage import Storage
from .world import World


LOGGER = logging.getLogger(__name__)


def database_path(save_path=None):
    path = Path(save_path).expanduser() if save_path else Path.home() / ".cold-world-game"
    if not path.is_dir() and (path.is_file() or path.suffix.lower() in (".db", ".sqlite", ".sqlite3")):
        return path.resolve()
    return (path / "world.sqlite3").resolve()


class GameServer:
    def __init__(self, password=None, save_path=None, seed=None, start_engine=True, admin=None):
        if password is not None and (not isinstance(password, str) or not password):
            raise ValueError("Server password must be a non-empty string")
        self.password = password if password is not None else secrets.token_urlsafe(18)
        self.password_generated = password is None
        admin = admin_id(admin)
        storage = Storage(database_path(save_path))
        try:
            self.world = World(storage, seed=seed, admin=admin)
        except BaseException:
            storage.close()
            raise
        self.stopping = threading.Event()
        self.connections = set()
        self.condition = threading.Condition()
        self.closed = False
        self.thread = None
        self.world.last_real = time.monotonic()
        if start_engine:
            self.thread = threading.Thread(target=self.run, name="cold-world-simulation", daemon=True)
            self.thread.start()

    def run(self):
        interval = 1 / TICK_RATE
        deadline = time.monotonic() + interval
        while not self.stopping.wait(max(0, deadline - time.monotonic())):
            try:
                with self.world.lock:
                    now = time.monotonic()
                    elapsed = max(0, now - self.world.last_real)
                    self.world.last_real = now
                    self.world.tick(elapsed)
            except Exception:
                LOGGER.exception("Simulation paused because an update failed")
                with self.world.lock:
                    self.world.fault = "Simulation paused; check the server log and restart"
            deadline += interval
            if deadline < time.monotonic():
                deadline = time.monotonic() + interval

    def register(self, websocket):
        with self.condition:
            if self.stopping.is_set():
                return False
            self.connections.add(websocket)
            return True

    def unregister(self, websocket):
        with self.condition:
            self.connections.discard(websocket)
            self.condition.notify_all()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.stopping.set()
        with self.condition:
            connections = list(self.connections)
        for websocket in connections:
            try:
                websocket.close()
            except Exception:
                LOGGER.debug("Connection already closed", exc_info=True)
        with self.condition:
            self.condition.wait_for(lambda: not self.connections, timeout=5)
        if self.thread is not None:
            self.thread.join()
        self.world.close()


def send(websocket, message):
    websocket.send(json.dumps(message, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
