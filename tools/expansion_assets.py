import hashlib
import importlib.util
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


def definitions(root):
    specification = importlib.util.spec_from_file_location("expansion_definitions", root / "cold_world_game/expansion.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.EXPANSION_ITEMS


def generate(save, canvas, palette, effects, bake, destination):
    root = Path(__file__).resolve().parents[1]
    items = definitions(root)
    outline = palette["outline"]
    for index, (kind, definition) in enumerate(items.items()):
        digest = hashlib.blake2b(kind.encode(), digest_size=8).digest()
        hue = int.from_bytes(digest[:2], "big") / 65535
        color = tuple(round(110 + 85 * (1 + math.cos((hue + offset) * math.tau)) / 2) for offset in (0, .33, .66))
        if definition["settings"].get("freeze_duration"):
            color = (101, 195, 220)
        elif definition["settings"].get("burn_duration"):
            color = (226, 126, 72)
        image, drawing = canvas()
        art, group = definition["art"], definition["group"]
        if group == "food":
            if art in ("can", "bowl", "meal"):
                drawing.rounded_rectangle((5, 10, 27, 27), radius=3, fill=outline)
                drawing.rectangle((7, 12, 25, 24), fill=color)
                drawing.ellipse((6, 7, 26, 15), fill=outline)
                drawing.ellipse((8, 9, 24, 13), fill="#e7dac1")
                for topping in range(3 + index % 4):
                    horizontal = 9 + topping * 5 % 15
                    vertical = 10 + topping % 2
                    drawing.rectangle((horizontal, vertical, horizontal + 2, vertical + 1), fill=color)
                drawing.rectangle((10, 17, 22, 22), fill="#ede7ce")
                drawing.line((12, 19, 19 + index % 3, 19), fill=color, width=2)
            elif art == "pizza":
                drawing.polygon(((5, 7), (27, 9), (15, 28)), fill=outline)
                drawing.polygon(((8, 10), (24, 11), (15, 24)), fill="#edc367")
                drawing.line((7, 8, 26, 10), fill="#a87c4f", width=4)
                for point in ((13, 14), (19, 14), (15, 20)):
                    drawing.ellipse((*point, point[0] + 3, point[1] + 3), fill="#be6651")
            elif art in ("fish", "jerky", "roll", "dumpling"):
                drawing.polygon(((5, 15), (13, 7), (25, 10), (28, 18), (19, 27), (8, 25)), fill=outline)
                drawing.polygon(((8, 16), (14, 10), (23, 12), (25, 18), (18, 24), (10, 22)), fill=color)
                for stripe in range(3):
                    drawing.line((11 + stripe * 4, 12, 9 + stripe * 4, 22), fill="#efe2b1", width=1)
                if art == "fish":
                    drawing.polygon(((7, 16), (2, 11), (3, 23), (8, 20)), fill=color)
                    drawing.point((22, 15), fill=outline)
            elif art == "biscuit":
                drawing.ellipse((5, 6, 27, 28), fill=outline)
                drawing.ellipse((7, 8, 25, 26), fill="#d7b274")
                for seed in range(9):
                    horizontal, vertical = 10 + seed * 5 % 13, 11 + seed * 7 % 12
                    drawing.point((horizontal, vertical), fill=color)
            else:
                drawing.polygon(((6, 6), (26, 6), (25, 27), (7, 27)), fill=outline)
                drawing.rectangle((8, 8, 24, 25), fill=color)
                drawing.rectangle((9, 11, 23, 22), fill="#eee4c9")
                for piece in range(3 + index % 3):
                    horizontal, vertical = 10 + piece * 7 % 10, 13 + piece * 3 % 7
                    drawing.ellipse((horizontal, vertical, horizontal + 4, vertical + 2), fill=color)
                drawing.line((7, 7, 25, 7), fill="#f5edda")
        elif definition["mechanic"] == "gun":
            long = art in ("rifle", "shotgun", "smg")
            drawing.polygon(((3, 12), (26, 9), (29, 12), (28, 18), (10, 21), (3, 19)), fill=outline)
            drawing.polygon(((5, 13), (25, 11), (27, 13), (26, 16), (10, 19), (5, 17)), fill=color)
            drawing.rectangle((24, 11, 29, 14 + (2 if art == "shotgun" else 0)), fill="#708891")
            drawing.polygon(((11, 19), (16, 18), (13, 27), (8, 27)), fill="#805e49")
            drawing.rectangle((10, 7, 17, 10), fill=outline)
            drawing.point((14, 8), fill="#eef4e4")
            if long:
                drawing.polygon(((3, 16), (8, 17), (7, 23), (2, 22)), fill="#a78663")
            if art == "revolver":
                drawing.ellipse((12, 13, 19, 19), fill=outline, outline="#f0cd83")
            if art == "nailer":
                drawing.rectangle((17, 18, 23, 25), fill=outline)
                drawing.rectangle((18, 19, 22, 24), fill=color)
        elif definition["mechanic"] == "melee":
            drawing.line((6, 27, 24, 7), fill=outline, width=5)
            drawing.line((6, 27, 24, 7), fill="#ac825d", width=3)
            if art in ("blade", "spear"):
                drawing.polygon(((13, 14), (28, 2), (25, 13), (17, 19)), fill=outline)
                drawing.polygon(((16, 14), (26, 5), (23, 12), (17, 17)), fill=color)
            elif art == "shovel":
                drawing.polygon(((17, 5), (23, 3), (30, 10), (25, 17), (19, 15)), fill=outline)
                drawing.polygon(((20, 6), (23, 5), (27, 10), (24, 14), (21, 13)), fill=color)
            elif art == "whip":
                drawing.arc((8, 2, 29, 20), 170, 340, fill=color, width=3)
                drawing.line((23, 14, 28, 24), fill="#f7ce72", width=2)
            else:
                drawing.line((17, 15, 26, 5), fill=color, width=5)
                drawing.line((26, 5, 29, 8), fill=outline, width=3)
                drawing.line((18, 14, 21, 10), fill="#f4ecce", width=1)
        elif definition["mechanic"] == "explosive":
            drawing.ellipse((6, 9, 26, 28), fill=outline)
            drawing.ellipse((8, 11, 24, 26), fill=color)
            drawing.rectangle((12, 5, 19, 11), fill=outline)
            drawing.line((16, 6, 24, 4), fill="#e8c67e", width=2)
            for stripe in range(3):
                drawing.line((10, 14 + stripe * 4, 22, 14 + stripe * 4), fill="#e3dac0")
            if art == "bottle":
                drawing.rectangle((13, 3, 18, 13), fill=color)
                drawing.line((17, 3, 24, 8), fill="#e8804c", width=2)
        else:
            if art in ("scarf", "coat", "blanket"):
                drawing.polygon(((7, 6), (24, 6), (28, 25), (20, 28), (15, 24), (5, 27)), fill=outline)
                drawing.polygon(((9, 8), (22, 8), (25, 24), (20, 25), (15, 21), (8, 24)), fill=color)
                for stripe in range(3):
                    drawing.line((10, 11 + stripe * 4, 22, 11 + stripe * 4), fill="#e8dec9")
            elif art in ("boots", "glove"):
                for offset in (0, 11):
                    drawing.polygon(((5 + offset, 7), (12 + offset, 7), (12 + offset, 20), (17 + offset, 22), (16 + offset, 27), (4 + offset, 27)), fill=outline)
                    drawing.rectangle((6 + offset, 9, 10 + offset, 22), fill=color)
                    drawing.rectangle((6 + offset, 23, 15 + offset, 25), fill=color)
            elif art in ("cane", "rod", "syringe"):
                drawing.line((7, 27, 24, 6), fill=outline, width=5)
                drawing.line((8, 25, 23, 7), fill=color, width=3)
                drawing.line((16, 13, 22, 18), fill="#e8dec9", width=2)
                if art == "cane":
                    drawing.arc((16, 2, 29, 13), 180, 340, fill=color, width=3)
            elif art in ("vial", "flask", "warmer", "lighter"):
                drawing.rounded_rectangle((9, 8, 23, 28), radius=3, fill=outline)
                drawing.rectangle((11, 10, 21, 25), fill=color)
                drawing.rectangle((12, 4, 20, 9), fill=outline)
                drawing.line((14, 13, 14, 21), fill="#f2e7c8", width=2)
                drawing.line((11, 17, 17, 17), fill="#f2e7c8", width=2)
            elif art == "helmet":
                drawing.pieslice((5, 7, 27, 29), 180, 360, fill=color, outline=outline, width=2)
                drawing.rectangle((3, 18, 29, 21), fill=outline)
                drawing.rectangle((7, 18, 25, 19), fill="#e8d29a")
            else:
                drawing.rounded_rectangle((5, 8, 27, 28), radius=3, fill=outline)
                drawing.rectangle((7, 10, 25, 25), fill=color)
                drawing.rectangle((11, 5, 21, 10), outline=outline, width=2)
                drawing.polygon(((16, 12), (22, 18), (16, 24), (10, 18)), fill="#f2dfae")
                drawing.point((16, 17 + index % 3), fill=outline)
        image = refine_icon(image, art, color, kind, outline)
        drawing = ImageDraw.Draw(image)
        drawing.rectangle((3, 29, 5 + index % 5, 29), fill=(*color, 120))
        save(kind, image)
    durian(save, canvas, outline)
    for kind, definition in items.items():
        if definition["mechanic"] != "melee":
            continue
        settings = definition["settings"]
        name = settings["effect"]
        sheet = Image.new("RGBA", (192, 32))
        for frame in range(6):
            image, drawing = canvas()
            alpha = (80, 160, 235, 255, 175, 65)[frame]
            color = (105, 217, 246, alpha) if settings.get("freeze_duration") else (255, 148, 70, alpha) if settings.get("burn_duration") else (241, 227, 180, alpha)
            half = settings["arc_degrees"] / 2
            drawing.pieslice((1, 1, 31, 31), -half, half, fill=color)
            drawing.pieslice((3, 3, 29, 29), -half, half, fill=(color[0], color[1], color[2], alpha // 3))
            drawing.arc((1, 1, 31, 31), -half, half, fill=(250, 253, 239, alpha), width=1)
            sheet.alpha_composite(image, (frame * 32, 0))
        save(name, sheet)
        effects[name] = {"asset": name, "frame_width": 96, "frame_height": 96, "frames": 6, "duration": .3}
        bake(kind, name, settings["arc_degrees"])
    source = Image.open(destination / "fx_explosion.png").convert("RGBA").resize((192, 32), Image.Resampling.NEAREST)
    for name, tint in (("fx_frost_blast", (70, 190, 255)), ("fx_fire_blast", (255, 130, 35)), ("fx_pulse_blast", (190, 140, 255))):
        sheet = source.copy()
        pixels = sheet.load()
        for vertical in range(32):
            for horizontal in range(192):
                red, green, blue, alpha = pixels[horizontal, vertical]
                if alpha:
                    light = (red + green + blue) / 765
                    pixels[horizontal, vertical] = (*[round(channel + (255 - channel) * light * .6) for channel in tint], alpha)
        save(name, sheet)
        effects[name] = {"asset": name, "frame_width": 96, "frame_height": 96, "frames": 6, "duration": .65}
    for name in ("fx_food_bite", "fx_supply_unpack"):
        sheet = Image.new("RGBA", (192, 32))
        for frame in range(6):
            image, drawing = canvas()
            alpha = (100, 220, 255, 210, 140, 45)[frame]
            for particle in range(5):
                angle = particle * math.tau / 5 - math.pi / 2
                radius = 3 + frame * 1.5
                horizontal = round(16 + math.cos(angle) * radius)
                vertical = round(16 + math.sin(angle) * radius - frame)
                color = (245, 206, 119, alpha) if name == "fx_food_bite" else (195, 151, 103, alpha)
                drawing.rectangle((horizontal - 1, vertical - 1, horizontal + 1, vertical + 1), fill=color)
                if name == "fx_supply_unpack":
                    drawing.line((horizontal - 1, vertical, horizontal + 2, vertical - 2), fill=(245, 219, 166, alpha))
            sheet.alpha_composite(image, (frame * 32, 0))
        save(name, sheet)
        effects[name] = {"asset": name, "frame_width": 96, "frame_height": 96, "frames": 6, "duration": .6}
    export_text(root, items)


def refine_icon(original, art, color, kind, outline):
    if art not in {"bar", "fruit", "bowl", "meal", "coat", "scarf", "glove", "beacon", "stone", "armor", "crate", "lunchbox", "tin", "lighter", "syringe"}:
        return original
    image = Image.new("RGBA", (32, 32))
    drawing = ImageDraw.Draw(image)
    if art == "bar":
        drawing.rectangle((5, 5, 26, 28), fill=outline)
        drawing.rectangle((7, 7, 24, 17), fill="#986a49")
        for horizontal in (8, 14, 20):
            for vertical in (8, 13):
                drawing.rectangle((horizontal, vertical, horizontal + 4, vertical + 3), fill="#68483c" if kind == "chocolate_bar" else "#cfb27a")
        drawing.polygon(((6, 17), (13, 20), (18, 17), (25, 20), (25, 26), (7, 26)), fill=color)
        drawing.line((8, 24, 22, 24), fill="#f2dfb2", width=2)
    elif art == "fruit":
        drawing.rectangle((5, 5, 27, 28), fill=outline)
        drawing.rectangle((7, 7, 25, 26), fill=color)
        for horizontal, vertical in ((9, 10), (16, 14), (9, 20)):
            drawing.ellipse((horizontal, vertical, horizontal + 8, vertical + 4), fill="#efc65e", outline="#c48e44")
    elif art in ("bowl", "meal"):
        drawing.ellipse((3, 9, 29, 26), fill=outline)
        drawing.ellipse((5, 11, 27, 24), fill=color)
        drawing.ellipse((5, 9, 27, 19), fill="#eee4c6")
        if art == "meal":
            drawing.pieslice((7, 10, 25, 18), 270, 90, fill="#bb874d")
            for horizontal in range(8, 16, 3):
                drawing.line((horizontal, 12, horizontal, 15), fill="#ffffff")
        else:
            drawing.ellipse((7, 11, 25, 17), fill="#b4a070" if kind == "oatmeal" else "#9d9265")
            for horizontal in (10, 16, 21):
                drawing.ellipse((horizontal, 12, horizontal + 2, 14), fill="#f0d4a0")
        for horizontal in (10, 18):
            drawing.line((horizontal, 6, horizontal - 1, 3), fill="#f4f0db", width=1)
    elif art == "coat":
        drawing.polygon(((10, 5), (14, 8), (18, 8), (22, 5), (29, 16), (25, 21), (22, 16), (23, 28), (8, 28), (9, 16), (6, 21), (2, 16)), fill=outline)
        drawing.polygon(((10, 8), (14, 11), (18, 11), (21, 8), (26, 16), (24, 18), (20, 13), (21, 26), (10, 26), (11, 13), (7, 18), (5, 16)), fill=color)
        drawing.line((16, 11, 16, 26), fill="#e9dec7")
        drawing.line((10, 19, 21, 19), fill="#a2afb1")
    elif art == "scarf":
        drawing.rounded_rectangle((4, 5, 27, 15), radius=3, fill=outline)
        drawing.rectangle((6, 7, 25, 13), fill=color)
        drawing.polygon(((10, 12), (17, 13), (15, 29), (7, 27)), fill=outline)
        drawing.polygon(((12, 14), (15, 15), (13, 26), (9, 25)), fill=color)
        for horizontal in (10, 13, 16, 19, 22):
            drawing.line((horizontal, 7, horizontal, 12), fill="#e1c99c")
    elif art == "glove":
        drawing.polygon(((9, 28), (7, 21), (2, 15), (4, 12), (9, 16), (7, 7), (10, 5), (13, 13), (12, 3), (15, 2), (17, 13), (19, 4), (22, 5), (21, 15), (25, 8), (28, 10), (25, 22), (21, 28)), fill=outline)
        drawing.polygon(((10, 25), (10, 18), (7, 15), (13, 18), (11, 7), (15, 16), (15, 6), (18, 18), (21, 9), (20, 21), (25, 14), (23, 23), (20, 25)), fill=color)
        drawing.rectangle((10, 25, 21, 27), fill="#c6a77a")
    elif art == "beacon":
        drawing.rounded_rectangle((7, 9, 25, 29), radius=2, fill=outline)
        drawing.rectangle((9, 11, 23, 26), fill=color)
        drawing.rectangle((11, 13, 21, 18), fill="#304e52")
        drawing.line((12, 9, 10, 1), fill=outline, width=2)
        drawing.arc((15, 1, 28, 12), 210, 320, fill="#f2d17c", width=2)
        drawing.line((12, 22, 20, 22), fill="#eaddba", width=2)
        drawing.point((20, 15), fill="#ed735c")
    elif art == "stone":
        drawing.polygon(((8, 6), (21, 3), (29, 15), (22, 27), (9, 29), (3, 17)), fill=outline)
        drawing.polygon(((10, 8), (20, 6), (25, 15), (20, 24), (10, 26), (6, 17)), fill="#92b1c2")
        drawing.line((17, 6, 13, 14, 20, 18, 15, 26), fill=outline, width=2)
        drawing.ellipse((9, 11, 21, 22), outline="#e8cf87", width=1)
    elif art == "armor":
        drawing.polygon(((8, 4), (13, 7), (19, 7), (24, 4), (29, 13), (25, 16), (25, 28), (7, 28), (7, 16), (3, 13)), fill=outline)
        drawing.polygon(((9, 8), (14, 10), (19, 10), (23, 8), (24, 25), (9, 25)), fill="#8c9ea3")
        drawing.rectangle((12, 13, 21, 21), fill=color, outline="#e3d2a2")
        drawing.line((10, 23, 23, 23), fill=outline)
    elif art == "crate":
        drawing.rectangle((4, 7, 28, 28), fill=outline)
        drawing.rectangle((6, 9, 26, 26), fill="#b58b60")
        for vertical in (13, 19):
            drawing.line((6, vertical, 26, vertical), fill="#71513d", width=2)
        drawing.line((7, 9, 25, 26), fill="#e1b780", width=3)
        drawing.line((25, 9, 7, 26), fill="#e1b780", width=3)
    elif art == "lunchbox":
        drawing.rounded_rectangle((3, 11, 29, 28), radius=3, fill=outline)
        drawing.rectangle((5, 14, 27, 25), fill=color)
        drawing.rectangle((4, 9, 28, 14), fill="#d6dcc6", outline=outline)
        drawing.ellipse((11, 3, 16, 7), fill="#dfd7b8")
        drawing.line((14, 5, 23, 11), fill="#dfd7b8", width=2)
        drawing.rectangle((12, 17, 20, 21), fill="#e5d19b")
    elif art == "tin":
        drawing.rectangle((4, 9, 28, 27), fill=outline)
        drawing.rectangle((6, 11, 26, 25), fill=color)
        drawing.rectangle((4, 7, 28, 11), fill="#c9d4ce", outline=outline)
        drawing.polygon(((14, 21), (11, 18), (16, 12), (18, 16), (22, 18), (19, 23)), fill="#efbd69")
    elif art == "lighter":
        drawing.rectangle((9, 11, 23, 28), fill=outline)
        drawing.rectangle((11, 14, 21, 26), fill=color)
        drawing.rectangle((11, 8, 21, 13), fill="#a7b7b8", outline=outline)
        drawing.polygon(((16, 9), (12, 5), (16, 1), (20, 5), (18, 9)), fill="#edbc6e")
    else:
        drawing.line((5, 28, 12, 20), fill="#a6c5ce")
        drawing.polygon(((10, 19), (20, 7), (26, 12), (15, 24)), fill=outline)
        drawing.polygon(((13, 19), (20, 10), (23, 12), (15, 21)), fill="#a6d6d2")
        drawing.line((18, 7, 26, 14), fill="#e4d4bd", width=2)
        drawing.line((22, 6, 27, 2), fill=outline, width=2)
        drawing.line((24, 1, 30, 5), fill=color, width=2)
    return image


def durian(save, canvas, outline):
    image, drawing = canvas()
    drawing.ellipse((5, 7, 27, 29), fill=outline)
    drawing.ellipse((7, 9, 25, 27), fill="#9aac55")
    for row in range(4):
        for column in range(4):
            horizontal, vertical = 7 + column * 5 + row % 2, 9 + row * 5
            drawing.polygon(((horizontal, vertical + 4), (horizontal + 2, vertical), (horizontal + 4, vertical + 4)), fill="#d6ce77", outline="#667c40")
    drawing.line((16, 8, 20, 3), fill="#8e6d47", width=3)
    save("durian", image)
    image, drawing = canvas()
    drawing.polygon(((3, 18), (9, 9), (16, 18), (23, 8), (29, 17), (22, 26), (9, 27)), fill=outline)
    drawing.polygon(((5, 18), (9, 12), (16, 21), (23, 11), (26, 17), (21, 23), (10, 24)), fill="#a3b15b")
    drawing.polygon(((8, 18), (10, 14), (16, 23), (23, 14), (24, 18), (20, 22), (12, 23)), fill="#f0df99")
    for horizontal, vertical in ((6, 20), (10, 25), (23, 23), (26, 19)):
        drawing.polygon(((horizontal - 1, vertical), (horizontal, vertical - 3), (horizontal + 2, vertical)), fill="#c3c478")
    save("durian_peel", image)


def export_text(root, items):
    messages = {}
    sweeps, blasts = {}, {}
    for kind, definition in items.items():
        messages[f"item.{kind}"] = definition["name"]
        messages[f"guide.effect.{kind}"] = definition["effect"]
        messages[f"guide.use.{kind}"] = definition["usage"]
        if definition["mechanic"] == "melee":
            sweeps[kind] = definition["settings"]["effect"]
        elif definition["mechanic"] == "explosive" and "effect" in definition["settings"]:
            blasts[kind] = definition["settings"]["effect"]
    messages.update({
        "item.durian": ["榴莲", "Durian"], "item.durian_peel": ["榴莲皮", "Durian peel"],
        "guide.effect.durian": ["恢复3点饥饿，可以超过10；吃完后同一个物品栏格子留下一个榴莲皮。自然箱子独立3%概率。", "Restores 3 hunger, including above 10, leaving one durian peel in the same hotbar slot. Independent 3% natural-chest chance."],
        "guide.use.durian": ["无需篝火；选中长按0.5秒，手机按住使用。饥饿大于10时不能吃；背包全满也能在原格产出皮，保存失败整次回滚。", "No fire needed. Equip and hold left click or Use for 0.5 s. Cannot eat above 10 hunger. Its peel replaces the fruit even with full storage; saving failure rolls everything back."],
        "guide.effect.durian_peel": ["一次性投掷物，与手榴弹相同：半径3格内怪物受20伤害，玩家和方块不受伤害，播放相同爆炸。", "Single-use throwable with grenade behavior: 20 damage to monsters within radius 3, no harm to players or blocks, with the same explosion."],
        "guide.use.durian_peel": ["选中后朝落点长按0.5秒；手机可直接长按场景，或瞄准后按住使用。消耗一片皮，飞行0.45秒后爆炸，最多每秒一次。", "Equip and hold 0.5 s toward the landing point. Hold the scene on mobile, or aim then hold Use. Consumes one peel; explodes after a 0.45 s flight, at most once per second."],
    })
    output = "export const expansionMessages = " + json.dumps(messages, ensure_ascii=False, indent=2) + ";\n\n"
    output += "export const expansionSweeps = " + json.dumps(sweeps, indent=2) + ";\n\n"
    output += "export const expansionBlasts = " + json.dumps(blasts, indent=2) + ";\n"
    (root / "cold_world_game/static/js/expansion-data.js").write_text(output, encoding="utf-8")
    manual = ["# 雪原扩展物品图鉴", "", "[返回项目首页](../README.md) · [手册目录](README.md)", "", "本次设计新增20食品、20武器、20道具；它们各自使用独立命名随机流，在每个新生成的自然房屋箱子里判定一次，概率为0.1%～2%，可以同时出现。榴莲与榴莲皮、追踪导弹属于另外的独立需求，不计入这60种。", "", "## 平衡与通用规则", "", "食品的小份即食物较常见，需火的大份餐食较稀有；食品仍只能在饥饿不大于10时吃，但一次进食可超过10。新增武器全都有弹药、次数或一次性限制，没有无限武器，也没有新增装填/复制配方或机器购买途径。强力范围、冰冻、灼烧和回城物品概率更低。", "", "枪械间隔受服务器冷却与每tick最多一枪共同限制；新自动枪也不能因低帧率补发。近战每次有效挥动含空挥耗一次，冷却内点击不扣次数。新投掷物不伤玩家或建筑。警长徽章仍只对小怪/快速怪乘2，同一状态不叠加，只取更晚结束时刻。", "", "所有被动同属性只取最好的一件，不叠加；不同属性可共存。手持装备必须选中才生效，不能与迅捷戒指同时选中叠加。医疗补给饥饿只补至10，保留已有超额值；食品则完整加值。新工具不新增离线消耗。", "", "体温与饥饿仍是原有生存系统，没有额外生命值。每件物品的说明卡同时提供中英文效果和用法。武器与工具耗尽消失；转移、消耗、产出、状态和命中沿用原子存档。", ""]
    for group, title in (("food", "20种食品"), ("weapon", "20种武器"), ("tool", "20种道具")):
        if group == "weapon":
            manual += [f"## {title}", "", "二十种有限武器的立绘、概率、伤害、弹药次数和操作统一收录在独立的[武器手册](weapons.md#二十种扩展武器)，此处不重复维护武器表。", ""]
            continue
        manual += [f"## {title}", "", "| 名称 / English / ID | 独立概率 | 效果 | 操作 |", "| --- | --- | --- | --- |"]
        for kind, definition in items.items():
            if definition["group"] == group:
                manual.append(f"| {definition['name'][0]} / {definition['name'][1]} / `{kind}` | {definition['chance'] * 100:g}% | {definition['effect'][0]} | {definition['usage'][0]} |")
        manual.append("")
    manual += ["## 榴莲与榴莲皮", "", "榴莲 `durian` 在新自然房屋箱子中独立有3%概率生成，无需篝火，长按0.5秒食用恢复3饥饿。等于10时仍能吃到13，大于10时不能吃。成功食用后，同一个物品栏格子被一个新的 `durian_peel` 榴莲皮替换；不另找空格，满背包也不会丢皮。未完成、取消或写盘失败不会产出皮或增加饥饿。", "", "榴莲皮选中后长按0.5秒投到指定已探索落点，目标在视野半对角线内；手机直接长按场景或瞄准后长按使用。一次性消耗，抛物线飞行0.45秒后使用手榴弹同一六帧爆炸与音效，半径3格内怪物受20伤害，不伤玩家、方块。它不是食品，不能再次吃。", "", "## 旧世界与资源", "", "当前地图生成版本见[世界规则](world.md)；已生成区块、箱子、采集记录与版本不改动。未探索区域始终使用当前生成器。新物品逐项使用 `chest_<item-id>:v1:<x>:<y>` 随机流，旧普通食品与火种使用冻结的旧候选池，避免新增项目改变原物品概率和布局。", "", "自然箱子通常30格；极端情况下多项独立稀有判定同时成功、物品超过30件时，自动保留额外格子而不是丢弃或重抽任何成功产物。额外格可在原容器界面滚动转移，保存重启保留。玩家背包仍30格、物品栏仍10格，玩家制作的箱子仍30格。", "", "新增美术每件一个独立PNG，近战各有独立六帧扇形与八方向预烘焙图集，冰霜/火焰/脉冲爆炸使用共享六帧动画。医疗、传送、枪口、灼烧复用已有动画，不为每只怪物增加独立粒子系统。生成脚本 `tools/generate_assets.py` 同时更新PNG、清单、双语扩展字典及本图鉴；设计源为 `cold_world_game/expansion.py`。", ""]
    (root / "docs/expansion.md").write_text("\n".join(manual), encoding="utf-8")
    weapons_path = root / "docs/weapons.md"
    weapons = weapons_path.read_text(encoding="utf-8")
    before, start, remaining = weapons.partition("## 二十种扩展武器\n")
    overview, end, after = remaining.partition("## 开发与存档\n")
    if not start or not end:
        raise ValueError("Weapon manual generation markers are missing")
    overview = overview.split("| 名称 / English / ID |", 1)[0].strip()
    table = ["| 名称 / English / ID | 独立概率 | 效果 | 操作 |", "| --- | --- | --- | --- |"]
    for kind, definition in items.items():
        if definition["group"] == "weapon":
            table.append(f"| {definition['name'][0]} / {definition['name'][1]} / `{kind}` | {definition['chance'] * 100:g}% | {definition['effect'][0]} | {definition['usage'][0]} |")
    weapons_path.write_text(before + start + "\n" + overview + "\n\n" + "\n".join(table) + "\n\n" + end + after, encoding="utf-8")
