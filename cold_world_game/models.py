import math
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, is_dataclass
from itertools import chain
from uuid import uuid4

from .constants import AMMO_PACKS, BIOME_ITEMS, CREATIVE_ITEMS, DURIAN_PEEL, MAX_HUNGER
from .constants import BACKPACK_SLOTS, DEFAULT_VIEWPORT, GUNS, HEALING_ITEMS, IGNITERS, INVENTORY_SLOTS, MELEE_WEAPONS, RETURN_ITEMS, SOLID
from .wildlife import MONSTER_TYPES, WRENCH_USES


_identifier_factory = ContextVar("cold_world_identifier_factory", default=None)


def identifier() -> str:
    factory = _identifier_factory.get()
    return factory() if factory is not None else uuid4().hex


@contextmanager
def identifier_scope(factory):
    token = _identifier_factory.set(factory)
    try:
        yield
    finally:
        _identifier_factory.reset(token)


@dataclass
class Item:
    kind: str
    id: str = field(default_factory=identifier)
    ammo: int | None = None
    uses: int | None = None
    count: int = 1

    @classmethod
    def create(cls, kind: str, count=1) -> "Item":
        settings = RETURN_ITEMS.get(kind) or MELEE_WEAPONS.get(kind) or HEALING_ITEMS.get(kind, {})
        uses = WRENCH_USES if kind == "repair_wrench" else settings.get("uses", BIOME_ITEMS.get(kind, {}).get("uses", IGNITERS.get(kind)))
        return cls(kind, ammo=GUNS[kind]["ammo"] if kind in GUNS else AMMO_PACKS.get(kind), uses=uses, count=count)


@dataclass
class Structure:
    kind: str
    x: int
    y: int
    id: str = field(default_factory=identifier)
    slots: list[Item | None] = field(default_factory=list)
    fuel: int = 0
    igniter: Item | None = None
    burn_remaining: float = 0.0
    balance: int = 0
    ammo: int | None = None
    owner: str | None = None
    repaired: bool = False
    door_open: bool = False
    biome_link: list[int] | None = None
    biome_anchor: list[int] | None = None
    biome_guard: str | None = None
    on_floor: bool = False
    cover_hits: int = 0
    restocked: int = 0

    @property
    def lit(self) -> bool:
        return self.burn_remaining > 0

    @property
    def solid(self) -> bool:
        return self.kind in SOLID and not (self.kind == "door" and self.door_open)

    @property
    def empty(self) -> bool:
        return not any(self.slots) and self.fuel == 0 and self.igniter is None and self.balance == 0


@dataclass
class Player:
    id: str
    x: float
    y: float
    inventory: list[Item | None] = field(default_factory=lambda: [None] * INVENTORY_SLOTS)
    backpack: list[Item | None] = field(default_factory=lambda: [None] * BACKPACK_SLOTS)
    temperature: float = 36.0
    hunger: float = MAX_HUNGER
    selected: int = 0
    next_shot: float = 0.0
    next_axe_attack: float = 0.0
    last_shot_tick: int = -1
    offline_since: float | None = None
    money: int = 0
    last_login_at: float | None = None
    excitement_remaining: float = 0.0
    chilled_until: float = 0.0
    scorched_until: float = 0.0
    next_scorch: float = 0.0

    def creative_effects(self):
        effects = {}
        for item in chain(self.inventory, self.backpack):
            if item and item.kind in CREATIVE_ITEMS:
                effects.update(CREATIVE_ITEMS[item.kind])
        return effects

    def apply_creative_vitals(self, effects):
        self.temperature = effects.get("temperature", self.temperature)
        self.hunger = effects.get("hunger", self.hunger)

    def carries(self, kind):
        return any(item and item.kind == kind for item in chain(self.inventory, self.backpack))

    def holds(self, kind):
        item = self.inventory[self.selected]
        return item is not None and item.kind == kind


@dataclass
class Controls:
    move_x: float = 0.0
    move_y: float = 0.0
    aim_x: float = 0.0
    aim_y: float = 0.0
    aim_target: str | None = None
    held: bool = False
    pending_shot: bool = False
    attack_id: str | None = None
    charge_item: str | None = None
    throw_only: bool = False
    shift: bool = False
    target: str | None = None
    progress: float = 0.0
    next_demolition_feedback: float = 0.0
    ui: bool = False
    container: str | None = None
    last_input: float = 0.0
    ghost_monsters: set[str] = field(default_factory=set)
    client_movement: bool = False
    movement_epoch: int = 0
    teleport_epoch: int = 0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    demolition_container: str | None = None
    seat: str | None = None
    view_width: float = DEFAULT_VIEWPORT[0]
    view_height: float = DEFAULT_VIEWPORT[1]
    next_biome_scan: float = 0.0
    next_fog_spawn: float = 0.0
    next_paced_spawn: float | None = None
    reload_target: str | None = None
    reload_until: float = 0.0
    reload_duration: float = 0.0

    def stop_attack(self) -> None:
        self.held = False
        self.pending_shot = False
        self.attack_id = None
        self.charge_item = None
        self.throw_only = False
        self.target = None
        self.progress = 0.0
        self.next_demolition_feedback = 0.0
        self.demolition_container = None


