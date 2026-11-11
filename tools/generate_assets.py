import colorsys
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


def monsters():
    for big in (False, True):
        image, drawing = canvas()
        drawing.ellipse((3, 25, 30, 30), fill="#587e8d77")
        if big:
            drawing.polygon(((4, 15), (9, 6), (22, 6), (28, 15), (27, 26), (22, 28), (17, 24), (11, 28), (5, 26)), fill=PALETTE["outline"])
            drawing.polygon(((6, 14), (10, 7), (22, 7), (26, 15), (24, 25), (20, 24), (16, 27), (11, 24), (7, 25)), fill="#6b919e")
            drawing.rectangle((10, 4, 21, 15), fill=PALETTE["ice"])
            drawing.rectangle((8, 8, 24, 14), fill=PALETTE["snow"])
            drawing.rectangle((10, 10, 22, 15), fill="#345761")
            drawing.rectangle((11, 10, 13, 11), fill="#f5aa78")
            drawing.rectangle((19, 10, 21, 11), fill="#f5aa78")
            drawing.rectangle((13, 17, 20, 22), fill=PALETTE["ice"])
            drawing.line((5, 15, 4, 21), fill=PALETTE["snow"], width=3)
            drawing.line((26, 15, 28, 21), fill=PALETTE["snow"], width=3)
        else:
            drawing.polygon(((6, 10), (6, 4), (12, 8), (20, 8), (26, 4), (26, 12), (28, 21), (23, 27), (9, 27), (4, 21)), fill=PALETTE["outline"])
            drawing.polygon(((8, 10), (8, 7), (12, 11), (21, 11), (24, 7), (24, 13), (26, 21), (21, 25), (10, 25), (6, 21)), fill=PALETTE["shade"])
            drawing.polygon(((9, 12), (22, 12), (24, 17), (20, 20), (12, 20), (8, 17)), fill=PALETTE["snow"])
            drawing.rectangle((10, 14, 12, 15), fill="#c36b61")
            drawing.rectangle((20, 14, 22, 15), fill="#c36b61")
            drawing.rectangle((15, 18, 18, 20), fill=PALETTE["outline"])
            drawing.line((10, 23, 8, 26), fill=PALETTE["outline"], width=3)
            drawing.line((22, 23, 24, 26), fill=PALETTE["outline"], width=3)
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


