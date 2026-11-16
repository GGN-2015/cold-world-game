"""Build the wiki's comparison tables from the current gameplay registries."""

from math import ceil

MONSTER_NAMES = {
    "small": "小怪", "big": "大怪", "fast": "快速怪", "crawler": "雪地爬行者",
    "armored": "冰甲怪", "stalker": "雪狐怪", "tree_spirit": "树精",
    "frost_guard": "冰守卫", "ember_guard": "火守卫",
}


def percent(rate):
    return f"{rate * 100:.2f}".rstrip("0").rstrip(".") + "%"


def harvest_chain(rules):
    adjacent, one_gap, two_gaps = rules.HARVEST_CHAIN_COSTS
    return (f"首棵之后有 {rules.HARVEST_CHAIN_LIMIT - 1} 次机会。优先直接相邻，再找隔 1 格、隔 2 格的树，"
            f"分别花 {adjacent}、{one_gap}、{two_gaps} 次机会。")


def render_chest(manual):
    lines = [
        "# 一区普通箱掉率", "",
        "每口普通自然箱按同一张表独立抽取各物品。档位用于平衡维护，每件仍按表中列出的实际概率判定。",
        "", "[武器与弹药用法](../items/weapons.md#枪械与掩体) · [数值与其他来源](items.md)", "",
    ]
    category_names = {"weapon": "武器", "consumable": "消耗品", "equipment": "装备"}
    categories = {kind: category_names[category] for category, rows in manual.profile["loot"].items()
                  for kind, _, _ in rows}
    tier_items = [kind for _, kinds in manual.loot_tiers.values() for kind in kinds]
    if len(tier_items) != len(set(tier_items)) or set(tier_items) != set(categories):
        raise ValueError("Every ordinary chest item must have exactly one loot tier")
    for tier, (description, kinds) in manual.loot_tiers.items():
        lines += [f"## {tier}", "", description, "", "| 物品 | 类型 | 每箱出现 | 命中数量 |", "| --- | --- | --- | --- |"]
        for kind in sorted(kinds, key=lambda item: (-manual.chest_odds[item][0], item)):
            chance, amount = manual.chest_odds[kind]
            lines.append(f"| {manual.link(kind)} | {categories[kind]} | {percent(chance)} | {amount} |")
        lines.append("")
    return lines


def chest_odds(profile):
    return {
        kind: (chance, f"{min(quantities)}–{max(quantities)} 件" if min(quantities) != max(quantities) else f"{min(quantities)} 件")
        for rows in profile["loot"].values() for kind, chance, quantities in rows
    }


def weapon_status(settings):
    statuses = []
    if "freeze_duration" in settings:
        statuses.append(f"冰冻 {settings['freeze_duration']:g} 秒")
    if "burn_duration" in settings:
        statuses.append(f"灼烧 {settings['burn_duration']:g} 秒")
    return "、".join(statuses) or "—"