@dataclass
class GroundItem:
    item: Item
    x: float
    y: float
    id: str = field(default_factory=identifier)
    dropped_by: str | None = None
    immune_until: float = 0.0
    unseen_since: float | None = None


@dataclass
class Monster:
    x: float
    y: float
    big: bool = False
    id: str = field(default_factory=identifier)
    hp: float = 10
    target: str | None = None
    seen_x: float = 0.0
    seen_y: float = 0.0
    last_seen: float = 0.0
    next_attack: float = 0.0
    next_plan: float = 0.0
    path: list[tuple[int, int]] = field(default_factory=list)
    wander_x: float = 0.0
    wander_y: float = 0.0
    next_wander: float = 0.0
    demolition: str | None = None
    demolition_progress: float = 0.0
    next_demolition_feedback: float = 0.0
    overlap_player: str | None = None
    fast: bool = False
    frozen_until: float = 0.0
    burning_until: float = 0.0
    next_burn: float = 0.0
    burn_owner: str | None = None
    impaled: bool = False
    impaled_until: float = 0.0
    next_impale: float = 0.0
    impale_owner: str | None = None
    species: str = "small"
    xray: bool = False
    dazed_until: float = 0.0
    next_light_daze: float = 0.0

    @property
    def kind(self):
        return "big" if self.big else "fast" if self.fast else self.species

    @property
    def speed(self):
        return MONSTER_TYPES.get(self.kind, MONSTER_TYPES["small"])["speed"]


@dataclass
class Projectile:
    x: float
    y: float
    velocity_x: float
    velocity_y: float
    remaining: float
    damage: float
    owner: str
    hostile: bool = False
    id: str = field(default_factory=identifier)
    shot: str = field(default_factory=identifier)
    origin_x: float | None = None
    origin_y: float | None = None
    spawned_at: float | None = None
    hit_targets: list[str] = field(default_factory=list)
    range_player: str | None = None
    range_x: float | None = None
    range_y: float | None = None
    range_radius: float | None = None
    kind: str = "bullet"
    target_x: float | None = None
    target_y: float | None = None
    detonates_at: float | None = None
    target_id: str | None = None
    weapon_kind: str | None = None
    mounted: bool = False


def item_from(data: dict | None) -> Item | None:
    if not data:
        return None
    values = dict(data)
    settings = RETURN_ITEMS.get(values["kind"]) or MELEE_WEAPONS.get(values["kind"]) or HEALING_ITEMS.get(values["kind"], {})
    if "uses" in settings and values.get("uses") is None:
        values["uses"] = settings["uses"]
    return Item(**values)


def projectile_from(data: dict) -> Projectile:
    values = dict(data)
    if values.get("kind") == "durian_peel" and values.get("detonates_at") is not None:
        horizontal = (values.get("target_x") or 0) - values["x"]
        vertical = (values.get("target_y") or 0) - values["y"]
        magnitude = math.hypot(horizontal, vertical)
        if magnitude <= 1e-9:
            horizontal, vertical, magnitude = 1.0, 0.0, 1.0
        values.update(velocity_x=horizontal / magnitude * DURIAN_PEEL["speed"], velocity_y=vertical / magnitude * DURIAN_PEEL["speed"], damage=0, detonates_at=None, weapon_kind="durian_peel", range_player=values["owner"])
    return Projectile(**values)


def structure_from(data: dict) -> Structure:
    values = dict(data)
    if values["kind"] == "mounted_gun" and "ammo" not in values:
        values["ammo"] = 200
    values["slots"] = [item_from(item) for item in data["slots"]]
    values["igniter"] = item_from(data["igniter"])
    return Structure(**values)


def player_from(data: dict) -> Player:
    values = dict(data)
    values["inventory"] = [item_from(item) for item in data["inventory"]]
    values["backpack"] = [item_from(item) for item in data.get("backpack", [None] * BACKPACK_SLOTS)]
    values["money"] = data.get("money", 0)
    values["hunger"] = min(MAX_HUNGER, max(0.0, data.get("hunger", MAX_HUNGER)))
    for storage in (values["inventory"], values["backpack"]):
        for slot, item in enumerate(storage):
            if item and item.kind == "coin":
                values["money"] += 1
                storage[slot] = None
    return Player(**values)


def encode(value):
    if value is None or isinstance(value, (str, int, float)):
        return value
    if type(value) is Item:
        result = vars(value).copy()
        if value.count == 1:
            result.pop("count")
        return result
    if type(value) is Structure:
        return {**vars(value), "slots": [encode(item) for item in value.slots], "igniter": encode(value.igniter)}
    if type(value) is Monster:
        return {**vars(value), "path": [list(point) for point in value.path]}
    if type(value) is Player:
        return {**vars(value), "inventory": [encode(item) for item in value.inventory], "backpack": [encode(item) for item in value.backpack]}
    if type(value) is Projectile:
        return {**vars(value), "hit_targets": list(value.hit_targets)}
    if type(value) is GroundItem:
        return {**vars(value), "item": encode(value.item)}
    if is_dataclass(value):
        return {name: encode(element) for name, element in vars(value).items()}
    if isinstance(value, (list, tuple)):
        return [encode(element) for element in value]
    if isinstance(value, dict):
        return {name: encode(element) for name, element in value.items()}
    return value
