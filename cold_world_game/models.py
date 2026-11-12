from dataclasses import dataclass, field, is_dataclass
from uuid import uuid4

from .constants import BACKPACK_SLOTS, DEFAULT_VIEWPORT, FAST_MONSTER_SPEED, GUNS, HEALING_ITEMS, IGNITERS, INVENTORY_SLOTS, MELEE_WEAPONS, MONSTER_SPEED, RETURN_ITEMS


def identifier() -> str:
    return uuid4().hex


@dataclass
class Item:
    kind: str
    id: str = field(default_factory=identifier)
    ammo: int | None = None
    uses: int | None = None

    @classmethod
    def create(cls, kind: str) -> "Item":
        settings = RETURN_ITEMS.get(kind) or MELEE_WEAPONS.get(kind) or HEALING_ITEMS.get(kind, {})
        return cls(kind, ammo=GUNS[kind]["ammo"] if kind in GUNS else None, uses=settings.get("uses", IGNITERS.get(kind)))


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

    @property
    def lit(self) -> bool:
        return self.burn_remaining > 0

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
    hunger: float = 10.0
    selected: int = 0
    next_shot: float = 0.0
    next_axe_attack: float = 0.0
    last_shot_tick: int = -1
    offline_since: float | None = None
    money: int = 0
    last_login_at: float | None = None
    excitement_remaining: float = 0.0


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
    view_width: float = DEFAULT_VIEWPORT[0]
    view_height: float = DEFAULT_VIEWPORT[1]

    def stop_attack(self) -> None:
        self.held = False
        self.pending_shot = False
        self.attack_id = None
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

    @property
    def speed(self):
        return FAST_MONSTER_SPEED if self.fast and not self.big else MONSTER_SPEED


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


def item_from(data: dict | None) -> Item | None:
    if not data:
        return None
    values = dict(data)
    settings = RETURN_ITEMS.get(values["kind"]) or MELEE_WEAPONS.get(values["kind"]) or HEALING_ITEMS.get(values["kind"], {})
    if "uses" in settings and values.get("uses") is None:
        values["uses"] = settings["uses"]
    return Item(**values)


def structure_from(data: dict) -> Structure:
    values = dict(data)
    values["slots"] = [item_from(item) for item in data["slots"]]
    values["igniter"] = item_from(data["igniter"])
    return Structure(**values)


def player_from(data: dict) -> Player:
    values = dict(data)
    values["inventory"] = [item_from(item) for item in data["inventory"]]
    values["backpack"] = [item_from(item) for item in data.get("backpack", [None] * BACKPACK_SLOTS)]
    values["money"] = data.get("money", 0)
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
        return vars(value).copy()
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
