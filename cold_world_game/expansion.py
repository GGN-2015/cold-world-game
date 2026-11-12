EXPANSION_ITEMS = {}


def register(kind, name, english, group, mechanic, chance, settings, effect, usage, art):
    EXPANSION_ITEMS[kind] = {"name": [name, english], "group": group, "mechanic": mechanic, "chance": chance, "settings": settings, "effect": effect, "usage": usage, "art": art}


def food(kind, name, english, chance, hunger, ready, art):
    register(kind, name, english, "food", "food", chance, {"hunger": hunger, "ready": ready},
             [f"恢复{hunger}点饥饿，可超过10。", f"Restores {hunger} hunger, including above 10."],
             [f"选中后长按0.5秒吃掉；{'不需要篝火' if ready else '需要燃烧篝火曼哈顿距离1至3格'}。饥饿大于10时不能吃，手机按住使用。", f"Equip and hold Use or left click for 0.5 s. {'No fire needed' if ready else 'Requires a lit campfire 1–3 Manhattan tiles away'}. Cannot eat while hunger exceeds 10."], art)


food("chocolate_bar", "巧克力", "Chocolate bar", .018, 2, True, "bar")
food("energy_bar", "能量棒", "Energy bar", .012, 3, True, "bar")
food("peanut_pack", "花生米", "Roasted peanuts", .015, 2.5, True, "nuts")
food("dried_mango", "芒果干", "Dried mango", .018, 1.5, True, "fruit")
food("beef_jerky", "牛肉干", "Beef jerky", .010, 3.5, True, "jerky")
food("canned_peaches", "黄桃罐头", "Canned peaches", .015, 2, True, "can")
food("canned_beans", "焗豆罐头", "Canned beans", .010, 3.5, True, "can")
food("canned_corn", "玉米罐头", "Canned corn", .015, 2.5, True, "can")
food("canned_pineapple", "菠萝罐头", "Canned pineapple", .016, 2, True, "can")
food("sesame_biscuit", "芝麻饼", "Sesame biscuit", .018, 2, True, "biscuit")
food("rice_cracker", "米饼", "Rice cracker", .020, 1, True, "biscuit")
food("honey_sachet", "蜂蜜包", "Honey sachet", .018, 1.5, True, "pouch")
food("mixed_nuts", "混合坚果", "Mixed nuts", .012, 3, True, "nuts")
food("seaweed_roll", "海苔卷", "Seaweed roll", .017, 1.5, True, "roll")
food("dried_fish", "小鱼干", "Dried fish", .012, 2.5, True, "fish")
food("frozen_pizza", "冷冻披萨", "Frozen pizza", .006, 5, False, "pizza")
food("curry_rice", "咖喱饭", "Curry rice", .005, 5.5, False, "meal")
food("oatmeal", "燕麦粥", "Oatmeal", .008, 4.5, False, "bowl")
food("mushroom_soup", "蘑菇汤", "Mushroom soup", .009, 4, False, "bowl")
food("festival_dumpling", "八宝粽", "Festival rice dumpling", .003, 6, False, "dumpling")


