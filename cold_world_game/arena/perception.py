from ..constants import BODY_RADIUS, DEFAULT_VIEWPORT


MINIMUM_VISIBLE_FRACTION = 0.3


def can_observe(observer, target, radius=BODY_RADIUS):
    half_width, half_height = DEFAULT_VIEWPORT[0] / 2, DEFAULT_VIEWPORT[1] / 2
    horizontal, vertical = target.x - observer.x, target.y - observer.y
    if radius == 0:
        return abs(horizontal) <= half_width and abs(vertical) <= half_height
    width = max(0.0, min(half_width, horizontal + radius) - max(-half_width, horizontal - radius))
    height = max(0.0, min(half_height, vertical + radius) - max(-half_height, vertical - radius))
    return width * height + 1e-12 >= (radius * 2) ** 2 * MINIMUM_VISIBLE_FRACTION
