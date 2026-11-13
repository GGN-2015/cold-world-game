import colorsys
import importlib.util
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw


DESTINATION = Path(__file__).resolve().parents[1] / "cold_world_game" / "static" / "assets"
PALETTE = {
    "outline": "#263e48",
    "snow": "#e9f3f3",
    "light": "#ffffff",
    "ice": "#b9d6dd",
    "shade": "#8aaebc",
    "wood": "#b68155",
    "wood_light": "#d5ac76",
    "wood_dark": "#704c3e",
    "pine": "#355b56",
    "pine_light": "#548379",
    "gold": "#eebd6b",
    "orange": "#d7784c",
}
ASSETS = {}
ANIMATIONS = {}
COMBAT_EFFECTS = {}
ACTOR_DIRECTIONS = ("down", "left", "right", "up")
WALK_POSES = ((0, 0, 0), (3, -2, 0), (1, 0, -1), (-3, 2, 0), (-1, 1, -1))


def canvas():
    image = Image.new("RGBA", (32, 32))
    return image, ImageDraw.Draw(image)


def save(name, image):
    width, height = image.width * 3, image.height * 3
    image.resize((width, height), Image.Resampling.NEAREST).save(DESTINATION / f"{name}.png", optimize=True)
    ASSETS[name] = {"file": f"{name}.png", "width": width, "height": height}


def snow():
    generator = random.Random(1701)
    for variant in range(3):
        image, drawing = canvas()
        drawing.rectangle((0, 0, 31, 31), fill=("#dcebed", "#d9e9ec", "#deedef")[variant])
        for flake in range(58):
            position_x, position_y = generator.randrange(32), generator.randrange(32)
            drawing.rectangle((position_x, position_y, position_x + generator.choice((0, 1, 2)), position_y), fill=generator.choice(("#d1e3e7", "#e8f1f2", "#cfe1e5")))
        save(f"snow_{variant}", image)


def tree():
    image, drawing = canvas()
    drawing.ellipse((4, 25, 28, 30), fill="#6a97a080")
    drawing.rectangle((14, 21, 18, 28), fill=PALETTE["wood_dark"])
    drawing.rectangle((14, 23, 15, 27), fill=PALETTE["wood"])
    for top, left, right, bottom in ((1, 10, 22, 12), (6, 6, 26, 20), (12, 2, 30, 26)):
        drawing.polygon(((16, top), (right, bottom - 2), (right - 2, bottom), (left + 1, bottom), (left, bottom - 2)), fill=PALETTE["outline"])
        drawing.polygon(((16, top), (right - 1, bottom - 3), (17, bottom - 1), (left + 1, bottom - 3)), fill=PALETTE["pine"])
        drawing.polygon(((16, top), (left + 2, bottom - 5), (12, bottom - 4), (16, bottom - 6), (21, bottom - 4), (right - 3, bottom - 5)), fill=PALETTE["snow"])
        drawing.line((16, top + 1, left + 4, bottom - 6), fill=PALETTE["light"], width=2)
        drawing.point((right - 3, bottom - 3), fill=PALETTE["pine_light"])
    save("tree", image)


def construction():
    for kind in ("wall", "floor", "fence", "chest", "wood"):
        image, drawing = canvas()
        if kind == "wall":
            drawing.rectangle((1, 4, 30, 29), fill=PALETTE["outline"])
            for top in (6, 13, 20):
                drawing.rectangle((2, top, 29, top + 5), fill=PALETTE["wood_dark"])
                drawing.rectangle((3, top, 28, top + 3), fill=PALETTE["wood"])
                drawing.line((4, top, 27, top), fill=PALETTE["wood_light"])
                drawing.line((7, top + 2, 13, top + 2), fill="#996441")
                drawing.rectangle((24, top + 1, 27, top + 3), fill=PALETTE["wood_light"])
            drawing.rectangle((1, 2, 30, 6), fill=PALETTE["snow"])
            drawing.line((3, 2, 29, 2), fill=PALETTE["light"], width=2)
            drawing.rectangle((3, 7, 5, 9), fill=PALETTE["ice"])
        elif kind == "floor":
            drawing.rectangle((0, 0, 31, 31), fill=PALETTE["wood_dark"])
            for left in range(1, 32, 8):
                drawing.rectangle((left, 1, left + 6, 30), fill=PALETTE["wood"])
                drawing.line((left, 2, left, 29), fill=PALETTE["wood_light"])
                drawing.line((left + 3, 7, left + 3, 16), fill="#a37350")
                drawing.point((left + 2, 4), fill=PALETTE["outline"])
                drawing.point((left + 2, 27), fill=PALETTE["outline"])
        elif kind == "fence":
            drawing.ellipse((1, 25, 31, 29), fill="#719aa060")
            for top in (14, 21):
                drawing.rectangle((2, top, 29, top + 3), fill=PALETTE["wood_dark"])
                drawing.line((3, top, 28, top), fill=PALETTE["wood_light"])
            for left in (4, 13, 23):
                drawing.polygon(((left, 28), (left, 8), (left + 2, 5), (left + 5, 8), (left + 5, 28)), fill=PALETTE["outline"])
                drawing.rectangle((left + 1, 9, left + 3, 27), fill=PALETTE["wood"])
                drawing.polygon(((left, 9), (left + 2, 6), (left + 4, 9)), fill=PALETTE["snow"])
        elif kind == "chest":
            drawing.ellipse((2, 25, 30, 30), fill="#577a8660")
            drawing.rectangle((3, 10, 28, 27), fill=PALETTE["outline"])
            drawing.rectangle((4, 12, 27, 25), fill=PALETTE["wood_dark"])
            drawing.rectangle((4, 10, 27, 17), fill=PALETTE["wood"])
            drawing.line((5, 11, 26, 11), fill=PALETTE["wood_light"], width=2)
            drawing.line((5, 19, 26, 19), fill="#422f2d")
            for left in (7, 23):
                drawing.rectangle((left, 10, left + 2, 25), fill=PALETTE["gold"])
                drawing.point((left + 1, 22), fill=PALETTE["wood_dark"])
            drawing.rectangle((14, 16, 18, 22), fill=PALETTE["outline"])
            drawing.rectangle((15, 17, 17, 20), fill=PALETTE["gold"])
            drawing.rectangle((5, 7, 25, 10), fill=PALETTE["snow"])
            drawing.rectangle((9, 6, 21, 8), fill=PALETTE["light"])
        else:
            for offset_x, offset_y in ((3, 18), (10, 10), (11, 20)):
                drawing.polygon(((offset_x, offset_y), (offset_x + 12, offset_y - 5), (offset_x + 17, offset_y - 1), (offset_x + 5, offset_y + 6), (offset_x, offset_y + 4)), fill=PALETTE["outline"])
                drawing.polygon(((offset_x + 2, offset_y), (offset_x + 12, offset_y - 3), (offset_x + 15, offset_y - 1), (offset_x + 5, offset_y + 4)), fill=PALETTE["wood"])
                drawing.line((offset_x + 3, offset_y, offset_x + 11, offset_y - 2), fill=PALETTE["wood_light"])
            drawing.line((15, 13, 20, 24), fill=PALETTE["gold"], width=2)
        save(kind, image)


def campfires():
    for lit in (False, True):
        image, drawing = canvas()
        drawing.ellipse((1, 22, 31, 30), fill="#577a8660")
        drawing.ellipse((3, 18, 29, 29), fill=PALETTE["outline"])
        drawing.ellipse((6, 20, 26, 26), fill="#544538")
        for left, top in ((3, 20), (7, 17), (21, 18), (25, 22), (20, 26), (9, 26)):
            drawing.rectangle((left, top, left + 4, top + 3), fill=PALETTE["shade"])
            drawing.line((left, top, left + 3, top), fill=PALETTE["ice"])
        drawing.line((9, 24, 22, 19), fill=PALETTE["wood_dark"], width=4)
        drawing.line((10, 19, 22, 25), fill=PALETTE["wood"], width=3)
        if lit:
            drawing.polygon(((9, 21), (9, 15), (13, 10), (13, 4), (17, 8), (20, 14), (23, 10), (24, 19), (20, 24), (13, 25)), fill="#b4513b")
            drawing.polygon(((11, 20), (14, 12), (15, 7), (19, 15), (21, 13), (22, 20), (18, 24), (14, 23)), fill="#f5a852")
            drawing.polygon(((14, 21), (16, 15), (19, 19), (19, 23), (16, 24)), fill="#fff0ad")
            drawing.rectangle((20, 5, 21, 6), fill="#f5bb67")
        save("campfire_lit" if lit else "campfire", image)


def travelers():
    for name, coat, back in (("player", "#cf784e", False), ("player_back", "#cf784e", True), ("player_other", "#498a97", False), ("player_other_back", "#498a97", True)):
        image, drawing = canvas()
        drawing.ellipse((7, 26, 26, 30), fill="#4d78877a")
        drawing.rectangle((10, 24, 14, 28), fill=PALETTE["outline"])
        drawing.rectangle((19, 24, 23, 28), fill=PALETTE["outline"])
        drawing.rectangle((8, 15, 25, 24), fill=PALETTE["outline"])
        drawing.rectangle((10, 15, 23, 25), fill=coat)
        drawing.rectangle((7, 18, 10, 23), fill=PALETTE["pine"])
        drawing.rectangle((24, 18, 27, 23), fill=PALETTE["pine"])
        drawing.rectangle((11, 5, 23, 8), fill=PALETTE["outline"])
        drawing.rectangle((8, 8, 25, 16), fill=PALETTE["outline"])
        drawing.rectangle((10, 7, 23, 14), fill=coat)
        drawing.line((12, 6, 21, 6), fill="#efb47e", width=2)
        if back:
            drawing.rectangle((12, 15, 22, 23), fill=PALETTE["wood_dark"])
            drawing.rectangle((13, 16, 21, 21), fill=PALETTE["wood"])
            drawing.line((14, 17, 20, 17), fill=PALETTE["wood_light"])
        else:
            drawing.rectangle((12, 10, 21, 14), fill="#f1c69e")
            drawing.point((14, 11), fill=PALETTE["outline"])
            drawing.point((19, 11), fill=PALETTE["outline"])
            drawing.rectangle((10, 15, 23, 17), fill="#e9cd9a")
            drawing.line((17, 18, 17, 24), fill="#92513c")
        save(name, image)
    image, drawing = canvas()
    drawing.ellipse((4, 22, 29, 28), fill="#5a7f8b88")
    drawing.rectangle((10, 18, 27, 24), fill=PALETTE["outline"])
    drawing.rectangle((10, 19, 23, 23), fill="#cf784e")
    drawing.rectangle((4, 17, 12, 24), fill=PALETTE["outline"])
    drawing.rectangle((5, 18, 11, 22), fill="#e9ba8a")
    drawing.line((24, 19, 28, 17), fill=PALETTE["outline"], width=3)
    save("player_downed", image)


