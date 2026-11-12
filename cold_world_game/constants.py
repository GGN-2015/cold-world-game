from .expansion import DURIAN_CHANCE, EXPANSION_ITEMS
from .room_machines import ROOM_MACHINES

TICK_RATE = 20
CHUNK_SIZE = 15
BODY_RADIUS = 0.35
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
TERRAIN_VERSION = 18
LANDMINE_CHANCE = 0.02
CHAINSAW_CHANCE = 0.02
HOMING_MISSILE_CHANCE = 0.02
SWIFTNESS_RING_CHANCE = 0.02
SHERIFF_BADGE_CHANCE = 0.02
VODKA_CHANCE = 0.02
PIGGY_BANK_CHANCE = 0.05
HEAT_PATCH_CHANCE = 0.02
MAX_COINS = 2 ** 53 - 1
VENDING_MACHINE_CHANCE = 0.02
MATCH_MACHINE_CHANCE = VENDING_MACHINE_CHANCE
FIRST_AID_KIT_CHANCE = 0.02
RETURN_STAFF_CHANCE = 0.02
ICE_STAFF_CHANCE = 0.02
GUN_MACHINE_CHANCE = 0.02
GRENADE_CHANCE = 0.02
FLAME_STAFF_CHANCE = 0.02
DEFIBRILLATOR_CHANCE = 0.02
MONSTER_LIMIT = 70
MONSTER_LIMIT_DOUBLING_DISTANCE = 1200.0
MONSTER_XRAY_CHANCE = 0.1
STARVATION_HUNGER = 1.0
STARVATION_TEMPERATURE = 18.0
STARVATION_AMBIENT = -30.0
MONSTER_COIN_DROPS = {"small": ((1, 0.1), (0, 0.9)), "fast": ((1, 0.5), (0, 0.5)), "big": ((1, 0.6), (2, 0.2), (0, 0.2))}
MONSTER_COIN_DROPS.update({"crawler": ((1, 0.15), (0, 0.85)), "armored": ((2, 0.05), (1, 0.35), (0, 0.6)), "stalker": ((1, 0.25), (0, 0.75))})
SMALL_MONSTER_FOOD_CHANCE = 0.1
SMALL_MONSTER_FOOD_WEIGHTS = {"oreos": 35, "cola": 25, "instant_noodles": 25, "compressed_biscuits": 10, "sardines": 5}
BODY_TEMPERATURE_RATES = ((30, 20), (20, 15), (10, 0), (0, -1), (-10, -2), (-20, -5))
DAY_SECONDS = 1440
SEASON_DAYS = 4
BURN_SECONDS = 360
SEASONS = ("spring", "summer", "autumn", "winter")
SEASON_OFFSETS = (0, 10, -5, -20)
FOODS = {
    "instant_noodles": 2.5,
    "dumplings": 4,
    "wontons": 3,
    "pork_trotters": 4,
    "beef": 5,
    "lamb": 5,
    "sardines": 3,
    "tuna": 3,
    "beef_balls": 5,
    "hotpot_vegetables": 2,
    "oreos": 1.5,
    "compressed_biscuits": 4,
    "cola": 2,
}
READY_TO_EAT_FOODS = frozenset({"cola", "oreos", "compressed_biscuits"})
DRINKS = {"vodka": {"duration": 0.5, "effect_duration": 30.0, "felt_temperature": 30.0}}
PASSIVE_ITEMS = {"sheriff_badge": {"damage_multiplier": 2, "monster_kinds": ["small", "fast"], "stackable": False}}
EQUIPPED_ITEMS = {"swiftness_ring": {"speed_multiplier": 3}}
HEALING_ITEMS = {"first_aid_kit": {"duration": 0.5, "temperature": 36.0, "hunger": 10.0}, "heat_patch": {"duration": 0.5, "temperature": 36.0}}
REVIVAL_ITEMS = {"defibrillator": {"duration": 1.5, "range": 2.0, "temperature": 36.0, "hunger": 10.0}}
RETURN_ITEMS = {"return_staff": {"duration": 1.5, "uses": 20}}
IGNITERS = {"lighter": 20, "gasoline": 5, "diesel": 5, "kerosene": 5, "matches": 1}
AXE = {"range": 3, "interval": 0.5, "damage": 4, "arc_degrees": 180}
CHAINSAW = {"range": 2.5, "interval": 0.5, "damage": 6, "arc_degrees": 180, "uses": 200, "consume_on_hit": True}
ICE_STAFF = {**AXE, "damage": AXE["damage"] * 2, "uses": 100, "freeze_duration": 4.0, "speed_scale": 0.5}
FLAME_STAFF = {**AXE, "uses": 100, "burn_duration": 4.0, "burn_interval": 0.5, "burn_damage": AXE["damage"]}
MELEE_WEAPONS = {"axe": AXE, "chainsaw": CHAINSAW, "ice_staff": ICE_STAFF, "flame_staff": FLAME_STAFF}
EXPLOSIVE_WEAPONS = {
    "grenade": {"duration": 0.5, "interval": 1.0, "flight_duration": 0.45, "radius": 3.0, "damage": AXE["damage"] * 5, "coin_cost": 0},
    "coin_launcher": {"duration": 0.5, "interval": 1.0, "flight_duration": 0.45, "radius": 3.0, "damage": AXE["damage"] * 5, "coin_cost": 1},
}
KNOCKBACK = {"axe": 0.7, "bullet": 0.4, "monster_melee": 0.65, "monster_big_melee": 1.0, "monster_bullet": 0.9, "player_bullet": 0.3, "big_monster_scale": 0.6, "fast_monster_scale": 2.5}
GUNS = {
    "handgun": {"ammo": 100, "interval": 0.25, "speed": 20, "range": PROJECTILE_RANGE, "damage": 5},
    "shotgun": {"ammo": 200, "interval": 0.8, "speed": 18, "range": PROJECTILE_RANGE, "damage": 2},
    "rifle": {"ammo": 1000, "interval": 0.15, "speed": 28, "range": PROJECTILE_RANGE, "damage": 5},
}
GUNS["homing_missile"] = {"ammo": 20, "interval": GUNS["shotgun"]["interval"], "speed": 18, "damage": GUNS["handgun"]["damage"] * 3, "launch_duration": 0.12, "launch_distance": 1.2, "impact_radius": 0.9}
TRADING_MACHINES = frozenset({"vending_machine", "match_machine", "gun_machine"}) | ROOM_MACHINES.keys()
PANEL_DEMOLITION = TRADING_MACHINES | {"chest", "campfire", "piggy_bank"}
BUILDINGS = frozenset({"landmine", "fence", "wall", "floor", "chest", "campfire", "piggy_bank"}) | TRADING_MACHINES
CONTAINERS = frozenset({"chest", "campfire", "piggy_bank"}) | TRADING_MACHINES
SOLID = frozenset({"tree", "wall", "fence"}) | CONTAINERS
OPAQUE = frozenset({"tree", "wall"})
BULLET_BLOCKERS = frozenset({"tree"})
MONSTER_BULLET_BLOCKERS = BULLET_BLOCKERS | CONTAINERS
DEMOLITION = {"tree": 0.5, "fence": 0.5, "wall": 1.5, "floor": 0.5, "chest": 1.5, "campfire": 1.5, "piggy_bank": 1.5, "vending_machine": 1.5, "match_machine": 1.5, "gun_machine": 1.5}
DEMOLITION.update({kind: 1.5 for kind in ROOM_MACHINES})
HARVEST_TOOLS = {"axe": DEMOLITION, "chainsaw": {**DEMOLITION, "tree": 0.25}}
MONSTER_DEMOLITION = {"fence": 1.0, "wall": 3.0}
RECIPES = {
    "fence": {"inputs": {"wood": 1}, "output": "fence", "count": 2},
    "wall": {"inputs": {"wood": 1}, "output": "wall", "count": 1},
    "floor": {"inputs": {"wood": 1}, "output": "floor", "count": 1},
    "chest": {"inputs": {"wood": 2}, "output": "chest", "count": 1},
    "campfire": {"inputs": {"wood": 1}, "output": "campfire", "count": 1},
    "recycle_fences": {"inputs": {"fence": 2}, "output": "wood", "count": 1},
}
VENDING_OFFERS = {
    "sell_wood": {"inputs": {"wood": 10}, "output": "coin", "count": 1},
    "buy_wood": {"inputs": {"coin": 1}, "output": "wood", "count": 10},
    "buy_cola": {"inputs": {"coin": 1}, "output": "cola", "count": 1},
}
MATCH_OFFERS = {
    "sell_wood": {"inputs": {"wood": 10}, "output": "coin", "count": 1},
    "buy_wood": {"inputs": {"coin": 1}, "output": "wood", "count": 10},
    "buy_matches": {"inputs": {"coin": 1}, "output": "matches", "count": 1},
}
GUN_OFFERS = {
    "buy_handgun": {"inputs": {"coin": 3}, "output": "handgun", "count": 1},
    "buy_shotgun": {"inputs": {"coin": 5}, "output": "shotgun", "count": 1},
    "buy_rifle": {"inputs": {"coin": 10}, "output": "rifle", "count": 1},
    "buy_grenade": {"inputs": {"coin": 5}, "output": "grenade", "count": 1},
    "buy_coin_launcher": {"inputs": {"coin": 10}, "output": "coin_launcher", "count": 1},
}
MACHINE_OFFERS = {"vending_machine": VENDING_OFFERS, "match_machine": MATCH_OFFERS, "gun_machine": GUN_OFFERS}
MACHINE_OFFERS.update({kind: definition["offers"] for kind, definition in ROOM_MACHINES.items()})
COMMON_CHEST_FOODS = tuple(FOODS)
COMMON_CHEST_IGNITERS = tuple(IGNITERS)
FOODS["durian"] = 3
READY_TO_EAT_FOODS = READY_TO_EAT_FOODS | {"durian"}
EXPLOSIVE_WEAPONS["durian_peel"] = {**EXPLOSIVE_WEAPONS["grenade"]}
RARE_CHEST_ITEMS = {"durian": DURIAN_CHANCE, "chainsaw": CHAINSAW_CHANCE, "landmine": LANDMINE_CHANCE, **{kind: definition["chance"] for kind, definition in EXPANSION_ITEMS.items()}}
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

ITEM_KINDS = frozenset({"wood", "coin"}) | BUILDINGS | FOODS.keys() | DRINKS.keys() | PASSIVE_ITEMS.keys() | EQUIPPED_ITEMS.keys() | HEALING_ITEMS.keys() | REVIVAL_ITEMS.keys() | RETURN_ITEMS.keys() | IGNITERS.keys() | GUNS.keys() | MELEE_WEAPONS.keys() | EXPLOSIVE_WEAPONS.keys()
