MONSTER_TYPES = {
    "small": {"hp": 10, "speed": 1.2, "damage": 1, "interval": 1.0, "score": 1.0},
    "big": {"hp": 50, "speed": 1.2, "damage": 2, "interval": 1.5, "score": 4.0},
    "fast": {"hp": 10, "speed": 4.8, "damage": 1, "interval": 1.0, "score": 2.5},
    "crawler": {"hp": 6, "speed": 0.75, "damage": 0.6, "interval": 1.2, "score": 1.0},
    "armored": {"hp": 24, "speed": 0.9, "damage": 1.5, "interval": 1.4, "score": 3.0},
    "stalker": {"hp": 8, "speed": 2.0, "damage": 1, "interval": 0.9, "score": 2.0},
}

OUTDOOR_FEATURES = {
    "park_bench": {"chance": 0.02, "stream": "open_park_bench:v1"},
    "mounted_gun": {"chance": 0.01, "stream": "open_mounted_gun:v1", "ammo": 5000},
}
SEATS = frozenset(OUTDOOR_FEATURES)
