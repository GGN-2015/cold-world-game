import argparse
import ast
import importlib
from pathlib import Path
import posixpath
import re
import sys
import types

if __package__:
    from . import web_wiki, wiki_tables
else:
    import web_wiki
    import wiki_tables


ROOT = Path(__file__).resolve().parents[1]
NAVIGATION = "[返回项目首页](../../README.md) · [手册目录](../README.md) · [本组目录](README.md)"
CATALOGS = {"food": "items/foods.md", "tool": "items/tools.md", "weapon": "items/weapons.md", "facility": "building/machines.md"}


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
        self.profile = importlib.import_module(self.rules.__package__ + ".procedural").profile()
        self.loot_tiers = importlib.import_module(self.rules.__package__ + ".loot").LOOT_TIERS
        self.wildlife = importlib.import_module(self.rules.__package__ + ".wildlife")
        self.roaming_monsters = importlib.import_module(self.rules.__package__ + ".monsters")
        biomes = importlib.import_module(self.rules.__package__ + ".biomes")
        self.monsters = {
            kind: name for kind, name in wiki_tables.MONSTER_NAMES.items()
            if kind in self.rules.MONSTER_SPAWN_CHANCES["day"] or kind == "tree_spirit"
            or "guard" in biomes.BIOME_RING["kinds"]
        }
        self.chest_odds = wiki_tables.chest_odds(self.profile)
        self.available = (
            self.chest_odds.keys()
            | self.rules.SMALL_MONSTER_FOOD_WEIGHTS.keys()
            | self.rules.CREATIVE_ITEMS.keys()
            | {kind for kind, _, _ in self.profile["machines"]}
            | {offer["output"] for offers in self.rules.MACHINE_OFFERS.values() for offer in offers.values()}
            | {recipe["output"] for recipe in self.rules.RECIPES.values()}
            | {"wood", "coin", "axe", "handgun", "lighter", "durian_peel"}
        )
        self.categories = {
            "food": set(self.rules.FOODS) | self.rules.DRINKS.keys(),
            "weapon": set(self.rules.GUNS) | self.rules.MELEE_WEAPONS.keys() | self.rules.EXPLOSIVE_WEAPONS.keys() | self.rules.AMMO_PACKS.keys(),
            "tool": {"repair_wrench", "spare_part", "lantern", "chain_charm", "quill", "papyrus"} | self.rules.IGNITERS.keys() | self.rules.NAVIGATION_ITEMS.keys() | self.rules.HEALING_ITEMS.keys() | self.rules.REVIVAL_ITEMS.keys() | self.rules.RETURN_ITEMS.keys() | self.rules.PASSIVE_ITEMS.keys() | self.rules.EQUIPPED_ITEMS.keys() | self.rules.CREATIVE_ITEMS.keys() | self.rules.BUILDING_WANDS.keys(),
            "facility": set(self.rules.CONTAINERS),
        }
        self.categories = {group: kinds & (self.available | {"fixed_heater"}) for group, kinds in self.categories.items()}
        self.seen = set()

    def link(self, kind):
        page = next((CATALOGS[group] for group, kinds in self.categories.items() if kind in kinds), "economy.md" if kind == "coin" else "building.md")
        anchor = "金钱属性" if kind == "coin" else self.names[kind][0]
        return f"[{self.names[kind][0]}]({page}#{anchor})"

    def acquisition(self, kind):
        sources = []
        if kind in self.chest_odds:
            chance, amount = self.chest_odds[kind]
            sources.append(f"每口普通自然箱有 {wiki_tables.percent(chance)} 概率出现（{amount}）")
        if kind == "axe":
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
        if not sources:
            raise ValueError(f"Missing acquisition method: {kind}")
        return "；".join(sources) + "。"

    def entry(self, kind, effect, usage, limits, acquisition=None):
        if kind in self.seen:
            raise ValueError(f"Duplicate manual entry: {kind}")
        self.seen.add(kind)
        chinese, english = self.names[kind]
        return [f"### {chinese}", "", f"![{chinese}](../../cold_world_game/static/assets/{kind}.png)", "", f"- **名称与标识**：{chinese} / {english} / `{kind}`。", f"- **获取方式**：{acquisition or self.acquisition(kind)}", f"- **效果与数值**：{effect}", f"- **操作方式**：{usage}", f"- **消耗与限制**：{limits}", ""]

    def foods(self):
        rules = self.rules
        lines = ["# 食品与饮料", "", NAVIGATION, "", "## 通用食用规则", "", "食品、饮料按使用条件和效果分类，不以加入时间区分。每个条目依次列出名称与标识、获取方式、效果与数值、操作方式、消耗与限制。箱内生成概率在每个自然箱子生成时判定一次，不因开箱刷新；详见[战利品生成](world.md#战利品生成)。部分常见食品也能由[普通小怪独立掉落](combat.md#普通小怪的食品掉落)，与箱内生成无关。", "", "食品必须先放到物品栏并选中，长按左键0.5秒；手机长按场景或“使用”。食品最多把饱食度补到 10；满值时不会消耗食物。需要火的食品要求已点燃篝火的曼哈顿距离1～3格。倒地仍可吃，松开、换物品、开面板或断线会取消未完成使用。食品不可堆叠，每次吃掉1件。", "", "状态饮料不属于补充饥饿的食品，不受饥饿禁食门槛限制。体温、饥饿与状态计时见[生存规则](survival.md)；篝火的点燃与供暖见[设施手册](machines.md#篝火)。", ""]
        for ready, heading in ((True, "即食食品"), (False, "需火食品")):
            lines += ["## " + heading, ""]
            for kind, hunger in rules.FOODS.items():
                if kind not in self.available or (kind in rules.READY_TO_EAT_FOODS) != ready:
                    continue
                effect = f"恢复至多 {hunger:g} 点饱食度，上限 10。"
                limits = "成功食用消耗 1 件。"
                if kind == "durian":
                    effect += "吃完后在原格留下1个" + self.link("durian_peel") + "，即使其余格子全满也能产出。"
                    limits += "榴莲消耗、饥饿增加和榴莲皮产出一起保存，失败整次回退。"
                usage = "放入物品栏并选中，长按左键或手机“使用”0.5秒；" + ("无需篝火。" if ready else "必须在已点燃篝火的曼哈顿距离1～3格内。")
                lines += self.entry(kind, effect, usage, limits)
        lines += ["## 状态饮料", ""]
        drink = rules.DRINKS["vodka"]
        rate = next(rate for minimum, rate in rules.BODY_TEMPERATURE_RATES if drink["felt_temperature"] >= minimum)
        lines += self.entry("vodka", f"饮用后{drink['effect_duration']:g}秒处于亢奋，通常体感温度恒为{drink['felt_temperature']:g}°C，按每现实分钟{rate:g}°C回复体温，{drink['effect_duration']:g}秒最多恢复{rate * drink['effect_duration'] / 60:g}°C；不直接补满、不增加饥饿。", "放入物品栏并选中，长按左键或手机“使用”0.5秒；无需篝火，倒地及满饱食时可用。", "一次性；再次饮用刷新为30秒，不累加。保暖装备不再额外提高亢奋时的体感温度；不能抵消饥饿≤1时高于18°C的强制降温，详见生存规则。离线与停机暂停个人状态计时。")
        return lines

    def tools(self):
        rules = self.rules
        lines = ["# 工具、医疗与随身装备", "", NAVIGATION, "", "## 通用装备规则", "", "主动用品需要先移入物品栏并选中；被动用品携带在背包或物品栏即生效；手持装备只有选中时生效。每个条目采用相同的五项说明。同一属性只取最强一件，不叠加；不同属性可共存。选中加速装备时不能同时手持武器。", "", "医疗补给的体温上限为 36°C，饱食度上限为 10。满饱食时仍可用医疗补给。倒地可用主动治疗及回城用品。取消未完成长按不消耗，完成时即使已满状态也会消耗；成功反馈使用预渲染医疗或传送动画。所有次数随物品转移和存档保存，耗尽消失，不因重新放置或登录补满。", "", "救援只针对其他在线倒地玩家，须在规定距离内、瞄准正确且视线畅通。回城寻找距原点最近的可站立格中心，木地板可落脚；同距格中选择到最近怪物格距离最大者，仍并列按坐标稳定选择，不受沿途障碍限制。回城不恢复体温或饥饿。", ""]
        base = {
            "first_aid_kit": ("体温恢复至36°C，饱食度恢复到 10；医疗光圈与红色十字绽放。", "选中后长按0.5秒，无需篝火；手机长按“使用”。", "一次性；恢复与消耗原子提交。"),
            "heat_patch": ("体温直接恢复至36°C，饥饿保持不变；播放小型医疗光圈。", "选中后长按0.5秒，无需篝火；手机长按“使用”。", "一次性；饱食度为 0 或 10 时也可用。"),
            "defibrillator": ("使目标倒地玩家恢复到 36°C、饱食度 10 并站立，播放医疗光效。", "对准2格内其他在线倒地玩家，长按1.5秒；手机长按目标或瞄准后按住“使用”。", "一次性，不能自救；施救者倒地仍可施救。目标变更需重新蓄力，目标失效、超距或遮挡不消耗。"),
            "return_staff": ("按通用回城落点规则返回原点附近；施法、离开与抵达均播放符文传送光效。", "选中后朝空地长按1.5秒；手机长按“使用”。", "初始20次，每次成功扣1次；完成后须松开再用，不自动连发。传送、扣次和必要区块生成一起保存。"),
            "sheriff_badge": (f"任何武器对小怪、快速怪的伤害×{rules.PASSIVE_ITEMS['sheriff_badge']['damage_multiplier']:g}，包括命中时的子弹、爆炸与每次灼烧；不增加击退，不增强对大怪或玩家的伤害。", "放在背包或物品栏即生效，无需选中。伤害发生时检查持有状态。", "不消耗，多枚不叠加；开火后丢弃徽章会影响尚未结算的伤害。"),
            "axe_handle": (f"为普通斧头增加 {rules.PASSIVE_ITEMS['axe_handle']['axe_range_bonus']:g} 格近战半径。", "放在背包或快捷栏即生效。", "可重复使用，多个长柄套不叠加。"),
            "swiftness_ring": ("当前体温和饥饿下移速×3；正常/一种减速/两种减速时分别12/6/3格每秒，倒地仍为0。", "移到物品栏并选中即可，手机点该格后用移动摇杆。", "不消耗、不叠加；切换选中格、移走或丢弃立即失效。只携带但未选中无效。"),
            "compass": ("红色针尖指向距自己欧氏距离最近的合格建筑区块中心，而不是固定指北；蓝色针尖指向相反方向。寻找目标时应跟随红色针尖，不要跟随蓝色针尖。整个区块须与当前游戏画面无交集（边界接触也排除）；从玩家指向目标的方向与从原点指向玩家的方向点积≥0，垂直方向也合格。在原点时不限制方向，同距目标按区块横坐标、纵坐标稳定选择。", "放在背包或物品栏即可自动指向，不用选中、点击或长按；桌面与手机均适用。红色针尖朝向与游戏画面的上下左右一致，不是现实手机朝向。", "不是建筑，不能放置；不消耗。区块按自然类型识别，拆过房屋仍算建筑区块，玩家在森林盖房不会改变类型。浏览器独立Worker只查询区块类型，不探索服务器地图，不生成箱子内容；所有随身指南针共用结果。搜索或连接不可用时指针变暗，不把尚未完成的搜索当成有效目标。"),
        }
        groups = (("自身恢复与补给", rules.HEALING_ITEMS), ("队友救援", rules.REVIVAL_ITEMS), ("回城用品", rules.RETURN_ITEMS), ("点火工具", rules.IGNITERS), ("导航工具", rules.NAVIGATION_ITEMS), ("随身被动装备", rules.PASSIVE_ITEMS), ("手持移动装备", rules.EQUIPPED_ITEMS))
        for heading, items in groups:
            lines += ["## " + heading, ""]
            for kind in items:
                if kind not in self.available:
                    continue
                if kind in rules.EXPANSION_ITEMS:
                    item = rules.EXPANSION_ITEMS[kind]
                    effect, usage = item["effect"][0], item["usage"][0]
                    settings = item["settings"]
                    limits = f"初始{settings['uses']}次，用尽消失。" if "uses" in settings else "不消耗，同属性不叠加。" if item["mechanic"] in {"passive", "equipment"} else "一次性，完成后消失。"
                    if kind == "fuel_pack":
                        limits += "包含原物品格在内必须能装下全部5木材，空间不足或结算失败时不拆包、不扣物品。"
                elif kind in base:
                    effect, usage, limits = base[kind]
                else:
                    effect = f"初始可点火 {rules.IGNITERS[kind]} 次，不代替木材燃料。"
                    usage = "打开篝火，放入火种格并添加木材，点击“点燃”；不能手持直接点火。"
                    limits = "每次成功点燃扣1次，用尽消失；木材另行消耗。"
                if kind in rules.IGNITERS:
                    limits += "成功点燃后，尚有次数且30格背包有空位时自动收回背包原物品；背包满则留在篝火，不转入物品栏、不丢到地面。"
                if kind == "gasoline":
                    effect += "也能为火焰喷射器补燃料，每剩余 1 次耐久可补 1 次喷射。"
                    usage += "随身携带汽油，选中火焰喷射器后按 R 或手机“装填”。"
                    limits += "每次成功装填消耗整件汽油，超过喷射器容量的部分作废。"
                lines += self.entry(kind, effect, usage, limits)
        lines += ["## 维修用品", ""]
        wrench_price = rules.VENDING_OFFERS["buy_wrench"]["inputs"]["coin"]
        lines += self.entry("repair_wrench", "12 次耐久。每次维修消耗 1 次及 1 个零件。", "放到物品栏后选中。点击 2 格内的供暖机或待维修机枪，维修索道、桥墩和路灯时长按。", "用尽消失；修好后无需重复维修；机枪弹药另行装填。", f"{self.acquisition('repair_wrench')}售货机售价 {wrench_price} 金币。")
        lines += self.entry("spare_part", "固定设备的维修耗材，每份占 1 格。", "维修时从背包或物品栏扣除。", "一次性。")
        lines += ["## 创造测试道具", ""]
        creative_effects = {
            "creative_warm_suit": "体温锁定在 36°C，拿到时立即解除倒地。受击仍会产生击退。",
            "creative_food": "饥饿值恒定为 10。",
            "creative_shoes": "当前体温和饥饿对应的移速乘以 2，同持其他移速装备时以创造鞋为准。",
            "creative_tool": "合成免材料，仍需空格存放产物。回收栅栏仍会消耗栅栏。",
            "creative_piggy_bank": "在交易机器购物免金币，仍需空格存放实物。银行存取使用钱包实际余额。",
        }
        for kind, effect in creative_effects.items():
            lines += self.entry(kind, effect, "放进背包或快捷栏即可生效。", "占 1 格，可随时存入箱子或丢弃来关闭效果。", "通过管理员控制台的 `creative` 或 `give` 命令领取。")
        lines += ["## 群系工具", ""]
        lines += self.entry("lantern", f"照亮 {rules.FOG_LANTERN_RADIUS} 格内的迷雾，范围内的光照由附近玩家共享。", "放在快捷栏并选中。换到另一格时熄灭。", "无耐久消耗。")
        lines += self.entry("chain_charm", f"普通斧头砍倒树时有 {wiki_tables.percent(rules.CHAIN_CHARM_CHANCE)} 概率触发。以首棵树为中心，随机选半径 {rules.HARVEST_CHAIN_RADIUS:g} 格内的树一起砍，含首棵最多 {rules.HARVEST_CHAIN_LIMIT} 棵，可以隔着空格。", "随身携带，手持斧头长按采伐。", "同类饰品不叠加。")
        lines += self.entry("quill", "复制卷轴需要原件、1份莎草纸与1次羽毛笔耐久，保留原卷轴。", "在背包中查看火球术或冰冻术卷轴，点击“复制卷轴”。", "初始6次，耗尽后消失。")
        lines += self.entry("papyrus", "用于复制卷轴。", "随身携带，与羽毛笔、原卷轴一起使用。", "每次消耗1份。")
        lines += ["## 建造法杖", ""]
        wand_use = "选中后瞄准 3 格内的中心落点，单击放置，手机点“放置”。"
        wand_limits = "自动从背包和快捷栏扣除木材，每成功一格扣 1 个。遇到障碍跳过，木材不足时从中心到外围尽量铺。法杖可重复使用。"
        lines += self.entry("building_wand", "铺 1×3 木墙。鼠标在游戏场景上滚动滚轮可切换横竖，手机点“旋转”。", wand_use, wand_limits)
        lines += self.entry("floor_wand", "铺 3×3 木地板。冰湖上的地板仍要求落点已经被冰冻术稳住。", wand_use, wand_limits)
        return lines

    def weapons(self):
        rules = self.rules
        lines = [
            "# 武器与弹药", "", NAVIGATION, "",
            "选中快捷栏中的武器使用。倒地时无法攻击。武器伤害对怪物结算；玩家受击会同时损失体温和饥饿。"
            "固定武器见[户外设施](outdoor-facilities.md#固定机枪)，地雷见[建造手册](building.md#地雷)。", "",
            "## 枪械与掩体", "",
            "每次开火扣一发。散弹的每枚弹丸分别判定命中。普通子弹撞到墙、闭门、树或第一个有效目标即停止，"
            "栅栏透弹。固定机枪子弹可穿过多只怪物，并逐步摧毁木墙、闭门或树。普通子弹射程为射手视野半对角线。", "",
            "随身带有兼容弹药时按 R 或手机“装填”，进度显示在角色旁。换枪、受击或打开面板会打断装填，完成时才扣弹。"
            "空枪可继续装填，未用完的弹药留在原包中。", "",
        ]
        for kind, settings in rules.GUNS.items():
            if kind not in self.available:
                continue
            pellets = settings.get("pellets", 5 if kind == "shotgun" else 1)
            effect = f"每枚弹丸伤害 {settings['damage']:g}，射击间隔 {settings['interval']:g} 秒，弹速 {settings['speed']:g} 格/秒。"
            if pellets > 1:
                effect += f"每发 {pellets} 枚弹丸，散布左右各 {settings.get('spread', 12):g}°。"
            use = "选中后按住左键或手机“使用”连射。" if kind == "rifle" or settings.get("automatic") else "选中后单击左键或手机“使用”开一枪。"
            pack, duration = rules.RELOAD_RULES[kind]
            limits = f"容量 {settings['ammo']} 发，取得时装满；使用" + self.link(pack) + f"装填，耗时 {duration:g} 秒。"
            lines += self.entry(kind, effect, use, limits)

        lines += ["## 近战武器", "", "挥击可以命中扇形内视线畅通的多只怪物，空挥只进入攻击冷却。", ""]
        for kind, settings in rules.MELEE_WEAPONS.items():
            if kind not in self.available:
                continue
            effect = (f"{settings['range']:g} 格、{settings['arc_degrees']:g}°扇形群攻。"
                      f"直接伤害 {settings['damage']:g}，间隔 {settings['interval']:g} 秒。")
            status = wiki_tables.weapon_status(settings)
            if status != "—":
                effect += status + "。"
            if "knockback" in settings:
                effect += f"基础击退 {settings['knockback']:g} 格。"
            use = "单击左键或手机“使用”朝瞄准方向挥动。"
            limits = f"耐久 {settings['uses']} 次；一次挥击只要命中，就消耗 1 次。" if "uses" in settings else "无限耐久。可以收进箱子，无法丢到地上。"
            if kind in rules.HARVEST_TOOLS:
                effect += f"长按 {rules.HARVEST_TOOLS[kind]['tree']:g} 秒砍一棵树。"
            if kind == "durian_peel":
                use = f"短按松开进行近战挥击，长按 {settings['throw_duration']:g} 秒直线投掷。"
                effect += (f"扎进首只怪物后，每 {settings['impale_interval']:g} 秒造成 {settings['impale_damage']:g} 点基础伤害，"
                           f"最多持续 {settings['impale_duration']:g} 秒。同一目标已有扎伤时不会叠加或刷新。")
                limits = "近战可重复使用。投掷消耗一片，无直接命中伤害或爆炸，穿过方块。"
            elif kind == "axe":
                effect += "携带" + self.link("axe_handle") + f"时攻击半径增加 {rules.PASSIVE_ITEMS['axe_handle']['axe_range_bonus']:g} 格。"
            elif kind == "chain_chainsaw":
                effect += "以首棵树为中心，随机连砍半径 5 格内的树，含首棵最多 5 棵，可以隔着空格。"
                limits += "完成一次采伐消耗 1 次，包含连锁砍倒的树。"
            lines += self.entry(kind, effect, use, limits)

        lines += [
            "## 投掷与喷射", "",
            "投掷物按爆心范围伤害怪物。灼烧每 0.5 秒造成 1 点伤害，重复命中延长持续时间。"
            "冰冻使活动怪物移动速度减半，大怪暂时无法发射子弹。", "",
        ]
        effects = {
            "grenade": "清除范围内的密林树木。",
            "cluster_charge": "清除范围内的密林树木。",
            "freeze_scroll": "稳定落点周围的冰面 15 秒，期间可正常移动并铺地板。",
            "frost_bomb": "稳定落点周围的冰面 25 秒，期间可正常移动并铺地板。",
            "fireball_scroll": "点燃落点附近的树，火球经过的路径短暂照亮迷雾 4 秒。",
            "fire_bottle": "点燃落点附近的树，火势可以蔓延。",
            "flare_bomb": "照亮落点 3 格内的迷雾 6 秒。",
        }
        for kind, settings in rules.EXPLOSIVE_WEAPONS.items():
            if kind not in self.available:
                continue
            status = wiki_tables.weapon_status(settings)
            status = "" if status == "—" else status + "。"
            if kind == "flamethrower":
                effect = (f"沿瞄准方向喷出最长 {settings['cast_range']:g} 格、宽 1.5 格的火带。"
                          f"每次对范围内每只怪造成 {settings['damage']:g} 点直接伤害。" + status
                          + "点燃带内的树，墙或闭门挡住火带中线时缩短喷射范围。")
                use = f"单击左键或手机“使用”喷一次，按住每 {settings['interval']:g} 秒继续喷。"
                pack, duration = rules.RELOAD_RULES[kind]
                use += f"随身带{self.link(pack)}时按 R 或点“装填”，耗时 {duration:g} 秒。"
                limits = (f"容量 {rules.BIOME_ITEMS[kind]['uses']} 次，取得时装满。喷射耗尽仍保留武器。"
                          "每次装填消耗一整件汽油，按其剩余耐久补充喷射次数，超出容量的部分作废。")
            else:
                effect = (f"落点半径 {settings['radius']:g} 格内的怪物受 {settings['damage']:g} 点直接伤害。"
                          + status + effects[kind])
                use = f"瞄准落点并长按 {settings['duration']:g} 秒投出，飞行 {settings['flight_duration']:g} 秒。"
                if "cast_range" in settings:
                    use += f"最远 {settings['cast_range']:g} 格。"
                limits = "一次性。"
                if kind in {"fireball_scroll", "freeze_scroll"}:
                    limits += "可以用羽毛笔和莎草纸复制，复制时保留原卷轴。"
            lines += self.entry(kind, effect, use, limits)

        lines += ["## 弹药包", ""]
        for kind, rounds in rules.AMMO_PACKS.items():
            compatible = [self.link(gun) for gun, (pack, _) in rules.RELOAD_RULES.items() if kind == pack and gun in self.available]
            if kind == "rifle_ammo":
                compatible.append("[固定机枪](outdoor-facilities.md#固定机枪)")
            lines += self.entry(kind, f"一包含 {rounds} 发。适用于" + "、".join(compatible) + "。",
                                "携带时按 R 或点“装填”。", "一包占一格。随身枪可分次使用，固定机枪使用整包。")
        return lines

    def facilities(self):
        rules = self.rules
        lines = ["# 容器、篝火与功能机器", "", NAVIGATION, "", "## 共用交互规则", "", "本册统一收录箱子、篝火、存钱罐与全部交易机器，按用途分类。同类条目均提供名称与标识、获取方式、效果与数值、操作方式、消耗与限制；交易设施另列完整兑换表。这里是设施功能和价格的唯一图鉴，地图只说明生成规则，建造手册只说明共用放置与回收流程。", "", "点击欧氏距离2格内、交互视线畅通的设施可打开窗口，同时显示背包。电脑使用鼠标，手机直接点设施或瞄准后点“使用”。武器瞄准操作优先时，请先换成斧头等非投射用品。搬运须取空内容物（篝火含燃料和火种、存钱罐含余额），选中斧头或电锯，在窗口内长按拆除1.5秒；成功掉落同一方块而非木材。机器无商品库存可取，但实际容器内容仍须为空。", "", "所有设施均占一格、阻挡移动和怪物子弹，不挡玩家子弹，怪物不能拆除。玩家放置时要求3格内合法空地，所有设施互相在八邻域不能相邻；没有放置视线限制。自然生成同样尊重间距、出生位置、入口和已有通路。拆除取消条件与完整放置规则见[采集、制作与建造](building.md)。", "", "## 交易与空间规则", "", "交易从30格背包与10格物品栏共同取料，金币直接扣金钱属性。产物先放物品栏，再放背包；输入消耗腾出的格可容纳产物，但必须一次装下全部结果，空间不足不扣款、不吞料、不丢一部分到地上。交易、状态变化与保存整次提交或回滚。每件产物保留自身的篝火、饥饿、选中和次数限制，出售火种不代替燃料。", "", "机器可以重复交易，但每次都支付完整输入；没有初始免费库存、定时生产、利息或免费弹药重置。搬走、放置、重连或重启不产生赠品或退款。自然生成概率是每房（弹夹机为每建筑区块）的独立判定，成功但没有合规空位会跳过，不强行改造房间。", "", "## 储物、取暖与共享资金", ""]
        standard = {
            "chest": ("通常30格。木材、木墙、木栅栏和燃料补给包可堆至每格 16 件，其他物品通常每格 1 件。自然战利品同时命中较多时保留全部成功结果，可带额外格位，不丢弃后判定成功的物品。", "打开窗口后拖放、单件点击或点“一键搜刮”。一键搜刮时，零件、莎草纸、木材、弹药和火种直接进背包，其他普通物品先填快捷栏再填背包。装不下的留在箱内。Shift点击随身物品存入。", "必须取空后才能拆除，回收箱子再次放置为空，不会重刷战利品。", "自然房屋有1～2个箱子；2木材制作1个，也可在营地建材售货机兑换。"),
            "campfire": (f"热量沿通路最多传9格，按距离、围墙和地板计算，多个热源不叠加。最多储备16木材，每份燃烧{rules.BURN_SECONDS}现实秒。详见[环境温度与室内供暖](survival.md#环境温度与室内供暖)。", "打开窗口，放入木材及火种后点“点燃”；每次点燃消耗火种1次并开始燃烧1份木材，储备耗尽后熄灭。未耗尽的火种在30格背包有空位时自动收回，背包满则留在火种格，不转入物品栏；用尽则消失。自动续燃不再消耗火种。需要火的食品仍仅在1～3格内吃。", "储备木材和火种均取空可拆除，即使仍在燃烧也可拆；剩余燃烧时间作废，不退当前燃料。掉落并再次放置的是熄灭、无燃料无火种的篝火。", "1木材制作1个，也可在营地建材售货机兑换。"),
            "fixed_heater": (f"修好后与篝火使用同样的取暖和做饭规则；每份木材燃烧{rules.FIXED_HEATER_BURN_SECONDS}现实秒。", "用扳手消耗1个零件维修，再通过窗口加入木材和火种点燃。", "固定在原地。修复状态、燃料和剩余燃烧时间会保存。", "区块有 1.8% 概率生成在可通行的屋外空位。区块 (2, 0) 也会尝试放置。"),
            "piggy_bank": ("共享非负整数金币余额，所有玩家看到同一数值，任何玩家均可取走；初始余额0，不出售商品。", "窗口中输入正整数数量，点存入或取出，在玩家金钱和共享存款间转移；背包全满也能操作。", "余额和内容物都为0才能拆除；余额不足整次失败，不会透支。数额及结果余额不超过9,007,199,254,740,991，多人操作按序原子保存。", f"每间自然房屋独立{rules.PIGGY_BANK_CHANCE * 100:g}%概率生成1个，无制作配方。"),
        }
        for kind, (effect, usage, limits, acquisition) in standard.items():
            lines += self.entry(kind, effect, usage, limits, acquisition)
        descriptions = {
            "vending_machine": "木材与金币双向等价兑换。也出售可乐、维修扳手（3金币）和零件（1金币）。",
            "match_machine": "木材与金币双向等价兑换，并出售单次火柴；每次点火仍需木材。",
            "gun_machine": "出售轻弹包、步枪弹包和霰弹包。枪械和投掷物仍靠探索获取。",
        }
        groups = (
            ("食品与饮料设施", ("vending_machine", "ration_dispenser", "food_dehydrator")),
            ("医疗与救援设施", ("medical_dispenser", "rescue_dispenser")),
            ("燃料与点火设施", ("match_machine", "fuel_packer", "ignition_dispenser")),
            ("建材与回收设施", ("building_supply_machine", "salvage_machine")),
            ("装备与远行设施", ("outfitter_machine", "expedition_machine")),
            ("弹药销售设施", ("gun_machine",)),
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
            CATALOGS["food"]: self.foods(),
            CATALOGS["tool"]: self.tools(),
            CATALOGS["weapon"]: self.weapons(),
            CATALOGS["facility"]: self.facilities(),
            "wiki/items.md": wiki_tables.render_items(self),
            "wiki/ordinary-chest-draft.md": wiki_tables.render_chest(self),
            "wiki/monsters.md": wiki_tables.render_monsters(self),
            "wiki/roles.md": web_wiki.render_roles(self),
        }
        expected = set().union(*self.categories.values())
        if self.seen != expected or (expected - {"fixed_heater"}) | {"wood", "coin", "wall", "fence", "floor", "door", "landmine"} != self.available:
            raise ValueError("Manual categories do not cover every item exactly once")
        return {filename: "\n".join(lines).rstrip() + "\n" for filename, lines in pages.items()}


