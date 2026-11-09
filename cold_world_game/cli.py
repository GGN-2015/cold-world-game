import argparse
import logging
import signal
import threading

from filelock import Timeout
from werkzeug.serving import make_server

from .app import create_app


def parser():
    arguments = argparse.ArgumentParser(description="Cold World Game browser game with Flask/WebSocket server")
    arguments.add_argument("--host", default="127.0.0.1", help="Bind address (use 0.0.0.0 for LAN access)")
    arguments.add_argument("--port", type=int, default=5000, help="HTTP/WebSocket port (default: 5000)")
    arguments.add_argument("--password", help="Shared server password; generated randomly when omitted")
    arguments.add_argument("--save-path", help="Save directory or .sqlite3/.sqlite/.db file; default: ~/.cold-world-game")
    arguments.add_argument("--seed", type=int, help="World seed for a new save only")
    arguments.add_argument("--allowed-origin", action="append", default=[], help="Additional browser Origin allowed to connect; repeatable")
    arguments.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    return arguments


def main(argv=None):
    arguments = parser()
    options = arguments.parse_args(argv)
    if not 0 <= options.port <= 65535:
        arguments.error("--port must be in [0, 65535]")
    if options.password == "":
        arguments.error("--password must not be empty")
    logging.basicConfig(level=options.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        app = create_app(password=options.password, save_path=options.save_path, seed=options.seed, allowed_origins=options.allowed_origin)
    except Timeout:
        arguments.exit(1, "This save is already open in another server process.\n")
    except (OSError, ValueError) as error:
        arguments.exit(1, f"Unable to open the game save: {error}\n")
    runtime = app.extensions["cold_world_game"]
    http_server = None
    serving = False
    stop = threading.Event()

    def stop_server(signum, frame):
        stop.set()

    previous = {}
    try:
        http_server = make_server(options.host, options.port, app, threaded=True)
        http_thread = threading.Thread(target=http_server.serve_forever, name="cold-world-http", daemon=True)
        for signal_number in (signal.SIGINT, signal.SIGTERM):
            previous[signal_number] = signal.signal(signal_number, stop_server)
        print(f"Cold World Game: http://{options.host}:{http_server.server_port}", flush=True)
        if options.host in ("0.0.0.0", "::"):
            print(f"Open http://127.0.0.1:{http_server.server_port} locally, or use this computer's LAN IP from another device.", flush=True)
        else:
            print("Open this address in your browser to play.", flush=True)
        print(f"Save: {runtime.world.storage.path}", flush=True)
        label = "Random server password" if runtime.password_generated else "Server password"
        print(f"{label}: {runtime.password}", flush=True)
        print("Press Ctrl+C to save and stop.", flush=True)
        http_thread.start()
        serving = True
        stop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if http_server is not None:
            if serving:
                http_server.shutdown()
            http_server.server_close()
        runtime.close()
        for signal_number, handler in previous.items():
            signal.signal(signal_number, handler)
    return 0
