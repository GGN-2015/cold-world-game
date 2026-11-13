import logging
import multiprocessing
import signal
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request
from flask_sock import Sock
from simple_websocket import ConnectionClosed
from werkzeug.serving import make_server

from ..actions import GameError
from ..app import parse_message, password_matches
from ..constants import DEFAULT_VIEWPORT, ITEM_KINDS, TICK_RATE
from ..models import Item
from ..server import send
from ..world import World
from .ai import AI_TYPES, item_support
from .history import HistoryStore, HistoryWriter, finish_record
from .simulation import AMBIENT_TEMPERATURE_RANGE, DEFAULT_AMBIENT_TEMPERATURE, DEFAULT_INVENTORY, FINISHED_STATUSES, MAX_MOUNTED_AMMO, Simulation, validate_config


LOGGER = logging.getLogger(__name__)


def simulate(connection, config, max_monsters, history_directory, run_id):
    simulation = None
    history = None
    outcome = "stopped"
    try:
        simulation = Simulation(config, max_monsters)
        history = HistoryWriter(history_directory, run_id, simulation)
        connection.send(history.append(simulation.snapshot()))
        if simulation.status in FINISHED_STATUSES:
            outcome = simulation.status
            return
        interval = 1 / TICK_RATE
        deadline = time.monotonic() + interval
        while True:
            waiting = max(0, deadline - time.monotonic()) if simulation.status == "running" else None
            if connection.poll(waiting):
                command = connection.recv()
                if command == "stop":
                    return
                if command == "pause":
                    simulation.pause()
                elif command == "resume":
                    simulation.resume()
                deadline = time.monotonic() + interval
                connection.send(history.append(simulation.snapshot()))
                continue
            simulation.step()
            if simulation.world.tick_number % 2 == 0 or simulation.status in FINISHED_STATUSES:
                connection.send(history.append(simulation.snapshot()))
            if simulation.status in FINISHED_STATUSES:
                outcome = simulation.status
                return
            deadline = max(deadline + interval, time.monotonic())
    except (EOFError, BrokenPipeError, ConnectionResetError):
        pass
    except Exception:
        outcome = "error"
        LOGGER.exception("Arena simulation failed")
        try:
            connection.send({"type": "error", "code": "arena_failed"})
        except (OSError, EOFError):
            pass
    finally:
        if history is not None:
            try:
                if simulation is not None:
                    history.append(simulation.snapshot())
                history.close(outcome)
            except Exception:
                LOGGER.exception("Could not finalize arena history")
        if simulation is not None:
            simulation.close()
        connection.close()


class ArenaSession:
    def __init__(self):
        self.process = None
        self.connection = None
        self.status = "idle"

    def start(self, config, max_monsters, history_directory):
        self.close()
        self.history_directory = Path(history_directory)
        self.run_id = uuid.uuid4().hex
        context = multiprocessing.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=simulate, args=(child, config, max_monsters, str(history_directory), self.run_id), name="cold-world-arena", daemon=True)
        try:
            self.process.start()
        except BaseException:
            self.process.close()
            self.process = None
            self.connection.close()
            self.connection = None
            raise
        finally:
            child.close()
        self.status = "starting"

    def close(self):
        if self.process is not None:
            if self.process.is_alive():
                try:
                    self.connection.send("stop")
                except (OSError, EOFError):
                    pass
            deadline = time.monotonic() + 3
            while self.process.is_alive() and time.monotonic() < deadline:
                try:
                    if self.connection.poll(0.05):
                        self.connection.recv()
                except (OSError, EOFError):
                    break
                self.process.join(timeout=0.01)
            self.process.join(timeout=0.1)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=2)
            self.process.close()
            self.process = None
            unfinished = self.history_directory / f"{self.run_id}.recording.sqlite3"
            if unfinished.exists():
                try:
                    finish_record(unfinished, "interrupted")
                except Exception:
                    LOGGER.exception("Could not recover terminated arena record")
        if self.connection is not None:
            self.connection.close()
            self.connection = None