def relative_links(content, filename, root):
    pages = {path.name: path.relative_to(root / "docs").as_posix() for path in (root / "docs").rglob("*.md") if path.name != "README.md"}
    pages.update({Path(page).name: page for page in CATALOGS.values()})

    def replace(match):
        target, anchor = match.groups()
        page = pages.get(posixpath.basename(target))
        if page is None or ":" in target:
            return match.group(0)
        return "](" + posixpath.relpath(page, posixpath.dirname(filename)) + (anchor or "") + ")"

    return re.sub(r"\]\(([^)#]+\.md)(#[^)]*)?\)", replace, content)


def generate(root=ROOT, check=False):
    manual = Manual()
    differences = []
    generated = {filename: relative_links(content, filename, root) for filename, content in manual.render().items()}
    outputs = {root / "docs" / filename: content for filename, content in generated.items()}
    outputs[root / "cold_world_game/static/wiki/data.json"] = web_wiki.generate(root, manual, generated)
    for path, content in outputs.items():
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            differences.append(path.relative_to(root).as_posix())
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
    if check and differences:
        raise SystemExit("Outdated manuals: " + ", ".join(differences))
    print("Verified domain catalogs: " + ", ".join(f"{group}={len(kinds)}" for group, kinds in manual.categories.items()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate domain-based item manuals from current game rules")
    parser.add_argument("--check", action="store_true", help="Check generated catalogs without writing")
    generate(check=parser.parse_args().check)
