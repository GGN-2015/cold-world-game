import copy
import math
import re
import time

from ..actions import GameError
from ..constants import DAY_SECONDS, DEFAULT_VIEWPORT, INVENTORY_SLOTS, ITEM_KINDS, TICK_RATE
from ..geometry import normalized
from ..models import Controls, Item, Player, Structure, identifier_scope
from ..world import World
from ..wildlife import OUTDOOR_FEATURES
from .ai import AI_TYPES
from .perception import can_observe


DEFAULT_INVENTORY = ["storm_smg", "crowbar"] + [None] * (INVENTORY_SLOTS - 2)
MAX_MOUNTED_AMMO = 1000000
DEFAULT_AMBIENT_TEMPERATURE = -15.0
AMBIENT_TEMPERATURE_RANGE = (-100.0, 100.0)
FINISHED_STATUSES = frozenset({"downed", "time_limit", "weapons_depleted"})


def validate_config(value, max_monsters=256):
    if not isinstance(value, dict):
        raise GameError("arena_config", "Expected an arena configuration")
    seed = value.get("seed", "45")
    if isinstance(seed, bool) or not isinstance(seed, (int, str)) or not re.fullmatch(r"-?[0-9]{1,19}", str(seed)):
        raise GameError("arena_seed", "Seed must be a signed 64-bit integer")
    seed = int(seed)
    if not -(2 ** 63) <= seed < 2 ** 63:
        raise GameError("arena_seed", "Seed must be a signed 64-bit integer")
    limit = value.get("monster_limit", 32)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= max_monsters:
        raise GameError("arena_limit", "Monster limit is outside the server limit")
    inventory = value.get("inventory", DEFAULT_INVENTORY)
    if not isinstance(inventory, list) or len(inventory) != INVENTORY_SLOTS or any(kind is not None and (not isinstance(kind, str) or kind not in ITEM_KINDS) for kind in inventory):
        raise GameError("arena_inventory", "Expected ten valid inventory slots")
    policy = value.get("ai", "bold")
    if not isinstance(policy, str) or policy not in AI_TYPES:
        raise GameError("arena_ai", "Unknown arena AI")
    mounted = value.get("mounted_gun", False)
    ammo = value.get("mounted_ammo", OUTDOOR_FEATURES["mounted_gun"]["ammo"])
    if not isinstance(mounted, bool) or isinstance(ammo, bool) or not isinstance(ammo, int) or not 0 <= ammo <= MAX_MOUNTED_AMMO:
        raise GameError("arena_mounted", "Invalid mounted gun configuration")
    ambient = value.get("ambient_temperature", DEFAULT_AMBIENT_TEMPERATURE)
    if isinstance(ambient, bool) or not isinstance(ambient, (int, float)) or not AMBIENT_TEMPERATURE_RANGE[0] <= ambient <= AMBIENT_TEMPERATURE_RANGE[1]:
        raise GameError("arena_temperature", "Ambient temperature must be between -100 and 100 degrees Celsius")
    hunger_drain = value.get("hunger_drain", True)
    if not isinstance(hunger_drain, bool):
        raise GameError("arena_hunger", "Hunger drain must be a boolean")
    time_limit = value.get("time_limit")
    if time_limit is not None and (isinstance(time_limit, bool) or not isinstance(time_limit, (int, float)) or not 1 / TICK_RATE <= time_limit < math.inf):
        raise GameError("arena_time_limit", "Time limit must be null or a finite number of at least 0.05 seconds")
    return {"seed": str(seed), "monster_limit": limit, "inventory": list(inventory), "ai": policy, "mounted_gun": mounted, "mounted_ammo": ammo,
            "ambient_temperature": float(ambient), "hunger_drain": hunger_drain, "time_limit": time_limit}


class MemoryStorage:
    def __init__(self):
        self.metadata = None
        self.structures = {}

    def load(self):
        if self.metadata is None:
            return None
        return copy.deepcopy({**self.metadata, "structures": list(self.structures.values())})

    def save(self, state):
        metadata = copy.deepcopy(dict(state))
        structures = copy.deepcopy(state.structures)
        self.metadata = {**(self.metadata or {}), **metadata}
        self.structures.update(structures)
        for identifier in state.removed:
            self.structures.pop(identifier, None)

    def close(self):
        self.metadata = None
        self.structures.clear()


