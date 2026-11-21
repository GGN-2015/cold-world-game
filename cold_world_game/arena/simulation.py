"""An isolated, deterministic fight on open ground."""

import math
from itertools import takewhile

from ..actions import GameError
from ..constants import (
    BACKPACK_STACK_LIMITS,
    DEFAULT_VIEWPORT,
    EXPLOSIVE_WEAPONS,
    GUNS,
    ITEM_KINDS,
    MAX_COINS,
    MAX_HUNGER,
    MELEE_WEAPONS,
    STACK_LIMITS,
    THROWABLE_WEAPONS,
    TICK_RATE,
)
from ..models import Controls, Item, Monster, Player, Structure, identifier_scope
from ..wildlife import MONSTER_TYPES, OUTDOOR_FEATURES
from ..world import World
from .ai import ArenaAI
from .perception import can_observe

WAVES = {
    "none": (),
    "low": ("small",),
    "medium": ("small", "small", "stalker"),
    "high": ("small", "small", "stalker", "fast", "armored", "crawler"),
}
SPAWN_POINTS = ((6, 0), (8, -3), (8, 3), (6, 5), (10, 0), (6, -5))
WEAPONS = tuple(sorted(GUNS.keys() | MELEE_WEAPONS.keys() | EXPLOSIVE_WEAPONS.keys() | THROWABLE_WEAPONS.keys())) + ("mounted_gun",)
TERRAIN = ("wall", "fence", "door", "floor", "tree", "campfire", "mounted_gun")
STRATEGIES = ("adaptive", "hold", "kite")
MAX_ACTIVE_MONSTERS = 64
SETUP_ACTIONS = ("equip", "player", "tile", "spawn", "spawning", "clear", "strategy")
TIME_LIMIT = 45
FINISHED_STATUSES = frozenset({"cleared", "downed", "time_limit", "weapons_depleted", "stopped"})


def number(value, minimum, maximum, *, integer=False):
    if type(value) not in ((int,) if integer else (int, float)) or not minimum <= value <= maximum:
        raise GameError("arena_edit", "A number is outside the allowed range")
    return value


def validate_config(value):
    if not isinstance(value, dict) or not {"weapon", "intensity"} <= value.keys() or value.keys() - {
        "weapon", "intensity", "duration", "seed", "editable", "strategy", "terrain", "setup",
    }:
        raise GameError("arena_config", "Choose one weapon and a monster intensity")
    weapon, intensity = value["weapon"], value["intensity"]
    if not isinstance(weapon, str) or weapon not in WEAPONS or not isinstance(intensity, str) or intensity not in WAVES:
        raise GameError("arena_config", "Unknown weapon or monster intensity")
    strategy, terrain, editable = value.get("strategy", "adaptive"), value.get("terrain", "open"), value.get("editable", False)
    if strategy not in STRATEGIES or terrain not in ("open", "cover", "forest") or type(editable) is not bool:
        raise GameError("arena_config", "Unknown arena setup")
    setup = value.get("setup", [])
    if not isinstance(setup, list) or any(not isinstance(edit, dict) or edit.get("action") not in SETUP_ACTIONS for edit in setup):
        raise GameError("arena_config", "Invalid opening edits")
    return {"weapon": weapon, "intensity": intensity, "strategy": strategy, "terrain": terrain, "editable": editable,
            "seed": number(value.get("seed", 45), 0, 2 ** 32 - 1, integer=True),
            "duration": number(value.get("duration", TIME_LIMIT), 1, 3600, integer=True), "setup": setup}


class ArenaStorage:
    """The fight lasts a single session and has no world save."""

    def load(self):
        return None

    def save(self, state):
        pass

    def close(self):
        pass


