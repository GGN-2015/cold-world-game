import json
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


def canvas():
    image = Image.new("RGBA", (32, 32))
    return image, ImageDraw.Draw(image)


def save(name, image):
    image.resize((96, 96), Image.Resampling.NEAREST).save(DESTINATION / f"{name}.png", optimize=True)
    ASSETS[name] = {"file": f"{name}.png", "width": 96, "height": 96}


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


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    snow()
    tree()
    construction()
    campfires()
    travelers()
    monsters()
    equipment()
    food()
    effects()
    (DESTINATION / "manifest.json").write_text(json.dumps({"version": 1, "pixel_art": True, "assets": ASSETS}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(ASSETS)} replaceable PNG assets to {DESTINATION}")


if __name__ == "__main__":
    main()