class ArenaServer:
    def __init__(self, max_sessions, history):
        self.limit = max_sessions
        self.history = history
        self.lock = threading.Lock()
        self.clients = set()
        self.stopping = threading.Event()

    def register(self, websocket):
        with self.lock:
            if self.stopping.is_set() or len(self.clients) >= self.limit:
                return False
            self.clients.add(websocket)
            return True

    def unregister(self, websocket):
        with self.lock:
            self.clients.discard(websocket)
            if self.stopping.is_set() and not self.clients:
                self.history.close()

    def close(self):
        self.stopping.set()
        with self.lock:
            clients = list(self.clients)
            if not clients:
                self.history.close()
        for websocket in clients:
            try:
                websocket.close()
            except OSError:
                pass


def create_arena_app(password=None, max_monsters=256, max_sessions=4, history_dir=None):
    root = Path(__file__).resolve().parent.parent
    app = Flask(__name__, template_folder=str(root / "templates"), static_folder=str(root / "static"), static_url_path="/static")
    app.config.update(MAX_CONTENT_LENGTH=32768, SOCK_SERVER_OPTIONS={"ping_interval": 25, "max_message_size": 32768})
    history = HistoryStore(history_dir)
    runtime = ArenaServer(max_sessions, history)
    app.extensions["cold_world_arena"] = runtime
    sock = Sock(app)

    @app.get("/")
    def index():
        return render_template("arena.html")

    @app.get("/api/info")
    def info():
        return jsonify({"catalog": World.catalog(), "max_monsters": max_monsters, "max_mounted_ammo": MAX_MOUNTED_AMMO,
                        "password_required": password is not None, "default_inventory": DEFAULT_INVENTORY,
                        "viewport": DEFAULT_VIEWPORT, "default_ambient_temperature": DEFAULT_AMBIENT_TEMPERATURE,
                        "ambient_temperature_range": AMBIENT_TEMPERATURE_RANGE,
                        "ais": [{"id": name, "version": policy.version} for name, policy in AI_TYPES.items()],
                        "items": [{"kind": kind, "ammo": Item.create(kind).ammo, "uses": Item.create(kind).uses, "support": item_support(kind)} for kind in sorted(ITEM_KINDS)]})

    @app.get("/health")
    def health():
        return jsonify({"ok": not runtime.stopping.is_set(), "mode": "arena"})

    def authorize_history():
        if password is not None and not password_matches(request.headers.get("X-Arena-Password"), password):
            raise GameError("unauthorized", "Invalid arena password")
        origin = request.headers.get("Origin")
        if origin and urlsplit(origin).netloc != request.host:
            raise GameError("invalid_origin", "Origin is not allowed")

    @app.errorhandler(GameError)
    def history_error(error):
        status = 403 if error.code in {"unauthorized", "invalid_origin"} else 404 if error.code == "arena_history_missing" else 409 if error.code == "arena_history_active" else 400
        return jsonify({"error": error.code}), status

    @app.get("/api/history")
    def list_history():
        authorize_history()
        return jsonify({"records": history.list(), "directory": str(history.directory)})

    @app.get("/api/history/<identifier>")
    def read_history(identifier):
        authorize_history()
        return jsonify(history.read(identifier))

    @app.delete("/api/history")
    def delete_all_history():
        authorize_history()
        return jsonify({"deleted": history.delete_all()})

    @app.get("/api/history/<identifier>/frames")
    def history_frames(identifier):
        authorize_history()
        start, limit = request.args.get("start", 0, type=int), request.args.get("limit", 64, type=int)
        if start is None or limit is None or start < 0 or not 1 <= limit <= 100:
            raise GameError("arena_history_range", "Invalid frame range")
        return jsonify(history.read(identifier, start, limit))

    @app.delete("/api/history/<identifier>")
    def delete_history(identifier):
        authorize_history()
        history.delete(identifier)
        return jsonify({"deleted": identifier})

    @sock.route("/ws")
    def websocket_handler(websocket):
        session = ArenaSession()
        registered = False
        try:
            origin = request.headers.get("Origin")
            if origin and urlsplit(origin).netloc != request.host:
                raise GameError("invalid_origin", "Origin is not allowed")
            message = parse_message(websocket.receive(timeout=10))
            if message.get("type") != "join" or password is not None and not password_matches(message.get("password"), password):
                raise GameError("unauthorized", "Invalid arena password")
            registered = runtime.register(websocket)
            if not registered:
                raise GameError("arena_busy", "The arena session limit has been reached")
            send(websocket, {"type": "ready"})
            while not runtime.stopping.is_set():
                if session.connection is not None:
                    try:
                        if session.connection.poll():
                            update = session.connection.recv()
                            if update["type"] == "state":
                                session.status = update["status"]
                            else:
                                session.status = "error"
                            if session.status in FINISHED_STATUSES or session.status == "error":
                                session.close()
                            send(websocket, update)
                    except (EOFError, OSError):
                        session.close()
                        session.status = "error"
                        send(websocket, {"type": "error", "code": "arena_failed"})
                raw = websocket.receive(timeout=0.02)
                if raw is None:
                    continue
                try:
                    message = parse_message(raw)
                    kind = message.get("type")
                    if kind == "start":
                        config = validate_config(message.get("config"), max_monsters)
                        session.start(config, max_monsters, history.directory)
                        send(websocket, {"type": "started", "config": config, "run_id": session.run_id})
                    elif kind in {"pause", "resume"}:
                        if session.connection is None or session.status not in {"running", "paused", "starting"}:
                            raise GameError("arena_finished", "This simulation cannot be resumed")
                        session.connection.send(kind)
                    else:
                        raise GameError("unknown_command", "Unknown arena command")
                except GameError as error:
                    send(websocket, {"type": "error", "code": error.code})
        except GameError as error:
            send(websocket, {"type": "error", "code": error.code})
        except (ConnectionClosed, OSError):
            pass
        except Exception:
            LOGGER.exception("Arena connection failed")
        finally:
            session.close()
            if registered:
                runtime.unregister(websocket)

    return app


