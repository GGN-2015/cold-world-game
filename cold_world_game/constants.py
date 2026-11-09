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
MONSTER_LIMIT = 70
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
}
IGNITERS = {"lighter": 20, "gasoline": 5, "diesel": 5, "kerosene": 5, "matches": 1}
AXE = {"range": 3, "interval": 0.5, "damage": 4}
GUNS = {
    "handgun": {"ammo": 100, "interval": 0.25, "speed": 20, "range": 20, "damage": 5},
    "shotgun": {"ammo": 200, "interval": 0.8, "speed": 18, "range": 12, "damage": 2},
    "rifle": {"ammo": 1000, "interval": 0.15, "speed": 28, "range": 30, "damage": 5},
}
BUILDINGS = frozenset({"fence", "wall", "floor", "chest", "campfire"})
SOLID = frozenset({"tree", "wall", "fence", "chest", "campfire"})
OPAQUE = frozenset({"tree", "wall"})
BULLET_BLOCKERS = frozenset({"tree", "wall", "chest"})
DEMOLITION = {"tree": 0.5, "fence": 0.5, "wall": 1.5, "floor": 0.5, "chest": 1.5, "campfire": 0.5}
MONSTER_DEMOLITION = {"fence": 1.0, "wall": 3.0}
RECIPES = {
    "fence": {"inputs": {"wood": 1}, "output": "fence", "count": 2},
    "wall": {"inputs": {"wood": 1}, "output": "wall", "count": 1},
    "floor": {"inputs": {"wood": 1}, "output": "floor", "count": 1},
    "chest": {"inputs": {"wood": 2}, "output": "chest", "count": 1},
    "campfire": {"inputs": {"wood": 1}, "output": "campfire", "count": 1},
    "recycle_fences": {"inputs": {"fence": 2}, "output": "wood", "count": 1},
}
ITEM_KINDS = frozenset({"wood", "axe"}) | BUILDINGS | FOODS.keys() | IGNITERS.keys() | GUNS.keys()
