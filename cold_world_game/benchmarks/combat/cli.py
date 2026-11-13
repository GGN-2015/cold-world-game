import argparse
import asyncio
import math
from datetime import datetime
from pathlib import Path
import sys


def integers(value):
    try:
        values = [int(entry) for entry in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected comma-separated integers") from error
    if not values or any(entry < 0 for entry in values):
        raise argparse.ArgumentTypeError("Values must be non-negative integers")
    return list(dict.fromkeys(values))


def configure_parser(result):
    result.add_argument("--players", type=int, default=16, choices=range(1, 65), metavar="1..64")
    result.add_argument("--levels", type=integers, default=[0, 35, 70, 100, 140, 200, 280, 400, 560], help="Increasing active-monster targets; 0 measures the no-monster baseline")
    result.add_argument("--latency-ms", type=integers, default=[0, 300], help="Added round-trip delay; half in each direction")
    result.add_argument("--scenarios", default="open,obstacles,effects,march", help="Comma-separated: open,obstacles,effects,march")
    result.add_argument("--seeds", type=integers, default=[43], help="Comma-separated disposable-world seeds")
    result.add_argument("--repeats", type=int, default=1)
    result.add_argument("--radius", type=int, default=20, choices=range(3, 41), metavar="3..40", help="Pre-generated chunk radius; 20 means 1681 chunks")
    result.add_argument("--warmup", type=float, default=30)
    result.add_argument("--seconds", type=float, default=120, help="Measured seconds per case; below 30 is smoke-only")
    result.add_argument("--refine-step", type=int, default=10, help="Refine between last passing and first failing levels; 0 disables")
    result.add_argument("--soak-seconds", type=float, default=0, help="Extra validation at recommended capacity for every requested case")
    result.add_argument("--safety-factor", type=float, default=.8)
    result.add_argument("--browser-clients", type=int, default=3, help="Full browser clients, included in --players; 0 means server-only")
    result.add_argument("--profiles", default="desktop,mobile-landscape,mobile-portrait", help="Browser profiles, cycled when needed; first is the density reference")
    result.add_argument("--browser-channel", choices=("chrome", "msedge"))
    result.add_argument("--browser-executable", type=Path)
    result.add_argument("--headed", action="store_true", help="Show interactive browser windows")
    result.add_argument("--startup-timeout", type=float, default=180)
    result.add_argument("--output", type=Path, default=Path.cwd() / "benchmark-results" / datetime.now().strftime("combat-%Y%m%d-%H%M%S"), help="Report directory (default: ./benchmark-results/combat-TIMESTAMP)")
    result.add_argument("--fail-on-regression", action="store_true", help="Exit 1 if a case fails or is invalid; otherwise capacity discovery exits 0")
    result.add_argument("--worker", type=Path, help=argparse.SUPPRESS)


def run(arguments, command):
    if arguments.worker:
        from .server import run_worker
        run_worker(arguments.worker)
        return 0
    arguments.scenarios = list(dict.fromkeys(arguments.scenarios.split(",")))
    arguments.profiles = arguments.profiles.split(",")
    if any(name not in ("open", "obstacles", "effects", "march") for name in arguments.scenarios):
        command.error("Unknown scenario")
    if any(name not in ("desktop", "mobile-landscape", "mobile-portrait") for name in arguments.profiles):
        command.error("Unknown browser profile")
    if not 0 <= arguments.browser_clients <= arguments.players:
        command.error("--browser-clients must be between 0 and --players")
    if arguments.levels != sorted(arguments.levels) or not arguments.levels:
        command.error("--levels must be non-negative, unique and increasing")
    durations = (arguments.warmup, arguments.seconds, arguments.soak_seconds, arguments.startup_timeout, arguments.safety_factor)
    if not all(math.isfinite(value) for value in durations) or arguments.warmup < 0 or arguments.seconds <= 0 or arguments.repeats < 1 or arguments.refine_step < 0 or arguments.soak_seconds < 0 or arguments.startup_timeout <= 0 or not 0 < arguments.safety_factor <= 1:
        command.error("Invalid duration, repetition, refinement or safety-factor setting")
    if arguments.soak_seconds and arguments.soak_seconds < 30:
        command.error("--soak-seconds must be 0 or at least 30")
    try:
        from .runner import run
        return asyncio.run(run(arguments))
    except KeyboardInterrupt:
        print("Interrupted. Completed cases remain in the output directory.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Benchmark failed: {error}", file=sys.stderr)
        print("Install dependencies with: uv sync --frozen --group benchmark", file=sys.stderr)
        print("Install Chromium with: uv run --group benchmark python -m playwright install chromium", file=sys.stderr)
        return 2
