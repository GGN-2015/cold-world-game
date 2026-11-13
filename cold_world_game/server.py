import json
import logging
import secrets
import socket
import threading
import time
from pathlib import Path

from .constants import TICK_RATE
from .admin import admin_id
from .storage import Storage
from .persistence import SaveCoordinator
from .publication import StatePublisher
from .world import World
from .actions import GameError


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
        self.publication_thread = None
        self.persistence = None
        self.observe = lambda name, value: None
        self.publisher = StatePublisher(self)
        self.world.last_real = time.monotonic()
        if start_engine:
            self.start()

    def start(self):
        if self.thread is not None or self.closed:
            raise RuntimeError("The game engine has already started or closed")
        self.persistence = SaveCoordinator(self.world, lambda name, value: self.observe(name, value))
        self.persistence.start()
        self.world.last_real = time.monotonic()
        self.thread = threading.Thread(target=self.run, name="cold-world-simulation", daemon=True)
        self.publication_thread = threading.Thread(target=self.publish, name="cold-world-publication", daemon=True)
        self.thread.start()
        self.publication_thread.start()

    def execute(self, player_id, command):
        with self.world.lock:
            if self.stopping.is_set():
                raise GameError("server_stopping", "The server is saving and shutting down")
            try:
                return self.world.execute(player_id, command)
            finally:
                sequence = command.get("seq") if isinstance(command, dict) else None
                if sequence is not None:
                    self.publisher.sequences[player_id] = max(sequence, self.publisher.sequences.get(player_id, 0))

    def snapshot(self, player_id, procedural, previous):
        return self.publisher.snapshot(player_id, procedural, previous)

    def roster(self):
        if self.publisher.roster is not None:
            return self.publisher.roster
        return self.world.player_roster()

    def publish(self):
        deadline = time.monotonic()
        while not self.stopping.wait(max(0, deadline - time.monotonic())):
            try:
                self.publisher.publish()
            except Exception:
                LOGGER.exception("State publication failed; retrying on the next publication")
                with self.world.lock:
                    self.publisher.frames.clear()
            deadline += .1
            if deadline < time.monotonic():
                deadline = time.monotonic()

    def run(self):
        interval = 1 / TICK_RATE
        deadline = time.monotonic() + interval
        while not self.stopping.wait(max(0, deadline - time.monotonic())):
            started = time.perf_counter()
            try:
                self.persistence.check_health()
                with self.world.lock:
                    now = time.monotonic()
                    elapsed = max(0, now - self.world.last_real)
                    self.world.last_real = now
                    self.world.tick(elapsed)
            except Exception:
                LOGGER.exception("Simulation paused because an update failed")
                with self.world.lock:
                    self.world.fault = "Simulation paused; check the server log and restart"
            self.persistence.observe_load(time.perf_counter() - started, interval)
            deadline += interval
            if deadline < time.monotonic():
                deadline = time.monotonic()

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
        LOGGER.info("Stopping network handlers and simulation before the final save")
        with self.condition:
            connections = list(self.connections)
        for websocket in connections:
            try:
                websocket.sock.settimeout(1)
                websocket.close()
            except Exception:
                LOGGER.debug("Connection already closed", exc_info=True)
            finally:
                try:
                    websocket.sock.shutdown(socket.SHUT_RDWR)
                except (AttributeError, OSError):
                    pass
        with self.condition:
            if not self.condition.wait_for(lambda: not self.connections, timeout=5):
                LOGGER.warning("Waiting for active connection handlers before the final save")
                self.condition.wait_for(lambda: not self.connections)
        if self.thread is not None:
            self.thread.join()
        if self.publication_thread is not None:
            self.publication_thread.join()
        try:
            LOGGER.info("Saving final world snapshot before shutdown: %s", self.world.storage.path)
            if self.persistence is not None:
                self.persistence.close()
            else:
                with self.world.lock:
                    self.world.save_changes()
            LOGGER.info("Final world snapshot committed: tick=%s generation=%s fault=%s path=%s", self.world.tick_number, self.world._save_generation, self.world.fault, self.world.storage.path)
        except Exception:
            LOGGER.exception("FINAL SAVE FAILED: recent in-memory progress was not fully committed; retain the existing save and check disk space/permissions")
            raise
        finally:
            self.world.close(save=False)


def send(websocket, message):
    websocket.send(json.dumps(message, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
