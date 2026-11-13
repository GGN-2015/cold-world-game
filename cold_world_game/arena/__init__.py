def configure_parser(arguments):
    arguments.add_argument("--host", default="127.0.0.1", help="Bind address (use 0.0.0.0 for LAN access)")
    arguments.add_argument("--port", type=int, default=5001, help="Arena HTTP/WebSocket port (default: 5001)")
    arguments.add_argument("--password", help="Optional arena access password")
    arguments.add_argument("--max-monsters", type=int, default=256, help="Maximum selectable monster cap (default: 256)")
    arguments.add_argument("--max-sessions", type=int, default=4, help="Maximum connected arena sessions (default: 4)")
    arguments.add_argument("--history-dir", help="Replay directory, separate from game saves (default: ~/.cold-world-arena/history)")
    arguments.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")


def run(options, arguments):
    from .server import serve
    return serve(options, arguments)
