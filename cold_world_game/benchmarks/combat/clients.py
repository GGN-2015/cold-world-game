import asyncio
from collections import Counter
import json
import math
import time

from websockets.asyncio.client import connect

from .metrics import Samples
from .protocol import State
from .control import combat_target, formation, steer


class CommandError(Exception):
    pass


class Bot:
    def __init__(self, index, url, password, latency_ms=0):
        self.index = index
        self.identifier = f"bench-{index:02d}"
        self.url = url
        self.password = password
        self.latency_ms = latency_ms
        self.state = State()
        self.sequence = 0
        self.pending = {}
        self.socket = None
        self.receiver = None
        self.tasks = []
        self.measuring = False
        self.mode = None
        self.fatal_errors = []
        self.reset_metrics()

    def reset_metrics(self):
        self.samples = {}
        self.counters = Counter()
        self.last_state = None
        self.bytes = 0

    def observe(self, name, value):
        if self.measuring:
            self.samples.setdefault(name, Samples()).add(value)

    async def open(self):
        self.socket = await connect(self.url.replace("http://", "ws://") + "/ws", proxy=None, max_size=32 * 1024 ** 2, ping_interval=None, open_timeout=30, close_timeout=2)
        await self.send("join", player_id=self.identifier, password=self.password, quiet_inputs=True, client_movement=False, player_roster=True, state_deltas=True, procedural_terrain=1, compact_state=1)
        message = self.state.decode(await asyncio.wait_for(self.socket.recv(), 30))
        if message.get("type") != "welcome":
            raise RuntimeError(f"{self.identifier}: {message}")
        self.state.apply(message)
        self.receiver = asyncio.create_task(self.receive())

    async def send(self, kind, **fields):
        await self.socket.send(json.dumps({"type": kind, **fields}, separators=(",", ":")))

    async def command(self, kind, **fields):
        self.sequence += 1
        sequence = self.sequence
        future = asyncio.get_running_loop().create_future()
        self.pending[sequence] = future, time.perf_counter(), kind
        try:
            await self.send(kind, seq=sequence, **fields)
            return await asyncio.wait_for(future, 8)
        finally:
            self.pending.pop(sequence, None)

    async def receive(self):
        try:
            async for raw in self.socket:
                now = time.perf_counter()
                if self.measuring:
                    self.bytes += len(raw.encode() if isinstance(raw, str) else raw)
                message = self.state.decode(raw)
                if message["type"] == "delta":
                    self.state.apply(message)
                    if self.last_state is not None:
                        self.observe("state_gap_ms", (now - self.last_state) * 1000)
                    self.last_state = now
                elif message["type"] in ("ack", "error"):
                    pending = self.pending.get(message.get("seq"))
                    if pending:
                        future, began, kind = pending
                        self.observe("command_rtt_ms", (now - began) * 1000)
                        if kind == "ping":
                            self.observe("ping_rtt_ms", (now - began) * 1000)
                        if message["type"] == "error":
                            if self.measuring:
                                self.counters["error_" + message["code"]] += 1
                            if not future.done():
                                future.set_exception(CommandError(message["code"]))
                        else:
                            if self.measuring:
                                self.counters["completed_" + kind] += 1
                            if not future.done():
                                future.set_result(message["result"])
                    elif message["type"] == "error" and message.get("code") in ("rate_limited", "unauthorized"):
                        raise RuntimeError(message["code"])
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.fatal_errors.append(str(error))
        finally:
            for future, began, kind in self.pending.values():
                if not future.done():
                    future.set_exception(ConnectionError("Benchmark connection closed"))

    async def prepare(self, epoch):
        deadline = time.monotonic() + 10
        while self.state.value.get("movement", {}).get("teleport_epoch") != epoch:
            if self.receiver.done() or time.monotonic() > deadline:
                raise RuntimeError(f"{self.identifier}: reset snapshot did not arrive")
            await asyncio.sleep(.02)

    def start(self, scenario, target, started):
        self.started = started
        self.scenario = scenario
        self.target_count = target
        self.attacking = False
        self.mode = None
        self.tasks = [asyncio.create_task(self.drive()), asyncio.create_task(self.workload()), asyncio.create_task(self.heartbeat())]

    async def drive(self):
        deadline = time.monotonic()
        last_attack = 0
        try:
            while True:
                elapsed = time.monotonic() - self.started
                player = self.state.value["you"]
                if not self.mode:
                    own = self.state.entities.get("players", {}).get(self.identifier, {})
                    move = steer((player["x"], player["y"]), (own.get("velocity_x", 0), own.get("velocity_y", 0)), formation(self.index, self.scenario, elapsed), speed=own.get("move_speed", 4), delay=self.latency_ms / 2000 + .1)
                    item = player["inventory"][player["selected"]]
                    target = combat_target(player, self.state.entities.get("monsters", {}).values(), self.state.entities.get("players", {}).values(), item["kind"] if item else None) if self.target_count and player["selected"] == 0 else None
                    aim = [target["x"], target["y"]] if target else [player["x"] + 2, player["y"]]
                    await self.send("input", move=move, aim=aim, target_id=target["id"] if target else None, viewport=[32, 20])
                    interval = .6 if item and item["kind"] in ("axe", "ice_staff", "flame_staff") else 1.1
                    if target is None and self.attacking:
                        await self.send("attack", pressed=False)
                        self.attacking = False
                    if target is not None and (not self.attacking or elapsed - last_attack >= interval):
                        if not item or item["kind"] != "rifle":
                            await self.send("attack", pressed=False)
                        await self.send("attack", pressed=True)
                        self.attacking = True
                        last_attack = elapsed
                else:
                    await self.send("input", move=[0, 0], aim=self.mode)
                deadline += .1
                self.observe("driver_lag_ms", max(0, time.monotonic() - deadline) * 1000)
                await asyncio.sleep(max(0, deadline - time.monotonic()))
                if time.monotonic() - deadline > .3:
                    deadline = time.monotonic()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.fatal_errors.append(f"drive: {error}")

    async def heartbeat(self):
        try:
            while True:
                await self.command("ping")
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.fatal_errors.append(f"heartbeat: {error}")

    async def workload(self):
        await asyncio.sleep(2 + self.index * .2)
        while True:
            try:
                player = self.state.value["you"]
                self.mode = [player["x"] + 1, player["y"]]
                await self.command("stop")
                self.attacking = False
                item = player["inventory"][9]
                if item and player["backpack"][0] is None:
                    await self.command("ui", open=True)
                    moved = await self.command("transfer", **{"from": {"kind": "inventory", "slot": 9}, "to": {"kind": "backpack", "slot": 0}, "item_id": item["id"]})
                    await self.command("transfer", **{"from": {"kind": "backpack", "slot": 0}, "to": {"kind": "inventory", "slot": 9}, "item_id": moved["item_id"]})
                    await self.command("ui", open=False)
                if self.index % 4 == 0:
                    player = self.state.value["you"]
                    point = [math.floor(player["x"] + .5) - 2, math.floor(player["y"] + .5)]
                    self.mode = point
                    await self.command("select", slot=8)
                    placed = await self.command("place", x=point[0], y=point[1])
                    await self.command("select", slot=1)
                    await self.command("input", move=[0, 0], aim=point, target_id=placed["id"])
                    await self.command("attack", pressed=True, shift=True)
                    await asyncio.sleep(1.2)
                    await self.command("attack", pressed=False)
            except CommandError:
                pass
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.fatal_errors.append(f"workload: {error}")
                return
            finally:
                try:
                    await self.command("stop")
                    await self.command("ui", open=False)
                    await self.command("select", slot=0)
                except (CommandError, ConnectionError, TimeoutError):
                    pass
                finally:
                    self.attacking = False
                    self.mode = None
            await asyncio.sleep(7)

    async def pause(self):
        self.measuring = False
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []
        if self.receiver and not self.receiver.done():
            try:
                await self.command("stop")
                await self.command("ui", open=False)
            except (CommandError, ConnectionError, TimeoutError):
                pass

    def report(self):
        return {"id": self.identifier, "kind": "protocol-bot", "movement": "server-authoritative", "bytes_received": self.bytes, "samples": {name: values.summary() for name, values in self.samples.items()}, "counters": dict(self.counters), "fatal_errors": self.fatal_errors, "connected": bool(self.receiver and not self.receiver.done())}

    async def close(self):
        try:
            await self.pause()
        finally:
            if self.socket:
                await self.socket.close()
            if self.receiver:
                self.receiver.cancel()
                await asyncio.gather(self.receiver, return_exceptions=True)