def monster_frame(big, direction, pose):
    stride, swing, lift = WALK_POSES[pose]
    image, drawing = canvas()
    drawing.ellipse((3, 27, 29, 30), fill="#587e8d66")
    body = Image.new("RGBA", (32, 32))
    drawing = ImageDraw.Draw(body)
    fur = "#6b919e" if big else PALETTE["shade"]
    side = direction in ("left", "right")
    if side:
        for position, phase in ((11, stride), (19, -stride)):
            drawing.line((position, 21, position + phase, 27), fill=PALETTE["outline"], width=4)
            drawing.line((position, 21, position + phase, 25), fill=fur, width=2)
            drawing.rectangle((position + phase, 26, position + phase + 4, 28), fill=PALETTE["snow"])
        if big:
            drawing.polygon(((8, 12 + lift), (18, 10 + lift), (24, 16 + lift), (22, 24 + lift), (9, 24 + lift), (5, 20 + lift)), fill=PALETTE["outline"])
            drawing.polygon(((9, 13 + lift), (18, 12 + lift), (22, 17 + lift), (20, 23 + lift), (9, 22 + lift), (7, 19 + lift)), fill=fur)
            drawing.line((16, 15 + lift, 16 - swing, 23 + lift), fill=PALETTE["outline"], width=5)
            drawing.line((16, 15 + lift, 16 - swing, 22 + lift), fill=PALETTE["ice"], width=3)
            drawing.rectangle((14 - swing, 22 + lift, 18 - swing, 25 + lift), fill=PALETTE["snow"])
            drawing.rectangle((12, 4 + lift, 23, 14 + lift), fill=PALETTE["ice"])
            drawing.rectangle((10, 7 + lift, 25, 13 + lift), fill=PALETTE["snow"])
            drawing.rectangle((19, 9 + lift, 25, 13 + lift), fill="#345761")
            drawing.rectangle((23, 10 + lift, 27, 12 + lift), fill="#345761")
            drawing.rectangle((22, 9 + lift, 24, 10 + lift), fill="#f5aa78")
            drawing.point((25, 13 + lift), fill=PALETTE["light"])
        else:
            drawing.polygon(((6, 15 + lift), (4, 12 + lift), (2, 15 + lift), (4, 23 + lift), (9, 24 + lift), (12, 20 + lift)), fill=PALETTE["outline"])
            drawing.polygon(((5, 15 + lift), (4, 18 + lift), (7, 22 + lift), (10, 20 + lift)), fill=PALETTE["snow"])
            drawing.polygon(((8, 13 + lift), (18, 11 + lift), (25, 16 + lift), (23, 24 + lift), (8, 24 + lift), (6, 20 + lift)), fill=PALETTE["outline"])
            drawing.polygon(((9, 14 + lift), (18, 13 + lift), (23, 17 + lift), (21, 22 + lift), (9, 22 + lift)), fill=fur)
            drawing.polygon(((13, 12 + lift), (13, 5 + lift), (18, 8 + lift), (22, 8 + lift), (24, 11 + lift), (29, 16 + lift), (27, 20 + lift), (17, 20 + lift), (12, 16 + lift)), fill=PALETTE["outline"])
            drawing.polygon(((15, 11 + lift), (15, 8 + lift), (18, 11 + lift), (22, 10 + lift), (24, 14 + lift), (27, 16 + lift), (25, 18 + lift), (18, 18 + lift), (14, 15 + lift)), fill=PALETTE["snow"])
            drawing.rectangle((22, 12 + lift, 24, 13 + lift), fill="#c36b61")
            drawing.rectangle((27, 16 + lift, 29, 17 + lift), fill=PALETTE["outline"])
            drawing.line((11, 17 + lift, 13 - swing, 23 + lift), fill=PALETTE["outline"], width=3)
            drawing.line((11, 17 + lift, 13 - swing, 22 + lift), fill=PALETTE["ice"], width=2)
    else:
        for position, phase in ((9, stride), (22, -stride)):
            foot = 28 + (1 if phase > 0 else -1 if phase < 0 else 0)
            drawing.rectangle((position - 2, 22, position + 2, foot), fill=PALETTE["outline"])
            drawing.rectangle((position - 1, 23, position + 1, foot - 1), fill=fur)
            drawing.rectangle((position - 2, foot - 1, position + 2, foot), fill=PALETTE["snow"])
        if big:
            drawing.polygon(((4, 15 + lift), (9, 7 + lift), (22, 7 + lift), (28, 15 + lift), (26, 25 + lift), (21, 26 + lift), (16, 24 + lift), (10, 26 + lift), (5, 25 + lift)), fill=PALETTE["outline"])
            drawing.polygon(((6, 15 + lift), (10, 9 + lift), (21, 9 + lift), (26, 15 + lift), (24, 23 + lift), (20, 24 + lift), (16, 22 + lift), (11, 24 + lift), (7, 23 + lift)), fill=fur)
            drawing.line((7, 16 + lift, 4, 21 + swing + lift), fill=PALETTE["snow"], width=3)
            drawing.line((25, 16 + lift, 28, 21 - swing + lift), fill=PALETTE["snow"], width=3)
            drawing.rectangle((10, 4 + lift, 21, 15 + lift), fill=PALETTE["ice"])
            drawing.rectangle((8, 8 + lift, 24, 14 + lift), fill=PALETTE["snow"])
            if direction == "down":
                drawing.rectangle((10, 10 + lift, 22, 15 + lift), fill="#345761")
                drawing.rectangle((11, 10 + lift, 13, 11 + lift), fill="#f5aa78")
                drawing.rectangle((19, 10 + lift, 21, 11 + lift), fill="#f5aa78")
                drawing.rectangle((13, 17 + lift, 20, 22 + lift), fill=PALETTE["ice"])
            else:
                drawing.line((16, 8 + lift, 16, 22 + lift), fill="#54808e", width=2)
                drawing.line((12, 16 + lift, 15, 18 + lift), fill=PALETTE["ice"], width=2)
                drawing.line((20, 16 + lift, 17, 18 + lift), fill=PALETTE["ice"], width=2)
        else:
            drawing.polygon(((6, 10 + lift), (6, 4 + lift), (12, 8 + lift), (20, 8 + lift), (26, 4 + lift), (26, 12 + lift), (28, 21 + lift), (23, 26 + lift), (9, 26 + lift), (4, 21 + lift)), fill=PALETTE["outline"])
            drawing.polygon(((8, 10 + lift), (8, 7 + lift), (12, 11 + lift), (21, 11 + lift), (24, 7 + lift), (24, 13 + lift), (26, 21 + lift), (21, 24 + lift), (10, 24 + lift), (6, 21 + lift)), fill=fur)
            drawing.line((7, 19 + swing + lift, 5, 23 + swing + lift), fill=PALETTE["ice"], width=2)
            drawing.line((25, 19 - swing + lift, 27, 23 - swing + lift), fill=PALETTE["ice"], width=2)
            if direction == "down":
                drawing.polygon(((9, 12 + lift), (22, 12 + lift), (24, 17 + lift), (20, 20 + lift), (12, 20 + lift), (8, 17 + lift)), fill=PALETTE["snow"])
                drawing.rectangle((10, 14 + lift, 12, 15 + lift), fill="#c36b61")
                drawing.rectangle((20, 14 + lift, 22, 15 + lift), fill="#c36b61")
                drawing.rectangle((15, 18 + lift, 18, 20 + lift), fill=PALETTE["outline"])
            else:
                drawing.line((16, 11 + lift, 16, 23 + lift), fill=PALETTE["snow"], width=3)
                drawing.polygon(((14, 22 + lift), (18, 22 + lift), (20, 26 + lift), (15, 27 + lift), (12, 25 + lift)), fill=PALETTE["outline"])
                drawing.rectangle((14, 23 + lift, 17, 25 + lift), fill=PALETTE["ice"])
    if direction == "left":
        body = body.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    image.alpha_composite(body)
    return image


