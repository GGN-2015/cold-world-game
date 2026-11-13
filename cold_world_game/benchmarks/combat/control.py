import math


def player_position(index):
    if index == 0:
        return 0, 0
    return (index % 4 - 1.5) * 1.1, (index // 4 - 1.5) * 1.1


def formation(index, scenario, elapsed):
    base_x, base_y = player_position(index)
    center = 60 * math.sin(elapsed / 90) if scenario == "march" else 0
    speed = 60 / 90 * math.cos(elapsed / 90) if scenario == "march" else 0
    return (center + base_x + .4 * math.sin(elapsed * .7), base_y + .25 * math.cos(elapsed * .7), speed + .28 * math.cos(elapsed * .7), -.175 * math.sin(elapsed * .7))


def steer(position, velocity, goal, speed=4, delay=0):
    if speed <= 0:
        return 0, 0
    horizontal = (goal[2] + 2 * (goal[0] - position[0] - velocity[0] * delay)) / speed
    vertical = (goal[3] + 2 * (goal[1] - position[1] - velocity[1] * delay)) / speed
    magnitude = max(1, math.hypot(horizontal, vertical))
    return horizontal / magnitude, vertical / magnitude


def firing_lane_clear(player, target, teammates, weapon, radius=19):
    if weapon not in {"rifle", "shotgun", "handgun"}:
        return True
    delta_x, delta_y = target["x"] - player["x"], target["y"] - player["y"]
    length = math.hypot(delta_x, delta_y)
    if length < .001:
        return False
    spread = math.sin(math.radians(12)) if weapon == "shotgun" else 0
    for teammate in teammates:
        if teammate["id"] == player["id"] or teammate.get("downed"):
            continue
        offset_x, offset_y = teammate["x"] - player["x"], teammate["y"] - player["y"]
        along = (offset_x * delta_x + offset_y * delta_y) / length
        if -.6 < along < radius:
            across = abs(offset_x * delta_y - offset_y * delta_x) / length
            if across < .6 + max(0, along) * spread:
                return False
    return True


def combat_target(player, monsters, teammates, weapon):
    candidates = (monster for monster in monsters if monster.get("hp", 1) > 0 and not monster.get("sleeping") and monster.get("rising") is None)
    ordered = sorted(candidates, key=lambda monster: (monster["x"] - player["x"]) ** 2 + (monster["y"] - player["y"]) ** 2)
    return next((monster for monster in ordered if firing_lane_clear(player, monster, teammates, weapon)), None)