def tool_effect(manual, kind):
    rules = manual.rules
    if kind == "gasoline":
        return f"{rules.IGNITERS[kind]} 次，可分次点火或补充喷射次数。装填后保留未转移的余量"
    if kind in rules.IGNITERS:
        return f"点火 {rules.IGNITERS[kind]} 次，每次另耗木材"
    if kind in rules.EQUIPPED_ITEMS:
        return f"选中时移速 ×{rules.EQUIPPED_ITEMS[kind]['speed_multiplier']:g}"
    if kind in rules.RETURN_ITEMS:
        settings = rules.RETURN_ITEMS[kind]
        return f"长按 {settings['duration']:g} 秒回原点附近，{settings['uses']} 次"
    if kind in rules.REVIVAL_ITEMS:
        item = rules.REVIVAL_ITEMS[kind]
        return f"长按 {item['duration']:g} 秒，救起 {item['range']:g} 格内的队友至 {item['temperature']:g}°C、至少 {item['hunger']:g} 饥饿"
    if kind in rules.HEALING_ITEMS:
        item = rules.HEALING_ITEMS[kind]
        effects = [f"长按 {item['duration']:g} 秒，{item.get('uses', 1)} 次"]
        if "temperature" in item:
            effects.append(f"体温回到 {item['temperature']:g}°C")
        if "temperature_delta" in item:
            effects.append(f"体温 +{item['temperature_delta']:g}°C")
        if "hunger" in item:
            effects.append(f"补到至少 {item['hunger']:g} 饥饿")
        if "hunger_delta" in item:
            effects.append(f"饥饿 +{item['hunger_delta']:g}")
        effects.extend(f"产出 {count} {manual.names[output][0]}" for output, count in item.get("supplies", {}).items())
        return "，".join(effects)
    if kind in rules.PASSIVE_ITEMS:
        fields = {
            "ambient_bonus": "体感温度 +{:g}°C",
            "damage_taken_multiplier": "受到的怪物伤害 ×{:g}",
            "knockback_taken_multiplier": "受到的怪物击退 ×{:g}",
            "hunger_drain_multiplier": "自然饥饿消耗 ×{:g}",
            "pickup_radius_bonus": "拾取半径 +{:g} 格",
            "damage_multiplier": "对普通小怪和快速怪的伤害 ×{:g}",
            "axe_range_bonus": "斧头近战半径 +{:g} 格",
        }
        return "，".join(label.format(rules.PASSIVE_ITEMS[kind][key])
                        for key, label in fields.items() if key in rules.PASSIVE_ITEMS[kind])
    return {
        "compass": "随身携带时，红针指向最近的合格屏外建筑区块",
        "repair_wrench": f"{manual.wildlife.WRENCH_USES} 次，每完成一个维修步骤扣 1 次",
        "spare_part": f"按设备扣除所需数量，可堆 {rules.STACK_LIMITS['spare_part']} 件／格",
        "lantern": f"选中后照亮 {rules.FOG_LANTERN_RADIUS} 格内迷雾，附近玩家共享光照",
        "chain_charm": f"斧头砍树有 {percent(rules.CHAIN_CHARM_CHANCE)} 概率触发连锁。{harvest_chain(rules)}",
        "quill": f"{rules.BIOME_ITEMS['quill']['uses']} 次，消耗莎草纸复制随身卷轴",
        "papyrus": f"复制卷轴每次消耗 1 张，可堆 {rules.STACK_LIMITS['papyrus']} 张／格",
        "building_wand": "铺 1×3 木墙，滚轮或触屏按钮切换横竖，每成功一格耗 1 木材",
        "floor_wand": "铺 3×3 木地板，每成功一格耗 1 木材",
        "creative_warm_suit": f"体温锁定 {rules.CREATIVE_ITEMS['creative_warm_suit']['temperature']:g}°C",
        "creative_food": f"饥饿锁定 {rules.CREATIVE_ITEMS['creative_food']['hunger']:g}",
        "creative_shoes": f"移速 ×{rules.CREATIVE_ITEMS['creative_shoes']['speed_multiplier']:g}",
        "creative_tool": "合成免材料，回收栅栏照常消耗",
        "creative_piggy_bank": "购物免金币，实物交易材料照常消耗",
    }[kind]


