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
