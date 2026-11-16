"""Deterministic features of the barrier between the first two regions."""

import math
import random
from functools import lru_cache

from .models import Structure


BIOMES = ("forest", "fog", "lake")
BIOME_RING = {"radius": 667, "half_width": 24, "overlap": 1.5, "kinds": BIOMES}
LEGACY_BIOMES = (*BIOMES, "guard")


def ring_parameters(settings):
    ring = settings["biome_ring"]
    return settings["size"], ring["radius"], ring["half_width"], ring["overlap"], tuple(ring.get("kinds", LEGACY_BIOMES))


@lru_cache(maxsize=32)
def sectors(seed, kinds=BIOMES):
    rng = random.Random(f"{seed}:biome_ring:v1")
    order = list(kinds)
    rng.shuffle(order)
    kinds = order + order
    weights = [rng.uniform(.85, 1.15) for kind in kinds]
    angle = rng.uniform(0, 360)
    result = []
    for kind, weight in zip(kinds, weights):
        span = 360 * weight / sum(weights)
        result.append((kind, angle, angle + span))
        angle += span
    return tuple(result)


@lru_cache(maxsize=16384)
def chunk_biomes(seed, horizontal, vertical, size, radius, half_width, overlap, kinds):
    x, y = horizontal * size, vertical * size
    if abs(math.hypot(x, y) - radius) > half_width:
        return ()
    angle = math.degrees(math.atan2(y, x))
    return tuple(kind for kind, start, end in sectors(seed, kinds)
                 if (angle - start + overlap) % 360 <= end - start + 2 * overlap)


def polar(radius, angle):
    radians = math.radians(angle)
    return math.floor(radius * math.cos(radians) + .5), math.floor(radius * math.sin(radians) + .5)


@lru_cache(maxsize=32)
def stations(seed, size, radius, half_width, overlap, kinds):
    points = {}
    for index, (kind, start, end) in enumerate(sectors(seed, kinds)):
        steps = math.ceil(math.radians(end - start) * radius / (37 if kind == "guard" else 100))
        for step in range(steps):
            angle = start + (step + .5) * (end - start) / steps
            outer = polar(radius + half_width + size, angle)
            if kind == "forest":
                a, b = polar(radius - half_width - size + 4, angle), outer
                points[a] = ("cable_station", b)
                points[b] = ("cable_station", a)
            elif kind == "fog":
                for offset in (-16, 0, 16):
                    points[polar(radius + offset, angle)] = ("street_lamp", None)
            elif kind == "lake":
                piers = [polar(radius + offset, angle) for offset in (-32, -16, 0, 16, 32, 40)]
                for pier, next_pier in zip(piers, piers[1:]):
                    points[pier] = ("bridge_pier", next_pier)
            else:
                points[polar(radius - 16, angle)] = ("service_gun", None)
                points[polar(radius - 5, angle)] = ("frost_guard" if (index + step) % 2 == 0 else "ember_guard", None)
                points[polar(radius + 15, angle + (end - start) / steps / 3)] = ("ember_guard" if (index + step) % 2 == 0 else "frost_guard", None)
    chunks = {}
    for (x, y), definition in points.items():
        key = (x + size // 2) // size, (y + size // 2) // size
        chunks.setdefault(key, {})[x, y] = definition
    return chunks


def add_biome_terrain(seed, horizontal, vertical, settings, objects, interior):
    size = settings["size"]
    parameters = ring_parameters(settings)
    zones = chunk_biomes(seed, horizontal, vertical, *parameters)
    features = stations(seed, *parameters).get((horizontal, vertical), {})
    if not (zones or features):
        return objects
    occupied = {(entry.x, entry.y) for entry in objects if entry.kind != "tree"} | set(interior)
    tile_positions = [(horizontal * size + dx, vertical * size + dy)
                      for dx in range(-(size // 2), size // 2 + 1)
                      for dy in range(-(size // 2), size // 2 + 1)]
    actual_features = {}
    for (x, y), (kind, link) in sorted(features.items()):
        available = [point for point in tile_positions if point not in occupied and point not in actual_features]
        if available:
            position = min(available, key=lambda point: ((point[0] - x) ** 2 + (point[1] - y) ** 2, point))
            actual_features[position] = (kind, link, [x, y])
    result = [entry for entry in objects if (entry.x, entry.y) not in actual_features]
    if "lake" in zones:
        result = [entry for entry in result if entry.kind != "tree"]
    if "forest" in zones:
        trees = {(entry.x, entry.y): entry for entry in result if entry.kind == "tree"}
        rng = random.Random(f"{seed}:{horizontal}:{vertical}:dense_forest:v1")
        for x, y in tile_positions:
            if (x, y) in occupied or (x, y) in actual_features or any(
                (x + sx, y + sy) in occupied or (x + sx, y + sy) in actual_features
                for sx, sy in ((-1, 0), (1, 0), (0, -1), (0, 1))
            ):
                continue
            if (x, y) not in trees and rng.random() < .81:
                trees[x, y] = Structure("tree", x, y)
                result.append(trees[x, y])
        # One disguised sentry per eligible chunk keeps ranged AI bounded.
        if trees:
            rng.choice(list(trees.values())).biome_guard = "tree_spirit"
    for (x, y), (kind, link, anchor) in actual_features.items():
        if kind in {"frost_guard", "ember_guard"}:
            result.append(Structure("guardian_site", x, y, biome_guard=kind))
        else:
            result.append(Structure(kind, x, y, ammo=0 if kind == "service_gun" else None,
                                    biome_link=list(link) if link else None, biome_anchor=anchor if link else None))
    return result
