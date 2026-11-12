import math

from .constants import GUNS


def homing_position(projectile, elapsed, target_x, target_y):
    settings = GUNS["homing_missile"]
    age = max(0.0, elapsed - projectile.spawned_at)
    direction_x = projectile.velocity_x / settings["speed"]
    direction_y = projectile.velocity_y / settings["speed"]
    launch = settings["launch_duration"]
    reach = settings["launch_distance"]
    if age < launch:
        progress = age / launch
        return projectile.origin_x + direction_x * reach * progress, projectile.origin_y + direction_y * reach * progress
    start_x = projectile.origin_x + direction_x * reach
    start_y = projectile.origin_y + direction_y * reach
    bend = min(4.0, math.hypot(target_x - start_x, target_y - start_y) / 2)
    control_x, control_y = start_x + direction_x * bend, start_y + direction_y * bend
    progress = min(1.0, (age - launch) / (projectile.detonates_at - projectile.spawned_at - launch))
    inverse = 1 - progress
    return inverse * inverse * start_x + 2 * inverse * progress * control_x + progress * progress * target_x, inverse * inverse * start_y + 2 * inverse * progress * control_y + progress * progress * target_y