def render_items(manual):
    rules, profile = manual.rules, manual.profile
    odds = manual.chest_odds
    pools = (
        (label, [kind for kind, _, _ in profile["loot"][key]])
        for key, label in (("weapon", "武器"), ("consumable", "消耗品"), ("equipment", "装备"))
    )
    lines = [
        "# 物品、掉率与价格速查", "",
        "[Wiki 首页](README.md) · [项目手册](../README.md) · [怪物与战斗](../world/combat.md)", "",
        "名称可跳到用途、操作和获取方式。击倒次数以无加成的 10 血小怪为例，按直接伤害计算。时间均为现实秒。", "",
        "## 如何读概率", "",
        "- 表里的每箱概率以一口普通自然箱为分母，表示至少开出 1 件。玩家放置的箱子为空。",
        "- 武器、消耗品和装备共用普通自然箱，每个条目独立判定，减少同功能物品占据新箱子的机会。",
        "- 机器出现率以对应的房屋或区块为分母，独立抽到后还要有合规空位。交易成本以一次兑换为单位。",
    ]
    lines += ["", "## 各组候选", "",
              "| 组别 | 候选物品 |", "| --- | --- |"]
    for label, kinds in pools:
        lines.append(f"| {label}（{len(kinds)} 种） | {'、'.join(manual.link(kind) for kind in kinds)} |")

    sources = {kind: [] for kind in rules.ITEM_KINDS}
    for kind in ("axe", "handgun", "lighter"):
        sources[kind].append("新玩家自带")
    sources["wood"].append("砍密林外的普通树 1–3；拆除部分建筑")
    sources["durian_peel"].append("食用榴莲后留下")
    sources["fireball_scroll"].append("原卷轴＋莎草纸＋羽毛笔 1 次可复制")
    sources["freeze_scroll"].append("原卷轴＋莎草纸＋羽毛笔 1 次可复制")
    sources["coin"].append("[怪物掉落](monsters.md#死亡掉落总表)")
    for kind, _, chance in profile["machines"]:
        sources[kind].append(f"房屋生成 {percent(chance)}（需空位）；可拆取")
    sources["chest"].append("房屋自然生成 1–2 个；取空可拆取")
    for kind in ("campfire", "door", "wall", "floor", "fence"):
        sources[kind].append("放置后按拆除规则处理")
    food_weights = rules.SMALL_MONSTER_FOOD_WEIGHTS
    for kind, weight in food_weights.items():
        chance = weight / sum(food_weights.values()) * rules.SMALL_MONSTER_FOOD_CHANCE
        sources[kind].append(f"小怪 {percent(chance)}")
    sources["oreos"].append("爬行者 5%")
    sources["wood"].append("雪狐怪 15%；燃料补给包拆出 5 个")
    for kind in rules.CREATIVE_ITEMS:
        sources[kind].append("管理员 `creative` / `give`")
    for recipe in rules.RECIPES.values():
        inputs = "＋".join(f"{count} {manual.names[kind][0]}" for kind, count in recipe["inputs"].items())
        sources[recipe["output"]].append(f"合成 {inputs} → {recipe['count']} 件")
    for machine, offers in rules.MACHINE_OFFERS.items():
        for offer in offers.values():
            inputs = "＋".join(f"{count} {'金币' if kind == 'coin' else manual.names[kind][0]}"
                              for kind, count in offer["inputs"].items())
            unit = "金币" if offer["output"] == "coin" else "件"
            sources[offer["output"]].append(f"{manual.link(machine)} {inputs} → {offer['count']} {unit}")

    written = set()

    def row(kind, *cells):
        if kind not in manual.available:
            return
        probability, origin = odds.get(kind, (0, ""))
        chance = f"{percent(probability)}（{origin}）" if origin else "—"
        label = f"{manual.link(kind)} · `{kind}`"
        values = (label, *cells, chance, "；".join(sources[kind]) or "—")
        if kind in written:
            raise ValueError(f"Duplicate wiki entry: {kind}")
        written.add(kind)
        lines.append("| " + " | ".join(map(str, values)) + " |")

    def section(title, *fields):
        headings = ("物品及 ID", *fields, "每箱出现", "其他获取 / 价格")
        lines.extend(["", f"## {title}", "", "| " + " | ".join(headings) + " |",
                      "| " + " | ".join(["---"] * len(headings)) + " |"])

    small_hp = manual.wildlife.MONSTER_TYPES["small"]["hp"]
    section("枪械", "弹量", "单弹 × 弹丸数", "间隔 / 弹速", "击倒小怪", "机制")
    for kind, settings in rules.GUNS.items():
        pellets = settings.get("pellets", 5 if kind == "shotgun" else 1)
        spread = settings.get("spread", 12 if kind == "shotgun" else 0)
        mode = "可按住连发" if kind == "rifle" or settings.get("automatic") else "单击发射"
        status = weapon_status(settings)
        mechanics = "，".join([mode] + ([f"±{spread}°"] if spread else []) + ([status] if status != "—" else []))
        hits = f"{ceil(small_hp / (settings['damage'] * pellets))} 发"
        if pellets > 1:
            hits += f"（全中），{ceil(small_hp / settings['damage'])} 发（每发中 1 枚）"
        row(kind, settings["ammo"], f"{settings['damage']:g} × {pellets}", f"{settings['interval']:g} 秒 / {settings['speed']:g} 格/秒", hits, mechanics)

    section("近战武器", "耐久", "单次伤害", "间隔", "半径 / 扇形", "击倒小怪", "机制")
    for kind, settings in rules.MELEE_WEAPONS.items():
        status = weapon_status(settings)
        if kind in rules.HARVEST_TOOLS:
            status = f"砍树 {rules.HARVEST_TOOLS[kind]['tree']:g} 秒"
        if kind == "chain_chainsaw":
            status += f"，邻树优先连锁，含首棵最多 {rules.HARVEST_CHAIN_LIMIT} 棵"
        if "knockback" in settings:
            status = f"基础击退 {settings['knockback']:g} 格"
        row(kind, settings.get("uses", "无限"), f"{settings['damage']:g}", f"{settings['interval']:g} 秒",
            f"{settings['range']:g} 格 / {settings['arc_degrees']}°", f"{ceil(small_hp / settings['damage'])} 挥", status)

    section("投掷、喷射与卷轴", "消耗", "基础伤害 / 形状", "蓄力 / 飞行 / 间隔", "直接击倒小怪", "机制")
    for kind, settings in rules.EXPLOSIVE_WEAPONS.items():
        duration = f"{settings['duration']:g} / {settings['flight_duration']:g} / {settings['interval']:g} 秒"
        charges = profile["items"][kind]["uses"]
        cost = f"每发 {settings['coin_cost']} 金币" if settings["coin_cost"] else f"{charges} 次" if charges else "一次性"
        status = weapon_status(settings)
        if "cast_range" in settings:
            status = f"{status}，最远 {settings['cast_range']:g} 格"
        special = {"flamethrower": "引燃树木，可用汽油装填", "fireball_scroll": "引燃树木与沿途照明",
                   "freeze_scroll": "稳定湖面 15 秒", "frost_bomb": "稳定湖面 25 秒", "fire_bottle": "引燃树木", "flare_bomb": "照明 6 秒"}.get(kind, "清除爆炸范围内的密林树木")
        shape = "5 × 1.5 格火带" if kind == "flamethrower" else f"{settings['radius']:g} 格半径"
        cadence = f"单击或每 {settings['interval']:g} 秒一次" if kind == "flamethrower" else duration
        row(kind, cost, f"{settings['damage']:g} / {shape}", cadence,
            f"{ceil(small_hp / settings['damage'])} {'次' if charges else '件'}",
            special if status == "—" else f"{status}；{special}")

    section("食品与饮料", "恢复或状态", "使用条件")
    for kind, hunger in rules.FOODS.items():
        row(kind, f"饱食度 +{hunger:g}", "即食，长按 0.5 秒" if kind in rules.READY_TO_EAT_FOODS else "需火，长按 0.5 秒")
    for kind, drink in rules.DRINKS.items():
        row(kind, f"{drink['effect_duration']:g} 秒体感 {drink['felt_temperature']:g}°C", f"长按 {drink['duration']:g} 秒")

    section("弹药包", "每包弹量", "兼容武器")
    for kind, rounds in rules.AMMO_PACKS.items():
        weapons = [manual.link(gun) for gun, (pack, _) in rules.RELOAD_RULES.items() if kind == pack and gun in manual.available]
        if kind == "rifle_ammo":
            weapons.append("[固定机枪](outdoor-facilities.md#固定机枪)")
        row(kind, f"{rounds} 发", "、".join(weapons))

    section("工具、装备与创造道具", "主要数值或用途")
    for kind in sorted(manual.categories["tool"], key=lambda item: (item in rules.CREATIVE_ITEMS, item)):
        row(kind, tool_effect(manual, kind))

    section("材料、货币、建筑与机器", "主要功能")
    roles = {"wood": "建造材料、燃料、交易物", "coin": "钱包货币，不占格", "wall": "挡人和视线，封闭房间",
             "fence": "挡人，可回收为木材", "floor": "可通行，提供地板保温", "door": "可开关，关闭时挡人和热量",
             "landmine": f"触发一次，{rules.EXPLOSIVE_WEAPONS['grenade']['radius']:g} 格内怪物基础伤害 {rules.EXPLOSIVE_WEAPONS['grenade']['damage']:g}",
             "chest": "自然房屋战利品 / 存储", "campfire": f"每份木材燃烧 {rules.BURN_SECONDS:g} 秒，可取暖、做饭，燃烧时周围 {rules.FOG_CAMPFIRE_RADIUS:g} 格内持续驱雾",
             "piggy_bank": "共享金币存取，可搬运的实体存钱罐"}
    remaining = sorted(manual.available - written, key=lambda kind: (kind in rules.MACHINE_OFFERS, kind))
    for kind in remaining:
        row(kind, roles[kind] if kind in roles else f"{len(rules.MACHINE_OFFERS[kind])} 种兑换")

    lines += ["", "## 自然固定设施", "",
              "不能作为背包物品。查看[户外座位与固定武器](outdoor-facilities.md)、[设施图鉴](machines.md)和[群系地图](world.md#地形与房屋)。", "",
              "| 设施 | 获取位置或概率 | 作用 |", "| --- | --- | --- |"]
    lines.extend([
        f"| [公园椅子](outdoor-facilities.md#公园椅子) | 每个自然空地区块 {percent(profile['outdoors']['park_bench']['chance'])} | 休息座位 |",
        f"| [固定机枪](outdoor-facilities.md#固定机枪) | 每个自然空地区块 {percent(profile['outdoors']['mounted_gun']['chance'])} | {profile['outdoors']['mounted_gun']['ammo']} 发，5 伤、0.15 秒，穿透怪物 |",
        "| [待维修机枪](outdoor-facilities.md#待维修机枪) | 区块独立 1.8% 且有空位；另有区块 (-2, 0) | 修理后可装整包步枪弹，5 伤、0.15 秒，穿透怪物 |",
        f"| [固定供暖机](machines.md#固定供暖机) | 区块独立 1.8% 且有空位；另有区块 (2, 0) | 维修后每份木材 {rules.FIXED_HEATER_BURN_SECONDS:g} 秒 |",
        f"| [林间索道](biome-devices.md#林间索道) | 密林固定成对点位 | 每次 1 零件，共 {manual.wildlife.CABLE_REPAIR_PARTS} 次，两端共享进度 |",
        f"| [路灯](biome-devices.md#路灯) | 迷雾固定点位 | 维修后照亮半径 {rules.FOG_STREET_LAMP_RADIUS} 格 |",
        f"| [桥墩](biome-devices.md#桥墩) / [桥面](biome-devices.md#桥面) | 冰湖主桥 {manual.wildlife.BRIDGE_REPAIRS_PER_CROSSING} 处需修桥墩 | 每段 1 零件，每格新桥面 1 木材，可承托篝火 |",
        "", "数据以[物品与交易常量](../../cold_world_game/constants.py)、[扩展物品](../../cold_world_game/expansion.py)、"
        "[交易机器](../../cold_world_game/room_machines.py)和[自然掉落实现](../../cold_world_game/procedural.py)为准。", "",
    ])
    return lines


