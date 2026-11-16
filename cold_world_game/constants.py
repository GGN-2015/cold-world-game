from .expansion import EXPANSION_ITEMS
from .room_machines import ROOM_MACHINES

TICK_RATE = 20
CHUNK_SIZE = 15
BODY_RADIUS = 0.35
STACK_LIMITS = dict.fromkeys(("wood", "spare_part", "papyrus", "wall", "floor", "fence", "door", "fuel_pack"), 16)
PERSONAL_STORAGE_KINDS = ("inventory", "backpack")
NORMAL_STORAGE_KINDS = ("inventory", "backpack", "chest")
BACKPACK_STACK_LIMITS = STACK_LIMITS.copy()
GROUND_ITEM_UNSEEN_SECONDS = 180.0
PLAYER_SPEED = 4.0
MONSTER_SPEED = 1.2
FAST_MONSTER_SPEED = PLAYER_SPEED * 1.2
NIGHT_MONSTER_HOURS = (21, 3)
MONSTER_REST_HOURS = (6, 18)
MONSTER_RISE_SECONDS = 1.0
MONSTER_SPAWN_CHANCES = {"day": {"small": 0.75, "big": 0.1, "fast": 0.0, "crawler": 0.07, "armored": 0.04, "stalker": 0.04}, "night": {"small": 0.65, "big": 0.1, "fast": 0.1, "crawler": 0.06, "armored": 0.05, "stalker": 0.04}}
MONSTER_PROJECTILE_SPEED = 2.25
DEFAULT_VIEWPORT = (32.0, 18.0)
PROJECTILE_RANGE = (DEFAULT_VIEWPORT[0] ** 2 + DEFAULT_VIEWPORT[1] ** 2) ** 0.5 / 2
INVENTORY_SLOTS = 10
BACKPACK_SLOTS = 30
DROP_DISTANCE = 2.0
PICKUP_RADIUS = 0.75
WORLD_RADIUS = 120
TERRAIN_VERSION = 37
ROOM_MONSTER_CHANCE = 0.20
ROOM_MONSTER_NOTICE_DISTANCE = 8
BIOME_SPAWN_MULTIPLIER = 3
ITEM_CATALOG_VERSION = 1
PIGGY_BANK_CHANCE = 0.05
MAX_COINS = 2 ** 53 - 1
VENDING_MACHINE_CHANCE = 0.04
MATCH_MACHINE_CHANCE = 0.02
GUN_MACHINE_CHANCE = 0.02
MONSTER_LIMIT = 70
MONSTER_XRAY_CHANCE = 0.05
STARVATION_HUNGER = 1.0
STARVATION_TEMPERATURE = 18.0
STARVATION_COOLING_PER_MINUTE = 3.0
MONSTER_COIN_DROPS = {"small": ((1, 0.1), (0, 0.9)), "fast": ((1, 0.5), (0, 0.5)), "big": ((1, 0.6), (2, 0.2), (0, 0.2))}
MONSTER_COIN_DROPS.update({"crawler": ((1, 0.15), (0, 0.85)), "armored": ((2, 0.05), (1, 0.35), (0, 0.6)), "stalker": ((1, 0.25), (0, 0.75))})
SMALL_MONSTER_FOOD_CHANCE = 0.1
SMALL_MONSTER_FOOD_WEIGHTS = {"oreos": 35, "cola": 25, "instant_noodles": 25, "compressed_biscuits": 10, "sardines": 5}
BODY_TEMPERATURE_RATES = ((30, 15), (25, 10), (20, 5), (15, 2), (10, 0), (0, -1), (-10, -2), (-20, -5))
DAY_SECONDS = 1440
WORLD_START_HOUR = 6
SEASON_DAYS = 4
BURN_SECONDS = 120
FIXED_HEATER_BURN_SECONDS = 150
MAX_HUNGER = 10.0
HUNGER_PER_MINUTE = .60
HUNGER_PER_DAMAGE = .25
MAX_HUNGER_LOSS_PER_HIT = 1.0
DOWNED_BUILDINGS = frozenset({"campfire", "wall", "floor", "door"})
SEASONS = ("spring", "summer", "autumn", "winter")
SEASON_OFFSETS = (0, 10, -5, -20)
FOODS = {
    "instant_noodles": 2.5,
    "dumplings": 4,
    "beef": 5,
    "sardines": 3,
    "oreos": 1.5,
    "compressed_biscuits": 4,
    "cola": 2,
}
READY_TO_EAT_FOODS = frozenset({"cola", "oreos", "compressed_biscuits"})
DRINKS = {"vodka": {"duration": 0.5, "effect_duration": 30.0, "felt_temperature": 30.0}}
PASSIVE_ITEMS = {
    "axe_handle": {"axe_range_bonus": .75},
}
EQUIPPED_ITEMS = {}
NAVIGATION_ITEMS = {"compass": {"chance": 0.02}}
HEALING_ITEMS = {"first_aid_kit": {"duration": 0.5, "temperature": 36.0, "hunger": 10.0}, "heat_patch": {"duration": 0.5, "temperature": 36.0}}
REVIVAL_ITEMS = {"defibrillator": {"duration": 1.5, "range": 2.0, "temperature": 36.0, "hunger": 10.0}}
RETURN_ITEMS = {}
IGNITERS = {"lighter": 20, "gasoline": 8, "matches": 1}
AXE = {"range": 1.5, "interval": 0.7, "damage": 3, "arc_degrees": 180}
CHAIN_CHAINSAW = {"range": 2.5, "interval": 0.5, "damage": 6, "arc_degrees": 180, "uses": 45}
STAFF_SWING = {"range": 3, "interval": 0.65, "damage": 4, "arc_degrees": 180}
ICE_STAFF = {**STAFF_SWING, "damage": 5, "uses": 50, "freeze_duration": 2.0, "speed_scale": 0.5}
FLAME_STAFF = {**STAFF_SWING, "uses": 50, "burn_duration": 2.0, "burn_interval": 0.5, "burn_damage": 1}
DURIAN_PEEL = {**AXE, "damage": 4, "throw_duration": 0.5, "throw_interval": 1.0, "speed": 20.0,
               "impale_duration": 6.0, "impale_interval": 0.5, "impale_damage": 1}
