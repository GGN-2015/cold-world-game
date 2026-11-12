import importlib.util
import json
from pathlib import Path

from PIL import Image


def definitions(root, filename, attribute):
    specification = importlib.util.spec_from_file_location(f"machine_art_{attribute}", root / "cold_world_game" / filename)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return getattr(module, attribute)


def draw_machine(kind, definition, save, canvas, palette, destination):
    image, drawing = canvas()
    outline = palette["outline"]
    drawing.ellipse((4, 26, 29, 31), fill=(38, 62, 72, 65))
    drawing.rectangle((5, 3, 27, 28), fill=outline)
    drawing.rectangle((7, 5, 25, 26), fill=definition["color"])
    drawing.rectangle((8, 5, 23, 6), fill="#dbdfc6")
    drawing.rectangle((25, 5, 26, 27), fill="#43565c")
    drawing.rectangle((8, 8, 21, 22), fill=outline)
    drawing.rectangle((9, 9, 20, 21), fill="#c0d1c3")
    drawing.rectangle((23, 10, 24, 14), fill=outline)
    drawing.point((24, 16), fill=palette["gold"])
    drawing.rectangle((11, 24, 21, 25), fill=outline)
    drawing.rectangle((7, 28, 10, 29), fill=outline)
    drawing.rectangle((23, 28, 25, 29), fill=outline)
    displays = {"ration": "chocolate_bar", "dehydrator": "beef_jerky", "medical": "first_aid_kit", "rescue": "defibrillator", "packing": "wood", "ignition": "firestarter", "construction": "wall", "salvage": "handgun", "outfitter": "down_coat", "expedition": "return_stone"}
    artwork = definition["art"]
    icon = Image.open(destination / f"{displays[artwork]}.png").convert("RGBA").resize((12, 12), Image.Resampling.NEAREST)
    image.alpha_composite(icon, (9, 10))
    if artwork == "ration":
        drawing.rectangle((10, 19, 19, 20), fill="#aa814b")
        drawing.rectangle((12, 1, 19, 3), fill=outline)
        drawing.rectangle((13, 1, 18, 2), fill="#f1d190")
    elif artwork == "dehydrator":
        for height in (12, 17, 21):
            drawing.line((9, height, 20, height), fill="#604f42")
        for horizontal in (10, 15, 20):
            drawing.line((horizontal, 1, horizontal, 3), fill="#d0e1df")
    elif artwork == "medical":
        drawing.rectangle((11, 2, 20, 7), fill="#e3ece2")
        drawing.line((15, 3, 15, 6), fill="#b54f62", width=2)
        drawing.line((13, 4, 18, 4), fill="#b54f62", width=2)
    elif artwork == "rescue":
        drawing.rectangle((2, 6, 4, 19), fill=outline)
        drawing.rectangle((28, 6, 30, 19), fill=outline)
        drawing.rectangle((2, 8, 3, 15), fill="#d5b483")
        drawing.rectangle((29, 8, 30, 15), fill="#d5b483")
        drawing.line((9, 9, 12, 9, 14, 7, 16, 11, 18, 9, 20, 9), fill="#ecddbc")
    elif artwork == "packing":
        drawing.rectangle((9, 7, 20, 10), fill="#53666b")
        drawing.rectangle((13, 6, 16, 10), fill="#bfcbbf")
        drawing.line((8, 22, 22, 22), fill="#dacb9d", width=2)
        drawing.rectangle((2, 22, 5, 25), fill=outline)
        drawing.rectangle((28, 22, 31, 25), fill=outline)
    elif artwork == "ignition":
        drawing.polygon(((12, 6), (14, 1), (16, 4), (18, 2), (20, 6)), fill="#edb458")
        drawing.point((16, 4), fill="#fff2ba")
        for horizontal in (10, 13, 16, 19):
            drawing.line((horizontal, 24, horizontal, 25), fill="#e4bf78")
    elif artwork == "construction":
        drawing.polygon(((3, 5), (15, 0), (29, 5)), fill=outline)
        drawing.line((5, 5, 15, 1, 27, 5), fill="#d1b689")
        drawing.rectangle((9, 22, 21, 23), fill="#cfb987")
    elif artwork == "salvage":
        drawing.line((10, 9, 18, 9, 20, 12), fill="#466c5d", width=2)
        drawing.polygon(((18, 12), (22, 13), (21, 9)), fill="#466c5d")
        drawing.line((20, 21, 12, 21, 10, 18), fill="#466c5d", width=2)
        drawing.polygon(((12, 18), (8, 17), (9, 21)), fill="#466c5d")
    elif artwork == "outfitter":
        drawing.line((15, 8, 15, 10, 10, 12, 20, 12, 15, 10), fill="#e5d5be")
        drawing.rectangle((2, 9, 4, 21), fill=outline)
        drawing.line((3, 10, 3, 18), fill="#c0b4d8")
    elif artwork == "expedition":
        drawing.line((22, 0, 22, 3), fill=outline)
        drawing.ellipse((20, 0, 24, 2), fill="#cfdfdb")
        drawing.line((6, 12, 6, 21), fill="#b5d3d7")
        drawing.rectangle((11, 22, 19, 23), fill="#d9c78c")
    save(kind, image)


def generate(save, canvas, palette, destination):
    root = Path(__file__).resolve().parents[1]
    machines = definitions(root, "room_machines.py", "ROOM_MACHINES")
    for kind, definition in machines.items():
        draw_machine(kind, definition, save, canvas, palette, destination)
    messages = {
        "machine.dismantle": ["长按拆除机器 · 1.5 秒", "Hold to dismantle machine · 1.5 s"],
        "machine.dismantleHint": ["选中斧头并在此持续按住1.5秒；松开取消。成功掉落同一种机器，可搬走重新放置，不能退回曾经支付的材料。", "Equip an axe and hold here for 1.5 s; release to cancel. Drops the same machine for relocation, never refunds past payments."],
        "machine.description": ["有偿兑换与加工，不自动生成物资、不产生利息。每次都重新支付全部材料，产物保留原本的使用限制。", "Paid exchanges and processing only: no passive production or interest. Every exchange consumes its full cost; normal item-use restrictions remain."],
        "machine.capacity": ["产物先入背包，再入物品栏；本次消耗的材料格可用于接收产物。必须装得下全部产物，空间不足或保存失败整次回退，不扣款、不吞材料。回收会销毁整件输入物品及其剩余弹药。", "Results fill backpack then hotbar; consumed ingredient slots may hold outputs. All results must fit. Insufficient space or failed saving rolls back payment and materials in full. Recycling destroys the entire input and its remaining ammo."],
    }
    for kind, definition in machines.items():
        messages[f"item.{kind}"] = definition["name"]
        messages[f"guide.effect.{kind}"] = definition["description"]
    output = "export const roomMachineKinds = " + json.dumps(list(machines), indent=2) + ";\n\n"
    output += "export const roomMachineMessages = " + json.dumps(messages, ensure_ascii=False, indent=2) + ";\n"
    (root / "cold_world_game/static/js/machine-data.js").write_text(output, encoding="utf-8", newline="\n")