def weapon(kind, name, english, mechanic, chance, settings, art):
    if mechanic == "gun":
        settings = {"speed": 22, "instant": True, **settings}
        count = settings.get("pellets", 1)
        effect = [f"初始{settings['ammo']}发，每弹丸伤害{settings['damage']}，每枪{count}弹丸，间隔{settings['interval']}秒。", f"{settings['ammo']} rounds; {settings['damage']} damage per pellet, {count} pellet(s) per shot, {settings['interval']} s interval."]
        usage = [f"选中后{'按住连续射击' if settings.get('automatic') else '单击发射一枪，长按不连发'}；手机使用按钮同理。耗尽消失，不能装填。普通子弹穿透规则及误伤规则不变。", f"Equip and {'hold for automatic fire' if settings.get('automatic') else 'click once per shot; no hold-to-repeat'}; use the mobile Use button likewise. Disappears when empty; no reload. Normal bullet piercing and friendly-fire rules apply."]
    elif mechanic == "melee":
        settings = {"effect": f"fx_{kind}_sweep", **settings}
        effect = [f"初始{settings['uses']}次，伤害{settings['damage']}，半径{settings['range']}格，正前方{settings['arc_degrees']}度扇形，间隔{settings['interval']}秒。", f"{settings['uses']} charges; {settings['damage']} damage, radius {settings['range']}, forward {settings['arc_degrees']}° sweep, {settings['interval']} s interval."]
        usage = ["单击空地或怪物挥动，手机瞄准后点使用；每次有效挥动含空挥消耗一次，耗尽消失。不能拆建筑，不可长按连攻。", "Click ground or a monster to swing; aim then tap Use on mobile. Each valid swing, even a miss, costs a charge. Disappears when spent. Cannot dismantle or hold for repeated swings."]
    else:
        settings = {"duration": .5, "interval": 1.0, "flight_duration": .45, "coin_cost": 0, **settings}
        effect = [f"一次性；爆炸半径{settings['radius']}格，伤害{settings['damage']}，只伤怪物，不伤玩家或建筑。", f"Single-use; blast radius {settings['radius']} tiles, {settings['damage']} damage to monsters only, never players or buildings."]
        usage = [f"选中后朝落点长按{settings['duration']}秒投掷；手机可长按场景，或瞄准后按住使用。落点须已探索且在视野半对角线内，用后消失。", f"Equip and hold {settings['duration']} s toward a landing point; hold the scene on mobile, or aim then hold Use. Landing must be explored and within half the viewport diagonal. Consumed on use."]
    if "freeze_duration" in settings:
        duration = settings["freeze_duration"]
        effect[0] += f" 活动怪物冰冻{duration}秒、速度减半，大怪不能射击；休眠怪物只受伤。"
        effect[1] += f" Freezes active monsters for {duration} s at half speed; frozen big monsters cannot shoot. Resting monsters only take damage."
    if "burn_duration" in settings:
        settings["burn_interval"] = .5
        duration = settings["burn_duration"]
        effect[0] += f" 灼烧{duration}秒，每0.5秒伤害4，无持续击退；同类状态不叠加，只延长。"
        effect[1] += f" Burns for {duration} s, dealing 4 every 0.5 s without ongoing knockback. Same status does not stack; it only extends."
    register(kind, name, english, "weapon", mechanic, chance, settings, effect, usage, art)


weapon("rust_revolver", "老式左轮", "Old revolver", "gun", .010, {"ammo": 24, "damage": 7, "interval": .5, "speed": 18}, "revolver")
weapon("compact_pistol", "袖珍手枪", "Pocket pistol", "gun", .014, {"ammo": 60, "damage": 5, "interval": .20}, "pistol")
weapon("hunting_rifle", "猎人步枪", "Hunting rifle", "gun", .006, {"ammo": 18, "damage": 12, "interval": .95, "speed": 30}, "rifle")
weapon("double_barrel", "双管猎枪", "Double-barrel shotgun", "gun", .008, {"ammo": 24, "damage": 3, "interval": 1.1, "pellets": 4, "spread": 9, "speed": 18}, "shotgun")
weapon("nail_gun", "射钉枪", "Nail gun", "gun", .012, {"ammo": 90, "damage": 2, "interval": .18, "pellets": 3, "spread": 4, "automatic": True, "speed": 16}, "nailer")
weapon("ice_carbine", "冰晶卡宾枪", "Ice carbine", "gun", .004, {"ammo": 24, "damage": 4, "interval": .65, "freeze_duration": 2}, "rifle")
weapon("ember_pistol", "余烬手枪", "Ember pistol", "gun", .003, {"ammo": 16, "damage": 3, "interval": .8, "burn_duration": 1.5}, "pistol")
weapon("storm_smg", "暴风冲锋枪", "Storm SMG", "gun", .002, {"ammo": 160, "damage": 4, "interval": .10, "automatic": True, "speed": 24}, "smg")
weapon("crowbar", "撬棍", "Crowbar", "melee", .018, {"uses": 60, "damage": 5, "range": 2.4, "arc_degrees": 120, "interval": .6}, "crowbar")
weapon("machete", "开山刀", "Machete", "melee", .012, {"uses": 80, "damage": 5, "range": 2.7, "arc_degrees": 180, "interval": .55}, "blade")
weapon("snow_shovel", "工兵铲", "Snow shovel", "melee", .015, {"uses": 50, "damage": 3, "range": 3.4, "arc_degrees": 180, "interval": .75, "knockback": 1.2}, "shovel")
weapon("shock_baton", "电击棍", "Shock baton", "melee", .006, {"uses": 40, "damage": 6, "range": 2, "arc_degrees": 120, "interval": .7, "freeze_duration": 1.5}, "baton")
weapon("frost_spear", "寒霜长矛", "Frost spear", "melee", .004, {"uses": 40, "damage": 7, "range": 4, "arc_degrees": 70, "interval": .9, "freeze_duration": 2}, "spear")
weapon("fire_whip", "火焰鞭", "Fire whip", "melee", .003, {"uses": 35, "damage": 3, "range": 3.6, "arc_degrees": 140, "interval": .8, "burn_duration": 2}, "whip")
weapon("tin_bomb", "铁罐炸弹", "Tin bomb", "explosive", .015, {"damage": 12, "radius": 2.2, "duration": .6, "flight_duration": .6}, "bomb")
weapon("frost_bomb", "冰霜弹", "Frost bomb", "explosive", .006, {"damage": 8, "radius": 2.5, "freeze_duration": 3, "effect": "fx_frost_blast"}, "orb")
weapon("fire_bottle", "燃烧瓶", "Fire bottle", "explosive", .008, {"damage": 4, "radius": 2.5, "burn_duration": 2, "effect": "fx_fire_blast"}, "bottle")
weapon("cluster_charge", "破片炸药", "Fragmentation charge", "explosive", .004, {"damage": 24, "radius": 2, "duration": 1, "flight_duration": .65}, "charge")
weapon("pulse_grenade", "脉冲手雷", "Pulse grenade", "explosive", .003, {"damage": 10, "radius": 3.5, "freeze_duration": 1.5, "effect": "fx_pulse_blast"}, "orb")
weapon("flare_bomb", "信号爆弹", "Flare bomb", "explosive", .010, {"damage": 8, "radius": 3, "burn_duration": 1, "effect": "fx_fire_blast"}, "bomb")