MELEE_WEAPONS = {"axe": AXE, "chain_chainsaw": CHAIN_CHAINSAW, "ice_staff": ICE_STAFF, "flame_staff": FLAME_STAFF, "durian_peel": DURIAN_PEEL}
THROWABLE_WEAPONS = {"durian_peel": DURIAN_PEEL}
EXPLOSIVE_WEAPONS = {
    "grenade": {"duration": 0.5, "interval": 1.0, "flight_duration": 0.45, "radius": 3.0, "damage": 20, "coin_cost": 0},
}
KNOCKBACK = {"axe": 0.7, "bullet": 0.4, "monster_melee": 0.65, "monster_big_melee": 1.0, "monster_bullet": 0.9, "player_bullet": 0.3, "big_monster_scale": 0.6, "fast_monster_scale": 2.5}
GUNS = {
    "handgun": {"ammo": 12, "interval": 0.25, "speed": 20, "range": PROJECTILE_RANGE, "damage": 5},
    "shotgun": {"ammo": 6, "interval": 0.8, "speed": 18, "range": PROJECTILE_RANGE, "damage": 2},
    "rifle": {"ammo": 20, "interval": 0.15, "speed": 28, "range": PROJECTILE_RANGE, "damage": 4},
}
AMMO_PACKS = {"light_ammo": 12, "rifle_ammo": 8, "shotgun_ammo": 4}
RELOAD_RULES = {
    "handgun": ("light_ammo", 1), "rust_revolver": ("light_ammo", 1.5),
    "rifle": ("rifle_ammo", 1), "hunting_rifle": ("rifle_ammo", 1),
    "shotgun": ("shotgun_ammo", 1.5),
    "flamethrower": ("gasoline", 1.5),
}
TRADING_MACHINES = frozenset({"vending_machine", "match_machine", "gun_machine"}) | ROOM_MACHINES.keys()
PANEL_DEMOLITION = TRADING_MACHINES | {"chest", "campfire", "piggy_bank"}
BUILDINGS = frozenset({"landmine", "fence", "wall", "floor", "door", "chest", "campfire", "piggy_bank"}) | TRADING_MACHINES
CONTAINERS = frozenset({"chest", "campfire", "fixed_heater", "piggy_bank"}) | TRADING_MACHINES
SOLID = frozenset({"tree", "wall", "fence", "door", "ring_wall", "ring_gate"}) | CONTAINERS
OPAQUE = frozenset({"tree", "wall", "door", "ring_wall"})
BULLET_BLOCKERS = frozenset({"tree", "wall", "door", "ring_wall"})
MOUNTED_COVER_HITS = {"tree": 12, "wall": 24, "door": 16}
MONSTER_BULLET_BLOCKERS = BULLET_BLOCKERS | CONTAINERS
DEMOLITION = {"tree": 0.5, "fence": 0.5, "wall": 1.5, "floor": 0.5, "chest": 1.5, "campfire": 1.5, "piggy_bank": 1.5, "vending_machine": 1.5, "match_machine": 1.5, "gun_machine": 1.5}
DEMOLITION.update({kind: 1.5 for kind in ROOM_MACHINES})
DEMOLITION["ring_gate"] = 1.5
DEMOLITION["door"] = 1.5
HARVEST_TOOLS = {"axe": DEMOLITION, "chain_chainsaw": {**DEMOLITION, "tree": 0.25}}
MONSTER_DEMOLITION = {"fence": 3.0, "wall": 10.0, "door": 10.0}
RECIPES = {
    "fence": {"inputs": {"wood": 1}, "output": "fence", "count": 2},
    "wall": {"inputs": {"wood": 1}, "output": "wall", "count": 1},
    "door": {"inputs": {"wood": 2}, "output": "door", "count": 1},
    "floor": {"inputs": {"wood": 1}, "output": "floor", "count": 1},
    "chest": {"inputs": {"wood": 2}, "output": "chest", "count": 1},
    "campfire": {"inputs": {"wood": 1}, "output": "campfire", "count": 1},
    "recycle_fences": {"inputs": {"fence": 2}, "output": "wood", "count": 1},
}
VENDING_OFFERS = {
    "sell_wood": {"inputs": {"wood": 10}, "output": "coin", "count": 1},
    "buy_wood": {"inputs": {"coin": 1}, "output": "wood", "count": 10},
    "buy_cola": {"inputs": {"coin": 1}, "output": "cola", "count": 1},
    "buy_wrench": {"inputs": {"coin": 3}, "output": "repair_wrench", "count": 1},
    "buy_spare_part": {"inputs": {"coin": 1}, "output": "spare_part", "count": 1},
}
MATCH_OFFERS = {
    "sell_wood": {"inputs": {"wood": 10}, "output": "coin", "count": 1},
    "buy_wood": {"inputs": {"coin": 1}, "output": "wood", "count": 10},
    "buy_matches": {"inputs": {"coin": 1}, "output": "matches", "count": 1},
}
GUN_OFFERS = {
    "buy_light_ammo": {"inputs": {"coin": 2}, "output": "light_ammo", "count": 1},
    "buy_rifle_ammo": {"inputs": {"coin": 3}, "output": "rifle_ammo", "count": 1},
    "buy_shotgun_ammo": {"inputs": {"coin": 3}, "output": "shotgun_ammo", "count": 1},
}
MACHINE_OFFERS = {"vending_machine": VENDING_OFFERS, "match_machine": MATCH_OFFERS, "gun_machine": GUN_OFFERS}
MACHINE_OFFERS.update({kind: definition["offers"] for kind, definition in ROOM_MACHINES.items()})
FOODS["durian"] = 3
READY_TO_EAT_FOODS = READY_TO_EAT_FOODS | {"durian"}
for item_kind, definition in EXPANSION_ITEMS.items():
    mechanic, settings = definition["mechanic"], definition["settings"]
    if mechanic == "food":
        FOODS[item_kind] = settings["hunger"]
        if settings["ready"]:
            READY_TO_EAT_FOODS = READY_TO_EAT_FOODS | {item_kind}
    elif mechanic == "igniter":
        IGNITERS[item_kind] = settings["uses"]
    else:
        {"gun": GUNS, "melee": MELEE_WEAPONS, "explosive": EXPLOSIVE_WEAPONS, "healing": HEALING_ITEMS, "revival": REVIVAL_ITEMS, "return": RETURN_ITEMS, "passive": PASSIVE_ITEMS, "equipment": EQUIPPED_ITEMS}[mechanic][item_kind] = settings

