import math
import threading
import time
from collections import Counter


class Samples:
    def __init__(self, resolution=0.1):
        self.resolution = resolution
        self.buckets = Counter()
        self.count = 0
        self.total = 0.0
        self.minimum = math.inf
        self.maximum = -math.inf

    def add(self, value):
        if not math.isfinite(value):
            return
        self.buckets[math.ceil(value / self.resolution)] += 1
        self.count += 1
        self.total += value
        self.minimum = min(self.minimum, value)
        self.maximum = max(self.maximum, value)

    def summary(self):
        if not self.count:
            return {"count": 0, "mean": None, "min": None, "max": None, "p05": None, "p50": None, "p95": None, "p99": None}
        result = {"count": self.count, "mean": self.total / self.count, "min": self.minimum, "max": self.maximum}
        cumulative = 0
        pending = [(name, max(1, math.ceil(self.count * fraction))) for name, fraction in (("p05", .05), ("p50", .5), ("p95", .95), ("p99", .99))]
        for bucket, count in sorted(self.buckets.items()):
            cumulative += count
            for name, rank in pending:
                if rank <= cumulative and name not in result:
                    result[name] = min(self.maximum, bucket * self.resolution)
        return result


class Recorder:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = False
        self.reset()

    def reset(self):
        with self.lock:
            self.started = time.monotonic()
            self.finished = None
            self.samples = {}
            self.counters = Counter()
            self.tick_times = []

    def observe(self, name, value):
        if self.active:
            with self.lock:
                self.samples.setdefault(name, Samples()).add(value)

    def count(self, name, amount=1):
        if self.active:
            with self.lock:
                self.counters[name] += amount

    def tick(self):
        if self.active:
            with self.lock:
                self.tick_times.append(time.monotonic())

    def stop(self):
        self.active = False
        with self.lock:
            self.finished = time.monotonic()

    def report(self):
        with self.lock:
            duration = (self.finished or time.monotonic()) - self.started
            times = list(self.tick_times)
            windows = []
            start = 0
            for stop, timestamp in enumerate(times):
                while start < stop and times[start] < timestamp - 10:
                    start += 1
                if timestamp - self.started >= 10:
                    windows.append((stop - start + 1) / 10)
            return {"duration_seconds": duration, "tick_count": len(times), "ticks_per_second": len(times) / max(duration, .001), "worst_10s_ticks_per_second": min(windows, default=None), "samples": {name: values.summary() for name, values in self.samples.items()}, "counters": dict(self.counters), "percentile_resolution": 0.1}


class TimedLock:
    def __init__(self, lock, recorder):
        self.lock = lock
        self.recorder = recorder
        self.local = threading.local()

    def __enter__(self):
        depth = getattr(self.local, "depth", 0)
        started = time.perf_counter()
        self.lock.acquire()
        if not depth:
            elapsed = (time.perf_counter() - started) * 1000
            self.recorder.observe("world_lock_wait_ms", elapsed)
            if threading.current_thread().name == "cold-world-simulation":
                self.recorder.observe("simulation_lock_wait_ms", elapsed)
        self.local.depth = depth + 1
        return self

    def __exit__(self, *exception):
        self.local.depth -= 1
        self.lock.release()


def timed(owner, name, recorder, metric=None):
    original = getattr(owner, name)

    def measured(*arguments, **keywords):
        started = time.perf_counter()
        try:
            return original(*arguments, **keywords)
        finally:
            recorder.observe(metric or name + "_ms", (time.perf_counter() - started) * 1000)

    setattr(owner, name, measured)
    return original