def tool(kind, name, english, mechanic, chance, settings, effect, usage, art):
    register(kind, name, english, "tool", mechanic, chance, settings, effect, usage, art)


tool("wool_scarf", "羊毛围巾", "Wool scarf", "passive", .018, {"ambient_bonus": 3},
     ["携带时体感温度增加3°C，不直接增加体温；同类保暖只取最高值。", "While carried, felt temperature rises by 3°C, not body temperature directly. Only the strongest insulation bonus applies."],
     ["放在背包或物品栏即生效，不用选中；不消耗，多件不叠加。亢奋时仍固定体感30°C。", "Keep in bag or hotbar, no selection needed. Not consumed or stacked. Excitement still fixes felt temperature at 30°C."], "scarf")
tool("down_coat", "羽绒服", "Down coat", "passive", .005, {"ambient_bonus": 6},
     ["携带时体感温度增加6°C，同类只取最高值；仍可能失温。", "Adds 6°C felt temperature while carried; only the strongest insulation applies. Hypothermia remains possible."],
     ["放背包或物品栏即生效，不用选中；不消耗，多件不叠加。亢奋时固定30°C。", "Carry in bag or hotbar without selecting. Not consumed or stacked. Excitement remains fixed at 30°C."], "coat")
tool("snow_boots", "雪地靴", "Snow boots", "equipment", .012, {"speed_multiplier": 1.5},
     ["选中时当前体温/饥饿下移速乘1.5，倒地仍不能移动。", "While selected, multiplies current temperature/hunger-adjusted speed by 1.5. Downed players still cannot move."],
     ["必须放在物品栏并选中；切换即失效，不消耗，不与其他手持加速叠加。", "Select in the hotbar; switching removes the bonus. Not consumed. Cannot stack with other selected speed equipment."], "boots")
tool("hiking_cane", "登山手杖", "Hiking cane", "equipment", .006, {"speed_multiplier": 1.8},
     ["选中时当前移速乘1.8，不会取消饥饿与失温惩罚；不能攻击。", "While selected, multiplies current speed by 1.8 without removing hunger or cold penalties. Cannot attack."],
     ["放物品栏并选中；未选中无效，倒地无效，不消耗、不叠加。", "Select in the hotbar. No benefit while unselected or downed; not consumed or stacked."], "cane")
tool("pocket_stove", "口袋暖炉", "Pocket warmer", "healing", .010, {"duration": .5, "temperature_delta": 12, "uses": 3},
     ["每次恢复12°C体温，上限36°C；不改变饥饿，初始3次。", "Restores 12°C body temperature per use, capped at 36°C. Hunger is unchanged. Starts with 3 charges."],
     ["选中后长按0.5秒；手机按住使用，无需篝火，倒地也能用。耗尽消失。", "Equip and hold left click or Use for 0.5 s. No fire needed; usable while downed. Disappears when spent."], "warmer")
