import asyncio
import math
from pathlib import Path
import time

from .control import formation, steer


PROFILES = {
    "desktop": {"viewport": {"width": 1280, "height": 800}, "device_scale_factor": 1},
    "mobile-landscape": {"viewport": {"width": 844, "height": 390}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True, "user_agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0.0.0 Mobile Safari/537.36"},
    "mobile-portrait": {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True, "user_agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0.0.0 Mobile Safari/537.36"},
}


class Observer:
    def __init__(self, index, profile, browser, url, password):
        self.index, self.profile, self.browser = index, profile, browser
        self.identifier = f"bench-{index:02d}"
        self.url, self.password = url, password
        self.tasks = []
        self.errors = []
        self.mouse_down = False
        self.measuring = False
        self.cached_report = None
        self.context = None
        self.page = None
        self.cdp = None

    async def open(self):
        self.context = await self.browser.new_context(**PROFILES[self.profile], locale="en-US")
        self.page = await self.context.new_page()
        self.page.set_default_timeout(30000)
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        await self.page.add_init_script("Object.defineProperty(document, 'hidden', {get: () => false}); Object.defineProperty(document, 'visibilityState', {get: () => 'visible'});")
        await self.page.goto(self.url, wait_until="networkidle", timeout=90000)
        await self.page.evaluate(Path(__file__).with_name("observer.js").read_text(encoding="utf-8"))
        await self.page.locator("#player-id").fill(self.identifier)
        await self.page.locator("#server-password").fill(self.password)
        await self.page.locator("#join-button").click()
        await self.page.locator("#game-hud").wait_for(state="visible")
        await self.page.keyboard.press("Escape")
        await self.page.wait_for_function("window.combatBenchmark?.connection?.ready && window.combatBenchmark?.renderer?.state")
        self.cdp = await self.context.new_cdp_session(self.page) if self.profile.startswith("mobile") else None

    async def prepare(self, epoch):
        await self.page.wait_for_function("epoch => window.combatBenchmark?.renderer?.state?.movement?.teleport_epoch === epoch", arg=epoch, timeout=10000)

    def start(self, scenario, target, started):
        self.started = started
        self.scenario = scenario
        self.target_count = target
        self.tasks = [asyncio.create_task(self.drive()), asyncio.create_task(self.heartbeat())]

    async def heartbeat(self):
        try:
            while True:
                await self.page.evaluate("window.combatBenchmark.connection.command('ping')")
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.errors.append(f"heartbeat: {error}")

    async def drive(self):
        last_click = -10
        touches_started = False
        try:
            while True:
                info = await self.page.evaluate("window.combatBenchmark.info()")
                if info is None:
                    await asyncio.sleep(.1)
                    continue
                elapsed = time.monotonic() - self.started
                goal = formation(self.index, self.scenario, elapsed)
                movement = steer((info["x"], info["y"]), (info["velocity_x"], info["velocity_y"]), goal, speed=info["move_speed"], delay=.1)
                if self.cdp:
                    aim_x, aim_y = info["target_x"] - info["x"], info["target_y"] - info["y"]
                    aim_magnitude = max(.001, math.hypot(aim_x, aim_y))
                    move, aim = info["touch_move"], info["touch_aim"]
                    points = [{"id": 11, "x": move["x"] + movement[0] * move["radius"], "y": move["y"] + movement[1] * move["radius"]}, {"id": 22, "x": aim["x"] + aim_x / aim_magnitude * aim["radius"], "y": aim["y"] + aim_y / aim_magnitude * aim["radius"]}]
                    await self.cdp.send("Input.dispatchTouchEvent", {"type": "touchMove" if touches_started else "touchStart", "touchPoints": points})
                    touches_started = True
                    await self.page.mouse.move(info["touch_use"]["x"], info["touch_use"]["y"])
                else:
                    horizontal = goal[0] + goal[2] * .2 - info["x"] - info["velocity_x"] * .1
                    vertical = goal[1] + goal[3] * .2 - info["y"] - info["velocity_y"] * .1
                    desired = {"a": horizontal < -.2, "d": horizontal > .2, "w": vertical < -.2, "s": vertical > .2}
                    for key, pressed in desired.items():
                        await (self.page.keyboard.down(key) if pressed else self.page.keyboard.up(key))
                    await self.page.mouse.move(info["screen_x"], info["screen_y"])
                interval = .6 if info["weapon"] in ("axe", "flame_staff", "ice_staff") else 1.1
                if not self.target_count or not info["has_target"]:
                    if self.mouse_down:
                        await self.page.mouse.up()
                        self.mouse_down = False
                elif info["weapon"] == "rifle":
                    if not self.mouse_down:
                        await self.page.mouse.down()
                        self.mouse_down = True
                elif elapsed - last_click >= interval:
                    if self.mouse_down:
                        await self.page.mouse.up()
                    await self.page.mouse.down()
                    self.mouse_down = True
                    if info["weapon"] in ("axe", "flame_staff", "ice_staff", "shotgun", "homing_missile"):
                        await self.page.mouse.up()
                        self.mouse_down = False
                    last_click = elapsed
                await asyncio.sleep(.15)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.errors.append(f"drive: {error}")

    async def measure(self):
        await self.page.evaluate("window.combatBenchmark.start()")
        self.measuring = True

    async def stop_measure(self):
        self.measuring = False
        await self.page.evaluate("window.combatBenchmark.stop()")
        self.cached_report = await self.page.evaluate("window.combatBenchmark.report()")

    async def pause(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []
        if not self.page or self.page.is_closed():
            return
        if self.mouse_down:
            await self.page.mouse.up()
            self.mouse_down = False
        if self.cdp:
            await self.cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        for key in ("w", "a", "s", "d"):
            await self.page.keyboard.up(key)
        await self.page.evaluate("window.combatBenchmark?.connection?.ready ? window.combatBenchmark.connection.command('stop') : null")

    def report(self):
        result = self.cached_report or {"samples": {}, "fatal_errors": [], "connected": False}
        return {**result, "id": self.identifier, "kind": "browser", "profile": self.profile, "fatal_errors": result["fatal_errors"] + self.errors, "mobile_is_emulated": self.profile.startswith("mobile")}

    async def close(self):
        try:
            await self.pause()
        finally:
            if self.context:
                await self.context.close()