def roster_icons():
    for online in (True, False):
        image, drawing = canvas()
        outline = PALETTE["outline"]
        coat = "#d99363" if online else "#718c9f"
        skin = "#f0c9a0" if online else "#b6c3c9"
        scarf = "#a6d8b6" if online else "#a7bbce"
        drawing.rectangle((5, 23, 26, 30), fill=outline)
        drawing.rectangle((7, 23, 24, 29), fill=coat)
        drawing.rectangle((8, 5, 23, 21), fill=outline)
        drawing.rectangle((10, 8, 21, 19), fill=skin)
        drawing.rectangle((8, 5, 23, 10), fill=outline)
        drawing.rectangle((9, 5, 22, 8), fill=coat)
        drawing.rectangle((7, 9, 24, 11), fill=scarf)
        drawing.rectangle((8, 20, 23, 24), fill=outline)
        drawing.rectangle((9, 20, 22, 22), fill=scarf)
        drawing.rectangle((18, 22, 21, 27), fill=scarf)
        for horizontal in (12, 19):
            drawing.line((horizontal, 14, horizontal + (0 if online else 1), 14 + (1 if online else 0)), fill=outline)
        drawing.line((14, 18, 17, 18), fill="#bf8d72" if online else "#8c9fae")
        save("roster_online" if online else "roster_offline", image)
    image, drawing = canvas()
    for horizontal, vertical, color in ((17, 5, "#9acdbb"), (5, 10, "#edcd94")):
        drawing.rectangle((horizontal - 3, vertical + 10, horizontal + 9, vertical + 18), fill=PALETTE["outline"])
        drawing.rectangle((horizontal - 1, vertical + 11, horizontal + 7, vertical + 17), fill=color)
        drawing.rectangle((horizontal, vertical, horizontal + 6, vertical + 9), fill=PALETTE["outline"])
        drawing.rectangle((horizontal + 1, vertical + 1, horizontal + 5, vertical + 7), fill=color)
        drawing.line((horizontal, vertical + 3, horizontal + 6, vertical + 3), fill=PALETTE["snow"])
    save("roster", image)


def fast_monster_tint(image):
    tinted = image.copy()
    for horizontal in range(image.width):
        for vertical in range(image.height):
            red, green, blue, alpha = image.getpixel((horizontal, vertical))
            if not alpha:
                continue
            hue, saturation, brightness = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
            color = colorsys.hsv_to_rgb((hue + 0.22) % 1, min(1, max(0.18, saturation * 1.3)), brightness)
            tinted.putpixel((horizontal, vertical), (*[round(channel * 255) for channel in color], alpha))
    return tinted


def ice_tint(image):
    tinted = image.copy()
    for horizontal in range(image.width):
        for vertical in range(image.height):
            red, green, blue, alpha = image.getpixel((horizontal, vertical))
            if alpha:
                brightness = (red * 0.3 + green * 0.59 + blue * 0.11) / 255
                tinted.putpixel((horizontal, vertical), (round(24 + brightness * 126), round(68 + brightness * 167), round(126 + brightness * 129), alpha))
    return tinted


def frozen_monster_image(image, big, direction="down", pose=0):
    frozen = ice_tint(image)
    drawing = ImageDraw.Draw(frozen)
    lift = WALK_POSES[pose][2]
    side = direction in ("left", "right")
    for horizontal, vertical in ((8, 16 + lift), (22, 20 + lift)):
        if direction == "left":
            horizontal = 31 - horizontal
        drawing.polygon(((horizontal - 2, vertical), (horizontal - 1, vertical - 5), (horizontal + 2, vertical - 1), (horizontal + 1, vertical + 4)), fill="#549bd7")
        drawing.line((horizontal - 1, vertical - 3, horizontal, vertical + 2), fill="#d7faff", width=1)
    horizontal = 19 if side else 16
    vertical = (7 if big else 11) + lift
    drawing.line((horizontal - 2, vertical, horizontal + 2, vertical), fill="#efffff", width=1)
    drawing.line((horizontal, vertical - 2, horizontal, vertical + 2), fill="#b3efff", width=1)
    return frozen


def frozen_monsters():
    for kind in ("monster_small", "monster_big", "monster_fast"):
        source = Image.open(DESTINATION / f"{kind}.png").convert("RGBA").resize((32, 32), Image.Resampling.NEAREST)
        save(f"{kind}_frozen", frozen_monster_image(source, kind == "monster_big"))


def monsters():
    for big in (False, True):
        image = monster_frame(big, "down", 0)
        save("monster_big" if big else "monster_small", image)
        if not big:
            save("monster_fast", fast_monster_tint(image))