tool("warming_flask", "保温壶", "Warming flask", "healing", .008, {"duration": .7, "temperature_delta": 18, "uses": 2},
     ["每次恢复18°C体温，上限36°C；饥饿不变，初始2次。", "Restores 18°C body temperature per use, capped at 36°C. No hunger change. Starts with 2 charges."],
     ["选中后长按0.7秒，无需火，倒地可用；手机按住使用，耗尽消失。", "Equip and hold for 0.7 s, without fire, even while downed. Hold Use on mobile. Disappears after 2 uses."], "flask")
tool("thermal_blanket", "保温毯", "Thermal blanket", "healing", .009, {"duration": 1, "temperature": 36},
     ["一次性恢复36°C满体温，不改变饥饿。", "Single-use; restores full 36°C body temperature without changing hunger."],
     ["选中后长按1秒，无需火，倒地也能用；手机按住使用。", "Equip and hold for 1 s; no fire needed, even while downed. Hold Use on mobile."], "blanket")
tool("glucose_vial", "葡萄糖补给", "Glucose vial", "healing", .014, {"duration": .5, "hunger_delta": 3},
     ["一次性补充3点饥饿，最多补至10，不降低已有超额饥饿，体温不变。", "Adds up to 3 hunger toward 10, preserving hunger already above 10. No temperature change; single-use."],
     ["选中后长按0.5秒，无需火，倒地也能用；它是恢复用品，不是可超额进食的食品。", "Equip and hold 0.5 s without fire, even while downed. This is a recovery supply, not an uncapped food."], "vial")
tool("field_supply", "野外补给袋", "Field supply pouch", "healing", .006, {"duration": 1, "temperature_delta": 8, "hunger_delta": 2, "uses": 2},
     ["初始2次，每次恢复8°C体温和最多2点饥饿，分别补至36°C/10；保留超额饥饿。", "2 charges; each adds 8°C toward 36°C and up to 2 hunger toward 10, preserving excess hunger."],
     ["选中长按1秒，无需火，倒地可用；手机按住使用，耗尽消失。", "Equip and hold 1 s; no fire needed, usable while downed. Hold Use on mobile. Disappears when spent."], "pouch")
tool("revival_syringe", "复苏针", "Revival syringe", "revival", .004, {"duration": 3, "range": 1, "temperature": 36, "hunger": 10},
     ["一次性救起1格内倒地队友，恢复36°C与至少10饥饿。", "Single-use; revives a downed teammate within 1 tile to 36°C and at least 10 hunger."],
     ["对准倒地的其他在线玩家长按3秒，视线须畅通。手机可长按该玩家或瞄准后按住使用；不能自救。", "Aim at another online downed player and hold 3 s with clear sight. Hold that player on mobile, or aim and hold Use. Cannot revive yourself."], "syringe")
tool("rescue_beacon", "救援信标", "Rescue beacon", "return", .002, {"duration": 2.5, "uses": 1},
     ["一次性回到原点附近最近可站立空地，地板可落脚，等距优先远离怪物。", "Single-use return to the nearest standable ground near origin, including floors; equal-distance ties favor safety from monsters."],
     ["选中长按2.5秒；手机按住使用，无需火，倒地可用；成功后消失。", "Equip and hold 2.5 s, or hold Use on mobile. No fire needed, even while downed. Consumed on success."], "beacon")
tool("return_stone", "裂纹回城石", "Cracked return stone", "return", .001, {"duration": 2, "uses": 3},
     ["初始3次，使用回城法杖相同落点规则。", "3 charges; uses the same safe origin destination rules as the return staff."],
     ["选中长按2秒；无需火，倒地可用，手机按住使用；耗尽消失。", "Equip and hold 2 s; no fire needed, usable while downed. Hold Use on mobile. Disappears when spent."], "stone")
tool("storm_lighter", "防风火种", "Storm lighter", "igniter", .008, {"uses": 10},
     ["可点燃篝火10次，每次仍需1木材，不延长燃烧时间。", "Lights a campfire 10 times; each ignition still needs 1 wood and does not extend burn duration."],
     ["打开篝火，放入火种格与木材后点燃；不能手持直接点火，耗尽消失。", "Open a campfire, place in its igniter slot and add wood, then Ignite. Cannot ignite directly in hand; disappears when spent."], "lighter")