def serve(options, arguments):
    if not 0 <= options.port <= 65535:
        arguments.error("--port must be in [0, 65535]")
    if not 1 <= options.max_monsters <= 1000 or not 1 <= options.max_sessions <= 32:
        arguments.error("--max-monsters must be in [1, 1000]; --max-sessions in [1, 32]")
    if options.password == "":
        arguments.error("--password must not be empty")
    logging.basicConfig(level=options.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = create_arena_app(options.password, options.max_monsters, options.max_sessions, options.history_dir)
    runtime = app.extensions["cold_world_arena"]
    http = None
    serving = False
    stop = threading.Event()
    previous = {}
    try:
        http = make_server(options.host, options.port, app, threaded=True)
        for signal_number in (signal.SIGINT, signal.SIGTERM):
            previous[signal_number] = signal.signal(signal_number, lambda signum, frame: stop.set())
        host = "127.0.0.1" if options.host in {"0.0.0.0", "::"} else options.host
        print(f"Cold World Arena: http://{host}:{http.server_port}", flush=True)
        print(f"Isolated simulations; game saves are never opened. Replay history: {runtime.history.directory}", flush=True)
        if options.host not in {"127.0.0.1", "localhost", "::1"} and options.password is None:
            print("WARNING: arena is reachable without a password. Set --password for shared networks.", flush=True)
        thread = threading.Thread(target=http.serve_forever, name="cold-world-arena-http", daemon=True)
        thread.start()
        serving = True
        stop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        runtime.close()
        if http is not None:
            if serving:
                http.shutdown()
            http.server_close()
        for signal_number, handler in previous.items():
            signal.signal(signal_number, handler)
    return 0
