from dataclasses import dataclass, field, is_dataclass
from uuid import uuid4

from .constants import BACKPACK_SLOTS, GUNS, IGNITERS, INVENTORY_SLOTS


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
        return cls(kind, ammo=GUNS[kind]["ammo"] if kind in GUNS else None, uses=IGNITERS.get(kind))


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

    @property
    def lit(self) -> bool:
        return self.burn_remaining > 0


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


@dataclass
class Controls:
    move_x: float = 0.0
    move_y: float = 0.0
    aim_x: float = 0.0
    aim_y: float = 0.0
    aim_target: str | None = None
    held: bool = False
    pending_shot: bool = False
    shift: bool = False
    target: str | None = None
    progress: float = 0.0
    ui: bool = False
    container: str | None = None
    last_input: float = 0.0
    ghost_monsters: set[str] = field(default_factory=set)

    def stop_attack(self) -> None:
        self.held = False
        self.pending_shot = False
        self.target = None
        self.progress = 0.0


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


def item_from(data: dict | None) -> Item | None:
    return Item(**data) if data else None


def structure_from(data: dict) -> Structure:
    values = dict(data)
    values["slots"] = [item_from(item) for item in data["slots"]]
    values["igniter"] = item_from(data["igniter"])
    return Structure(**values)


def player_from(data: dict) -> Player:
    values = dict(data)
    values["inventory"] = [item_from(item) for item in data["inventory"]]
    values["backpack"] = [item_from(item) for item in data.get("backpack", [None] * BACKPACK_SLOTS)]
    return Player(**values)


def encode(value):
    if is_dataclass(value):
        return {name: encode(element) for name, element in vars(value).items()}
    if isinstance(value, (list, tuple)):
        return [encode(element) for element in value]
    if isinstance(value, dict):
        return {name: encode(element) for name, element in value.items()}
    return value