tool("firestarter", "引火棒", "Firestarter rod", "igniter", .018, {"uses": 3},
     ["提供3次篝火点火，其他燃烧规则不变。", "Provides 3 campfire ignitions. Other burning rules are unchanged."],
     ["放入篝火火种格并备木材，再点燃；每次耗一格次数，用完消失。", "Place in the campfire igniter slot with wood available, then Ignite. Each ignition costs one charge; disappears when empty."], "rod")
tool("tinder_box", "火绒盒", "Tinder box", "igniter", .010, {"uses": 8},
     ["提供8次篝火点火，不代替木材燃料。", "Provides 8 campfire ignitions; does not replace wood fuel."],
     ["放进篝火火种格并添加木材，通过窗口点燃，用完消失。", "Put in a campfire igniter slot, add wood and ignite through its panel. Disappears when spent."], "tin")
tool("armor_plate", "护甲片", "Armor plate", "passive", .004, {"damage_taken_multiplier": .8},
     ["携带时怪物命中造成的体温和饥饿损失减少20%；不减寒冷或自然饥饿，不减玩家枪伤。", "While carried, monster-hit temperature and hunger damage is reduced by 20%. Does not reduce weather, natural hunger drain or player gunfire."],
     ["放背包或物品栏即生效，不用选中、不消耗，多件只取最强，不叠加。", "Carry in bag or hotbar without selecting. Not consumed. Multiple copies use only the strongest reduction."], "armor")
tool("safety_helmet", "安全头盔", "Safety helmet", "passive", .010, {"knockback_taken_multiplier": .75},
     ["携带时怪物造成的击退距离减少25%，不减少伤害，不改变玩家枪击击退。", "While carried, reduces monster knockback by 25%, without reducing damage or player-gun knockback."],
     ["放背包或物品栏即生效，不用选中、不消耗、多件不叠加。", "Keep in bag or hotbar; no selection required. Not consumed or stacked."], "helmet")
tool("collector_glove", "拾荒手套", "Scavenger glove", "passive", .007, {"pickup_radius_bonus": .35},
     ["携带时自动拾取半径从0.75米增至1.1米；仍要求背包有空格、视线畅通。", "While carried, increases auto-pickup radius from 0.75 m to 1.1 m. Ordinary items still require a free bag slot and clear sight."],
     ["放背包或物品栏即生效，不消耗、多件不叠加；硬币仍直接计入金钱。", "Carry in bag or hotbar. Not consumed or stacked; coins still go directly to money."], "glove")
tool("insulated_lunchbox", "保鲜饭盒", "Insulated lunchbox", "passive", .006, {"hunger_drain_multiplier": .8},
     ["携带时自然饥饿消耗降低20%，不降低受击损失，不增加食品回复值。", "While carried, reduces natural hunger drain by 20%, not damage losses, and does not boost food restoration."],
     ["放背包或物品栏即生效，不消耗、多件不叠加；离线仍不消耗饥饿。", "Carry in bag or hotbar. Not consumed or stacked. Hunger still does not drain offline."], "lunchbox")
tool("fuel_pack", "燃料补给包", "Fuel supply pack", "healing", .012, {"duration": 1, "supplies": {"wood": 5}},
     ["一次性拆出5木材，优先放背包，再放物品栏，不改变饥饿或体温。", "Single-use; unpacks 5 wood, preferring bag then hotbar. No temperature or hunger change."],
     ["选中长按1秒，无需火；需要含补给包原格在内至少5个空格，不足时不消耗、不产出。手机按住使用。", "Equip and hold 1 s without fire. Needs at least 5 free slots including its own consumed slot. Insufficient space consumes or produces nothing. Hold Use on mobile."], "crate")


DURIAN_CHANCE = .03
EXPANSION_CATEGORIES = {"food": "food", "gun": "gun", "melee": "melee", "explosive": "explosive", "healing": "medical", "revival": "medical", "return": "return", "igniter": "igniter", "passive": "passive", "equipment": "equipment"}


def carried_modifier(player, key, default=1.0, minimum=False):
    values = [EXPANSION_ITEMS[item.kind]["settings"].get(key, default) for storage in (player.inventory, player.backpack) for item in storage if item and item.kind in EXPANSION_ITEMS and EXPANSION_ITEMS[item.kind]["mechanic"] == "passive"]
    return min([default, *values]) if minimum else max([default, *values])