def actor_animations():
    for kind in ("player", "player_other", "monster_small", "monster_big", "monster_fast"):
        sheet = Image.new("RGBA", (160, 128))
        for row, direction in enumerate(ACTOR_DIRECTIONS):
            for pose in range(len(WALK_POSES)):
                if kind.startswith("player"):
                    frame = traveler_frame("#cf784e" if kind == "player" else "#498a97", direction, pose)
                else:
                    frame = monster_frame(kind == "monster_big", direction, pose)
                    if kind == "monster_fast":
                        frame = fast_monster_tint(frame)
                sheet.alpha_composite(frame, (pose * 32, row * 32))
        asset = f"{kind}_motion"
        save(asset, sheet)
        ANIMATIONS[kind] = {"asset": asset, "frame_width": 96, "frame_height": 96, "directions": ACTOR_DIRECTIONS, "idle_frame": 0, "walk_frames": [1, 2, 3, 4], "stride": 1.5 if kind.startswith("player") else 1.35 if kind == "monster_big" else 1.0}


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


def combat_effects():
    durations = {"fx_slash": 0.28, "fx_claw": 0.32, "fx_impact": 0.3, "fx_debris": 0.5, "fx_muzzle": 0.15}
    for name, duration in durations.items():
        sheet = Image.new("RGBA", (32 * 6, 32))
        for frame in range(6):
            image, drawing = canvas()
            phase = frame / 5
            alpha = round(255 * (1 - phase * 0.75))
            if name == "fx_slash":
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
            else:
                reach = round(26 - phase * 11)
                drawing.polygon(((4, 16), (13, 11), (reach, 4 + frame), (reach - 3, 13), (30 - frame, 16), (reach - 3, 19), (reach, 28 - frame), (13, 21)), fill=(245, 182, 83, alpha))
                drawing.polygon(((5, 16), (17, 13), (23 - frame, 16), (17, 19)), fill=(255, 250, 219, alpha))
            sheet.alpha_composite(image, (frame * 32, 0))
        save(name, sheet)
        COMBAT_EFFECTS[name] = {"asset": name, "frame_width": 96, "frame_height": 96, "frames": 6, "duration": duration}
    for kind in ("monster_small", "monster_big", "monster_fast"):
        source = Image.open(DESTINATION / f"{kind}.png").convert("RGBA").resize((32, 32), Image.Resampling.NEAREST)
        sheet = Image.new("RGBA", (32 * 6, 32))
        for frame in range(6):
            image = source.rotate(-min(90, frame * 24), resample=Image.Resampling.NEAREST, center=(16, 20))
            opacity = (255, 255, 240, 200, 125, 45)[frame]
            image.putalpha(image.getchannel("A").point(lambda value: value * opacity // 255))
            sheet.alpha_composite(image, (frame * 32, 0))
        name = f"{kind}_death"
        save(name, sheet)
        COMBAT_EFFECTS[name] = {"asset": name, "frame_width": 96, "frame_height": 96, "frames": 6, "duration": 0.65}


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    snow()
    tree()
    construction()
    campfires()
    travelers()
    roster_icons()
    monsters()
    actor_animations()
    equipment()
    vending_items()
    match_machine()
    food()
    effects()
    combat_effects()
    (DESTINATION / "manifest.json").write_text(json.dumps({"version": 2, "pixel_art": True, "assets": ASSETS, "animations": ANIMATIONS, "effects": COMBAT_EFFECTS}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(ASSETS)} replaceable PNG assets to {DESTINATION}")


if __name__ == "__main__":
    main()