def traveler_frame(coat, direction, pose):
    stride, swing, lift = WALK_POSES[pose]
    image, drawing = canvas()
    drawing.ellipse((7, 27, 26, 30), fill="#4d78876b")
    body = Image.new("RGBA", (32, 32))
    drawing = ImageDraw.Draw(body)
    if direction in ("left", "right"):
        drawing.rectangle((12 - stride, 22, 16 - stride, 28), fill=PALETTE["outline"])
        drawing.rectangle((14 + stride, 22, 18 + stride, 28), fill=PALETTE["outline"])
        drawing.rectangle((13 - stride, 23, 15 - stride, 25), fill="#42636c")
        drawing.rectangle((15 + stride, 23, 17 + stride, 26), fill="#6d7b79")
        drawing.rectangle((16 + stride, 27, 20 + stride, 28), fill=PALETTE["wood_dark"])
        drawing.rectangle((10, 14 + lift, 22, 24 + lift), fill=PALETTE["outline"])
        drawing.rectangle((12, 15 + lift, 21, 23 + lift), fill=coat)
        drawing.rectangle((9, 15 + lift, 13, 22 + lift), fill=PALETTE["wood_dark"])
        drawing.rectangle((9, 16 + lift, 11, 20 + lift), fill=PALETTE["wood"])
        drawing.line((11, 17 + lift, 11, 20 + lift), fill=PALETTE["wood_light"])
        drawing.line((18, 17 + lift, 17 - swing, 23 + lift), fill=PALETTE["outline"], width=4)
        drawing.line((18, 17 + lift, 17 - swing, 21 + lift), fill=coat, width=2)
        drawing.rectangle((16 - swing, 22 + lift, 19 - swing, 24 + lift), fill=PALETTE["pine"])
        drawing.rectangle((12, 5 + lift, 21, 7 + lift), fill=PALETTE["outline"])
        drawing.rectangle((10, 7 + lift, 23, 15 + lift), fill=PALETTE["outline"])
        drawing.rectangle((12, 7 + lift, 21, 14 + lift), fill=coat)
        drawing.line((13, 6 + lift, 20, 6 + lift), fill="#efb47e", width=2)
        drawing.rectangle((19, 9 + lift, 23, 13 + lift), fill="#f1c69e")
        drawing.rectangle((23, 11 + lift, 25, 12 + lift), fill="#f1c69e")
        drawing.point((22, 10 + lift), fill=PALETTE["outline"])
        drawing.rectangle((16, 15 + lift, 22, 17 + lift), fill="#e9cd9a")
        drawing.rectangle((19 - swing, 17 + lift, 21 - swing, 20 + lift), fill="#e9cd9a")
    else:
        left_foot = 28 + (1 if stride > 0 else -1 if stride < 0 else 0)
        right_foot = 28 + (1 if stride < 0 else -1 if stride > 0 else 0)
        drawing.rectangle((10 - abs(stride) // 2, 22, 14, left_foot), fill=PALETTE["outline"])
        drawing.rectangle((19, 22, 23 + abs(stride) // 2, right_foot), fill=PALETTE["outline"])
        drawing.rectangle((11, 23, 13, left_foot - 2), fill="#42636c")
        drawing.rectangle((20, 23, 22, right_foot - 2), fill="#6d7b79")
        drawing.rectangle((10 - abs(stride) // 2, left_foot - 1, 14, left_foot), fill=PALETTE["wood_dark"])
        drawing.rectangle((19, right_foot - 1, 23 + abs(stride) // 2, right_foot), fill=PALETTE["wood_dark"])
        drawing.rectangle((8, 15 + lift, 25, 24 + lift), fill=PALETTE["outline"])
        drawing.rectangle((10, 15 + lift, 23, 24 + lift), fill=coat)
        drawing.rectangle((7, 17 + swing + lift, 10, 22 + swing + lift), fill=PALETTE["pine"])
        drawing.rectangle((24, 17 - swing + lift, 27, 22 - swing + lift), fill=PALETTE["pine"])
        drawing.rectangle((11, 5 + lift, 23, 8 + lift), fill=PALETTE["outline"])
        drawing.rectangle((8, 8 + lift, 25, 16 + lift), fill=PALETTE["outline"])
        drawing.rectangle((10, 7 + lift, 23, 14 + lift), fill=coat)
        drawing.line((12, 6 + lift, 21, 6 + lift), fill="#efb47e", width=2)
        if direction == "up":
            drawing.line((16, 8 + lift, 16, 13 + lift), fill="#aa6246")
            drawing.rectangle((12, 15 + lift, 22, 23 + lift), fill=PALETTE["wood_dark"])
            drawing.rectangle((13, 16 + lift, 21, 21 + lift), fill=PALETTE["wood"])
            drawing.line((14, 17 + lift, 20, 17 + lift), fill=PALETTE["wood_light"])
            drawing.rectangle((15, 21 + lift, 18, 23 + lift), fill=PALETTE["gold"])
        else:
            drawing.rectangle((12, 10 + lift, 21, 14 + lift), fill="#f1c69e")
            drawing.point((14, 11 + lift), fill=PALETTE["outline"])
            drawing.point((19, 11 + lift), fill=PALETTE["outline"])
            drawing.rectangle((10, 15 + lift, 23, 17 + lift), fill="#e9cd9a")
            drawing.line((17, 18 + lift, 17, 23 + lift), fill="#92513c")
    if direction == "left":
        body = body.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    image.alpha_composite(body)
    return image


def small_monster_art(image, direction, step):
    drawing = ImageDraw.Draw(image)
    outline = "#293e4d"
    if direction == "right":
        drawing.polygon(((9, 19), (5, 16), (3, 18), (3, 23), (7, 26), (12, 24)), fill=outline)
        drawing.polygon(((7, 20), (5, 18), (5, 22), (8, 24), (11, 23)), fill="#d5e6e5")
        drawing.polygon(((9, 15), (15, 13), (22, 16), (24, 23), (20, 26), (11, 25), (7, 21)), fill=outline)
        drawing.polygon(((11, 16), (16, 15), (21, 18), (21, 23), (18, 24), (11, 23), (9, 20)), fill="#7093a3")
        drawing.line((12, 17, 15, 18, 16, 21), fill="#a8c7cf", width=1)
        drawing.polygon(((13, 11), (13, 4), (18, 7), (22, 7), (26, 10), (26, 13), (29, 15), (28, 19), (22, 21), (16, 19), (12, 15)), fill=outline)
        drawing.polygon(((15, 10), (15, 7), (18, 10), (23, 9), (25, 12), (24, 15), (27, 16), (25, 18), (21, 19), (17, 17), (14, 14)), fill="#9fbec8")
        drawing.polygon(((15, 12), (19, 11), (21, 13), (25, 13), (24, 15), (27, 16), (24, 18), (20, 18), (18, 16), (15, 17)), fill="#e8f0e9")
        drawing.rectangle((22, 12, 25, 13), fill="#b86564")
        drawing.point((24, 12), fill="#ffd3b2")
        drawing.rectangle((27, 15, 29, 16), fill=outline)
        drawing.polygon(((24, 18), (26, 18), (25, 21)), fill="#f7f0d7")
        drawing.line((17, 18, 18 - step, 22, 20 - step, 25), fill=outline, width=4)
        drawing.line((17, 18, 18 - step, 22), fill="#9cbac5", width=2)
        drawing.line((18 - step, 24, 21 - step, 24), fill="#e5eee7", width=1)
        return
    drawing.polygon(((10, 17), (21, 17), (25, 21), (23, 26), (9, 26), (7, 22)), fill=outline)
    drawing.polygon(((11, 19), (20, 19), (22, 22), (20, 24), (11, 24), (10, 22)), fill="#7598a8")
    for side in (-1, 1):
        horizontal = 16 + side * 9
        reach = step * side // 2
        drawing.line((horizontal, 17, horizontal + side, 21 + reach, horizontal, 24 + reach), fill=outline, width=4)
        drawing.line((horizontal, 18, horizontal + side, 21 + reach), fill="#acc7ce", width=2)
        drawing.line((horizontal - 1, 24 + reach, horizontal + 1, 24 + reach), fill="#ebf1e8", width=1)
    drawing.polygon(((7, 10), (7, 3), (13, 7), (20, 7), (25, 3), (25, 10), (28, 14), (27, 20), (23, 23), (19, 21), (16, 23), (11, 21), (7, 22), (4, 17)), fill=outline)
    drawing.polygon(((9, 10), (9, 7), (13, 10), (20, 9), (23, 7), (23, 12), (25, 15), (24, 19), (21, 21), (17, 20), (12, 20), (9, 18), (7, 16)), fill="#8faebb")
    drawing.polygon(((10, 10), (14, 8), (19, 8), (23, 10), (20, 12), (16, 11), (12, 13)), fill="#bed6d9")
    if direction == "down":
        drawing.polygon(((8, 13), (12, 12), (16, 14), (20, 12), (25, 13), (24, 17), (22, 19), (19, 18), (16, 21), (13, 18), (10, 19), (8, 17)), fill="#e8f0e9")
        drawing.line((10, 13, 13, 14), fill=outline, width=1)
        drawing.line((19, 14, 22, 13), fill=outline, width=1)
        drawing.rectangle((10, 15, 12, 16), fill="#c87570")
        drawing.rectangle((20, 15, 22, 16), fill="#c87570")
        drawing.point((10, 15), fill="#ffceac")
        drawing.point((22, 15), fill="#ffceac")
        drawing.rectangle((15, 17, 17, 18), fill=outline)
        drawing.polygon(((12, 18), (14, 19), (13, 22)), fill="#f8f1d9")
        drawing.polygon(((19, 19), (21, 18), (20, 22)), fill="#f8f1d9")
        drawing.line((13, 24, 19, 24), fill="#bad3d7", width=1)
    else:
        drawing.line((16, 11, 16, 18), fill="#5d8395", width=1)
        drawing.line((11, 13, 13, 16), fill="#b8d1d6", width=1)
        drawing.line((21, 13, 19, 16), fill="#b8d1d6", width=1)
        drawing.polygon(((13, 21), (18, 20), (21, 23), (20, 26), (16, 27), (12, 25)), fill=outline)
        drawing.polygon(((15, 22), (18, 22), (19, 24), (16, 25), (14, 24)), fill="#dceae5")


def big_monster_art(image, direction, step):
    drawing = ImageDraw.Draw(image)
    outline = "#2b414d"
    if direction == "right":
        drawing.polygon(((5, 16), (7, 11), (12, 8), (19, 9), (24, 14), (26, 21), (23, 26), (18, 25), (13, 27), (7, 25), (4, 21)), fill=outline)
        drawing.polygon(((7, 16), (9, 12), (13, 10), (18, 11), (22, 15), (24, 21), (21, 24), (17, 23), (13, 25), (8, 23), (6, 20)), fill="#b0cbcd")
        drawing.polygon(((8, 14), (11, 11), (15, 10), (19, 12), (18, 15), (15, 17), (13, 16), (10, 19), (8, 17)), fill="#e6eee4")
        drawing.line((8, 20, 10, 22, 13, 23), fill="#d3e3da", width=1)
        drawing.ellipse((14, 4, 20, 10), fill=outline)
        drawing.ellipse((15, 5, 19, 9), fill="#e5ede4")
        drawing.polygon(((16, 7), (20, 5), (25, 7), (28, 10), (28, 13), (30, 15), (29, 19), (26, 21), (22, 20), (18, 21), (14, 17), (13, 12)), fill=outline)
        drawing.polygon(((16, 9), (20, 7), (24, 8), (26, 11), (26, 14), (28, 16), (27, 19), (23, 18), (20, 19), (17, 17), (15, 13)), fill="#dce9de")
        drawing.polygon(((17, 9), (20, 7), (23, 8), (24, 10), (21, 11), (18, 10), (16, 13)), fill="#f4f4e8")
        drawing.ellipse((15, 5, 19, 9), fill="#dbe7df")
        drawing.point((17, 7), fill="#a0bdc3")
        drawing.line((22, 11, 25, 12), fill="#536c76", width=1)
        drawing.rectangle((23, 12, 25, 13), fill="#c18160")
        drawing.point((24, 12), fill="#ffdc9e")
        drawing.polygon(((24, 15), (28, 14), (30, 16), (29, 18), (26, 19), (23, 18)), fill="#f4f0dc")
        drawing.rectangle((28, 15, 30, 16), fill=outline)
        drawing.line((26, 18, 28, 18), fill="#768b8d", width=1)
        drawing.polygon(((24, 18), (26, 19), (25, 21)), fill="#f8f1d8")
        reach = step // 2
        drawing.polygon(((17, 16), (21, 15), (24, 19 + reach), (24, 24 + reach), (21, 27 + reach), (17, 26 + reach), (15, 22 + reach)), fill=outline)
        drawing.polygon(((18, 17), (20, 17), (22, 20 + reach), (22, 24 + reach), (20, 25 + reach), (18, 24 + reach), (17, 21 + reach)), fill="#dce9de")
        drawing.line((18, 18, 19, 21 + reach), fill="#f2f3e7", width=2)
        drawing.line((19, 25 + reach, 21, 25 + reach), fill="#9ab7bd", width=1)
        drawing.point((19, 26 + reach), fill="#f5efda")
        drawing.point((21, 26 + reach), fill="#f5efda")
        return
    for side in (-1, 1):
        horizontal = 16 + side * 9
        reach = step * side // 2
        drawing.polygon(((horizontal - 2, 13), (horizontal + 2, 13), (horizontal + 4, 18 + reach), (horizontal + 3, 24 + reach), (horizontal + 1, 27 + reach), (horizontal - 3, 26 + reach), (horizontal - 4, 22 + reach), (horizontal - 4, 17)), fill=outline)
        drawing.polygon(((horizontal - 2, 15), (horizontal + 1, 15), (horizontal + 2, 19 + reach), (horizontal + 1, 24 + reach), (horizontal - 1, 25 + reach), (horizontal - 3, 23 + reach), (horizontal - 2, 20 + reach), (horizontal - 3, 18)), fill="#d5e5da")
        drawing.line((horizontal - 2, 17, horizontal - 2, 20 + reach), fill="#f1f3e6", width=1)
        drawing.line((horizontal - 1, 24 + reach, horizontal + 1, 24 + reach), fill="#9bb9bf", width=1)
        drawing.point((horizontal - 1, 26 + reach), fill="#f6efda")
        drawing.point((horizontal + 1, 26 + reach), fill="#f6efda")
    drawing.polygon(((8, 13), (12, 10), (20, 10), (25, 14), (26, 21), (24, 26), (19, 27), (16, 26), (11, 27), (7, 24), (6, 19)), fill=outline)
    drawing.polygon(((10, 14), (13, 12), (19, 12), (23, 15), (24, 21), (22, 24), (18, 25), (15, 24), (12, 25), (9, 23), (8, 19)), fill="#aac6c9")
    drawing.polygon(((11, 15), (15, 13), (20, 14), (22, 18), (21, 23), (18, 24), (16, 23), (13, 25), (11, 22), (9, 20)), fill="#e0ebdf")
    drawing.line((12, 21, 14, 22), fill="#c0d7d1", width=1)
    drawing.line((20, 20, 19, 23), fill="#c0d7d1", width=1)
    for horizontal in (9, 23):
        drawing.ellipse((horizontal - 3, 3, horizontal + 3, 9), fill=outline)
        drawing.ellipse((horizontal - 2, 4, horizontal + 2, 8), fill="#d2e1d8")
        drawing.point((horizontal, 5), fill="#a0b9be")
    drawing.polygon(((8, 8), (11, 5), (15, 4), (21, 5), (25, 8), (26, 13), (25, 18), (22, 21), (18, 20), (15, 22), (11, 21), (7, 18), (6, 13)), fill=outline)
    drawing.polygon(((10, 9), (12, 7), (16, 6), (20, 7), (23, 9), (24, 13), (23, 17), (21, 19), (18, 18), (15, 20), (12, 19), (9, 17), (8, 13)), fill="#dae7db")
    drawing.polygon(((11, 9), (13, 7), (17, 6), (20, 7), (22, 9), (19, 10), (16, 9), (13, 11)), fill="#f3f3e5")
    if direction == "down":
        drawing.line((10, 11, 13, 12), fill="#627a80", width=1)
        drawing.line((19, 12, 22, 11), fill="#627a80", width=1)
        drawing.rectangle((10, 13, 12, 14), fill="#bc7e5e")
        drawing.rectangle((20, 13, 22, 14), fill="#bc7e5e")
        drawing.point((10, 13), fill="#ffdb9e")
        drawing.point((22, 13), fill="#ffdb9e")
        drawing.polygon(((13, 14), (18, 14), (22, 17), (20, 20), (17, 19), (15, 21), (12, 19), (10, 17)), fill="#f4efdb")
        drawing.polygon(((14, 15), (18, 15), (19, 16), (17, 18), (15, 18), (13, 16)), fill=outline)
        drawing.line((16, 18, 16, 19), fill="#7d9494", width=1)
        drawing.polygon(((11, 18), (13, 19), (12, 21)), fill="#fcf2d6")
        drawing.polygon(((20, 19), (22, 18), (21, 21)), fill="#fcf2d6")
    else:
        drawing.line((11, 12, 13, 14, 12, 17), fill="#b1ccc8", width=1)
        drawing.line((21, 12, 19, 14, 20, 17), fill="#b1ccc8", width=1)
        drawing.line((16, 10, 16, 14), fill="#e8eee0", width=1)
        drawing.polygon(((14, 24), (16, 23), (19, 24), (19, 26), (17, 27), (14, 26)), fill="#e6edde")


def monster_frame(big, direction, pose):
    if direction == "left":
        return monster_frame(big, "right", pose).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    step = (0, 2, 1, -2, -1)[pose]
    lift = WALK_POSES[pose][2]
    image, drawing = canvas()
    drawing.ellipse((3, 27, 29, 30), fill="#587e8d66")
    for horizontal, reach in ((10, step), (22, -step)):
        width = 3 if big else 2
        foot = horizontal + reach
        drawing.polygon(((horizontal - width, 22), (horizontal + width, 22), (foot + width, 27), (foot + width, 29), (foot - width, 29), (foot - width - 1, 27)), fill="#293e4d")
        if big:
            drawing.polygon(((foot - 2, 24), (foot + 1, 24), (foot + 2, 27), (foot + 2, 28), (foot - 2, 28), (foot - 3, 27)), fill="#d2e3d8")
            for toe in (-2, 0, 2):
                drawing.point((foot + toe, 29), fill="#f2ead3")
        else:
            drawing.rectangle((foot - width + 1, 26, foot + width - 1, 27), fill="#7093a3")
            drawing.line((foot - width + 1, 28, foot + width - 1, 28), fill="#e8eee3", width=1)
    body = Image.new("RGBA", (32, 32))
    if big:
        big_monster_art(body, direction, step)
    else:
        small_monster_art(body, direction, step)
    image.alpha_composite(body, (0, lift))
    return image


def actor_animations():
    for kind in ("player", "player_other", "monster_small", "monster_big", "monster_fast", "monster_small_frozen", "monster_big_frozen", "monster_fast_frozen"):
        base_kind = kind.removesuffix("_frozen")
        sheet = Image.new("RGBA", (160, 128))
        for row, direction in enumerate(ACTOR_DIRECTIONS):
            for pose in range(len(WALK_POSES)):
                if kind.startswith("player"):
                    frame = traveler_frame("#cf784e" if kind == "player" else "#498a97", direction, pose)
                else:
                    frame = monster_frame(base_kind == "monster_big", direction, pose)
                    if base_kind == "monster_fast":
                        frame = fast_monster_tint(frame)
                    if kind.endswith("_frozen"):
                        frame = frozen_monster_image(frame, base_kind == "monster_big", direction, pose)
                sheet.alpha_composite(frame, (pose * 32, row * 32))
        asset = f"{kind}_motion"
        save(asset, sheet)
        ANIMATIONS[kind] = {"asset": asset, "frame_width": 96, "frame_height": 96, "directions": ACTOR_DIRECTIONS, "idle_frame": 0, "walk_frames": [1, 2, 3, 4], "stride": 1.5 if kind.startswith("player") else 1.35 if base_kind == "monster_big" else 1.0}


def sleeping_big_monster_frame():
    image, drawing = canvas()
    outline = "#2b414d"
    drawing.ellipse((3, 27, 29, 30), fill="#587e8d66")
    drawing.polygon(((12, 18), (16, 13), (22, 12), (26, 15), (29, 20), (29, 25), (26, 28), (16, 28), (11, 25), (9, 21)), fill=outline)
    drawing.polygon(((13, 19), (17, 15), (22, 14), (25, 17), (27, 21), (27, 25), (24, 26), (16, 26), (12, 23)), fill="#d5e5d9")
    drawing.polygon(((15, 18), (18, 15), (22, 14), (25, 17), (25, 20), (21, 19), (19, 21), (16, 20)), fill="#f0f2e5")
    drawing.line((23, 22, 25, 24, 24, 26), fill="#a8c3c5", width=1)
    drawing.ellipse((8, 10, 14, 16), fill=outline)
    drawing.ellipse((9, 11, 13, 15), fill="#dbe7dc")
    drawing.polygon(((5, 16), (8, 13), (12, 13), (16, 16), (17, 22), (14, 26), (8, 26), (3, 24), (2, 20)), fill=outline)
    drawing.polygon(((6, 17), (9, 15), (12, 15), (14, 17), (15, 21), (13, 24), (8, 24), (5, 22), (4, 20)), fill="#deeadf")
    drawing.line((8, 18, 10, 19, 12, 18), fill="#7d9598", width=1)
    drawing.polygon(((4, 21), (8, 20), (10, 22), (9, 24), (5, 24), (3, 22)), fill="#f5efdc")
    drawing.rectangle((3, 21, 5, 22), fill=outline)
    drawing.polygon(((14, 23), (18, 23), (21, 25), (20, 28), (13, 28), (11, 26)), fill=outline)
    drawing.polygon(((14, 24), (18, 24), (19, 26), (17, 27), (13, 26)), fill="#e3ecdf")
    drawing.point((14, 27), fill="#f6eed6")
    drawing.point((17, 27), fill="#f6eed6")
    return image


def sleeping_monster_frame(big):
    if big:
        return sleeping_big_monster_frame()
    image, drawing = canvas()
    outline = "#293e4d"
    drawing.ellipse((3, 27, 29, 30), fill="#587e8d66")
    drawing.polygon(((11, 19), (16, 14), (23, 14), (28, 18), (29, 24), (26, 27), (13, 27), (9, 24)), fill=outline)
    drawing.polygon(((13, 20), (17, 16), (22, 16), (26, 19), (27, 24), (24, 25), (14, 25), (11, 23)), fill="#7f9fac")
    drawing.polygon(((14, 18), (18, 15), (23, 16), (27, 19), (26, 22), (23, 20), (20, 22), (18, 20), (14, 22)), fill="#dce9e2")
    drawing.line((19, 24, 22, 26, 27, 25), fill=outline, width=2)
    drawing.line((21, 25, 26, 25), fill="#c8ddd8", width=1)
    drawing.polygon(((3, 19), (4, 12), (9, 16), (13, 17), (16, 22), (12, 26), (6, 25), (3, 23)), fill=outline)
    drawing.polygon(((5, 19), (5, 16), (9, 19), (12, 19), (14, 22), (11, 24), (7, 23), (5, 22)), fill="#dfece6")
    drawing.line((7, 21, 10, 22), fill="#7a6777", width=1)
    drawing.rectangle((3, 22, 5, 23), fill=outline)
    drawing.polygon(((8, 24), (10, 24), (9, 26)), fill="#f4edd6")
    drawing.line((10, 26, 15, 27), fill="#dce9df", width=2)
    drawing.line((21, 16, 24, 17), fill="#f6f7ee", width=1)
    return image


def monster_resting():
    sleeping = sleeping_monster_frame(True)
    save("monster_big_sleep", sleeping)
    save("monster_fast_sleep", fast_monster_tint(sleeping_monster_frame(False)))
    standing = monster_frame(True, "down", 0)
    sheet = Image.new("RGBA", (32 * 6, 32))
    for frame in range(6):
        if frame == 0:
            image = sleeping.copy()
        elif frame < 3:
            image, drawing = canvas()
            drawing.ellipse((3, 27, 29, 30), fill="#587e8d66")
            height = 17 if frame == 1 else 23
            body = standing.crop((1, 1, 31, 30)).resize((30, height), Image.Resampling.NEAREST)
            image.alpha_composite(body, (1, 29 - height))
        else:
            image = standing.copy()
            drawing = ImageDraw.Draw(image)
            if frame < 5:
                left_hand = 18 if frame == 3 else 10
                right_hand = 22 if frame == 3 else 14
                drawing.line((7, 16, left_hand, 21), fill=PALETTE["outline"], width=5)
                drawing.line((7, 16, left_hand, 21), fill=PALETTE["ice"], width=3)
                drawing.ellipse((left_hand - 2, 19, left_hand + 2, 23), fill="#dbe9dc")
                drawing.line((25, 16, right_hand, 19), fill=PALETTE["outline"], width=5)
                drawing.line((25, 16, right_hand, 19), fill=PALETTE["ice"], width=3)
                drawing.ellipse((right_hand - 2, 17, right_hand + 2, 21), fill="#dbe9dc")
        drawing = ImageDraw.Draw(image)
        if frame > 0:
            for flake in range(7):
                horizontal = max(1, min(30, 16 + (-1 if flake % 2 else 1) * (3 + frame + flake)))
                vertical = min(30, 13 + flake % 3 * 3 + frame * 2)
                drawing.rectangle((horizontal, vertical, horizontal + 1, vertical + 1), fill=(239, 249, 255, 240 - frame * 22))
        sheet.alpha_composite(image, (frame * 32, 0))
    save("monster_big_rise", sheet)
    COMBAT_EFFECTS["monster_big_rise"] = {"asset": "monster_big_rise", "frame_width": 96, "frame_height": 96, "frames": 6, "duration": 1.0}


def monster_sleep_effect():
    frames = 24
    sheet = Image.new("RGBA", (32 * frames, 32))
    for frame in range(frames):
        phase = frame / frames
        opacity = round(255 * min(1, phase / 0.18, (1 - phase) / 0.25))
        drift = round(math.sin(phase * math.tau))
        rise = round(phase * 5)
        image, drawing = canvas()
        for horizontal, vertical, size in ((4, 22, 5), (12, 15, 6), (21, 9, 7)):
            left, top = horizontal + drift, vertical - rise
            points = ((left, top), (left + size - 1, top), (left, top + size - 1), (left + size - 1, top + size - 1))
            drawing.line(points, fill=(45, 78, 96, opacity), width=3)
            drawing.line(points, fill=(218, 246, 255, opacity), width=1)
        sheet.alpha_composite(image, (frame * 32, 0))
    save("fx_sleep_zzz", sheet)
    COMBAT_EFFECTS["fx_sleep_zzz"] = {"asset": "fx_sleep_zzz", "frame_width": 96, "frame_height": 96, "frames": frames, "duration": 2.4}


def equipment():
    for kind in ("axe", "lighter", "matches", "handgun", "shotgun", "rifle", "gasoline", "diesel", "kerosene"):
        image, drawing = canvas()
        if kind == "axe":
            drawing.line((9, 27, 22, 7), fill=PALETTE["outline"], width=5)
            drawing.line((9, 26, 21, 7), fill=PALETTE["wood"], width=3)
            drawing.polygon(((16, 6), (24, 3), (29, 7), (25, 15), (18, 11)), fill=PALETTE["outline"])
            drawing.polygon(((18, 6), (24, 5), (27, 8), (24, 12), (19, 10)), fill=PALETTE["ice"])
            drawing.line((25, 6, 27, 8, 24, 12), fill=PALETTE["light"], width=2)
        elif kind in ("handgun", "shotgun", "rifle"):
            barrel = 15 if kind == "handgun" else 26
            drawing.rectangle((3, 10, barrel + 3, 15), fill=PALETTE["outline"])
            drawing.line((5, 10, barrel + 2, 10), fill=PALETTE["shade"], width=2)
            drawing.polygon(((7, 15), (15, 15), (12, 25), (6, 25)), fill=PALETTE["outline"])
            drawing.line((9, 17, 8, 23), fill=PALETTE["wood"], width=3)
            if kind != "handgun":
                drawing.rectangle((17, 13, 24, 17), fill=PALETTE["wood"])
                drawing.polygon(((3, 13), (3, 23), (10, 20), (11, 14)), fill=PALETTE["wood_dark"])
            if kind == "rifle":
                drawing.rectangle((13, 6, 21, 8), fill=PALETTE["outline"])
                drawing.rectangle((17, 8, 18, 10), fill=PALETTE["outline"])
                drawing.rectangle((17, 17, 20, 22), fill=PALETTE["outline"])
        elif kind in ("gasoline", "diesel", "kerosene"):
            color = {"gasoline": "#bb6752", "diesel": "#c0a259", "kerosene": "#548d9d"}[kind]
            drawing.rectangle((7, 9, 25, 28), fill=PALETTE["outline"])
            drawing.rectangle((8, 10, 24, 26), fill=color)
            drawing.rectangle((10, 5, 22, 10), fill=PALETTE["outline"])
            drawing.rectangle((13, 7, 19, 9), fill="#00000000")
            drawing.rectangle((7, 7, 10, 10), fill=PALETTE["shade"])
            drawing.line((11, 14, 21, 23), fill="#ffffff50", width=2)
            drawing.line((21, 14, 11, 23), fill="#ffffff50", width=2)
        elif kind == "lighter":
            drawing.rectangle((10, 10, 22, 28), fill=PALETTE["outline"])
            drawing.rectangle((11, 14, 21, 26), fill="#d29357")
            drawing.rectangle((11, 9, 21, 14), fill=PALETTE["shade"])
            drawing.rectangle((12, 10, 15, 12), fill=PALETTE["light"])
            drawing.rectangle((18, 7, 21, 10), fill=PALETTE["outline"])
        else:
            drawing.polygon(((6, 12), (21, 6), (27, 10), (27, 24), (12, 29), (6, 25)), fill=PALETTE["outline"])
            drawing.polygon(((7, 12), (21, 8), (25, 11), (12, 16)), fill=PALETTE["gold"])
            drawing.polygon(((12, 17), (25, 12), (25, 23), (12, 27)), fill="#b8614f")
            drawing.line((8, 15, 8, 23), fill=PALETTE["wood_light"], width=2)
            drawing.polygon(((16, 19), (20, 15), (22, 20), (19, 24)), fill=PALETTE["gold"])
        save(kind, image)


def compass():
    image, drawing = canvas()
    drawing.polygon(((10, 2), (21, 2), (29, 10), (29, 21), (21, 29), (10, 29), (2, 21), (2, 10)), fill=PALETTE["outline"])
    drawing.polygon(((11, 4), (20, 4), (27, 11), (27, 20), (20, 27), (11, 27), (4, 20), (4, 11)), fill="#91b9c2")
    drawing.polygon(((11, 6), (20, 6), (25, 11), (25, 20), (20, 25), (11, 25), (6, 20), (6, 11)), fill="#152d3a")
    drawing.line((7, 10, 11, 6, 20, 6), fill="#e3f5eb", width=1)
    drawing.line((10, 26, 20, 26, 26, 20), fill="#507888", width=1)
    for points in ((15, 7, 16, 9), (15, 22, 16, 24), (7, 15, 9, 16), (22, 15, 24, 16)):
        drawing.rectangle(points, fill=PALETTE["gold"])
    drawing.line((10, 11, 21, 22), fill="#274551", width=1)
    drawing.line((10, 21, 21, 10), fill="#274551", width=1)
    save("compass_base", image)
    needle, drawing = canvas()
    drawing.polygon(((15, 7), (19, 16), (16, 24), (12, 15)), fill="#0c1b27")
    drawing.polygon(((15, 7), (18, 15), (13, 16)), fill="#f15d58")
    drawing.polygon(((15, 9), (15, 15), (13, 16)), fill="#ffb1a0")
    drawing.polygon(((13, 16), (18, 15), (16, 24)), fill="#c6e1e2")
    drawing.polygon(((16, 17), (18, 15), (16, 24)), fill="#638d9f")
    drawing.rectangle((14, 14, 17, 17), fill=PALETTE["gold"])
    drawing.rectangle((15, 15, 16, 16), fill="#fff0b2")
    save("compass_needle", needle)
    save("compass", Image.alpha_composite(image, needle))


def swiftness_ring():
    image, drawing = canvas()
    drawing.ellipse((5, 25, 27, 29), fill=(38, 62, 72, 65))
    drawing.ellipse((7, 10, 25, 28), fill=PALETTE["outline"])
    drawing.ellipse((9, 12, 23, 26), fill=PALETTE["gold"])
    drawing.ellipse((12, 15, 20, 23), fill=PALETTE["outline"])
    drawing.arc((9, 12, 23, 26), 50, 200, fill="#fff1b8", width=2)
    drawing.polygon(((16, 3), (22, 8), (16, 14), (10, 8)), fill=PALETTE["outline"])
    drawing.polygon(((16, 5), (20, 8), (16, 12), (12, 8)), fill="#64d2ce")
    drawing.line((16, 5, 16, 11), fill="#d4ffed", width=1)
    drawing.polygon(((4, 8), (9, 8), (11, 12), (7, 11)), fill="#a8e6e0")
    drawing.polygon(((22, 9), (28, 5), (26, 10), (23, 13)), fill="#a8e6e0")
    drawing.line((2, 17, 6, 17), fill="#64d2ce", width=1)
    drawing.line((25, 20, 30, 20), fill="#64d2ce", width=1)
    save("swiftness_ring", image)


def sheriff_badge():
    image, drawing = canvas()
    drawing.ellipse((4, 25, 29, 30), fill=(38, 62, 72, 65))
    drawing.rounded_rectangle((7, 6, 25, 27), radius=4, fill=PALETTE["outline"])
    drawing.rounded_rectangle((9, 7, 23, 25), radius=3, fill=PALETTE["wood_dark"])
    points = []
    for index in range(12):
        angle = -math.pi / 2 + index * math.pi / 6
        radius = 13 if index % 2 == 0 else 6
        points.append((round(16 + math.cos(angle) * radius), round(16 + math.sin(angle) * radius)))
    drawing.polygon(points, fill=PALETTE["outline"])
    points = [(round(16 + (horizontal - 16) * .82), round(16 + (vertical - 16) * .82)) for horizontal, vertical in points]
    drawing.polygon(points, fill=PALETTE["gold"])
    drawing.line((16, 6, 13, 12, 7, 12), fill="#fff1b8", width=1)
    drawing.ellipse((11, 11, 21, 21), fill=PALETTE["wood_dark"])
    drawing.ellipse((12, 12, 20, 20), fill="#d99b48")
    drawing.ellipse((14, 14, 18, 18), fill="#f9df8b")
    drawing.point((15, 14), fill=PALETTE["light"])
    save("sheriff_badge", image)


def vodka():
    image, drawing = canvas()
    drawing.ellipse((8, 26, 25, 30), fill=(38, 62, 72, 65))
    drawing.rounded_rectangle((12, 1, 20, 10), radius=1, fill=PALETTE["outline"])
    drawing.rectangle((13, 2, 19, 5), fill="#ad4e55")
    drawing.rectangle((14, 6, 18, 10), fill="#b6e5e5")
    drawing.polygon(((13, 9), (19, 9), (24, 14), (24, 27), (8, 27), (8, 14)), fill=PALETTE["outline"])
    drawing.polygon(((14, 10), (18, 10), (22, 15), (22, 25), (10, 25), (10, 15)), fill="#92c2cb")
    drawing.rectangle((11, 16, 21, 23), fill="#f5e7ca")
    drawing.rectangle((11, 16, 21, 17), fill="#ad4e55")
    drawing.line((14, 19, 16, 22, 18, 19), fill="#ad4e55", width=1)
    drawing.line((11, 14, 11, 24), fill="#e1ffff", width=1)
    drawing.line((13, 12, 14, 11), fill="#e1ffff", width=1)
    save("vodka", image)


def piggy_bank():
    image, drawing = canvas()
    drawing.ellipse((2, 25, 29, 30), fill=(38, 62, 72, 65))
    drawing.rounded_rectangle((3, 11, 26, 26), radius=6, fill=PALETTE["outline"])
    drawing.rounded_rectangle((5, 12, 25, 24), radius=5, fill="#d98492")
    drawing.ellipse((7, 12, 23, 20), fill="#f3b0ad")
    drawing.rectangle((8, 23, 12, 28), fill=PALETTE["outline"])
    drawing.rectangle((20, 23, 24, 28), fill=PALETTE["outline"])
    drawing.rectangle((9, 24, 11, 26), fill="#d98492")
    drawing.rectangle((21, 24, 23, 26), fill="#d98492")
    drawing.polygon(((19, 13), (21, 7), (26, 12)), fill=PALETTE["outline"])
    drawing.polygon(((21, 12), (22, 10), (24, 12)), fill="#ef9fa5")
    drawing.rounded_rectangle((23, 16, 30, 22), radius=2, fill=PALETTE["outline"])
    drawing.rectangle((24, 17, 29, 20), fill="#f3b0ad")
    drawing.point((26, 18), fill="#a75170")
    drawing.point((28, 18), fill="#a75170")
    drawing.rectangle((20, 14, 21, 15), fill=PALETTE["outline"])
    drawing.arc((0, 12, 7, 19), 70, 335, fill="#d98492", width=2)
    drawing.line((10, 12, 17, 12), fill=PALETTE["outline"], width=2)
    drawing.ellipse((10, 2, 17, 9), fill=PALETTE["outline"])
    drawing.ellipse((11, 3, 16, 8), fill=PALETTE["gold"])
    drawing.line((13, 4, 13, 7), fill="#fff1b8")
    save("piggy_bank", image)


def heat_patch():
    image, drawing = canvas()
    drawing.ellipse((5, 26, 28, 30), fill=(38, 62, 72, 55))
    drawing.polygon(((5, 9), (23, 6), (28, 26), (9, 29)), fill=PALETTE["outline"])
    drawing.polygon(((7, 10), (22, 8), (26, 25), (10, 27)), fill="#f4e6bb")
    drawing.line((8, 12, 23, 10), fill="#d7a778", width=2)
    drawing.line((11, 25, 24, 23), fill="#d7a778", width=1)
    drawing.polygon(((12, 16), (14, 14), (17, 15), (19, 13), (22, 15), (21, 19), (18, 23), (14, 21)), fill="#d7784c")
    drawing.line((15, 16, 16, 17), fill="#ffd09a", width=2)
    for horizontal, vertical in ((9, 3), (15, 1), (21, 0)):
        drawing.line((horizontal, vertical + 4, horizontal - 1, vertical + 2, horizontal, vertical), fill="#edaa9d", width=1)
    save("heat_patch", image)


def first_aid_kit():
    image, drawing = canvas()
    drawing.ellipse((4, 25, 28, 30), fill=(38, 62, 72, 65))
    drawing.rounded_rectangle((10, 3, 22, 11), radius=2, fill=PALETTE["outline"])
    drawing.rectangle((13, 6, 19, 9), fill=(0, 0, 0, 0))
    drawing.rounded_rectangle((4, 9, 28, 28), radius=3, fill=PALETTE["outline"])
    drawing.rounded_rectangle((6, 11, 26, 26), radius=2, fill="#eff4e5")
    drawing.rectangle((7, 12, 25, 15), fill="#8fbaa5")
    drawing.rectangle((7, 24, 25, 26), fill="#b9cfc2")
    drawing.rounded_rectangle((10, 14, 22, 25), radius=2, fill="#3a8d72")
    drawing.rectangle((15, 16, 17, 23), fill=PALETTE["light"])
    drawing.rectangle((12, 18, 20, 20), fill=PALETTE["light"])
    drawing.rectangle((7, 17, 8, 20), fill=PALETTE["wood_dark"])
    drawing.rectangle((24, 17, 25, 20), fill=PALETTE["wood_dark"])
    save("first_aid_kit", image)


def defibrillator():
    image, drawing = canvas()
    drawing.ellipse((3, 25, 29, 30), fill=(38, 62, 72, 65))
    drawing.rounded_rectangle((8, 5, 24, 28), radius=3, fill=PALETTE["outline"])
    drawing.rounded_rectangle((10, 7, 22, 26), radius=2, fill="#efe4b5")
    drawing.rectangle((11, 9, 21, 16), fill="#244d50")
    drawing.line((12, 13, 14, 13, 15, 10, 17, 15, 18, 12, 20, 12), fill="#8ee9cb", width=1)
    drawing.rectangle((14, 19, 18, 23), fill="#cf6858")
    drawing.rectangle((15, 18, 17, 24), fill="#cf6858")
    drawing.line((8, 11, 4, 14, 4, 23, 8, 25), fill=PALETTE["outline"], width=2)
    drawing.line((24, 11, 28, 14, 28, 23, 24, 25), fill=PALETTE["outline"], width=2)
    for left in (1, 25):
        drawing.rounded_rectangle((left, 16, left + 5, 23), radius=1, fill=PALETTE["outline"])
        drawing.rectangle((left + 1, 17, left + 4, 21), fill="#9cb9bf")
        drawing.rectangle((left + 2, 15, left + 3, 17), fill="#e9d6a1")
    save("defibrillator", image)


def return_staff():
    image, drawing = canvas()
    drawing.ellipse((4, 26, 26, 30), fill=(38, 62, 72, 55))
    drawing.line((7, 27, 23, 8), fill=PALETTE["outline"], width=6)
    drawing.line((7, 27, 23, 8), fill=PALETTE["wood_dark"], width=4)
    drawing.line((7, 26, 22, 8), fill=PALETTE["wood_light"], width=2)
    for horizontal, vertical in ((9, 24), (13, 19), (17, 14)):
        drawing.line((horizontal - 1, vertical - 1, horizontal + 2, vertical + 1), fill=PALETTE["gold"], width=2)
    drawing.arc((14, 1, 29, 16), 10, 235, fill=PALETTE["outline"], width=5)
    drawing.arc((15, 2, 28, 15), 10, 235, fill=PALETTE["gold"], width=3)
    drawing.polygon(((21, 2), (26, 7), (22, 14), (17, 8)), fill=PALETTE["outline"])
    drawing.polygon(((21, 3), (25, 7), (22, 12), (18, 8)), fill="#9186ee")
    drawing.polygon(((21, 3), (23, 7), (20, 9), (18, 8)), fill="#8ef1ef")
    drawing.line((21, 4, 20, 7), fill=PALETTE["light"], width=1)
    for horizontal, vertical in ((9, 5), (28, 20), (5, 15)):
        drawing.line((horizontal - 2, vertical, horizontal + 2, vertical), fill="#b5ecf6", width=1)
        drawing.line((horizontal, vertical - 2, horizontal, vertical + 2), fill="#e9e3ff", width=1)
    save("return_staff", image)


def ice_staff():
    image, drawing = canvas()
    drawing.ellipse((4, 27, 27, 30), fill=(38, 62, 72, 55))
    drawing.line((7, 28, 23, 9), fill="#234366", width=6)
    drawing.line((7, 27, 23, 9), fill="#648fb6", width=4)
    drawing.line((7, 26, 22, 9), fill="#c6edff", width=1)
    for horizontal, vertical in ((10, 23), (14, 18), (18, 13)):
        drawing.line((horizontal - 1, vertical - 1, horizontal + 2, vertical + 1), fill="#efffff", width=2)
    drawing.polygon(((20, 1), (28, 6), (28, 12), (23, 17), (16, 11), (16, 6)), fill="#234366")
    drawing.polygon(((20, 2), (26, 7), (26, 11), (23, 15), (18, 10), (18, 6)), fill="#68bce9")
    drawing.polygon(((20, 3), (23, 7), (21, 11), (18, 9), (18, 6)), fill="#dcfaff")
    drawing.line((23, 7, 23, 14), fill="#b3edff", width=1)
    for horizontal, vertical in ((9, 6), (29, 19), (5, 16)):
        drawing.line((horizontal - 2, vertical, horizontal + 2, vertical), fill="#8fdaff", width=1)
        drawing.line((horizontal, vertical - 2, horizontal, vertical + 2), fill="#eaffff", width=1)
    save("ice_staff", image)


def match_machine():
    image, drawing = canvas()
    drawing.ellipse((5, 25, 28, 30), fill=(38, 62, 72, 65))
    drawing.rectangle((5, 3, 26, 28), fill=PALETTE["outline"])
    drawing.rectangle((7, 5, 24, 26), fill="#b58b47")
    drawing.rectangle((24, 5, 25, 26), fill="#75603f")
    drawing.rectangle((8, 6, 22, 9), fill="#f4ddb0")
    drawing.line((10, 8, 16, 8), fill="#8d4d3d")
    drawing.rectangle((8, 11, 19, 21), fill="#344f55")
    for vertical in (12, 17):
        drawing.rectangle((10, vertical, 17, vertical + 3), fill="#e5be77")
        drawing.rectangle((11, vertical + 1, 15, vertical + 2), fill="#b95640")
        drawing.line((12, vertical + 1, 14, vertical + 1), fill="#fff0ce")
    drawing.rectangle((21, 12, 22, 14), fill=PALETTE["outline"])
    drawing.point((22, 17), fill=PALETTE["gold"])
    drawing.line((19, 8, 21, 6), fill="#8d4d3d")
    drawing.point((21, 6), fill="#d86e43")
    drawing.rectangle((9, 23, 21, 25), fill=PALETTE["outline"])
    drawing.rectangle((8, 28, 10, 29), fill=PALETTE["outline"])
    drawing.rectangle((22, 28, 24, 29), fill=PALETTE["outline"])
    save("match_machine", image)


def vending_items():
    image, drawing = canvas()
    drawing.ellipse((5, 25, 28, 30), fill=(38, 62, 72, 65))
    drawing.rectangle((5, 3, 26, 28), fill=PALETTE["outline"])
    drawing.rectangle((7, 5, 24, 26), fill="#bb5553")
    drawing.rectangle((24, 5, 25, 26), fill="#783e46")
    drawing.rectangle((8, 6, 22, 8), fill="#f4d3a0")
    drawing.rectangle((8, 10, 19, 21), fill="#314e5b")
    drawing.line((9, 11, 9, 19), fill="#88bdc7")
    for vertical in (12, 17):
        for horizontal, color in ((11, "#e9b566"), (15, "#d97161")):
            drawing.rectangle((horizontal, vertical, horizontal + 2, vertical + 2), fill=color)
            drawing.point((horizontal + 1, vertical - 1), fill=PALETTE["light"])
    drawing.rectangle((21, 11, 22, 13), fill=PALETTE["outline"])
    drawing.point((22, 16), fill=PALETTE["gold"])
    drawing.rectangle((9, 23, 21, 25), fill=PALETTE["outline"])
    drawing.rectangle((8, 28, 10, 29), fill=PALETTE["outline"])
    drawing.rectangle((22, 28, 24, 29), fill=PALETTE["outline"])
    save("vending_machine", image)
    image, drawing = canvas()
    drawing.ellipse((6, 7, 26, 27), fill=PALETTE["outline"])
    drawing.ellipse((7, 7, 25, 25), fill="#b4803d")
    drawing.ellipse((7, 6, 25, 24), fill=PALETTE["gold"])
    drawing.ellipse((10, 9, 22, 21), outline="#b4803d", width=1)
    drawing.line((16, 11, 16, 19), fill="#fff0c6", width=2)
    drawing.line((13, 13, 16, 11), fill="#fff0c6", width=2)
    save("coin", image)
    image, drawing = canvas()
    drawing.rectangle((13, 4, 19, 8), fill=PALETTE["outline"])
    drawing.rectangle((14, 4, 18, 5), fill="#e57869")
    drawing.rectangle((14, 7, 18, 9), fill="#8fb0b8")
    drawing.polygon(((13, 9), (19, 9), (22, 14), (22, 26), (20, 28), (12, 28), (10, 26), (10, 14)), fill=PALETTE["outline"])
    drawing.rectangle((12, 13, 20, 26), fill="#653c3c")
    drawing.rectangle((12, 16, 20, 22), fill="#c35c54")
    drawing.line((13, 20, 19, 18), fill=PALETTE["light"], width=2)
    drawing.line((12, 12, 12, 15), fill="#b8d2d3")
    save("cola", image)


def arsenal_equipment():
    image, drawing = canvas()
    drawing.ellipse((4, 26, 28, 30), fill=(38, 62, 72, 65))
    drawing.rectangle((5, 3, 26, 28), fill=PALETTE["outline"])
    drawing.rectangle((7, 5, 24, 26), fill="#526b62")
    drawing.rectangle((24, 5, 25, 26), fill="#344c48")
    drawing.rectangle((8, 6, 22, 8), fill=PALETTE["gold"])
    drawing.rectangle((8, 10, 20, 21), fill="#1c333c")
    drawing.line((10, 11, 10, 19), fill="#819a9c")
    drawing.rectangle((11, 12, 18, 14), fill="#b3c4c3")
    drawing.line((13, 15, 13, 17), fill="#d6ac70", width=2)
    drawing.rectangle((12, 18, 19, 19), fill="#a59b7c")
    drawing.point((22, 13), fill=PALETTE["gold"])
    drawing.rectangle((9, 23, 21, 25), fill=PALETTE["outline"])
    drawing.rectangle((8, 28, 10, 29), fill=PALETTE["outline"])
    drawing.rectangle((22, 28, 24, 29), fill=PALETTE["outline"])
    save("gun_machine", image)
    image, drawing = canvas()
    drawing.ellipse((8, 25, 25, 29), fill=(38, 62, 72, 65))
    drawing.ellipse((8, 10, 24, 27), fill=PALETTE["outline"])
    drawing.ellipse((10, 12, 22, 25), fill="#71845a")
    for horizontal in (13, 18):
        drawing.line((horizontal, 13, horizontal, 24), fill="#3c5546")
    for vertical in (16, 21):
        drawing.line((10, vertical, 22, vertical), fill="#3c5546")
    drawing.rectangle((13, 7, 19, 12), fill="#c1b58c")
    drawing.line((18, 7, 25, 17), fill="#e0d4b7", width=2)
    drawing.ellipse((9, 3, 15, 9), outline=PALETTE["gold"], width=1)
    save("grenade", image)
    image, drawing = canvas()
    drawing.line((6, 27, 23, 9), fill=PALETTE["outline"], width=5)
    drawing.line((6, 27, 23, 9), fill="#ae6848", width=3)
    drawing.line((7, 26, 22, 10), fill="#edb06a", width=1)
    drawing.polygon(((20, 14), (15, 8), (20, 9), (22, 2), (24, 7), (29, 5), (28, 12), (24, 17)), fill="#e76436")
    drawing.polygon(((20, 12), (19, 9), (23, 5), (23, 10), (26, 9), (24, 14)), fill="#ffc967")
    drawing.polygon(((21, 12), (23, 9), (24, 12), (23, 14)), fill="#fff6c7")
    drawing.point((14, 4), fill="#ffa44f")
    drawing.point((29, 16), fill="#ffc967")
    save("flame_staff", image)
    image, drawing = canvas()
    drawing.polygon(((3, 14), (21, 7), (29, 10), (29, 17), (12, 23), (5, 21)), fill=PALETTE["outline"])
    drawing.polygon(((5, 15), (21, 9), (27, 11), (27, 16), (11, 21), (6, 20)), fill="#c39543")
    drawing.line((9, 15, 23, 10), fill="#ffe1a0", width=2)
    drawing.polygon(((11, 20), (15, 19), (13, 27), (9, 27)), fill="#795d48")
    drawing.ellipse((21, 11, 28, 18), fill="#304853", outline="#e5c47d")
    drawing.ellipse((23, 12, 26, 16), fill="#172d38")
    drawing.ellipse((9, 13, 15, 19), fill=PALETTE["gold"], outline="#825e34")
    drawing.line((12, 14, 12, 17), fill="#fff2bf")
    save("coin_launcher", image)


def homing_missile():
    image, drawing = canvas()
    drawing.polygon(((3, 15), (22, 8), (29, 11), (29, 19), (10, 25), (3, 22)), fill=PALETTE["outline"])
    drawing.polygon(((5, 16), (22, 10), (27, 12), (27, 17), (10, 23), (5, 21)), fill="#899ba0")
    drawing.line((7, 16, 22, 11), fill="#e3eef0", width=2)
    drawing.ellipse((22, 11, 29, 19), fill="#263e48", outline="#f59b72")
    drawing.ellipse((24, 13, 27, 17), fill="#e55047")
    drawing.rectangle((12, 7, 18, 11), fill=PALETTE["outline"])
    drawing.line((13, 8, 17, 8), fill="#69d2ca")
    drawing.polygon(((10, 22), (15, 20), (13, 28), (8, 28)), fill="#586965")
    drawing.ellipse((4, 3, 11, 10), outline="#e55047")
    drawing.line((7, 2, 7, 11), fill="#e55047")
    drawing.line((3, 6, 12, 6), fill="#e55047")
    save("homing_missile", image)
    rocket, drawing = canvas()
    drawing.polygon(((2, 16), (9, 12), (7, 16), (9, 20)), fill="#ffad53")
    drawing.polygon(((5, 16), (11, 14), (11, 18)), fill="#fff2bb")
    drawing.polygon(((10, 12), (19, 12), (27, 16), (19, 20), (10, 20)), fill=PALETTE["outline"])
    drawing.polygon(((11, 13), (19, 13), (24, 16), (19, 19), (11, 19)), fill="#e7eddf")
    drawing.polygon(((20, 13), (27, 16), (20, 19)), fill="#e55047")
    drawing.rectangle((12, 14, 18, 14), fill="#ffffff")
    drawing.polygon(((10, 12), (14, 7), (17, 12)), fill="#dc6156")
    drawing.polygon(((10, 20), (14, 25), (17, 20)), fill="#dc6156")
    for index, direction in enumerate(("e", "se", "s", "sw", "w", "nw", "n", "ne")):
        save(f"missile_{direction}", rocket.rotate(-index * 45, resample=Image.Resampling.NEAREST, center=(16, 16)))
    sheet = Image.new("RGBA", (32 * 6, 32))
    for frame in range(6):
        image, drawing = canvas()
        radius = (4, 8, 12, 13, 12, 10)[frame]
        alpha = (255, 255, 245, 205, 135, 50)[frame]
        drawing.ellipse((16 - radius, 16 - radius, 16 + radius, 16 + radius), outline=(255, 106, 57, alpha), width=2)
        core = max(1, 10 - frame)
        drawing.polygon(((16, 16 - core), (19, 13), (16 + core, 16), (19, 19), (16, 16 + core), (13, 19), (16 - core, 16), (13, 13)), fill=(255, 211, 113, alpha))
        if frame < 3:
            drawing.ellipse((13, 13, 19, 19), fill=(255, 251, 221, alpha))
        sheet.alpha_composite(image, (frame * 32, 0))
    save("fx_missile_explosion", sheet)
    COMBAT_EFFECTS["fx_missile_explosion"] = {"asset": "fx_missile_explosion", "frame_width": 96, "frame_height": 96, "frames": 6, "duration": 0.65}


def flame_tint(image):
    output = image.copy()
    pixels = output.load()
    for vertical in range(output.height):
        for horizontal in range(output.width):
            red, green, blue, alpha = pixels[horizontal, vertical]
            if alpha:
                pixels[horizontal, vertical] = (255, min(245, round(red * 0.6 + green * 0.25)), round(blue * 0.18), alpha)
    return output


def arsenal_effects():
    for name, duration in (("fx_explosion", 0.65), ("fx_burning", 0.5)):
        sheet = Image.new("RGBA", (32 * 6, 32))
        for frame in range(6):
            image, drawing = canvas()
            if name == "fx_explosion":
                radius = (4, 10, 15, 15, 14, 13)[frame]
                alpha = (255, 255, 245, 190, 110, 35)[frame]
                points = []
                for vertex in range(20):
                    angle = vertex * math.tau / 20
                    reach = radius if vertex % 2 == 0 else radius * 0.7
                    points.append((16 + math.cos(angle) * reach, 16 + math.sin(angle) * reach))
                drawing.polygon(points, fill=(238, 100, 42, alpha))
                drawing.ellipse((16 - radius * .65, 16 - radius * .65, 16 + radius * .65, 16 + radius * .65), fill=(255, 197, 77, alpha))
                core = radius * (0.5 if frame < 3 else .25)
                drawing.ellipse((16 - core, 16 - core, 16 + core, 16 + core), fill=(255, 247, 193, alpha))
                if frame >= 3:
                    for horizontal, vertical in ((7, 7), (23, 8), (6, 23), (24, 23)):
                        drawing.ellipse((horizontal - 3, vertical - 3, horizontal + 3, vertical + 3), fill=(101, 102, 100, alpha // 2))
            else:
                for offset, base in ((-7, 24), (0, 26), (7, 24)):
                    sway = ((frame + offset) % 3) - 1
                    top = 6 + (frame + offset) % 4
                    horizontal = 16 + offset
                    drawing.polygon(((horizontal - 5, base), (horizontal - 6, base - 5), (horizontal + sway - 2, top + 5), (horizontal + sway, top), (horizontal + 3, top + 8), (horizontal + 5, base - 5), (horizontal + 4, base)), fill=(238, 96, 36, 205))
                    drawing.polygon(((horizontal - 3, base - 1), (horizontal + sway, top + 7), (horizontal + 3, base - 2)), fill=(255, 195, 65, 235))
                    drawing.line((horizontal, base - 2, horizontal + sway, base - 8), fill=(255, 247, 178, 245), width=2)
            sheet.alpha_composite(image, (frame * 32, 0))
        save(name, sheet)
        COMBAT_EFFECTS[name] = {"asset": name, "frame_width": 96, "frame_height": 96, "frames": 6, "duration": duration}


def food():
    kinds = ("instant_noodles", "dumplings", "wontons", "pork_trotters", "beef", "lamb", "sardines", "tuna", "beef_balls", "hotpot_vegetables", "oreos", "compressed_biscuits")
    colors = ("#bd7253", "#88a5b4", "#758f9e", "#b67c6a", "#a65e5d", "#9d7a68", "#839e9d", "#6b8fa5", "#b78c67", "#789677", "#496c96", "#b49b72")
    for kind, color in zip(kinds, colors):
        image, drawing = canvas()
        if kind in ("sardines", "tuna"):
            drawing.rectangle((5, 12, 27, 25), fill=PALETTE["outline"])
            drawing.rectangle((6, 12, 26, 23), fill=color)
            drawing.ellipse((5, 8, 27, 16), fill=PALETTE["outline"])
            drawing.ellipse((7, 9, 25, 14), fill=PALETTE["ice"])
            drawing.ellipse((15, 10, 21, 12), outline=PALETTE["shade"])
            drawing.polygon(((10, 20), (14, 17), (21, 19), (24, 16), (24, 22), (21, 20), (14, 22)), fill=PALETTE["snow"])
        elif kind == "instant_noodles":
            drawing.polygon(((6, 9), (27, 9), (24, 27), (10, 27)), fill=PALETTE["outline"])
            drawing.polygon(((8, 11), (25, 11), (22, 25), (11, 25)), fill=color)
            drawing.ellipse((6, 6, 27, 13), fill=PALETTE["gold"])
            drawing.line((10, 9, 21, 9), fill=PALETTE["wood_dark"])
            drawing.rectangle((12, 17, 21, 20), fill=PALETTE["snow"])
        else:
            drawing.polygon(((6, 6), (26, 6), (25, 12), (27, 26), (24, 29), (7, 29), (5, 26), (7, 12)), fill=PALETTE["outline"])
            drawing.polygon(((8, 8), (24, 8), (23, 13), (25, 26), (23, 27), (8, 27), (7, 25), (9, 12)), fill=color)
            drawing.line((10, 9, 22, 9), fill="#ffffff88")
            drawing.rectangle((10, 14, 22, 23), fill="#e5e7d8")
            if kind in ("beef", "lamb", "pork_trotters"):
                drawing.ellipse((12, 16, 20, 21), fill="#b96f67")
                drawing.line((14, 17, 18, 20), fill="#f1c8ac", width=2)
            elif kind in ("dumplings", "wontons"):
                for left, top in ((11, 16), (17, 16), (14, 20)):
                    drawing.pieslice((left, top, left + 5, top + 4), 180, 360, fill="#a48d6c")
            elif kind == "hotpot_vegetables":
                drawing.line((13, 21, 19, 16), fill="#477951", width=3)
                drawing.rectangle((18, 19, 21, 22), fill="#c59c56")
            elif kind == "beef_balls":
                for left, top in ((11, 16), (17, 17), (14, 20)):
                    drawing.ellipse((left, top, left + 4, top + 3), fill="#a98059")
            elif kind == "oreos":
                drawing.ellipse((12, 15, 20, 22), fill="#41424b")
                drawing.line((13, 19, 19, 19), fill=PALETTE["snow"])
            else:
                drawing.rectangle((12, 16, 20, 21), fill="#bb9766")
                for point in ((14, 18), (18, 18), (16, 20)):
                    drawing.point(point, fill=PALETTE["wood_dark"])
        save(kind, image)


def effects():
    image, drawing = canvas()
    drawing.rectangle((14, 4, 17, 27), fill="#ecf8f8")
    drawing.rectangle((4, 14, 27, 17), fill="#ecf8f8")
    drawing.line((8, 8, 23, 23), fill="#ecf8f8", width=2)
    drawing.line((23, 8, 8, 23), fill="#ecf8f8", width=2)
    save("snowflake", image)
    image, drawing = canvas()
    drawing.polygon(((15, 5), (19, 12), (26, 15), (19, 19), (16, 27), (12, 19), (5, 16), (12, 12)), fill="#ffd994")
    drawing.rectangle((13, 12, 19, 19), fill="#fff2c8")
    save("spark", image)
    image, drawing = canvas()
    drawing.rectangle((10, 11, 14, 19), fill="#6995a550")
    drawing.rectangle((18, 17, 22, 25), fill="#6995a550")
    save("footprint", image)


def chainsaw():
    image, drawing = canvas()
    drawing.ellipse((3, 25, 29, 29), fill="#52768060")
    drawing.polygon(((13, 13), (26, 3), (30, 4), (31, 8), (18, 21)), fill=PALETTE["outline"])
    drawing.polygon(((15, 14), (27, 5), (29, 6), (29, 8), (18, 18)), fill=PALETTE["shade"])
    drawing.line(((16, 14), (28, 6)), fill=PALETTE["light"], width=2)
    for tooth in range(5):
        horizontal, vertical = 17 + tooth * 2, 13 - tooth * 2
        drawing.rectangle((horizontal - 2, vertical - 3, horizontal, vertical - 2), fill=PALETTE["outline"])
        drawing.rectangle((horizontal + 2, vertical + 2, horizontal + 3, vertical + 3), fill=PALETTE["outline"])
    drawing.rounded_rectangle((1, 15, 12, 26), radius=3, fill=PALETTE["outline"])
    drawing.rectangle((4, 18, 10, 22), fill=PALETTE["snow"])
    drawing.rounded_rectangle((7, 14, 21, 26), radius=3, fill=PALETTE["outline"])
    drawing.rectangle((9, 16, 19, 23), fill=PALETTE["orange"])
    drawing.rectangle((10, 16, 18, 17), fill=PALETTE["gold"])
    drawing.rectangle((10, 20, 14, 21), fill=PALETTE["wood_dark"])
    drawing.ellipse((16, 19, 19, 22), fill=PALETTE["ice"])
    drawing.line(((8, 13), (10, 10), (16, 10), (19, 13)), fill=PALETTE["outline"], width=3)
    drawing.line(((10, 11), (15, 11)), fill=PALETTE["shade"], width=1)
    save("chainsaw", image)


def combat_effects():
    durations = {"fx_slash": 0.28, "fx_claw": 0.32, "fx_impact": 0.3, "fx_debris": 0.5, "fx_muzzle": 0.15, "fx_heal": 0.9, "fx_teleport": 1.0, "fx_axe_sweep": 0.3, "fx_ice_sweep": 0.3, "fx_flame_sweep": 0.3, "fx_chainsaw_sweep": 0.3}
    for name, duration in durations.items():
        sheet = Image.new("RGBA", (32 * 6, 32))
        for frame in range(6):
            image, drawing = canvas()
            phase = frame / 5
            alpha = round(255 * (1 - phase * 0.75))
            if name in ("fx_axe_sweep", "fx_ice_sweep", "fx_flame_sweep", "fx_chainsaw_sweep"):
                fade = round(210 * (1 - phase * 0.8))
                drawing.pieslice((1, 1, 31, 31), -90, 90, fill=(140, 219, 244, round(36 * (1 - phase))))
                drawing.line((16, 1, 16, 31), fill=(168, 223, 248, fade // 2), width=1)
                drawing.arc((1, 1, 31, 31), -90, 90, fill=(139, 214, 246, fade), width=1)
                leading = -90 + phase * 180
                drawing.arc((2, 2, 30, 30), max(-90, leading - 70), leading + 1, fill=(255, 235, 180, alpha), width=3)
                drawing.arc((3, 3, 29, 29), max(-90, leading - 50), leading + 1, fill=(255, 255, 240, alpha), width=1)
                if name == "fx_chainsaw_sweep":
                    for spark in range(5):
                        angle = math.radians(leading - spark * 11)
                        horizontal = round(16 + math.cos(angle) * (11 + spark % 2))
                        vertical = round(16 + math.sin(angle) * (11 + spark % 2))
                        drawing.rectangle((horizontal, vertical, horizontal + 1, vertical + 1), fill=(255, 172 + spark * 12, 80, alpha))
                angle = math.radians(leading)
                horizontal = round(16 + math.cos(angle) * 14)
                vertical = round(16 + math.sin(angle) * 14)
                drawing.line((horizontal - 1, vertical, horizontal + 1, vertical), fill=(255, 255, 255, alpha), width=1)
            elif name == "fx_slash":
                start = -100 + phase * 120
                drawing.arc((3, 3, 29, 29), start, start + 90, fill=(220, 151, 71, alpha), width=5)
                drawing.arc((5, 5, 27, 27), start + 5, start + 80, fill=(255, 241, 197, alpha), width=2)
            elif name == "fx_claw":
                for offset in (-5, 0, 5):
                    top = 7 + offset + round(phase * 4)
                    drawing.line(((7, top), (16, top + 3), (25, top + 9)), fill=(103, 43, 79, alpha), width=4)
                    drawing.line(((8, top), (16, top + 2), (25, top + 8)), fill=(255, 158, 165, alpha), width=2)
            elif name == "fx_impact":
                radius = 5 + phase * 9
                points = []
                for vertex in range(16):
                    angle = vertex * math.pi / 8 + frame * 0.08
                    reach = radius if vertex % 2 == 0 else radius * 0.32
                    points.append((16 + math.cos(angle) * reach, 16 + math.sin(angle) * reach))
                drawing.polygon(points, fill=(232, 104, 87, alpha))
                drawing.ellipse((12, 12, 20, 20), fill=(255, 239, 192, alpha))
            elif name == "fx_debris":
                for chip in range(9):
                    angle = chip * math.tau / 9 + 0.3
                    reach = 2 + phase * (8 + chip % 3)
                    horizontal = round(16 + math.cos(angle) * reach)
                    vertical = round(16 + math.sin(angle) * reach - math.sin(phase * math.pi) * 3)
                    drawing.rectangle((horizontal, vertical, horizontal + 1 + chip % 2, vertical + 1), fill=(213, 172, 118, alpha) if chip % 2 else (112, 76, 62, alpha))
            elif name == "fx_teleport":
                radius = 4 + round(phase * 10)
                glow = round(210 * (1 - phase * 0.6))
                drawing.ellipse((16 - radius, 23 - radius // 3, 16 + radius, 23 + radius // 3), fill=(98, 79, 209, glow // 3), outline=(165, 141, 255, glow), width=2)
                drawing.ellipse((18 - radius, 24 - radius // 3, 14 + radius, 22 + radius // 3), outline=(146, 248, 245, glow), width=1)
                for rune in range(6):
                    angle = rune * math.tau / 6 + phase * 1.4
                    horizontal = round(16 + math.cos(angle) * radius)
                    vertical = round(23 + math.sin(angle) * radius / 3)
                    drawing.line((horizontal, vertical - 2, horizontal, vertical + 1), fill=(255, 234, 170, glow), width=1)
                    drawing.point((horizontal + 1, vertical - 1), fill=(255, 255, 240, glow))
                for pillar in range(5):
                    horizontal = 10 + pillar * 3
                    top = max(2, 18 - round(math.sin(phase * math.pi) * (10 + pillar % 2 * 4)))
                    drawing.line((horizontal, 21, horizontal, top), fill=(139, 215, 255, glow // 3), width=3)
                    drawing.line((horizontal, 20, horizontal, top + 1), fill=(213, 250, 255, glow // 2), width=1)
                for spark in range(7):
                    horizontal = 4 + (spark * 7 + frame * 2) % 25
                    vertical = 19 - (spark * 5 + frame * 3) % 18
                    drawing.line((horizontal - 1, vertical, horizontal + 1, vertical), fill=(225, 221, 255, glow), width=1)
                    drawing.line((horizontal, vertical - 1, horizontal, vertical + 1), fill=(255, 244, 194, glow), width=1)
            elif name == "fx_heal":
                radius = 4 + round(phase * 11)
                halo_alpha = round(230 * (1 - phase * 0.9))
                drawing.ellipse((16 - radius, 23 - radius // 3, 16 + radius, 23 + radius // 3), outline=(255, 229, 166, halo_alpha), width=2)
                drawing.ellipse((17 - radius, 24 - radius // 3, 15 + radius, 22 + radius // 3), outline=(255, 255, 222, halo_alpha), width=1)
                for offset, top, drift in ((-8, 13, -2), (0, 9, 0), (8, 15, 2)):
                    horizontal = 16 + offset + round(phase * drift)
                    vertical = top - round(phase * 7)
                    drawing.rectangle((horizontal - 3, vertical - 1, horizontal + 3, vertical + 1), fill=(255, 245, 236, alpha))
                    drawing.rectangle((horizontal - 1, vertical - 3, horizontal + 1, vertical + 3), fill=(255, 245, 236, alpha))
                    drawing.line((horizontal - 2, vertical, horizontal + 2, vertical), fill=(237, 64, 77, alpha), width=1)
                    drawing.line((horizontal, vertical - 2, horizontal, vertical + 2), fill=(237, 64, 77, alpha), width=1)
            else:
                reach = round(26 - phase * 11)
                drawing.polygon(((4, 16), (13, 11), (reach, 4 + frame), (reach - 3, 13), (30 - frame, 16), (reach - 3, 19), (reach, 28 - frame), (13, 21)), fill=(245, 182, 83, alpha))
                drawing.polygon(((5, 16), (17, 13), (23 - frame, 16), (17, 19)), fill=(255, 250, 219, alpha))
            sheet.alpha_composite(image, (frame * 32, 0))
        save(name, ice_tint(sheet) if name == "fx_ice_sweep" else flame_tint(sheet) if name == "fx_flame_sweep" else sheet)
        COMBAT_EFFECTS[name] = {"asset": name, "frame_width": 96, "frame_height": 96, "frames": 6, "duration": duration}
    for kind in ("monster_small", "monster_big", "monster_fast"):
        source = Image.open(DESTINATION / f"{kind}.png").convert("RGBA").resize((32, 32), Image.Resampling.NEAREST)
        sheet = Image.new("RGBA", (32 * 6, 32))
        for frame in range(6):
            image = source.rotate(-min(90, frame * 24), resample=Image.Resampling.NEAREST, center=(16, 16))
            opacity = (255, 255, 240, 200, 125, 45)[frame]
            image.putalpha(image.getchannel("A").point(lambda value: value * opacity // 255))
            sheet.alpha_composite(image, (frame * 32, 0))
        name = f"{kind}_death"
        save(name, sheet)
        COMBAT_EFFECTS[name] = {"asset": name, "frame_width": 96, "frame_height": 96, "frames": 6, "duration": 0.65}


def directional_weapon_sweeps(kind, effect, arc=180):
    source = Image.open(DESTINATION / f"{effect}.png").convert("RGBA")
    weapon = Image.open(DESTINATION / f"{kind}.png").convert("RGBA").resize((8, 8), Image.Resampling.NEAREST)
    directions = ("e", "se", "s", "sw", "w", "nw", "n", "ne")
    names = []
    for direction_index, direction in enumerate(directions):
        sheet = Image.new("RGBA", (64 * 6, 64))
        for frame in range(6):
            image = source.crop((frame * 96, 0, (frame + 1) * 96, 96)).resize((64, 64), Image.Resampling.NEAREST)
            phase = frame / 5
            swing = math.radians(arc) * (phase - .5)
            tool = weapon.rotate(-math.degrees(swing + math.pi / 4), resample=Image.Resampling.NEAREST, expand=True)
            horizontal = round(32 + math.cos(swing) * 5.5 - tool.width / 2)
            vertical = round(29.2 + math.sin(swing) * 5.5 - tool.height / 2)
            image.alpha_composite(tool, (horizontal, vertical))
            image = image.rotate(-direction_index * 45, resample=Image.Resampling.NEAREST, center=(32, 32))
            sheet.alpha_composite(image, (frame * 64, 0))
        name = f"{effect}_{direction}"
        save(name, sheet)
        names.append(name)
    COMBAT_EFFECTS[effect].update(directions=names, direction_frame_width=192, direction_frame_height=192, radius_ratio=30 / 64)


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    snow()
    tree()
    construction()
    campfires()
    travelers()
    roster_icons()
    monsters()
    frozen_monsters()
    actor_animations()
    monster_resting()
    monster_sleep_effect()
    equipment()
    first_aid_kit()
    piggy_bank()
    heat_patch()
    sheriff_badge()
    swiftness_ring()
    compass()
    vodka()
    defibrillator()
    return_staff()
    ice_staff()
    vending_items()
    match_machine()
    arsenal_equipment()
    homing_missile()
    chainsaw()
    food()
    effects()
    combat_effects()
    arsenal_effects()
    directional_weapon_sweeps("axe", "fx_axe_sweep")
    directional_weapon_sweeps("ice_staff", "fx_ice_sweep")
    directional_weapon_sweeps("flame_staff", "fx_flame_sweep")
    directional_weapon_sweeps("chainsaw", "fx_chainsaw_sweep")
    specification = importlib.util.spec_from_file_location("expansion_art", Path(__file__).with_name("expansion_assets.py"))
    expansion_art = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(expansion_art)
    expansion_art.generate(save, canvas, PALETTE, COMBAT_EFFECTS, directional_weapon_sweeps, DESTINATION)
    specification = importlib.util.spec_from_file_location("machine_art", Path(__file__).with_name("machine_assets.py"))
    machine_art = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(machine_art)
    machine_art.generate(save, canvas, PALETTE, DESTINATION)
    specification = importlib.util.spec_from_file_location("outdoor_art", Path(__file__).with_name("outdoor_assets.py"))
    outdoor_art = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(outdoor_art)
    outdoor_art.generate(save, ANIMATIONS, COMBAT_EFFECTS, traveler_frame, frozen_monster_image)
    specification = importlib.util.spec_from_file_location("manuals", Path(__file__).with_name("generate_manuals.py"))
    manuals = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(manuals)
    manuals.generate()
    specification = importlib.util.spec_from_file_location("manual_art", Path(__file__).with_name("manual_assets.py"))
    manual_art = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(manual_art)
    manual_art.illustrate(Path(__file__).resolve().parents[1], ASSETS)
    (DESTINATION / "manifest.json").write_text(json.dumps({"version": 2, "pixel_art": True, "assets": ASSETS, "animations": ANIMATIONS, "effects": COMBAT_EFFECTS}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(ASSETS)} replaceable PNG assets to {DESTINATION}")


if __name__ == "__main__":
    main()
