import argparse
import logging
import signal
import threading

from filelock import Timeout
from werkzeug.serving import make_server

from .app import create_app


def parser():
    arguments = argparse.ArgumentParser(prog="cold-world-game", description="Cold World Game browser game with Flask/WebSocket server")
    arguments.set_defaults(handler=None, command_parser=arguments)
    commands = arguments.add_subparsers(title="commands")
    game = commands.add_parser("game", help="Start the browser game server", description="Start the Flask/WebSocket game server")
    game_arguments(game)
    game.set_defaults(handler=run_game, command_parser=game)
    tests = commands.add_parser("test", help="Run isolated performance tests", description="Performance tests use disposable worlds and never open the game save")
    tests.set_defaults(handler=None, command_parser=tests)
    checks = tests.add_subparsers(title="tests")
    from .benchmarks import combat, sync, terrain
    for name, module, description in (
        ("combat", combat, "Measure same-screen combat capacity with WebSocket players and optional browsers"),
        ("terrain", terrain, "Compare terrain protocols and SQLite size on the same disposable world"),
        ("sync", sync, "Compare JSON and compact combat streaming on identical authoritative frames"),
    ):
        check = checks.add_parser(name, help=description, description=description)
        module.configure_parser(check)
        check.set_defaults(handler=module.run, command_parser=check)
    return arguments


def game_arguments(arguments):
    arguments.add_argument("--host", default="127.0.0.1", help="Bind address (use 0.0.0.0 for LAN access)")
    arguments.add_argument("--port", type=int, default=5000, help="HTTP/WebSocket port (default: 5000)")
    arguments.add_argument("--password", help="Shared server password; generated randomly when omitted")
    arguments.add_argument("--admin", help="Exact player ID allowed to use the administrator console; disabled when omitted")
    arguments.add_argument("--save-path", help="Save directory or .sqlite3/.sqlite/.db file; default: ~/.cold-world-game")
    arguments.add_argument("--seed", type=int, help="World seed for a new save only")
    arguments.add_argument("--allowed-origin", action="append", default=[], help="Additional browser Origin allowed to connect; repeatable")
    arguments.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")


def main(argv=None):
    arguments = parser()
    options = arguments.parse_args(argv)
    handler = vars(options).pop("handler")
    command_parser = vars(options).pop("command_parser")
    if handler is None:
        command_parser.print_help()
        return 0
    return handler(options, command_parser)


def run_game(options, arguments):
    if not 0 <= options.port <= 65535:
        arguments.error("--port must be in [0, 65535]")
    if options.password == "":
        arguments.error("--password must not be empty")
    logging.basicConfig(level=options.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        app = create_app(password=options.password, save_path=options.save_path, seed=options.seed, allowed_origins=options.allowed_origin, admin=options.admin)
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
        if runtime.world.admin is not None:
            print(f"Administrator player ID: {runtime.world.admin}", flush=True)
        print("Press Ctrl+C to save and stop.", flush=True)
        print("Saving: background snapshots (normally 15s, forced by 150s under load; pause if uncommitted for 180s). A forced stop can lose recent progress.", flush=True)
        http_thread.start()
        serving = True
        stop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if http_server is not None:
                try:
                    if serving:
                        http_server.shutdown()
                finally:
                    http_server.server_close()
        finally:
            try:
                runtime.close()
                print("Final world snapshot saved. Server stopped.", flush=True)
            except Exception as error:
                arguments.exit(1, f"FINAL SAVE FAILED: {error}. Check the server log; recent progress may not be saved.\n")
            finally:
                for signal_number, handler in previous.items():
                    signal.signal(signal_number, handler)
    return 0