class ArenaWorld(World):
    def __init__(self, config):
        self.monster_limit = config["monster_limit"]
        self.ambient_temperature = config["ambient_temperature"]
        self.hunger_drain = config["hunger_drain"]
        super().__init__(MemoryStorage(), seed=int(config["seed"]))
        self.elapsed = DAY_SECONDS * 21 / 24
        self.next_save = self.elapsed + 2
        player = Player("arena-ai", 0.0, 0.0)
        player.inventory = [Item.create(kind) if kind else None for kind in config["inventory"]]
        self.players[player.id] = player
        self.online.add(player.id)
        self.controls[player.id] = Controls(aim_x=1.0, last_input=time.monotonic(), view_width=DEFAULT_VIEWPORT[0], view_height=DEFAULT_VIEWPORT[1])
        if config["mounted_gun"]:
            self.add_structure(Structure("mounted_gun", 0, 0, id="arena-mounted-gun", ammo=config["mounted_ammo"]))
        self.save_changes()

    def generate_chunk(self, chunk_x, chunk_y):
        point = chunk_x, chunk_y
        if point not in self.chunks:
            self.touch_terrain()
            self.chunks.add(point)
            self.chunk_versions[point] = 1

    def monster_spawn_available(self):
        return len(self.monsters) < self.monster_limit and any(player.temperature >= 5 for player in self.players.values())

    def input_expired(self, controls):
        return False

    def environment(self):
        return {**super().environment(), "ambient_temperature": self.ambient_temperature}

    def drain_hunger(self, player, seconds):
        if self.hunger_drain:
            super().drain_hunger(player, seconds)

    def monster_spawn_radius(self, stream):
        return 20.0

    def visible_monsters(self, observer):
        return [monster for monster in self.monsters.values() if can_observe(observer, monster)]

    def homing_targets(self, player):
        return self.visible_monsters(player)

    def visible_projectiles(self, observer):
        return [projectile for projectile in self.projectiles.values() if can_observe(observer, projectile, radius=0)]

    def monster_perceives(self, monster, player):
        return can_observe(monster, player)

    def spawn_monster(self):
        before = set(self.monsters)
        super().spawn_monster()
        for identifier in self.monsters.keys() - before:
            monster = self.monsters[identifier]
            monster.xray = True
            player = self.players["arena-ai"]
            monster.wander_x, monster.wander_y = normalized(player.x - monster.x, player.y - monster.y)

    def monster_activity(self):
        return False, None

    def set_monster_target(self, monster, player):
        if not self.monster_perceives(monster, player):
            return
        super().set_monster_target(monster, player)
        monster.next_plan = 1e100

    def follow_path(self, monster, seconds):
        horizontal, vertical = normalized(monster.seen_x - monster.x, monster.seen_y - monster.y)
        separation = math.hypot(monster.seen_x - monster.x, monster.seen_y - monster.y)
        travel = min(self.monster_speed(monster) * seconds, max(0.0, separation - 0.05))
        self.move_body(monster, horizontal * travel, vertical * travel, monster_id=monster.id)

    def wander(self, monster, seconds):
        travel = self.monster_speed(monster) * seconds
        self.move_body(monster, monster.wander_x * travel, monster.wander_y * travel, monster_id=monster.id)

    def pickup(self, player):
        return None

    def drop_item(self, item, x, y, dropped_by=None):
        return None


class Simulation:
    def __init__(self, config, max_monsters=256):
        self.config = validate_config(config, max_monsters)
        self.serial = 0
        with identifier_scope(self.next_identifier):
            self.world = ArenaWorld(self.config)
        self.ai = AI_TYPES[self.config["ai"]]()
        self.status = "running"
        self.kills = 0
        self.spawned = 0
        self.player_id = "arena-ai"
        self.check_completion()

    def next_identifier(self):
        self.serial += 1
        return f"arena:{self.serial}"

    def pause(self):
        if self.status == "running":
            self.status = "paused"

    def resume(self):
        if self.status == "paused":
            self.status = "running"

    def step(self):
        if self.status != "running" or self.check_completion():
            return
        previous = set(self.world.monsters)
        with identifier_scope(self.next_identifier):
            self.ai.step(self.world, self.player_id)
            self.world.tick(1 / TICK_RATE)
        current = set(self.world.monsters)
        self.kills += len(previous - current)
        self.spawned += len(current - previous)
        self.check_completion()

    def check_completion(self):
        if self.world.players[self.player_id].temperature < 5:
            self.status = "downed"
        elif self.config["time_limit"] is not None and self.world.tick_number / TICK_RATE + 1e-9 >= self.config["time_limit"]:
            self.status = "time_limit"
        elif not self.ai.has_usable_weapon(self.world, self.player_id) and not any(projectile.kind == "durian_peel" for projectile in self.world.projectiles.values()) and not any(monster.impaled for monster in self.world.monsters.values()):
            self.status = "weapons_depleted"
        return self.status in FINISHED_STATUSES

    def snapshot(self):
        state = self.world.snapshot(self.player_id)
        state["paused"] = self.status != "running"
        controls = self.world.controls[self.player_id]
        mounted = self.world.structures.get("arena-mounted-gun")
        return {"type": "state", "status": self.status, "seconds": self.world.tick_number / TICK_RATE,
                "alive": len(self.world.monsters), "kills": self.kills, "spawned": self.spawned,
                "mounted_ammo": mounted.ammo if mounted else None,
                "decision": self.ai.decision, "aim": [controls.aim_x, controls.aim_y], "state": state}

    def close(self):
        self.world.close(save=False)
