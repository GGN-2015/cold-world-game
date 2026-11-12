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
    expansion = definitions(root, "expansion.py", "EXPANSION_ITEMS")
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
    names = {"coin": "金币", "wood": "木材", "wall": "木墙", "floor": "地板", "chest": "空箱子", "campfire": "熄灭篝火", "beef": "鲜牛肉", "sardines": "沙丁鱼", "heat_patch": "暖宝宝贴", "first_aid_kit": "急救包", "defibrillator": "除颤器", "handgun": "手枪", "shotgun": "霰弹枪", "rifle": "步枪"}
    names.update({kind: value["name"][0] for kind, value in expansion.items()})
    manual = ["# 十种房屋功能机器", "", "[返回项目首页](../README.md) · [手册目录](README.md) · [基础交易规则](trading.md)", "", "## 设计与获取", "", "十种机器均为独立建筑物品，直接出现在新生成房屋的室内，而不是箱子里的额外掉落。概率按每间自然房屋、每种机器独立判定，使用 `room_machine:<kind>:v1` 确定性随机流。每种每房至多一台；判定成功但没有合规空位时跳过，不移动原有墙、入口、箱子或其他机器。实际出现率可能略低于表内判定概率。", "", "所有机器是有偿加工设施，不会按时间产出物资、补贴、金币或利息，也不提供免费耐久/弹药重置。可以重复交易，但每次都必须重新付费。机器无可领取的初始库存，搬走再放置、重连或保存重启都不会赠送物品。", "", "## 机器一览", "", "| 建筑 / English / ID | 每房独立概率 | 功能与取舍 |", "| --- | --- | --- |"]
    for kind, definition in machines.items():
        manual.append(f"| {definition['name'][0]} / {definition['name'][1]} / `{kind}` | {definition['chance'] * 100:g}% | {definition['description'][0]} |")
    manual += ["", "## 全部兑换配方", "", "输入和输出均不可堆叠；金币从玩家金钱属性扣除，不占背包格。带次数的产物以物品原设定次数创建，既有食品的篝火、饥饿上限以及装备选中/不叠加限制全部保留。", ""]
    for kind, definition in machines.items():
        manual += [f"### {definition['name'][0]}", "", "| 兑换ID | 完整输入 | 输出 |", "| --- | --- | --- |"]
        for identifier, recipe in definition["offers"].items():
            cost = " + ".join(f"{count} {names[item]}" for item, count in recipe["inputs"].items())
            manual.append(f"| `{identifier}` | {cost} | {recipe['count']} {names[recipe['output']]} |")
        manual.append("")
    manual += ["## 防套利与游戏平衡", "", "- 不增加免费刷新、定时分红、无限武器或弹药恢复服务；所有输出都消耗金币或不可返还的实物。", "- 木材压缩只改变携带体积：5木材仍只解出5木材，额外手续费不能取回；一包只能拆一次，拆包仍须完整容纳5木材。", "- 食品脱水额外消耗木材，而且牛肉5饱腹变3.5、沙丁鱼3变2.5，以饱腹损失换无需火；没有反向加工配方。", "- 机器出售的墙、地板和箱子按原制作成本折算，最多只相当于每金币6木材，低于基础售货机每金币10木材；就算再拆解出售也无法盈利。", "- 废枪回收摧毁剩余弹药，只返3/5/10木材，分别远低于3/5/10金币购买新枪的成本；旧枪不会被自动换成满弹同款。", "- 引火棒和火绒盒每次点火仍需1金币，只节省携带格位。防寒装备同属性不叠加，雪地靴仍需选中才能加速。", "- 医疗和回城物品价格较高且使用后消耗或扣次数；救援必须接近队友，远行补给站本身不直接传送。", "", "## 放置、操作与拆除", "", "单击机器打开背包和兑换面板，手机点机器或瞄准后点使用。材料同时读取30格背包和10格物品栏，产物优先放背包。每次交易只有全部成功或全部回退，不会在空间不足时丢到地上或只领取一部分。", "", "与箱子、篝火、小猪存钱罐及全部机器保持八邻域不相邻；自然生成也遵守此限制，并保留入口、已有可走地面与所有容器的通路。怪物不能拆机器，怪物子弹被机器挡住，玩家普通子弹仍能穿透；追踪导弹保持原本的穿透规则。", "", "搬运时选中斧头，在机器窗口长按拆除按钮1.5秒；松开即取消。成功后只掉落同一种机器方块，不掉木材、不退货款。重新放置沿用左键/手机放置按钮和3格放置距离限制。", "", "## 旧世界与美术", "", "本次地图生成版本15；旧区块及其 `chunk_versions`、玩家修改、箱子内容和被采集对象保持原样，缺少版本记录的旧区按1读取。只有未生成区域使用新生成器，不重刷旧房间。机器不引入持久库存或每日计数，新旧SQLite无需删除、重建或换种子。", "", "每种机器各有一张独立96×96透明PNG，由 `tools/machine_assets.py` 生成，再由 `tools/generate_assets.py` 统一写入清单；机器名称和说明同时生成中英文数据。机器没有逐帧生产、全地图扫描或额外粒子动画，复用已有交易、放置与拆除反馈。设计与价格源文件为 `cold_world_game/room_machines.py`。", ""]
    (root / "docs/machines.md").write_text("\n".join(manual), encoding="utf-8", newline="\n")
