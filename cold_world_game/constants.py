TICK_RATE = 20
CHUNK_SIZE = 15
BODY_RADIUS = 0.35
PLAYER_SPEED = 4.0
MONSTER_SPEED = 1.2
INVENTORY_SLOTS = 10
BACKPACK_SLOTS = 30
DROP_DISTANCE = 2.0
PICKUP_RADIUS = 0.75
WORLD_RADIUS = 120
TERRAIN_VERSION = 2
VENDING_MACHINE_CHANCE = 0.02
MONSTER_LIMIT = 70
MONSTER_COIN_DROPS = {"small": ((1, 0.1), (0, 0.9)), "big": ((1, 0.6), (2, 0.2), (0, 0.2))}
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
IGNITERS = {"lighter": 20, "gasoline": 5, "diesel": 5, "kerosene": 5, "matches": 1}
AXE = {"range": 3, "interval": 0.5, "damage": 4}
KNOCKBACK = {"axe": 0.7, "bullet": 0.4, "monster_melee": 0.65, "monster_big_melee": 1.0, "monster_bullet": 0.9, "player_bullet": 0.3, "big_monster_scale": 0.6}
GUNS = {
    "handgun": {"ammo": 100, "interval": 0.25, "speed": 20, "range": 20, "damage": 5},
    "shotgun": {"ammo": 200, "interval": 0.8, "speed": 18, "range": 12, "damage": 2},
    "rifle": {"ammo": 1000, "interval": 0.15, "speed": 28, "range": 30, "damage": 5},
}
BUILDINGS = frozenset({"fence", "wall", "floor", "chest", "campfire", "vending_machine"})
CONTAINERS = frozenset({"chest", "campfire", "vending_machine"})
SOLID = frozenset({"tree", "wall", "fence", "chest", "campfire", "vending_machine"})
OPAQUE = frozenset({"tree", "wall"})
BULLET_BLOCKERS = frozenset({"tree", "wall", "chest", "vending_machine"})
DEMOLITION = {"tree": 0.5, "fence": 0.5, "wall": 1.5, "floor": 0.5, "chest": 1.5, "campfire": 0.5, "vending_machine": 1.5}
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
ITEM_KINDS = frozenset({"wood", "axe", "coin"}) | BUILDINGS | FOODS.keys() | IGNITERS.keys() | GUNS.keys()
