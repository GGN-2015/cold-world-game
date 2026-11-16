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
from ..constants import TICK_RATE
from ..replay_routes import register_replay_routes
from ..replays import ReplayLibrary, ReplayWriter
from ..server import send
from ..world import World
from .simulation import (
    FINISHED_STATUSES,
    STRATEGIES,
    TERRAIN,
    WAVES,
    WEAPONS,
    Simulation,
    validate_config,
)

LOGGER = logging.getLogger(__name__)


def simulate(connection, config, replay_directory, run_id):
    simulation = None
    writer = None
    outcome = "stopped"
    try:
        simulation = Simulation(config)
        writer = ReplayWriter(ReplayLibrary(replay_directory), "arena", config["weapon"], config, identifier=run_id)

        def publish():
            frame = simulation.capture(writer)
            frame["run_id"] = run_id
            if simulation.status in FINISHED_STATUSES:
                writer.meta["configuration"]["setup"] = simulation.opening
                writer.finish(simulation.status, kills=simulation.kills, spawned=simulation.spawned)
                frame["setup"] = simulation.opening
            connection.send(frame)

        publish()
        if simulation.config["setup"]:
            simulation.restore_opening(writer)
            publish()
        interval = 1 / TICK_RATE
        deadline = time.monotonic() + interval
        while simulation.status not in FINISHED_STATUSES:
            running = simulation.status == "running"
            if connection.poll(max(0, deadline - time.monotonic()) if running else .1):
                command = connection.recv()
                try:
                    simulation.apply(writer, command)
                except GameError as error:
                    connection.send({"type": "edit_error", "code": error.code, "message": str(error)})
                else:
                    publish()
                if not running:
                    deadline = time.monotonic() + interval
            elif running:
                simulation.step()
                if simulation.world.tick_number % 2 == 0 or simulation.status != "running":
                    publish()
                deadline = max(deadline + interval, time.monotonic())
    except (EOFError, BrokenPipeError, ConnectionResetError):
        pass
    except Exception:
        outcome = "error"
        LOGGER.exception("Arena run failed")
        try:
            connection.send({"type": "error", "code": "arena_failed"})
        except (EOFError, OSError):
            pass
    finally:
        if writer is not None and simulation is not None:
            try:
                writer.finish(outcome, kills=simulation.kills, spawned=simulation.spawned)
            except OSError:
                LOGGER.exception("Could not finalize arena replay")
        if simulation is not None:
            simulation.close()
        connection.close()


class ArenaSession:
    def __init__(self):
        self.process = None
        self.connection = None
        self.status = "idle"

    def start(self, config, replay_directory):
        self.close()
        self.run_id = uuid.uuid4().hex
        context = multiprocessing.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=simulate, args=(child, config, str(replay_directory), self.run_id), name="cold-world-arena", daemon=True)
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
                    self.connection.send({"action": "stop"})
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
        if self.connection is not None:
            self.connection.close()
            self.connection = None


class ArenaServer:
    def __init__(self, max_sessions, library):
        self.limit = max_sessions
        self.library = library
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

    def close(self):
        self.stopping.set()
        with self.lock:
            clients = list(self.clients)
        for websocket in clients:
            try:
                websocket.close()
            except OSError:
                pass


def create_arena_app(password=None, max_sessions=4, history_dir=None, replay_dir=None):
    root = Path(__file__).resolve().parent.parent
    app = Flask(__name__, template_folder=str(root / "templates"), static_folder=str(root / "static"), static_url_path="/static")
    app.config.update(MAX_CONTENT_LENGTH=32768, SOCK_SERVER_OPTIONS={"ping_interval": 25, "max_message_size": 32768})
    library = ReplayLibrary(replay_dir)
    for directory in (history_dir, Path("arena-history"), Path("arena-history/fights"), Path.home() / ".cold-world-arena/fights"):
        if directory:
            library.import_arena(directory)
    runtime = ArenaServer(max_sessions, library)
    app.extensions["cold_world_arena"] = runtime
    sock = Sock(app)

    @app.get("/")
    def index():
        return render_template("arena.html")

    register_replay_routes(app, library, password, arena=True)

    @app.get("/api/info")
    def info():
        return jsonify({"catalog": World.catalog(), "weapons": WEAPONS, "waves": WAVES, "terrain": TERRAIN, "strategies": STRATEGIES, "password_required": password is not None})

    @app.get("/health")
    def health():
        return jsonify({"ok": not runtime.stopping.is_set(), "mode": "arena"})

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
                            elif update["type"] == "error":
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
                        config = validate_config(message.get("config"))
                        session.start(config, library.directory)
                        send(websocket, {"type": "started", "config": config, "run_id": session.run_id})
                    elif kind == "control" and session.connection is not None:
                        session.connection.send(message)
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
    if not 1 <= options.max_sessions <= 32:
        arguments.error("--max-sessions must be in [1, 32]")
    if options.password == "":
        arguments.error("--password must not be empty")
    if options.host not in {"127.0.0.1", "localhost", "::1"} and options.password is None:
        arguments.error("--password is required when sharing the arena and its replay library over the network")
    logging.basicConfig(level=options.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = create_arena_app(options.password, options.max_sessions, options.history_dir, options.replay_dir)
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
        print(f"Isolated simulations; game saves are never opened. Replay history: {runtime.library.directory}", flush=True)
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
