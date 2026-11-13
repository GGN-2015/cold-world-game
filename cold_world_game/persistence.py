import logging
import threading
import time


LOGGER = logging.getLogger(__name__)


class SaveCoordinator:
    interval = 15.0
    busy_interval = 60.0
    force_interval = 150.0
    maximum_age = 180.0
    failure_message = "Background save is overdue or repeatedly failing; gameplay is paused until saving recovers"

    def __init__(self, world, observe):
        self.world = world
        self.observe = observe
        self.wakeup = threading.Event()
        self.progress = threading.Condition()
        self.saved_generation = world._save_generation
        self.last_saved = time.monotonic()
        self.requested = self.saved_generation
        self.pressure = 0.0
        self.failures = 0
        self.error = None
        self.pending = None
        self.closing = False
        self.closed = False
        self.thread = threading.Thread(target=self.run, name="cold-world-save", daemon=True)

    def start(self):
        self.world._persistence = self
        self.thread.start()

    def observe_load(self, seconds, interval):
        self.pressure = self.pressure * .9 + min(seconds / interval, 2.0) * .1

    def changed(self):
        if self.world._save_generation <= self.saved_generation:
            self.last_saved = time.monotonic()
        self.world._save_generation += 1

    def request(self):
        with self.progress:
            self.requested = max(self.requested, self.world._save_generation)
        self.wakeup.set()

    def check_health(self):
        with self.world.lock:
            dirty = self.world._save_generation > self.saved_generation
            if dirty and time.monotonic() - self.last_saved >= self.maximum_age and self.world.fault is None:
                self.world.fault = self.failure_message
                LOGGER.error(self.failure_message)

    def status(self):
        return {"mode": "background", "dirty": self.world._save_generation > self.saved_generation, "unsaved_seconds": max(0.0, time.monotonic() - self.last_saved) if self.world._save_generation > self.saved_generation else 0.0, "maximum_unsaved_seconds": self.maximum_age, "failures": self.failures, "error": str(self.error) if self.error else None}

    def flush(self, timeout=30):
        with self.world.lock:
            self.changed()
            target = self.world._save_generation
            self.request()
        with self.progress:
            completed = self.progress.wait_for(lambda: self.saved_generation >= target or self.closed, timeout=timeout)
            if self.saved_generation >= target:
                return
            if not completed:
                raise TimeoutError("Timed out waiting for the background save to commit")
            raise OSError("Unable to commit the final world snapshot") from self.error

    def close(self):
        with self.world.lock:
            self.changed()
        with self.progress:
            self.closing = True
        self.wakeup.set()
        self.thread.join()
        if self.error is not None:
            raise OSError("Unable to commit the final world snapshot") from self.error

    def capture(self):
        started = time.perf_counter()
        with self.world.lock:
            batch = self.world.capture_save()
            generation = self.world._save_generation
            captured = time.monotonic()
        self.observe("save_capture_ms", (time.perf_counter() - started) * 1000)
        return batch, generation, captured

    def run(self):
        try:
            while True:
                self.wakeup.wait(.25)
                self.wakeup.clear()
                self.check_health()
                if self.pending is None:
                    with self.progress:
                        requested, closing = self.requested, self.closing
                    age = time.monotonic() - self.last_saved
                    interval = self.busy_interval if self.pressure >= .65 else self.interval
                    due = age >= interval and self.pressure < .9 or age >= self.force_interval
                    if not closing and self.world._save_generation <= self.saved_generation:
                        continue
                    if not closing and requested <= self.saved_generation and not due:
                        continue
                    self.pending = self.capture()
                batch, generation, captured = self.pending
                started = time.perf_counter()
                try:
                    self.world.storage.save(batch)
                except Exception as error:
                    self.error = error
                    self.failures += 1
                    LOGGER.exception("Background world save failed; retaining the complete pending snapshot for retry")
                    if self.failures >= 3:
                        with self.world.lock:
                            if self.world.fault is None:
                                self.world.fault = self.failure_message
                        if self.closing:
                            break
                    self.wakeup.wait(min(2 ** min(self.failures - 1, 3), 5))
                    self.wakeup.clear()
                    continue
                finally:
                    self.observe("background_save_ms", (time.perf_counter() - started) * 1000)
                self.pending = None
                with self.world.lock:
                    self.world.finish_save(batch)
                    if self.world.fault == self.failure_message:
                        self.world.fault = None
                    self.saved_generation = generation
                    self.last_saved = captured
                with self.progress:
                    self.error = None
                    self.failures = 0
                    self.progress.notify_all()
                    if self.closing and self.world._save_generation <= self.saved_generation:
                        break
        except Exception as error:
            self.error = error
            LOGGER.exception("Background save worker stopped unexpectedly")
            with self.world.lock:
                if self.world.fault is None:
                    self.world.fault = self.failure_message
        finally:
            with self.progress:
                self.closed = True
                self.progress.notify_all()