class ArenaWorld(World):
    def __init__(self, config):
        super().__init__(ArenaStorage(), seed=config["seed"])
        self.next_save = math.inf
        player = Player("arena-ai", 0.0, 0.0)
        self.players[player.id] = player
        self.online.add(player.id)
        self.controls[player.id] = Controls(aim_x=1.0, view_width=DEFAULT_VIEWPORT[0], view_height=DEFAULT_VIEWPORT[1])
        if config["weapon"] == "mounted_gun":
            self.add_structure(Structure("mounted_gun", 0, 0, id="arena-mounted-gun", ammo=OUTDOOR_FEATURES["mounted_gun"]["ammo"]))
        else:
            player.inventory[0] = Item.create(config["weapon"])
        for index, (kind, point) in enumerate(zip(WAVES[config["intensity"]], SPAWN_POINTS)):
            identifier = f"arena-monster:{index}"
            self.add_monster(kind, *point, identifier)
        for x, y, kind in {
            "open": (),
            "cover": ((3, -2, "wall"), (3, -1, "wall"), (3, 0, "door"), (3, 1, "fence")),
            "forest": ((3, -2, "tree"), (4, 0, "tree"), (4, 1, "tree"), (2, 3, "tree")),
        }[config["terrain"]]:
            self.add_structure(Structure(kind, x, y))

    def add_monster(self, kind, x, y, identifier):
        self.monsters[identifier] = Monster(x, y, id=identifier, big=kind == "big", fast=kind == "fast",
                                             species="small" if kind in {"big", "fast"} else kind, hp=MONSTER_TYPES[kind]["hp"])

    def generate_chunk(self, chunk_x, chunk_y):
        point = chunk_x, chunk_y
        if point not in self.chunks:
            self.touch_terrain()
            self.chunks.add(point)
            self.chunk_versions[point] = 1

    def input_expired(self, controls):
        return False

    def update_player_temperature(self, player, seconds):
        pass

    def drain_hunger(self, player, seconds):
        pass

    def spawn_monster(self):
        pass

    def monster_activity(self):
        return False, None

    def monster_perceives(self, monster, player):
        return can_observe(monster, player)

    def set_monster_target(self, monster, player):
        if self.monster_perceives(monster, player):
            super().set_monster_target(monster, player)

    def pickup(self, player):
        pass

    def drop_item(self, item, x, y, dropped_by=None):
        pass

    def fire_mounted_gun(self, player, controls, structure):
        super().fire_mounted_gun(player, controls, structure)
        if not structure.ammo:
            self.leave_empty_mounted_gun(player, controls, structure)