for kind, rounds in {"rust_revolver": 6, "hunting_rifle": 5}.items():
    GUNS[kind] = {**GUNS[kind], "ammo": rounds}
for kind, stats in {
    "crowbar": {"uses": 50, "damage": 6}, "machete": {"uses": 50},
    "snow_shovel": {"damage": 4}, "frost_spear": {"uses": 45},
}.items():
    MELEE_WEAPONS[kind] = {**MELEE_WEAPONS[kind], **stats}
for stats in MELEE_WEAPONS.values():
    stats["consume_on_hit"] = True
for kind, stats in {
    "frost_bomb": {"damage": 10, "radius": 3, "freeze_duration": 3.5},
    "fire_bottle": {"damage": 6, "radius": 3, "burn_duration": 3},
    "flare_bomb": {"burn_duration": 2},
}.items():
    EXPLOSIVE_WEAPONS[kind] = {**EXPLOSIVE_WEAPONS[kind], **stats}

CREATIVE_ITEMS = {
    "creative_warm_suit": {"temperature": 36.0},
    "creative_food": {"hunger": 10.0},
    "creative_shoes": {"speed_multiplier": 2},
    "creative_tool": {"free_craft": True},
    "creative_piggy_bank": {"free_purchases": True},
}

BIOME_ITEMS = {"chain_chainsaw": {}, "chain_charm": {}, "flamethrower": {"uses": 8}, "fireball_scroll": {},
               "freeze_scroll": {}, "quill": {"uses": 6}, "papyrus": {}, "lantern": {}}
