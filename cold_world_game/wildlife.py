MONSTER_TYPES = {
    "small": {"hp": 10, "speed": 1.2, "damage": 1, "interval": 1.0, "score": 1.0},
    "big": {"hp": 50, "speed": 1.2, "damage": 2, "interval": 1.5, "score": 4.0},
    "fast": {"hp": 10, "speed": 4.8, "damage": 1, "interval": 1.0, "score": 2.5},
    "crawler": {"hp": 6, "speed": 0.75, "damage": 0.6, "interval": 1.2, "score": 1.0},
    "armored": {"hp": 24, "speed": 0.9, "damage": 1.5, "interval": 1.4, "score": 3.0},
    "stalker": {"hp": 8, "speed": 2.0, "damage": 1, "interval": 0.9, "score": 2.0},
    "tree_spirit": {"hp": 18, "speed": 0, "damage": 2, "interval": 1.6, "score": 2.0},
    "frost_guard": {"hp": 140, "speed": 0, "damage": 5, "interval": 1.8, "score": 8.0},
    "ember_guard": {"hp": 140, "speed": 0, "damage": 5, "interval": 1.6, "score": 8.0},
}

BIOME_GUARDS = {"tree_spirit": "tree_shot", "frost_guard": "ice_beam", "ember_guard": "ember_shot"}

OUTDOOR_FEATURES = {
    "park_bench": {"chance": 0.02, "stream": "open_park_bench:v1"},
    "mounted_gun": {"chance": 0.005, "stream": "open_mounted_gun:v1", "ammo": 80},
}
SEATS = frozenset(OUTDOOR_FEATURES) | {"service_gun"}
REPAIRABLE = frozenset({"service_gun", "fixed_heater", "cable_station", "street_lamp", "bridge_pier"})
MOUNTED_RESUPPLY = 24
# The widened crossing averages about 139 tiles between the two approach points.
BRIDGE_REPAIRS_PER_CROSSING = 10
CABLE_REPAIR_PARTS = BRIDGE_REPAIRS_PER_CROSSING * 2
SERVICE_GUN_REPAIR_PARTS = (BRIDGE_REPAIRS_PER_CROSSING + 1) // 2
DEVICE_REPAIR_SECONDS = 1.5
WRENCH_USES = CABLE_REPAIR_PARTS * 2
