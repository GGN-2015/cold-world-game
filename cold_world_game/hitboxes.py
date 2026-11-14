import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MonsterHitbox:
    rectangles: tuple
    bounds: tuple
    aim: tuple


def compile_hitbox(definition, size, radius):
    rectangles = []
    active = {}
    width, height, offset = definition["width"], definition["height"], definition["offset"]
    for vertical, row in enumerate([*definition["rows"], 0]):
        runs = set()
        horizontal = 0
        while horizontal < size:
            if not row & (1 << horizontal):
                horizontal += 1
                continue
            first = horizontal
            while horizontal < size and row & (1 << horizontal):
                horizontal += 1
            runs.add((first, horizontal))
        for run in sorted(active.keys() - runs):
            first_y = active.pop(run)
            rectangles.append((run[0] * width / size - width / 2, first_y * height / size - height / 2 - offset,
                               run[1] * width / size - width / 2, vertical * height / size - height / 2 - offset))
        for run in sorted(runs - active.keys()):
            active[run] = vertical
    body = max(rectangles, key=lambda rectangle: (rectangle[2] - rectangle[0]) * (rectangle[3] - rectangle[1]))
    aim = ((body[0] + body[2]) / 2, (body[1] + body[3]) / 2)
    expanded = tuple((left - radius, top - radius, right + radius, bottom + radius) for left, top, right, bottom in rectangles)
    bounds = (min(rectangle[0] for rectangle in expanded), min(rectangle[1] for rectangle in expanded),
              max(rectangle[2] for rectangle in expanded), max(rectangle[3] for rectangle in expanded))
    return MonsterHitbox(expanded, bounds, aim)


MANIFEST = json.loads((Path(__file__).parent / "static" / "assets" / "manifest.json").read_text(encoding="utf-8"))["monster_hitboxes"]
BULLET_RADIUS = MANIFEST["bullet_radius"]
MONSTER_HITBOXES = {name: compile_hitbox(definition, MANIFEST["size"], BULLET_RADIUS) for name, definition in MANIFEST["profiles"].items()}
MONSTER_BOUNDS = (min(shape.bounds[0] for shape in MONSTER_HITBOXES.values()), min(shape.bounds[1] for shape in MONSTER_HITBOXES.values()),
                  max(shape.bounds[2] for shape in MONSTER_HITBOXES.values()), max(shape.bounds[3] for shape in MONSTER_HITBOXES.values()))


def monster_hitbox(monster, elapsed, activity):
    resting, rising = activity
    name = f"monster_{monster.kind}"
    if (monster.big or monster.fast) and resting:
        name += "_sleep"
    elif monster.big and rising is not None:
        name += "_rise"
    elif elapsed < monster.frozen_until:
        name += "_frozen"
    return MONSTER_HITBOXES[name]


def segment_rectangle(start_x, start_y, end_x, end_y, left, top, right, bottom):
    lower, upper = 0.0, 1.0
    for start, end, near_edge, far_edge in ((start_x, end_x, left, right), (start_y, end_y, top, bottom)):
        delta = end - start
        if abs(delta) < 1e-12:
            if start < near_edge or start > far_edge:
                return None
        else:
            near, far = (near_edge - start) / delta, (far_edge - start) / delta
            lower = max(lower, min(near, far))
            upper = min(upper, max(near, far))
            if lower > upper:
                return None
    return lower


def segment_monster(start_x, start_y, end_x, end_y, monster, shape):
    start_x, start_y, end_x, end_y = start_x - monster.x, start_y - monster.y, end_x - monster.x, end_y - monster.y
    if segment_rectangle(start_x, start_y, end_x, end_y, *shape.bounds) is None:
        return None
    earliest = None
    for rectangle in shape.rectangles:
        fraction = segment_rectangle(start_x, start_y, end_x, end_y, *rectangle)
        if fraction is not None and (earliest is None or fraction < earliest):
            earliest = fraction
            if fraction == 0:
                break
    return earliest


def monster_aim(world, monster):
    horizontal, vertical = monster_hitbox(monster, world.elapsed, world.monster_activity()).aim
    return monster.x + horizontal, monster.y + vertical
