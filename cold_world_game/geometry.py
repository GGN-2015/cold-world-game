import math

from .constants import BODY_RADIUS, CHUNK_SIZE


def tile(value: float) -> int:
    return math.floor(value + 0.5)


def chunk(value: float) -> int:
    return math.floor((value + CHUNK_SIZE / 2) / CHUNK_SIZE)


def distance(first, second) -> float:
    return math.hypot(first.x - second.x, first.y - second.y)


def circle_square(x: float, y: float, center_x: int, center_y: int, radius=BODY_RADIUS) -> bool:
    delta_x = max(abs(x - center_x) - 0.5, 0)
    delta_y = max(abs(y - center_y) - 0.5, 0)
    return delta_x * delta_x + delta_y * delta_y < radius * radius - 1e-10


def segment_box(start_x, start_y, end_x, end_y, center_x, center_y) -> float | None:
    lower, upper = 0.0, 1.0
    for start, end, center in ((start_x, end_x, center_x), (start_y, end_y, center_y)):
        delta = end - start
        if abs(delta) < 1e-12:
            if abs(start - center) > 0.5:
                return None
        else:
            near = (center - 0.5 - start) / delta
            far = (center + 0.5 - start) / delta
            lower = max(lower, min(near, far))
            upper = min(upper, max(near, far))
            if lower > upper:
                return None
    return lower


def segment_tiles(start_x, start_y, end_x, end_y):
    first_x, first_y = tile(start_x), tile(start_y)
    delta_x, delta_y = end_x - start_x, end_y - start_y
    direction_x = (delta_x > 0) - (delta_x < 0) if abs(delta_x) >= 1e-12 else 0
    direction_y = (delta_y > 0) - (delta_y < 0) if abs(delta_y) >= 1e-12 else 0
    step_x = 1 / abs(delta_x) if direction_x else math.inf
    step_y = 1 / abs(delta_y) if direction_y else math.inf
    next_x = (first_x + direction_x * .5 - start_x) / delta_x if direction_x else math.inf
    next_y = (first_y + direction_y * .5 - start_y) / delta_y if direction_y else math.inf
    vertical_edge = not direction_x and abs(start_x - (first_x - .5)) <= 1e-12
    horizontal_edge = not direction_y and abs(start_y - (first_y - .5)) <= 1e-12
    visited = set()

    def include(horizontal, vertical, edge_x=vertical_edge, edge_y=horizontal_edge):
        for offset_x in (0, -1) if edge_x else (0,):
            for offset_y in (0, -1) if edge_y else (0,):
                point = horizontal + offset_x, vertical + offset_y
                if point not in visited:
                    visited.add(point)
                    yield point

    yield from include(first_x, first_y, abs(start_x - (first_x - .5)) <= 1e-12, abs(start_y - (first_y - .5)) <= 1e-12)
    current_x, current_y = first_x, first_y
    while min(next_x, next_y) <= 1 + 1e-12:
        if next_x < next_y - 1e-12:
            current_x += direction_x
            next_x += step_x
        elif next_y < next_x - 1e-12:
            current_y += direction_y
            next_y += step_y
        else:
            yield from include(current_x + direction_x, current_y)
            yield from include(current_x, current_y + direction_y)
            current_x += direction_x
            current_y += direction_y
            next_x += step_x
            next_y += step_y
        yield from include(current_x, current_y)
    last_x, last_y = tile(end_x), tile(end_y)
    yield from include(last_x, last_y, abs(end_x - (last_x - .5)) <= 1e-12, abs(end_y - (last_y - .5)) <= 1e-12)


def segment_circle(start_x, start_y, end_x, end_y, center_x, center_y, radius=BODY_RADIUS):
    delta_x, delta_y = end_x - start_x, end_y - start_y
    offset_x, offset_y = start_x - center_x, start_y - center_y
    constant = offset_x * offset_x + offset_y * offset_y - radius * radius
    if constant <= 0:
        return 0.0
    quadratic = delta_x * delta_x + delta_y * delta_y
    if quadratic < 1e-16:
        return None
    linear = 2 * (offset_x * delta_x + offset_y * delta_y)
    discriminant = linear * linear - 4 * quadratic * constant
    if discriminant < 0:
        return None
    fraction = (-linear - math.sqrt(discriminant)) / (2 * quadratic)
    return fraction if 0 <= fraction <= 1 else None


def normalized(delta_x, delta_y):
    length = math.hypot(delta_x, delta_y)
    return (delta_x / length, delta_y / length) if length else (0.0, 0.0)


DIRECTIONS = tuple((offset_x, offset_y) for offset_x in (-1, 0, 1) for offset_y in (-1, 0, 1) if offset_x or offset_y)
