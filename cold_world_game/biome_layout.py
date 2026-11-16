"""Deterministic features of the barrier between the first two regions."""

import math
import random
from functools import lru_cache

from .models import Structure
from .wildlife import BRIDGE_REPAIRS_PER_CROSSING


BIOMES = ("forest", "fog", "lake")
BIOME_RING = {"radius": 1334, "half_width": 24, "overlap": 1.5, "kinds": BIOMES, "axis_bridges": True}
LEGACY_BIOMES = (*BIOMES, "guard")
BRIDGE_DEAD_END_CHANCE = .25


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


def sector_angles(start, end, radius, spacing):
    steps = math.ceil(math.radians(end - start) * radius / spacing)
    return (start + (step + .5) * (end - start) / steps for step in range(steps))


@lru_cache(maxsize=32)
def bridge_layout(seed, size, radius, half_width, overlap, kinds):
    piers, reserved = {}, set()
    routes = []
    outer = radius + half_width + size
    inner = radius - half_width - size
    for kind, start, end in sectors(seed, kinds):
        if kind != "lake":
            continue
        for angle in sector_angles(start, end, radius, 100):
            x, y = polar(inner, angle)
            dx, dy = ((1 if x > 0 else -1), 0) if abs(x) >= abs(y) else (0, (1 if y > 0 else -1))
            route = [(x, y)]
            while math.hypot(x, y) < outer:
                x, y = x + dx, y + dy
                route.append((x, y))
            if reserved.isdisjoint(route):
                routes.append((route, dx, dy))
                reserved.update(route)
                last = len(route) - 1
                points = [route[round(last * index / BRIDGE_REPAIRS_PER_CROSSING)]
                          for index in range(BRIDGE_REPAIRS_PER_CROSSING + 1)]
                piers.update((point, ("bridge_pier", successor)) for point, successor in zip(points, points[1:]))

    for route, dx, dy in routes:
        stream = random.Random(f"{seed}:{route[0]}:bridge_dead_end:v1")
        if stream.random() >= BRIDGE_DEAD_END_CHANCE:
            continue
        side = stream.choice((-1, 1))
        x, y = route[len(route) // 2]
        branch = [(x - dy * side * length, y + dx * side * length) for length in range(1, 20)]
        if reserved.isdisjoint(branch) and all(
            "lake" in chunk_biomes(seed, (px + size // 2) // size, (py + size // 2) // size, size, radius, half_width, overlap, kinds)
            for px, py in branch
        ):
            reserved.update(branch)
            piers[branch[0]] = ("bridge_pier", branch[9])
            piers[branch[9]] = ("bridge_pier", branch[-1])

    by_chunk = {}
    for x, y in reserved:
        point = ((x + size // 2) // size, (y + size // 2) // size)
        by_chunk.setdefault(point, set()).add((x, y))
    return piers, by_chunk


@lru_cache(maxsize=32)
def stations(seed, size, radius, half_width, overlap, kinds, axis_bridges=False):
    points = {}
    for index, (kind, start, end) in enumerate(sectors(seed, kinds)):
        spacing = 37 if kind == "guard" else 100
        steps = math.ceil(math.radians(end - start) * radius / spacing)
        for step, angle in enumerate(sector_angles(start, end, radius, spacing)):
            outer = polar(radius + half_width + size, angle)
            if kind == "forest":
                a, b = polar(radius - half_width - size + 4, angle), outer
                points[a] = ("cable_station", b)
                points[b] = ("cable_station", a)
            elif kind == "fog":
                for offset in (-16, 0, 16):
                    points[polar(radius + offset, angle)] = ("street_lamp", None)
            elif kind == "lake":
                if axis_bridges:
                    continue
                piers = [polar(radius + offset, angle) for offset in (-32, -16, 0, 16, 32, 40)]
                for pier, next_pier in zip(piers, piers[1:]):
                    points[pier] = ("bridge_pier", next_pier)
            else:
                points[polar(radius - 16, angle)] = ("service_gun", None)
                points[polar(radius - 5, angle)] = ("frost_guard" if (index + step) % 2 == 0 else "ember_guard", None)
                points[polar(radius + 15, angle + (end - start) / steps / 3)] = ("ember_guard" if (index + step) % 2 == 0 else "frost_guard", None)
    if axis_bridges:
        points.update(bridge_layout(seed, size, radius, half_width, overlap, kinds)[0])
    chunks = {}
    for (x, y), definition in points.items():
        key = (x + size // 2) // size, (y + size // 2) // size
        chunks.setdefault(key, {})[x, y] = definition
    return chunks


def add_biome_terrain(seed, horizontal, vertical, settings, objects, interior):
    size = settings["size"]
    parameters = ring_parameters(settings)
    zones = chunk_biomes(seed, horizontal, vertical, *parameters)
    axis_bridges = settings["biome_ring"].get("axis_bridges", False)
    point = horizontal, vertical
    features = stations(seed, *parameters, axis_bridges).get(point, {})
    reserved = bridge_layout(seed, *parameters)[1].get(point, set()) if axis_bridges else set()
    if not (zones or features or reserved):
        return objects
    objects = [entry for entry in objects if (entry.x, entry.y) not in reserved]
    occupied = {(entry.x, entry.y) for entry in objects if entry.kind != "tree"} | set(interior)
    tile_positions = [(horizontal * size + dx, vertical * size + dy)
                      for dx in range(-(size // 2), size // 2 + 1)
                      for dy in range(-(size // 2), size // 2 + 1)]
    actual_features = {}
    for (x, y), (kind, link) in sorted(features.items()):
        if axis_bridges and kind == "bridge_pier":
            actual_features[x, y] = (kind, link, [x, y])
            continue
        available = [tile for tile in tile_positions if tile not in occupied and tile not in actual_features and tile not in reserved]
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
            if (x, y) in occupied or (x, y) in actual_features or (x, y) in reserved or any(
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
