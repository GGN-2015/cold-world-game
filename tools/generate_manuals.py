import argparse
import ast
import importlib
from pathlib import Path
import re
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
NAVIGATION = "[返回项目首页](../README.md) · [手册目录](README.md)"
CATALOGS = {"food": "foods.md", "tool": "tools.md", "weapon": "weapons.md", "facility": "machines.md"}


def definitions():
    package = types.ModuleType("_manual_game_rules")
    package.__path__ = [str(ROOT / "cold_world_game")]
    sys.modules[package.__name__] = package
    rules = importlib.import_module(package.__name__ + ".constants")
    source = (ROOT / "cold_world_game/static/js/i18n.js").read_text(encoding="utf-8")
    names = {kind: ast.literal_eval(pair) for kind, pair in re.findall(r"'item\.([a-z_]+)': (\['[^'\n]*', '[^'\n]*'\])", source)}
    names.update({"durian": ["榴莲", "Durian"], "durian_peel": ["榴莲皮", "Durian peel"]})
    names.update({kind: item["name"] for kind, item in rules.EXPANSION_ITEMS.items()})
    names.update({kind: item["name"] for kind, item in rules.ROOM_MACHINES.items()})
    return rules, names


class Manual:
    def __init__(self):
        self.rules, self.names = definitions()
        self.categories = {
            "food": set(self.rules.FOODS) | self.rules.DRINKS.keys(),
            "weapon": set(self.rules.GUNS) | self.rules.MELEE_WEAPONS.keys() | self.rules.EXPLOSIVE_WEAPONS.keys(),
            "tool": set(self.rules.IGNITERS) | self.rules.HEALING_ITEMS.keys() | self.rules.REVIVAL_ITEMS.keys() | self.rules.RETURN_ITEMS.keys() | self.rules.PASSIVE_ITEMS.keys() | self.rules.EQUIPPED_ITEMS.keys(),
            "facility": set(self.rules.CONTAINERS),
        }
        self.chances = dict(self.rules.RARE_CHEST_ITEMS)
        for kind in ("first_aid_kit", "heat_patch", "return_staff", "ice_staff", "flame_staff", "grenade", "defibrillator", "sheriff_badge", "vodka", "swiftness_ring", "homing_missile"):
            self.chances[kind] = getattr(self.rules, kind.upper() + "_CHANCE")
        self.seen = set()

    def link(self, kind):
        page = next((CATALOGS[group] for group, kinds in self.categories.items() if kind in kinds), "economy.md" if kind == "coin" else "building.md")
        anchor = "金钱属性" if kind == "coin" else "木材" if kind == "wood" else self.names[kind][0]
        return f"[{self.names[kind][0]}]({page}#{anchor})"

    def acquisition(self, kind):
        sources = []
        if kind in self.chances:
            sources.append(f"每个自然房屋箱子独立 {self.chances[kind] * 100:g}% 概率生成1件")
        elif kind in self.rules.COMMON_CHEST_FOODS:
            sources.append("自然箱子的食品组有30%概率生成1～5份食品，本物品从该组等概率抽选")
        elif kind in self.rules.COMMON_CHEST_IGNITERS:
            sources.append("自然箱子的火种组有20%概率生成1件火种，本物品从该组等概率抽选")
        elif kind in {"handgun", "shotgun", "rifle"}:
            chance = {"handgun": 7, "shotgun": 2, "rifle": 1}[kind]
            sources.append(f"自然箱子枪械组抽选，折合每箱 {chance}% 概率")
        elif kind == "axe":
            sources.append("新玩家初始携带")
        elif kind == "durian_peel":
            sources.append("吃完榴莲后留在原物品栏格子")
        if kind in {"handgun", "lighter"}:
            sources.append("新玩家初始携带1件")
        if kind in self.rules.SMALL_MONSTER_FOOD_WEIGHTS:
            sources.append("普通小怪死亡时独立10%概率掉1份食品，食品种类按[掉落表](combat.md#普通小怪的食品掉落)抽选")
        sellers = [self.link(machine) for machine, offers in self.rules.MACHINE_OFFERS.items() if any(offer["output"] == kind for offer in offers.values())]
        if sellers:
            sources.append("也可在" + "、".join(sellers) + "兑换，完整价格见设施条目")
        return "；".join(sources) + "。"

    def entry(self, kind, effect, usage, limits, acquisition=None):
        if kind in self.seen:
            raise ValueError(f"Duplicate manual entry: {kind}")
        self.seen.add(kind)
        chinese, english = self.names[kind]
        return [f"### {chinese}", "", f"![{chinese}](../cold_world_game/static/assets/{kind}.png)", "", f"- **名称与标识**：{chinese} / {english} / `{kind}`。", f"- **获取方式**：{acquisition or self.acquisition(kind)}", f"- **效果与数值**：{effect}", f"- **操作方式**：{usage}", f"- **消耗与限制**：{limits}", ""]

    def foods(self):
        rules = self.rules
        lines = ["# 食品与饮料", "", NAVIGATION, "", "## 通用食用规则", "", "食品、饮料按使用条件和效果分类，不以加入时间区分。每个条目依次列出名称与标识、获取方式、效果与数值、操作方式、消耗与限制。箱内生成概率在每个自然箱子生成时判定一次，不因开箱刷新；详见[战利品生成](world.md#战利品生成)。部分常见食品也能由[普通小怪独立掉落](combat.md#普通小怪的食品掉落)，与箱内生成无关。", "", "食品必须先放到物品栏并选中，长按左键0.5秒；手机长按场景或“使用”。当前饥饿≤10才可吃，完整增加食品数值，因此可以超过10；超过10后不能继续吃。需要火的食品要求已点燃篝火的曼哈顿距离1～3格。倒地仍可吃，松开、换物品、开面板或断线会取消未完成使用。食品不可堆叠，每次吃掉1件。", "", "状态饮料不属于补充饥饿的食品，不受饥饿禁食门槛限制。体温、饥饿与状态计时见[生存规则](survival.md)；篝火的点燃与供暖见[设施手册](machines.md#篝火)。", ""]
        for ready, heading in ((True, "即食食品"), (False, "需火食品")):
            lines += ["## " + heading, ""]
            for kind, hunger in rules.FOODS.items():
                if (kind in rules.READY_TO_EAT_FOODS) != ready:
                    continue
                effect = f"恢复 {hunger:g} 点饥饿；完整加值，可超过10。"
                limits = "每次消耗1件；当前饥饿大于10时不能吃。"
                if kind == "durian":
                    effect += "吃完后在原格留下1个" + self.link("durian_peel") + "，即使其余格子全满也能产出。"
                    limits += "榴莲消耗、饥饿增加和榴莲皮产出一起保存，失败整次回退。"
                usage = "放入物品栏并选中，长按左键或手机“使用”0.5秒；" + ("无需篝火。" if ready else "必须在已点燃篝火的曼哈顿距离1～3格内。")
                lines += self.entry(kind, effect, usage, limits)
        lines += ["## 状态饮料", ""]
        drink = rules.DRINKS["vodka"]
        rate = next(rate for minimum, rate in rules.BODY_TEMPERATURE_RATES if drink["felt_temperature"] >= minimum)
        lines += self.entry("vodka", f"饮用后{drink['effect_duration']:g}秒处于亢奋，体感温度恒为{drink['felt_temperature']:g}°C，按每现实分钟{rate:g}°C回复体温，{drink['effect_duration']:g}秒最多恢复{rate * drink['effect_duration'] / 60:g}°C；不直接补满、不增加饥饿。", "放入物品栏并选中，长按左键或手机“使用”0.5秒；无需篝火，倒地及饥饿大于10时可用。", "一次性；再次饮用刷新为30秒，不累加。保暖装备不再额外提高亢奋时的体感温度；离线与停机暂停个人状态计时。")
        return lines

    def tools(self):
        rules = self.rules
        lines = ["# 工具、医疗与随身装备", "", NAVIGATION, "", "## 通用装备规则", "", "主动用品需要先移入物品栏并选中；被动用品携带在背包或物品栏即生效；手持装备只有选中时生效。每个条目采用相同的五项说明。同一属性只取最强一件，不叠加；不同属性可共存。选中加速装备时不能同时手持武器。", "", "医疗补给的体温上限为36°C，饥饿补至10时保留已有超额值；它们不是食品，不受饥饿大于10的禁食限制。倒地可用主动治疗及回城用品。取消未完成长按不消耗，完成时即使已满状态也会消耗；成功反馈使用预渲染医疗或传送动画。所有次数随物品转移和存档保存，耗尽消失，不因重新放置或登录补满。", "", "救援只针对其他在线倒地玩家，须在规定距离内、瞄准正确且视线畅通。回城寻找距原点最近的可站立格中心，木地板可落脚；同距格中选择到最近怪物格距离最大者，仍并列按坐标稳定选择，不受沿途障碍限制。回城不恢复体温或饥饿。", ""]
        base = {
            "first_aid_kit": ("体温恢复至36°C，饥饿恢复到至少10；医疗光圈与红色十字绽放。", "选中后长按0.5秒，无需篝火；手机长按“使用”。", "一次性；恢复与消耗原子提交。"),
            "heat_patch": ("体温直接恢复至36°C，饥饿保持不变；播放小型医疗光圈。", "选中后长按0.5秒，无需篝火；手机长按“使用”。", "一次性；饥饿为0或超过10时也可用。"),
            "defibrillator": ("使目标倒地玩家恢复36°C、至少10饥饿并站立，播放医疗光效。", "对准2格内其他在线倒地玩家，长按1.5秒；手机长按目标或瞄准后按住“使用”。", "一次性，不能自救；施救者倒地仍可施救。目标变更需重新蓄力，目标失效、超距或遮挡不消耗。"),
            "return_staff": ("按通用回城落点规则返回原点附近；施法、离开与抵达均播放符文传送光效。", "选中后朝空地长按1.5秒；手机长按“使用”。", "初始20次，每次成功扣1次；完成后须松开再用，不自动连发。传送、扣次和必要区块生成一起保存。"),
            "sheriff_badge": ("任何武器对小怪、快速怪的伤害×2，包括命中时的子弹、爆炸与每次灼烧；不增加击退，不增强对大怪或玩家的伤害。", "放在背包或物品栏即生效，无需选中。伤害发生时检查持有状态。", "不消耗，多枚不叠加；开火后丢弃徽章会影响尚未结算的伤害。"),
            "swiftness_ring": ("当前体温和饥饿下移速×3；正常/一种减速/两种减速时分别12/6/3格每秒，倒地仍为0。", "移到物品栏并选中即可，手机点该格后用移动摇杆。", "不消耗、不叠加；切换选中格、移走或丢弃立即失效。只携带但未选中无效。"),
        }
        groups = (("自身恢复与补给", rules.HEALING_ITEMS), ("队友救援", rules.REVIVAL_ITEMS), ("回城用品", rules.RETURN_ITEMS), ("点火工具", rules.IGNITERS), ("随身被动装备", rules.PASSIVE_ITEMS), ("手持移动装备", rules.EQUIPPED_ITEMS))
        for heading, items in groups:
            lines += ["## " + heading, ""]
            for kind in items:
                if kind in rules.EXPANSION_ITEMS:
                    item = rules.EXPANSION_ITEMS[kind]
                    effect, usage = item["effect"][0], item["usage"][0]
                    settings = item["settings"]
                    limits = f"初始{settings['uses']}次，用尽消失。" if "uses" in settings else "不消耗，同属性不叠加。" if item["mechanic"] in {"passive", "equipment"} else "一次性，完成后消失。"
                    if kind == "fuel_pack":
                        limits += "包含原物品格在内必须能装下全部5木材，不足或保存失败时不拆包、不扣物品。"
                elif kind in base:
                    effect, usage, limits = base[kind]
                else:
                    effect = f"初始可点火 {rules.IGNITERS[kind]} 次，不代替木材燃料。"
                    usage = "打开篝火，放入火种格并添加木材，点击“点燃”；不能手持直接点火。"
                    limits = "每次成功点燃扣1次，用尽消失；木材另行消耗。"
                if kind in rules.IGNITERS:
                    limits += "成功点燃后，尚有次数且30格背包有空位时自动收回背包原物品；背包满则留在篝火，不转入物品栏、不丢到地面。"
                lines += self.entry(kind, effect, usage, limits)
        return lines

    def weapons(self):
        rules = self.rules
        lines = ["# 武器图鉴与使用", "", NAVIGATION, "", "## 通用攻击规则", "", "所有武器按攻击方式归类，条目统一介绍名称与标识、获取方式、效果与数值、操作方式、消耗与限制。必须放入物品栏并选中；倒地不能攻击。伤害作用于怪物血量，玩家没有独立血条。怪物属性与作息见[怪物手册](combat.md)，伤害加成见[警长徽章](tools.md#警长徽章)。", "", "有效攻击受各自冷却限制，每个模拟tick最多发射一次，不补发卡顿期间错过的攻击。有限近战每次有效挥动（含空挥）扣1次，冷却内点击不扣次数；枪械每次射击扣1发，散弹多个弹丸仍只扣1发。最后一次用完后物品消失，已发射投射物仍结算；不能装填或用转移补满次数。", "", "## 弹道、范围与状态", "", "普通玩家子弹从射手坐标发出，不能命中自己，可贯穿多只怪物及其他玩家；每枚弹丸对同一实体至多伤害一次，不衰减。墙和柱子可穿透，树木阻挡；箱子、篝火、存钱罐和所有机器仅阻挡怪物子弹，不阻挡玩家子弹。一次射击对同一玩家最多扣1体温和1饥饿，玩家体温≤0时不再受子弹伤害。", "", "普通子弹在距离射手当前坐标超过当前视野半对角线时消失：`sqrt(视野宽²+视野高²)/2`；32×18格视野约18.36格，手机随实际画布更新，转屏也更新已发射子弹的上限。不是累计路程；射手离线使用最后位置和视野，全员离线暂停。部分枪械收到按下边沿立即产生首发，无须等下一tick；普通子弹仍按实际弹速飞行，在碰撞时结算伤害。", "", "近战以瞄准向量为中线，用物品所列半径和扇形角度群攻，攻击视线须畅通。180°即向前半圆，边缘包含在内；不伤玩家。单击立即播放对应八方向PNG刃光与挥动音效，伤害由服务器确认；长按采集不等于连续攻击。", "", "冰冻使速度×0.5，大怪期间不能发射远程子弹；活动怪物使用蓝色差分，白天倒地怪物仍受伤但不切换冰冻立绘。灼烧每0.5秒跳一次4点基础伤害、不击退，状态结束停止；同状态刷新持续时间、不叠层，冰冻与灼烧可同时存在。直接近战/普通弹击退有效，快速怪为普通怪的2.5倍，大怪为0.6倍；爆炸与灼烧无击退。", "", "爆炸仅伤怪物，包含白天休眠怪物，不伤玩家和建筑；按爆心欧氏距离结算且不受障碍遮挡。手机投掷可长按场景落点，或瞄准后按住“使用”。", ""]
        for heading, items in (("枪械与追踪武器", rules.GUNS), ("近战武器", rules.MELEE_WEAPONS), ("投掷与爆炸武器", rules.EXPLOSIVE_WEAPONS)):
            lines += ["## " + heading, ""]
            for kind, settings in items.items():
                if kind in rules.EXPANSION_ITEMS:
                    item = rules.EXPANSION_ITEMS[kind]
                    effect, usage = item["effect"][0], item["usage"][0]
                elif kind in rules.GUNS:
                    effect = f"每弹基础伤害{settings['damage']:g}，最短间隔{settings['interval']:g}秒，弹速{settings['speed']:g}格/秒。"
                    usage = "选中后单击左键；手机瞄准后点“使用”。" if kind != "rifle" else "选中后按住左键连发；手机瞄准后按住“使用”。"
                    if kind == "shotgun":
                        effect += "每枪5枚弹丸、±12°散布，每只怪物至多10伤害。"
                    elif kind == "homing_missile":
                        effect += "开火时锁定离自己欧氏距离最近的怪物，先沿瞄准方向飞1.2格，再曲线追踪；命中播放小型爆炸但无范围伤害。"
                        usage += "瞄准只决定起飞方向，不能指定目标；长按不连发。"
                elif kind in rules.MELEE_WEAPONS:
                    effect = f"半径{settings['range']:g}格、{settings['arc_degrees']:g}°扇形群攻，直接伤害{settings['damage']:g}，最短间隔{settings['interval']:g}秒。"
                    usage = "选中后单击左键朝瞄准方向挥动；手机点“使用”，无需长按。"
                    if kind == "ice_staff":
                        effect += "命中施加4秒冰冻。"
                    elif kind == "flame_staff":
                        effect += "直接命中击退，施加4秒灼烧、每0.5秒4伤害；跳伤不击退。"
                    elif kind == "axe":
                        usage += "采树或拆建筑另用长按，容器/机器须用窗口内拆除按钮。"
                else:
                    effect = f"飞行{settings['flight_duration']:g}秒后在指定坐标爆炸，半径{settings['radius']:g}格内怪物受{settings['damage']:g}基础伤害，无击退。"
                    usage = f"选中后对落点长按{settings['duration']:g}秒，最短间隔{settings['interval']:g}秒。"
                    if kind == "coin_launcher":
                        usage += "持续按住可重复发射。"
                if kind in rules.GUNS:
                    limits = f"初始{settings['ammo']}发，每枪1发，用完消失，不能装填。"
                    if kind == "homing_missile":
                        limits += "仅伤锁定怪物，忽略其他怪物、玩家与全部方块，不受视野射程限制；目标死亡即消失，不重新索敌；无目标不开火也不扣弹药或冷却。"
                elif kind in rules.MELEE_WEAPONS:
                    limits = f"初始{settings['uses']}次，每次有效挥动扣1次，用尽消失。" if "uses" in settings else "无次数限制；攻击仍受冷却、距离、方向和视线限制。不能用Q、拖到场景或手机丢弃，可正常转移背包或存入箱子。"
                else:
                    limits = "本体无弹药计数，每枪消耗1金币，余额为0时不能射击；不产生可回收手榴弹。" if kind == "coin_launcher" else "一次性，成功投出消耗1件；长按完成后须松开再投。"
                    limits += "不伤玩家，不破坏方块；保存失败时消耗与效果整次回退。"
                lines += self.entry(kind, effect, usage, limits)
        return lines

    def facilities(self):
        rules = self.rules
        lines = ["# 容器、篝火与功能机器", "", NAVIGATION, "", "## 共用交互规则", "", "本册统一收录箱子、篝火、存钱罐与全部交易机器，按用途分类。同类条目均提供名称与标识、获取方式、效果与数值、操作方式、消耗与限制；交易设施另列完整兑换表。这里是设施功能和价格的唯一图鉴，地图只说明生成规则，建造手册只说明共用放置与回收流程。", "", "点击欧氏距离2格内、交互视线畅通的设施可打开窗口，同时显示背包。电脑使用鼠标，手机直接点设施或瞄准后点“使用”。武器瞄准操作优先时，请先换成斧头等非投射用品。搬运须取空内容物（篝火含燃料和火种、存钱罐含余额），选中斧头，在窗口内长按拆除1.5秒；成功掉落同一方块而非木材。机器无商品库存可取，但实际容器内容仍须为空。", "", "所有设施均占一格、阻挡移动和怪物子弹，不挡玩家子弹，怪物不能拆除。玩家放置时要求3格内合法空地，所有设施互相在八邻域不能相邻；没有放置视线限制。自然生成同样尊重间距、出生位置、入口和已有通路。拆除取消条件与完整放置规则见[采集、制作与建造](building.md)。", "", "## 交易与空间规则", "", "交易从30格背包与10格物品栏共同取料，金币直接扣金钱属性。产物先放背包，再放物品栏；输入消耗腾出的格可容纳产物，但必须一次装下全部结果，空间不足不扣款、不吞料、不丢一部分到地上。交易、状态变化与保存整次提交或回滚。每件产物保留自身的篝火、饥饿、选中和次数限制，出售火种不代替燃料。", "", "机器可以重复交易，但每次都支付完整输入；没有初始免费库存、定时生产、利息或免费弹药重置。搬走、放置、重连或重启不产生赠品或退款。自然生成概率是每房（枪械机为每建筑区块）的独立判定，成功但没有合规空位会跳过，不强行改造房间。", "", "## 储物、取暖与共享资金", ""]
        standard = {
            "chest": ("通常30格，每格1件、不可堆叠；自然战利品同时命中较多时保留全部成功结果，可带额外格位，不丢弃后判定成功的物品。", "打开窗口后拖放；点击容器物品取到背包，Shift点击随身物品存入。", "必须取空后才能拆除，回收箱子再次放置为空，不会重刷战利品。", "自然房屋有1～2个箱子；2木材制作1个，也可在营地建材售货机兑换。"),
            "campfire": ("点燃后按曼哈顿距离1～3/4～6/7～9格分别提供30/20/10°C；取最近已点燃篝火，不叠加，墙不挡热。30°C时每现实分钟回温20°C，20°C时每现实分钟回温15°C；火光约覆盖30°C暖区，仅为视觉效果，不改变热圈或食用距离。最多储备16木材，每份燃烧6游戏小时（6现实分钟）。", "打开窗口，放入木材及火种后点“点燃”；每次点燃消耗火种1次并开始燃烧1份木材，储备耗尽后熄灭。未耗尽的火种在30格背包有空位时自动收回，背包满则留在火种格，不转入物品栏；用尽则消失。自动续燃不再消耗火种。需要火的食品仍仅在1～3格内吃。", "储备木材和火种均取空可拆除，即使仍在燃烧也可拆；剩余燃烧时间作废，不退当前燃料。掉落并再次放置的是熄灭、无燃料无火种的篝火。", "1木材制作1个，也可在营地建材售货机兑换。"),
            "piggy_bank": ("共享非负整数金币余额，所有玩家看到同一数值，任何玩家均可取走；初始余额0，不出售商品。", "窗口中输入正整数数量，点存入或取出，在玩家金钱和共享存款间转移；背包全满也能操作。", "余额和内容物都为0才能拆除；余额不足整次失败，不会透支。数额及结果余额不超过9,007,199,254,740,991，多人操作按序原子保存。", f"每间自然房屋独立{rules.PIGGY_BANK_CHANCE * 100:g}%概率生成1个，无制作配方。"),
        }
        for kind, (effect, usage, limits, acquisition) in standard.items():
            lines += self.entry(kind, effect, usage, limits, acquisition)
        descriptions = {
            "vending_machine": "木材与金币双向等价兑换，并出售可乐；可乐无需篝火、恢复2饥饿。",
            "match_machine": "木材与金币双向等价兑换，并出售单次火柴；每次点火仍需木材。",
            "gun_machine": "出售满弹枪械、一次性手榴弹与金币榴弹炮，不提供免费补弹或武器回售。",
        }
        groups = (
            ("食品与饮料设施", ("vending_machine", "ration_dispenser", "food_dehydrator")),
            ("医疗与救援设施", ("medical_dispenser", "rescue_dispenser")),
            ("燃料与点火设施", ("match_machine", "fuel_packer", "ignition_dispenser")),
            ("建材与回收设施", ("building_supply_machine", "salvage_machine")),
            ("装备与远行设施", ("outfitter_machine", "expedition_machine")),
            ("武器销售设施", ("gun_machine",)),
        )
        for heading, machines in groups:
            lines += ["## " + heading, ""]
            for kind in machines:
                item = rules.ROOM_MACHINES.get(kind)
                chance = item["chance"] if item else getattr(rules, kind.upper() + "_CHANCE")
                scope = "每个建筑区块" if kind == "gun_machine" else "每间自然房屋"
                effect = item["description"][0] if item else descriptions[kind]
                limits = "每次支付完整投入，产物须能全部装入随身空间；不自动产出或补货。取空实际内容物后在窗口长按拆除1.5秒，掉落同种机器，可重新放置，无退款。"
                if kind == "salvage_machine":
                    limits += "回收摧毁整件输入及其剩余弹药，不是用旧枪换满弹枪。"
                elif kind == "fuel_packer":
                    limits += "每包仅拆出5木材，金币加工费不退；批量配方只节省操作，不增殖木材。"
                acquisition = f"{scope}独立{chance * 100:g}%概率生成1台，无制作配方；判定成功仍须有合规空位。"
                lines += self.entry(kind, effect, "点击打开窗口并选择兑换项目；完整输入和输出见下表，手机可点同样按钮。", limits, acquisition)
                lines += ["| 兑换标识 | 完整投入 | 完整产物 |", "| --- | --- | --- |"]
                for identifier, offer in rules.MACHINE_OFFERS[kind].items():
                    inputs = " + ".join(f"{count} {self.link(item_kind)}" for item_kind, count in offer["inputs"].items())
                    lines += [f"| `{identifier}` | {inputs} | {offer['count']} {self.link(offer['output'])} |"]
                lines += [""]
        return lines

    def render(self):
        pages = {
            "foods.md": self.foods(),
            "tools.md": self.tools(),
            "weapons.md": self.weapons(),
            "machines.md": self.facilities(),
        }
        expected = set().union(*self.categories.values())
        if self.seen != expected or expected | {"wood", "coin", "wall", "fence", "floor"} != self.rules.ITEM_KINDS:
            raise ValueError("Manual categories do not cover every item exactly once")
        return {filename: "\n".join(lines).rstrip() + "\n" for filename, lines in pages.items()}


def generate(root=ROOT, check=False):
    manual = Manual()
    differences = []
    for filename, content in manual.render().items():
        path = root / "docs" / filename
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            differences.append(filename)
            if not check:
                path.write_text(content, encoding="utf-8", newline="\n")
    if check and differences:
        raise SystemExit("Outdated manuals: " + ", ".join(differences))
    print("Verified domain catalogs: " + ", ".join(f"{group}={len(kinds)}" for group, kinds in manual.categories.items()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate domain-based item manuals from current game rules")
    parser.add_argument("--check", action="store_true", help="Check generated catalogs without writing")
    generate(check=parser.parse_args().check)