def render_monsters(manual):
    rules, wildlife, names = manual.rules, manual.wildlife, manual.monsters
    roaming = manual.roaming_monsters
    nearby_radius = roaming.PACED_SPAWN_RADIUS
    dawn, dusk = rules.MONSTER_REST_HOURS
    lines = [
        "# 怪物数值、生成与掉落速查", "",
        "[Wiki 首页](README.md) · [完整怪物图鉴与行为](combat.md) · [物品与武器速查](items.md)", "",
        "攻击栏为未计装备减伤的基础值。单次命中扣减的饱食度是减伤后体温伤害的四分之一，最多扣 1 点。时间均为现实秒。", "",
        "## 战斗属性", "",
        "| 怪物及 ID | HP | 基础移速（格/秒） | 近战伤害 / 间隔 | 远程伤害 / 间隔 | 特性 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    features = {"small": "全天近战", "big": "白天休眠，能拆栅栏、墙和闭门", "fast": "白天休眠，受击退量较大",
                "crawler": "慢速近战", "armored": "较高 HP，无专属减伤", "stalker": "敏捷近战",
                "tree_spirit": "伪装成树，靠近后现身", "frost_guard": "驻点，弱火，遇光眩晕，命中减速",
                "ember_guard": "驻点，弱冰，命中附加灼烧"}
    for kind, settings in wildlife.MONSTER_TYPES.items():
        if kind not in names:
            continue
        attack = f"{settings['damage']:g} / {settings['interval']:g} 秒"
        fixed = kind in wildlife.BIOME_GUARDS
        melee = "—" if fixed else attack
        ranged = attack if fixed else "5 / 2 秒" if kind == "big" else "—"
        name = names[kind]
        lines.append(f"| [{name}](combat.md#{name}) · `{kind}` | {settings['hp']:g} | {settings['speed']:g} | {melee} | {ranged} | {features[kind]} |")
    lines += ["", f"大怪与驻点怪物弹速均为 **{rules.MONSTER_PROJECTILE_SPEED:g} 格/秒**。"
              "普通近战通常在 1 格内。驻点怪物在 13 格内有视线时射击。", "",
              "## 刷怪机制", "",
              "全地图的普通怪统一使用**一区难度档**。下表时段为游戏内时间，等待时间为现实秒。", "",
              "| 时段 | 首次尝试 | 成功生成一只后的间隔 | 暂缓条件 |",
              "| --- | --- | --- | --- |"]
    periods = (("day", f"白天（{dawn:02d}:00–{dusk:02d}:00）"),
               ("night", f"夜间（{dusk:02d}:00–次日 {dawn:02d}:00）"))
    for phase, label in periods:
        (first_min, first_max), (interval_min, interval_max), limit = roaming.ZONE_ONE_SPAWN_PACING[phase]
        lines.append(f"| {label} | {first_min}–{first_max} 秒 | {interval_min}–{interval_max} 秒 | "
                     f"玩家周围 {nearby_radius} 格内已有 {limit} 只活动怪 |")
    lines += [
        "",
        f"普通怪以在线且站立的玩家为中心，在 20–{nearby_radius} 格内寻找落点。相距 {nearby_radius} 格以内的队友共享间隔。"
        f"达到附近活动怪上限、世界上限或找不到落点时，等 {roaming.PACED_SPAWN_RETRY} 秒再试。",
        "",
        "普通怪落点须已生成、空置且能落脚，并且至少离每位在线玩家 20 格。全员离线时暂停刷怪。"
        "详见[完整生成与清除规则](combat.md#怪物生成)。",
        "",
        f"全世界同时存在的普通怪上限固定为 **{rules.MONSTER_LIMIT} 只**。超过上限的存档暂停补刷，已有怪物继续按正常规则活动与清除。", "",
              "### 群系和房屋", "",
              "- 密林树精由预设的伪装树现身。",
              f"- 冰湖和迷雾使用 {rules.BIOME_SPAWN_MULTIPLIER} 倍普通刷怪节奏。等待时间除以该倍率，附近活动怪上限乘以该倍率。落点留在对应群系内，两种群系重叠时倍率不叠加。",
              f"- 非出生房屋首次生成时有 {percent(rules.ROOM_MONSTER_CHANCE)} 概率尝试放入 1 只初始小怪。",
              "", "详见[群系怪物的生成](combat.md#群系怪物的生成)。", "",
              "## 普通怪物类型概率", "",
              "| 普通刷怪池 | " + " | ".join(names[kind] for kind in rules.MONSTER_SPAWN_CHANCES["day"]) + " |",
              "| --- | " + " | ".join(["---"] * len(rules.MONSTER_SPAWN_CHANCES["day"])) + " |"]
    for phase, label in (("day", "03:00–21:00"), ("night", "21:00–次日 03:00")):
        ratios = " | ".join(percent(rate) for rate in rules.MONSTER_SPAWN_CHANCES[phase].values())
        lines.append(f"| {label} | {ratios} |")
    lines += ["", f"表内概率以一次普通刷怪成功为分母。每只普通怪另有 **{percent(rules.MONSTER_XRAY_CHANCE)}** 概率获得夜间透视资质。", "",
              "## 死亡掉落总表", "",
              "| 怪物 | 不掉金币 | 掉 1 枚 | 掉 2 枚 | 独立额外掉落 |",
              "| --- | --- | --- | --- | --- |"]
    extra = {"small": f"{percent(rules.SMALL_MONSTER_FOOD_CHANCE)} 食品，见[条件分布](combat.md#普通小怪的食品掉落)",
             "crawler": "5% 奥利奥", "stalker": "15% 木材"}
    for kind in names:
        distribution = dict(rules.MONSTER_COIN_DROPS.get(kind, ((0, 1),)))
        coins = " | ".join(percent(distribution.get(number, 0)) for number in range(3))
        lines.append(f"| {names[kind]} | {coins} | {extra.get(kind, '—')} |")
    lines += ["", "金币结果互斥。", "",
              "代码来源见[怪物属性](../../cold_world_game/wildlife.py)、[普通生成与索敌](../../cold_world_game/monsters.py)、"
              "[群系怪物](../../cold_world_game/biomes.py)和[战斗结算](../../cold_world_game/combat.py)。", ""]
    return lines