class Simulation:
    def __init__(self, config):
        self.config = validate_config(config)
        self.serial = 0
        with identifier_scope(self.next_identifier):
            self.world = ArenaWorld(self.config)
        self.ai = ArenaAI(self.config["strategy"])
        self.status = "paused" if self.config["editable"] else "running"
        self.kills = 0
        self.spawned = len(self.world.monsters)
        self.player_id = "arena-ai"
        self.spawning = None
        self.next_wave = math.inf
        self.notes = []
        self.last_decision = None
        self.opening = []

    def next_identifier(self):
        self.serial += 1
        return f"arena:{self.serial}"

    def step(self):
        if self.status != "running":
            return
        previous_sequence = self.world.event_sequence
        with identifier_scope(self.next_identifier):
            if self.spawning and self.world.elapsed + 1e-9 >= self.next_wave:
                rule = self.spawning
                count = min(rule["count"], rule["cap"] - len(self.world.monsters))
                if count > 0:
                    spawned = self.spawn(rule["kind"], count)
                    self.notes.append({"type": "wave", "kind": rule["kind"], "spawned": spawned})
                self.next_wave += rule["interval"]
            self.ai.step(self.world, self.player_id)
            trace = self.ai.trace
            decision = tuple(trace.get(key) for key in ("decision", "target", "weapon", "equipment_action"))
            if decision != self.last_decision or "attack_result" in trace or "attack_error" in trace:
                self.notes.append({"type": "decision", **trace})
                self.last_decision = decision
            self.world.tick(1 / TICK_RATE)
        recent = takewhile(lambda event: event["id"] > previous_sequence, reversed(self.world.events))
        self.kills += sum(event["type"] == "death" and event.get("source") == self.player_id for event in recent)
        player = self.world.players[self.player_id]
        if self.world.tick_number >= self.config["duration"] * TICK_RATE:
            self.status = "time_limit"
        elif player.temperature < 5:
            self.status = "paused" if self.config["editable"] else "downed"
            self.notes.append({"type": "downed"})
        elif self.config["editable"]:
            return
        elif not self.world.monsters:
            self.status = "cleared"
        elif not self.ai.armed(self.world, player):
            in_flight = any(shot.owner == self.player_id for shot in self.world.projectiles.values())
            ongoing = any(monster.impaled or monster.next_burn > 0 for monster in self.world.monsters.values())
            if not in_flight and not ongoing:
                self.status = "weapons_depleted"

    def spawn(self, kind, count, point=None):
        player = self.world.players[self.player_id]
        x, y = point if point is not None else (player.x, player.y)
        self.world.ensure_terrain(x, y)
        created = []
        for index in range(count):
            for attempt in range(24):
                angle = (index + attempt * .618) * math.tau / count
                radius = (0 if index == 0 and attempt == 0 else 1.1 + attempt * .4) if point is not None else 6 + attempt * .4
                px, py = x + math.cos(angle) * radius, y + math.sin(angle) * radius
                if math.hypot(px - player.x, py - player.y) >= 1 and self.world.can_stand(px, py):
                    identifier = self.next_identifier()
                    self.world.add_monster(kind, px, py, identifier)
                    created.append({"id": identifier, "x": round(px, 2), "y": round(py, 2)})
                    break
        self.spawned += len(created)
        return created

    def control(self, command):
        action = command.get("action")
        world = self.world
        player = world.players[self.player_id]
        if action in ("pause", "resume", "stop"):
            if action == "resume" and player.temperature < 5:
                raise GameError("arena_edit", "Raise the player's temperature before resuming")
            self.status = {"pause": "paused", "resume": "running", "stop": "stopped"}[action]
        elif action == "equip":
            storage = command.get("storage")
            if storage not in ("inventory", "backpack"):
                raise GameError("arena_edit", "Unknown storage")
            slots = getattr(player, storage)
            slot = number(command.get("slot"), 0, len(slots) - 1, integer=True)
            kind = command.get("kind")
            if kind is None:
                slots[slot] = None
            else:
                if not isinstance(kind, str) or kind not in ITEM_KINDS:
                    raise GameError("arena_edit", "Unknown item")
                limits = BACKPACK_STACK_LIMITS if storage == "backpack" else STACK_LIMITS
                count = number(command.get("count", 1), 1, limits.get(kind, 1), integer=True)
                with identifier_scope(self.next_identifier):
                    item = Item.create(kind, count)
                if command.get("remaining") is not None:
                    field = "ammo" if item.ammo is not None else "uses"
                    remaining = number(command["remaining"], 0, getattr(item, field) or 0, integer=True)
                    if getattr(item, field) is not None:
                        setattr(item, field, remaining)
                slots[slot] = item
            if storage == "inventory" and slot == player.selected:
                world.controls[player.id].stop_attack()
        elif action == "player":
            temperature = number(command.get("temperature", player.temperature), 0, 36)
            hunger = number(command.get("hunger", player.hunger), 0, MAX_HUNGER)
            money = number(command.get("money", player.money), 0, MAX_COINS, integer=True)
            x = number(command.get("x", player.x), -500, 500)
            y = number(command.get("y", player.y), -500, 500)
            if (x, y) != (player.x, player.y):
                world.ensure_terrain(x, y)
                if not world.can_stand(x, y, player_id=player.id):
                    raise GameError("arena_edit", "The player cannot stand on that tile")
                world.controls[player.id].seat = None
            player.temperature, player.hunger, player.money, player.x, player.y = temperature, hunger, money, x, y
        elif action == "tile":
            x, y = (number(command.get(axis), -500, 500, integer=True) for axis in ("x", "y"))
            kind = command.get("kind")
            if kind is not None and kind not in TERRAIN:
                raise GameError("arena_edit", "Unknown terrain tile")
            with identifier_scope(self.next_identifier):
                tile = Structure(kind, x, y) if kind else None
            if tile and tile.solid and any(abs(x - body.x) < .85 and abs(y - body.y) < .85
                                            for body in (player, *world.monsters.values())):
                raise GameError("arena_edit", "A solid tile cannot overlap a player or monster")
            if kind == "mounted_gun":
                tile.ammo = number(command.get("ammo", OUTDOOR_FEATURES[kind]["ammo"]), 0, 1000, integer=True)
            elif kind == "campfire":
                tile.burn_remaining = 60
            current = world.structure_at(x, y)
            if current:
                if world.controls[player.id].seat == current.id:
                    world.controls[player.id].seat = None
                world.remove_structure(current)
            if tile:
                world.add_structure(tile)
        elif action in ("spawn", "spawning"):
            kind = command.get("kind")
            if not isinstance(kind, str) or kind not in MONSTER_TYPES:
                raise GameError("arena_edit", "Unknown monster")
            count = number(command.get("count"), 0 if action == "spawning" else 1, MAX_ACTIVE_MONSTERS, integer=True)
            if action == "spawn":
                point = tuple(number(command.get(axis), -500, 500) for axis in ("x", "y")) if "x" in command or "y" in command else None
                return self.spawn(kind, min(count, MAX_ACTIVE_MONSTERS - len(world.monsters)), point)
            interval = number(command.get("interval"), .5, 300)
            cap = number(command.get("cap"), 1, MAX_ACTIVE_MONSTERS, integer=True)
            self.spawning = {"kind": kind, "count": count, "interval": interval, "cap": cap} if count else None
            self.next_wave = world.elapsed + interval
        elif action == "clear":
            world.monsters.clear()
            world.projectiles.clear()
        elif action == "strategy":
            if command.get("strategy") not in STRATEGIES:
                raise GameError("arena_edit", "Unknown strategy")
            self.ai.strategy = command["strategy"]
        else:
            raise GameError("arena_edit", "Unknown arena action")
        return None

    def apply(self, writer, command):
        try:
            result = self.control(command)
        except GameError as error:
            writer.note({"type": "edit", "command": command, "accepted": False, "error": error.code})
            raise
        writer.note({"type": "edit", "command": command, "accepted": True, "result": result})
        if self.world.tick_number == 0 and command.get("action") in SETUP_ACTIONS:
            self.opening.append(command)

    def restore_opening(self, writer):
        for command in self.config["setup"]:
            self.apply(writer, command)

    def capture(self, writer):
        for note in self.notes:
            writer.note(note)
        self.notes.clear()
        frame = self.snapshot()
        writer.append(frame["seconds"], frame["state"], aim=frame["aim"], decision=frame["decision"], trace=frame["trace"])
        return frame

    def snapshot(self):
        state = self.world.snapshot(self.player_id)
        state["paused"] = self.status != "running"
        controls = self.world.controls[self.player_id]
        mounted = self.world.seated_structure(controls) or self.world.structures.get("arena-mounted-gun")
        return {"type": "state", "status": self.status, "seconds": self.world.tick_number / TICK_RATE,
                "alive": len(self.world.monsters), "kills": self.kills, "spawned": self.spawned,
                "mounted_ammo": mounted.ammo if mounted else None,
                "decision": self.ai.decision, "trace": self.ai.trace, "aim": [controls.aim_x, controls.aim_y],
                "strategy": self.ai.strategy, "spawning": self.spawning, "state": state}

    def close(self):
        self.world.close(save=False)