CHAIN_CHARM_CHANCE = .35
HARVEST_CHAIN_LIMIT = 5
HARVEST_CHAIN_COSTS = (1, 1, 3)
FOG_VIEW_RADIUS = 3
FOG_LANTERN_RADIUS = 6
FOG_CAMPFIRE_RADIUS = 3.5
FOG_STREET_LAMP_RADIUS = 10
EXPLOSIVE_WEAPONS.update({
    "flamethrower": {"duration": .25, "interval": .5, "flight_duration": .18, "radius": 2, "damage": 3, "coin_cost": 0, "cast_range": 5, "burn_duration": 2, "burn_interval": .5},
    "fireball_scroll": {"duration": .5, "interval": 1, "flight_duration": .4, "radius": 2, "damage": 5, "coin_cost": 0, "cast_range": 11, "burn_duration": 1.5, "burn_interval": .5},
    "freeze_scroll": {"duration": .5, "interval": 1, "flight_duration": .4, "radius": 2.5, "damage": 4, "coin_cost": 0, "cast_range": 11, "freeze_duration": 2},
})

BUILDING_WANDS = {
    "building_wand": {"building": "wall", "rotate": True, "tiles": ((0, 0), (-1, 0), (1, 0))},
    "floor_wand": {"building": "floor", "tiles": (
        (0, 0), (-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1),
    )},
}

ITEM_KINDS = frozenset({"wood", "coin", "repair_wrench", "spare_part"}) | BUILDINGS | FOODS.keys() | DRINKS.keys() | PASSIVE_ITEMS.keys() | EQUIPPED_ITEMS.keys() | HEALING_ITEMS.keys() | REVIVAL_ITEMS.keys() | RETURN_ITEMS.keys() | IGNITERS.keys() | GUNS.keys() | MELEE_WEAPONS.keys() | EXPLOSIVE_WEAPONS.keys() | CREATIVE_ITEMS.keys() | BIOME_ITEMS.keys() | BUILDING_WANDS.keys() | AMMO_PACKS.keys() | NAVIGATION_ITEMS.keys()
