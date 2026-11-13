import asyncio
from collections import defaultdict
from datetime import datetime, timezone
import itertools
import json
import math
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import tempfile
import time
from urllib.request import ProxyHandler, Request, build_opener

import psutil

from .browser import Observer
from .clients import Bot
from .proxy import LatencyProxy


HTTP = build_opener(ProxyHandler({}))


class Control:
    def __init__(self, port, token):
        self.url = f"http://127.0.0.1:{port}"
        self.token = token

    async def call(self, path, payload=None, timeout=10):
        def request():
            body = json.dumps(payload).encode() if payload is not None else None
            message = Request(self.url + "/__benchmark/" + path, data=body, headers={"Content-Type": "application/json", "X-Benchmark-Token": self.token}, method="POST" if body is not None else "GET")
            with HTTP.open(message, timeout=timeout) as response:
                return json.load(response)

        return await asyncio.to_thread(request)


class Worker:
    def __init__(self, arguments, seed, output):
        self.arguments, self.seed, self.output = arguments, seed, output
        self.directory = tempfile.TemporaryDirectory(prefix="cold-combat-capacity-")
        self.control = None

    async def start(self):
        folder = Path(self.directory.name)
        self.config = {"seed": self.seed, "players": self.arguments.players, "radius": self.arguments.radius, "password": secrets.token_urlsafe(20), "token": secrets.token_urlsafe(24), "save_path": str(folder / "save"), "ready_path": str(folder / "ready.json")}
        config_path = folder / "config.json"
        config_path.write_text(json.dumps(self.config), encoding="utf-8")
        self.log_path = self.output / f"worker-{self.seed}-{time.time_ns()}.log"
        self.log = self.log_path.open("w", encoding="utf-8")
        self.process = subprocess.Popen([sys.executable, "-m", "cold_world_game", "test", "combat", "--worker", str(config_path)], stdout=self.log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        deadline = time.monotonic() + self.arguments.startup_timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"Benchmark server exited; see {self.log_path}")
            try:
                self.ready = json.loads(Path(self.config["ready_path"]).read_text(encoding="utf-8"))
                self.control = Control(self.ready["port"], self.config["token"])
                await self.control.call("stats")
                return self
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                await asyncio.sleep(.2)
        raise TimeoutError(f"Benchmark server startup exceeded {self.arguments.startup_timeout}s; see {self.log_path}")

    async def close(self):
        process = getattr(self, "process", None)
        if process and process.poll() is None:
            if self.control:
                try:
                    await self.control.call("shutdown", {}, timeout=2)
                except Exception:
                    pass
            try:
                await asyncio.to_thread(process.wait, timeout=8)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    await asyncio.to_thread(process.wait, timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    await asyncio.to_thread(process.wait)
        if hasattr(self, "log"):
            self.log.close()
        await asyncio.to_thread(self.directory.cleanup)


def metric(samples, name, field="p95", default=0):
    return samples.get(name, {}).get(field) if samples.get(name, {}).get(field) is not None else default


def evaluate(result, arguments):
    samples = result["server"]["metrics"]["samples"]
    counters = result["server"]["metrics"]["counters"]
    server_invalid, scene_invalid, server_failures, browser_failures = [], [], [], []
    if result["server"]["fault"]:
        server_invalid.append("server_fault")
    if result["server"]["online"] != arguments.players or metric(samples, "standing_online", "min") < arguments.players:
        server_invalid.append("not_all_players_active")
    if metric(samples, "population", "p05") < result["monsters"] * .9:
        server_invalid.append("insufficient_active_monster_density")
    for client in result["clients"]:
        if client["fatal_errors"] or not client["connected"]:
            server_invalid.append(client["id"] + ":client_error_or_disconnect")
        if metric(client["samples"], "driver_lag_ms") > 50:
            server_invalid.append(client["id"] + ":load_generator_overloaded")
    if result["monsters"] == 0 and (counters.get("event_shot") or counters.get("friendly_fire_hits")):
        server_invalid.append("baseline_has_unexpected_combat")
    checks = (("tick_ms", "p95", 35), ("tick_ms", "p99", 50), ("simulation_lock_wait_ms", "p99", 10), ("command_ms", "p95", 50), ("command_ms", "p99", 100), ("pathless_wait_ms", "p95", 500))
    for name, percentile, limit in checks:
        if metric(samples, name, percentile) > limit:
            server_failures.append(f"{name}.{percentile}>{limit}")
    tps = result["server"]["metrics"]["worst_10s_ticks_per_second"]
    if tps is not None and tps < 19:
        server_failures.append("worst_10s_ticks_per_second<19")
    if result["seconds"] >= 30 and result["server"]["metrics"]["ticks_per_second"] < 19:
        server_failures.append("ticks_per_second<19")
    if result["server"]["oldest_pathless_wait_ms"] > 1000:
        server_failures.append("unresolved_pathless_wait>1000ms")
    browsers = [client for client in result["clients"] if client["kind"] == "browser"]
    for index, client in enumerate(browsers):
        values = client["samples"]
        if metric(values, "frame_ms", "count") < result["seconds"] * 5:
            scene_invalid.append(client["id"] + ":missing_browser_frames")
        if index == 0 and metric(values, "visible_monsters", "p05") < result["monsters"] * .9:
            scene_invalid.append(client["id"] + ":insufficient_visible_monster_density")
        if index == 0 and metric(values, "visible_players", "p05") < arguments.players:
            scene_invalid.append(client["id"] + ":players_not_all_visible")
        mobile = client["profile"].startswith("mobile")
        for name, percentile, limit in (("frame_ms", "p95", 33 if mobile else 20), ("frame_ms", "p99", 50 if mobile else 33), ("local_feedback_ms", "p95", 50 if mobile else 33), ("state_gap_ms", "p95", 150), ("state_gap_ms", "p99", 200)):
            if metric(values, name, percentile) > limit:
                browser_failures.append(f'{client["id"]}:{name}.{percentile}>{limit}')
        if metric(values, "long_task_ms", "max") > 100:
            browser_failures.append(client["id"] + ":main_thread_task>100ms")
        if client.get("counters", {}).get("unexpected_jumps", 0):
            browser_failures.append(client["id"] + ":unexpected_movement_jump")
        if index == 0 and result["monsters"] > 0 and metric(values, "local_feedback_ms", "count") == 0:
            scene_invalid.append(client["id"] + ":missing_local_attack_feedback")
    if result["monsters"] > 0 and result["seconds"] >= 30 and not counters.get("event_hit"):
        server_invalid.append("no_real_combat_hits")
    smoke = min(result["seconds"], result["requested_seconds"]) < 30
    normal = "smoke" if smoke else "pass"
    server_status = "invalid" if server_invalid else "fail" if server_failures else normal
    browser_status = "not_measured" if not browsers else "invalid" if scene_invalid or server_invalid else "fail" if browser_failures else normal
    invalid = server_invalid + scene_invalid
    status = "invalid" if invalid else "fail" if server_failures or browser_failures else "smoke" if smoke else "pass"
    coverage = ("event_death", "event_place", "event_break") if result["monsters"] else ("event_place", "event_break")
    return {"status": status, "server_status": server_status, "browser_status": browser_status, "invalid_reasons": invalid, "server_invalid_reasons": server_invalid, "scene_invalid_reasons": scene_invalid, "server_failures": server_failures, "browser_failures": browser_failures, "browser_verified": bool(browsers) and browser_status not in ("invalid", "smoke"), "friendly_fire_hits": counters.get("friendly_fire_hits", 0), "combat_events": {key: value for key, value in counters.items() if key.startswith("event_")}, "coverage_warnings": [name for name in coverage if not counters.get(name)]}


async def stage(worker, clients, target, scenario, latency, repeat, arguments, seconds=None):
    seconds = seconds if seconds is not None else arguments.seconds
    phase = await worker.control.call("reset", {"target": target, "scenario": scenario})
    await asyncio.gather(*(client.prepare(phase["epochs"][client.identifier]) for client in clients))
    for client in clients:
        client.start(scenario, target, phase["started"])
    try:
        await asyncio.sleep(arguments.warmup)
        for client in clients:
            if isinstance(client, Observer):
                await client.measure()
            else:
                client.reset_metrics()
                client.measuring = True
        await worker.control.call("measure", {})
        began = time.monotonic()
        monitor = []
        aborted = None
        while time.monotonic() - began < seconds:
            await asyncio.sleep(min(1, max(.01, seconds - (time.monotonic() - began))))
            state = await worker.control.call("stats")
            monitor.append({"at": time.monotonic() - began, "tps": state["metrics"]["ticks_per_second"], "rss_mib": state["rss_mib"], "cpu_percent": state["cpu_percent"], "host_cpu_percent": psutil.cpu_percent(), "population": state["population"], "path_jobs": state["path_jobs"], "oldest_pathless_wait_ms": state["oldest_pathless_wait_ms"], "persistence": state["persistence"]})
            if state["fault"] or psutil.virtual_memory().percent > 92 or time.monotonic() - began >= 10 and state["metrics"]["ticks_per_second"] < 10:
                aborted = "server_fault_or_emergency_resource_limit"
                break
        await worker.control.call("stop-measure", {})
        for client in clients:
            if isinstance(client, Observer):
                await client.stop_measure()
            else:
                client.measuring = False
        state = await worker.control.call("stats")
        result = {"monsters": target, "scenario": scenario, "seed": worker.seed, "latency_ms": latency, "repeat": repeat, "seconds": state["metrics"]["duration_seconds"], "requested_seconds": seconds, "server": state, "clients": [client.report() for client in clients], "monitor": monitor, "aborted": aborted}
        result["evaluation"] = evaluate(result, arguments)
        if aborted:
            result["evaluation"]["status"] = "invalid"
            result["evaluation"]["server_status"] = "invalid"
            result["evaluation"]["browser_status"] = "invalid" if arguments.browser_clients else "not_measured"
            result["evaluation"]["server_invalid_reasons"].append(aborted)
            result["evaluation"]["invalid_reasons"].append(aborted)
        evaluation = result["evaluation"]
        print(f'{evaluation["status"].upper():7} N={target:<4} {scenario:<9} RTT+{latency:<3} seed={worker.seed} run={repeat} tickP95={metric(state["metrics"]["samples"], "tick_ms"):.1f}ms server={evaluation["server_status"]} browser={evaluation["browser_status"]}', flush=True)
        reasons = evaluation["invalid_reasons"] + evaluation["server_failures"] + evaluation["browser_failures"]
        if reasons:
            print("  Reasons: " + "; ".join(reasons), flush=True)
        return result
    finally:
        for client in clients:
            if isinstance(client, Bot):
                client.measuring = False
        await asyncio.gather(*(client.pause() for client in clients), return_exceptions=True)


async def level(target, arguments, browser, output, report, persist, seconds=None, soak=False):
    results = []
    for seed in arguments.seeds:
        worker = Worker(arguments, seed, output)
        try:
            await worker.start()
            report["server_hardware"] = worker.ready
            for latency in arguments.latency_ms:
                proxy = await LatencyProxy(worker.ready["port"], latency).start()
                clients = []
                try:
                    url = f"http://127.0.0.1:{proxy.port}"
                    print(f"CONNECT RTT+{latency}: {arguments.players} players, including {arguments.browser_clients} browsers", flush=True)
                    for index in range(arguments.players):
                        client = Observer(index, arguments.profiles[index % len(arguments.profiles)], browser, url, worker.config["password"]) if index < arguments.browser_clients else Bot(index, url, worker.config["password"], latency)
                        clients.append(client)
                        await client.open()
                    print(f"CONNECTED RTT+{latency}: {len(clients)} players", flush=True)
                    await asyncio.sleep(.5)
                    for scenario, repeat in itertools.product(arguments.scenarios, range(1, arguments.repeats + 1)):
                        result = await stage(worker, clients, target, scenario, latency, repeat, arguments, seconds)
                        result["soak"] = soak
                        results.append(result)
                        report["results"].append(result)
                        persist()
                finally:
                    await asyncio.gather(*(client.close() for client in clients), return_exceptions=True)
                    await proxy.close()
        finally:
            await worker.close()
    return results


def capacity(report, arguments):
    groups = defaultdict(list)
    for result in report["results"]:
        if not result.get("soak"):
            groups[result["monsters"]].append(result)
    expected = set(itertools.product(arguments.seeds, arguments.latency_ms, arguments.scenarios, range(1, arguments.repeats + 1)))
    complete = {count: results for count, results in groups.items() if len(results) == len(expected) and {(result["seed"], result["latency_ms"], result["scenario"], result["repeat"]) for result in results} == expected and all(min(result["seconds"], result["requested_seconds"]) >= 30 for result in results)}
    passing = [count for count, results in complete.items() if all(result["evaluation"]["status"] == "pass" for result in results)]
    largest = max(passing, default=None)
    server_passing = [count for count, results in complete.items() if all(result["evaluation"]["server_status"] == "pass" for result in results)]
    failures = sorted(count for count, results in complete.items() if all(result["evaluation"]["status"] != "invalid" for result in results) and any(result["evaluation"]["status"] == "fail" for result in results))
    invalid = sorted(count for count, results in groups.items() if any(result["evaluation"]["status"] == "invalid" for result in results))
    safe = max(1, math.floor(largest * arguments.safety_factor / 10) * 10) if largest else None
    baseline = "not_requested"
    baseline_server = "not_requested"
    if 0 in groups:
        if 0 not in complete:
            baseline = baseline_server = "incomplete"
        else:
            baseline = next((status for status in ("invalid", "fail") if any(result["evaluation"]["status"] == status for result in complete[0])), "pass")
            baseline_server = next((status for status in ("invalid", "fail") if any(result["evaluation"]["server_status"] == status for result in complete[0])), "pass")
    if baseline not in ("pass", "not_requested"):
        safe = None
    higher_failures = [count for count in failures if largest is not None and count > largest]
    return {"largest_all_passed": largest, "largest_server_passed": max(server_passing, default=None), "first_failed_level": min(failures, default=None), "first_failed_above_pass": min(higher_failures, default=None), "baseline_status": baseline, "baseline_server_status": baseline_server, "invalid_levels": invalid, "incomplete_levels": sorted(set(groups) - set(complete)), "recommended_with_headroom": safe, "safety_factor": arguments.safety_factor, "upper_bound_found": bool(higher_failures) and baseline in ("pass", "not_requested"), "scope": "primary observer viewport, all requested scenarios/networks/seeds/repetitions" if arguments.browser_clients else "server-only; browser smoothness not verified", "short_runs_are_smoke_only": arguments.seconds < 30, "expected_cases_per_level": len(expected)}


def write_report(output, report):
    path = output / "report.json"
    temporary = output / "report.json.tmp"
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    lines = ["# Combat capacity benchmark", "", f"Status: {report['status']}", "", "All figures apply to the recorded machine, workload and observer viewport. Emulated phones are not physical-device certification.", "", "## Capacity", "", "```json", json.dumps(report.get("capacity", {}), ensure_ascii=False, indent=2), "```", "", "## Cases", "", "| Monsters | Scenario | Added RTT | Seed | Repeat | Result | Server | Browser | Tick P95 ms | Lock P99 ms | Primary frame P95 ms | Visible players P05 | Visible monsters P05 | Friendly hits |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for result in report["results"]:
        primary = next((client for client in result["clients"] if client["kind"] == "browser"), {"samples": {}})
        values = result["server"]["metrics"]["samples"]
        evaluation = result["evaluation"]
        lines.append(f'| {result["monsters"]} | {result["scenario"]} | {result["latency_ms"]} | {result["seed"]} | {result["repeat"]} | {evaluation["status"]} | {evaluation["server_status"]} | {evaluation["browser_status"]} | {metric(values, "tick_ms"):.1f} | {metric(values, "simulation_lock_wait_ms", "p99"):.1f} | {metric(primary["samples"], "frame_ms"):.1f} | {metric(primary["samples"], "visible_players", "p05"):.0f} | {metric(primary["samples"], "visible_monsters", "p05"):.0f} | {evaluation["friendly_fire_hits"]} |')
    lines.extend(["", "## Findings", ""])
    for result in report["results"]:
        evaluation = result["evaluation"]
        reasons = evaluation["invalid_reasons"] + evaluation["server_failures"] + evaluation["browser_failures"]
        if reasons:
            lines.append(f'- N={result["monsters"]}, {result["scenario"]}, RTT+{result["latency_ms"]}, seed={result["seed"]}, run={result["repeat"]}: ' + "; ".join(reasons))
    lines.extend(["", "Per-client frame/feedback/network summaries, invalid reasons, fixture overhead, combat coverage and detailed server components are in report.json.", ""])
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


async def run(arguments):
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "report.json").exists():
        raise ValueError("Output already contains report.json; choose a new output directory")
    report = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(), "arguments": {name: str(value) if isinstance(value, Path) else value for name, value in vars(arguments).items()}, "load_generator": {"platform": platform.platform(), "python": platform.python_version(), "logical_cpus": psutil.cpu_count(), "same_host_as_server": True, "mobile_is_emulated": True}, "fixture": {"disposable_world": True, "production_spawn_cap_bypassed": True, "night_ai_forced_active": True, "simulation_clock_monotonic": True, "normal_damage_collision_drops_and_saves": True, "finite_weapons_resupplied": True, "fixture_time_included_in_tick": True, "no_target_no_combat": True, "formation_uses_teleport_corrections": False}, "results": []}

    def persist():
        report["capacity"] = capacity(report, arguments)
        if report.get("soak_status") in ("running", "fail"):
            report["capacity"]["recommended_with_headroom"] = None
        write_report(output, report)

    playwright = browser = None
    persist()
    try:
        if arguments.browser_clients:
            from playwright.async_api import async_playwright
            playwright = await async_playwright().start()
            options = {"headless": not arguments.headed, "args": ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows"]}
            if arguments.browser_channel:
                options["channel"] = arguments.browser_channel
            if arguments.browser_executable:
                options["executable_path"] = str(arguments.browser_executable)
            browser = await playwright.chromium.launch(**options)
            report["load_generator"]["browser_version"] = browser.version
        previous_pass = None
        first_failure = None
        for target in arguments.levels:
            print(f"LEVEL {target}: {len(arguments.seeds) * len(arguments.latency_ms) * len(arguments.scenarios) * arguments.repeats} cases", flush=True)
            results = await level(target, arguments, browser, output, report, persist)
            if all(result["evaluation"]["status"] == "pass" for result in results):
                previous_pass = target
            elif any(result["evaluation"]["status"] in ("fail", "invalid") for result in results):
                if target == 0 and not any(result["evaluation"]["server_invalid_reasons"] or result.get("aborted") for result in results):
                    print("Baseline did not pass. Continuing diagnostic monster levels; no capacity recommendation will be issued.", flush=True)
                    continue
                first_failure = target
                break
        if previous_pass is not None and first_failure is not None and arguments.refine_step:
            for target in range(previous_pass + arguments.refine_step, first_failure, arguments.refine_step):
                results = await level(target, arguments, browser, output, report, persist)
                if not all(result["evaluation"]["status"] == "pass" for result in results):
                    break
        recommendation = capacity(report, arguments)["recommended_with_headroom"]
        if recommendation and arguments.soak_seconds:
            report["soak_status"] = "running"
            persist()
            soaked = await level(recommendation, arguments, browser, output, report, persist, arguments.soak_seconds, soak=True)
            report["soak_passed"] = all(result["evaluation"]["status"] == "pass" for result in soaked)
            report["soak_status"] = "pass" if report["soak_passed"] else "fail"
        report["status"] = "complete"
        persist()
        if report.get("soak_passed") is False:
            report["capacity"]["recommended_with_headroom"] = None
            write_report(output, report)
        print(f"REPORT {output / 'report.json'}", flush=True)
        print(json.dumps(report["capacity"], ensure_ascii=False, indent=2), flush=True)
        return 1 if arguments.fail_on_regression and any(result["evaluation"]["status"] in ("fail", "invalid") for result in report["results"]) else 0
    except BaseException as error:
        report["status"] = "interrupted" if isinstance(error, (KeyboardInterrupt, asyncio.CancelledError)) else "error"
        report["error"] = f"{type(error).__name__}: {error}"
        persist()
        raise
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()
