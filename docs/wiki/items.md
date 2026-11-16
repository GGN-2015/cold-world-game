# 物品、掉率与价格速查

[Wiki 首页](README.md) · [项目手册](../README.md) · [怪物与战斗](../world/combat.md)

名称可跳到用途、操作和获取方式。击倒次数以无加成的 10 血小怪为例，按直接伤害计算。时间均为现实秒。

## 如何读概率

- 表里的每箱概率以一口普通自然箱为分母，表示至少开出 1 件。玩家放置的箱子为空。
- 武器、消耗品和装备共用普通自然箱，每个条目独立判定，减少同功能物品占据新箱子的机会。
- 机器出现率以对应的房屋或区块为分母，独立抽到后还要有合规空位。交易成本以一次兑换为单位。

## 各组候选

| 组别 | 候选物品 |
| --- | --- |
| 武器（20 种） | [手枪](../items/weapons.md#手枪)、[老式左轮](../items/weapons.md#老式左轮)、[霰弹枪](../items/weapons.md#霰弹枪)、[步枪](../items/weapons.md#步枪)、[猎人步枪](../items/weapons.md#猎人步枪)、[撬棍](../items/weapons.md#撬棍)、[开山刀](../items/weapons.md#开山刀)、[工兵铲](../items/weapons.md#工兵铲)、[寒霜长矛](../items/weapons.md#寒霜长矛)、[寒冰法杖](../items/weapons.md#寒冰法杖)、[烈焰法杖](../items/weapons.md#烈焰法杖)、[连锁电锯](../items/weapons.md#连锁电锯)、[火焰喷射器](../items/weapons.md#火焰喷射器)、[手榴弹](../items/weapons.md#手榴弹)、[破片炸药](../items/weapons.md#破片炸药)、[冰霜弹](../items/weapons.md#冰霜弹)、[火球术卷轴](../items/weapons.md#火球术卷轴)、[冰冻术卷轴](../items/weapons.md#冰冻术卷轴)、[燃烧瓶](../items/weapons.md#燃烧瓶)、[信号爆弹](../items/weapons.md#信号爆弹) |
| 消耗品（31 种） | [轻弹包](../items/weapons.md#轻弹包)、[步枪弹包](../items/weapons.md#步枪弹包)、[霰弹包](../items/weapons.md#霰弹包)、[木材](../building/building.md#木材)、[零件](../items/tools.md#零件)、[莎草纸](../items/tools.md#莎草纸)、[打火机](../items/tools.md#打火机)、[火柴](../items/tools.md#火柴)、[汽油](../items/tools.md#汽油)、[火绒盒](../items/tools.md#火绒盒)、[奥利奥](../items/foods.md#奥利奥)、[可乐](../items/foods.md#可乐)、[巧克力](../items/foods.md#巧克力)、[压缩饼干](../items/foods.md#压缩饼干)、[混合坚果](../items/foods.md#混合坚果)、[榴莲](../items/foods.md#榴莲)、[伏特加](../items/foods.md#伏特加)、[沙丁鱼罐头](../items/foods.md#沙丁鱼罐头)、[方便面](../items/foods.md#方便面)、[速冻饺子](../items/foods.md#速冻饺子)、[冷冻牛肉](../items/foods.md#冷冻牛肉)、[八宝粽](../items/foods.md#八宝粽)、[暖宝宝贴](../items/tools.md#暖宝宝贴)、[急救包](../items/tools.md#急救包)、[口袋暖炉](../items/tools.md#口袋暖炉)、[野外补给袋](../items/tools.md#野外补给袋)、[燃料补给包](../items/tools.md#燃料补给包)、[救援信标](../items/tools.md#救援信标)、[除颤器](../items/tools.md#除颤器)、[复苏针](../items/tools.md#复苏针)、[地雷](../building/building.md#地雷) |
| 装备（13 种） | [手提灯](../items/tools.md#手提灯)、[羽毛笔](../items/tools.md#羽毛笔)、[伐木护符](../items/tools.md#伐木护符)、[维修扳手](../items/tools.md#维修扳手)、[指南针](../items/tools.md#指南针)、[长柄套](../items/tools.md#长柄套)、[建筑法杖](../items/tools.md#建筑法杖)、[地板法杖](../items/tools.md#地板法杖)、[羊毛围巾](../items/tools.md#羊毛围巾)、[雪地靴](../items/tools.md#雪地靴)、[护甲片](../items/tools.md#护甲片)、[安全头盔](../items/tools.md#安全头盔)、[保鲜饭盒](../items/tools.md#保鲜饭盒) |

## 枪械

| 物品及 ID | 弹量 | 单弹 × 弹丸数 | 间隔 / 弹速 | 击倒小怪 | 机制 | 每箱出现 | 其他获取 / 价格 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [手枪](../items/weapons.md#手枪) · `handgun` | 12 | 5 × 1 | 0.25 秒 / 20 格/秒 | 2 发 | 单击发射 | 14%（1 件） | 新玩家自带 |
| [霰弹枪](../items/weapons.md#霰弹枪) · `shotgun` | 6 | 2 × 5 | 0.8 秒 / 18 格/秒 | 1 发（全中），5 发（每发中 1 枚） | 单击发射，±12° | 4%（1 件） | — |
| [步枪](../items/weapons.md#步枪) · `rifle` | 20 | 4 × 1 | 0.15 秒 / 28 格/秒 | 3 发 | 可按住连发 | 2%（1 件） | — |
| [老式左轮](../items/weapons.md#老式左轮) · `rust_revolver` | 6 | 7 × 1 | 0.5 秒 / 18 格/秒 | 2 发 | 单击发射 | 1%（1 件） | — |
| [猎人步枪](../items/weapons.md#猎人步枪) · `hunting_rifle` | 5 | 12 × 1 | 0.95 秒 / 30 格/秒 | 1 发 | 单击发射 | 2.6%（1 件） | — |

## 近战武器

| 物品及 ID | 耐久 | 单次伤害 | 间隔 | 半径 / 扇形 | 击倒小怪 | 机制 | 每箱出现 | 其他获取 / 价格 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [斧头](../items/weapons.md#斧头) · `axe` | 无限 | 3 | 0.7 秒 | 1.5 格 / 180° | 4 挥 | 砍树 0.5 秒 | — | 新玩家自带 |
| [寒冰法杖](../items/weapons.md#寒冰法杖) · `ice_staff` | 50 | 5 | 0.65 秒 | 3 格 / 180° | 2 挥 | 冰冻 2 秒 | 3.9%（1 件） | — |
| [烈焰法杖](../items/weapons.md#烈焰法杖) · `flame_staff` | 50 | 4 | 0.65 秒 | 3 格 / 180° | 3 挥 | 灼烧 2 秒 | 3.9%（1 件） | — |
| [榴莲皮](../items/weapons.md#榴莲皮) · `durian_peel` | 无限 | 4 | 0.7 秒 | 1.5 格 / 180° | 3 挥 | — | — | 食用榴莲后留下 |
| [撬棍](../items/weapons.md#撬棍) · `crowbar` | 50 | 6 | 0.6 秒 | 2.4 格 / 120° | 2 挥 | — | 3.7%（1 件） | — |
| [开山刀](../items/weapons.md#开山刀) · `machete` | 50 | 5 | 0.55 秒 | 2.7 格 / 180° | 2 挥 | — | 3.1%（1 件） | — |
| [工兵铲](../items/weapons.md#工兵铲) · `snow_shovel` | 50 | 4 | 0.75 秒 | 3.4 格 / 180° | 3 挥 | 基础击退 1.2 格 | 1.5%（1 件） | — |
| [寒霜长矛](../items/weapons.md#寒霜长矛) · `frost_spear` | 45 | 7 | 0.9 秒 | 4 格 / 70° | 2 挥 | 冰冻 2 秒 | 2.4%（1 件） | — |
| [连锁电锯](../items/weapons.md#连锁电锯) · `chain_chainsaw` | 45 | 6 | 0.5 秒 | 2.5 格 / 180° | 2 挥 | 砍树 0.25 秒，半径 5 格内连锁，含首棵最多 5 棵 | 7.5%（1 件） | — |

## 投掷、喷射与卷轴

| 物品及 ID | 消耗 | 基础伤害 / 形状 | 蓄力 / 飞行 / 间隔 | 直接击倒小怪 | 机制 | 每箱出现 | 其他获取 / 价格 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [手榴弹](../items/weapons.md#手榴弹) · `grenade` | 一次性 | 20 / 3 格半径 | 0.5 / 0.45 / 1 秒 | 1 件 | 清除爆炸范围内的密林树木 | 2%（1 件） | — |
| [冰霜弹](../items/weapons.md#冰霜弹) · `frost_bomb` | 一次性 | 10 / 3 格半径 | 0.5 / 0.45 / 1 秒 | 1 件 | 冰冻 3.5 秒；稳定湖面 25 秒 | 0.6%（1 件） | — |
| [燃烧瓶](../items/weapons.md#燃烧瓶) · `fire_bottle` | 一次性 | 6 / 3 格半径 | 0.5 / 0.45 / 1 秒 | 2 件 | 灼烧 3 秒；引燃树木 | 0.8%（1 件） | — |
| [破片炸药](../items/weapons.md#破片炸药) · `cluster_charge` | 一次性 | 24 / 2 格半径 | 1 / 0.65 / 1 秒 | 1 件 | 清除爆炸范围内的密林树木 | 0.4%（1 件） | — |
| [信号爆弹](../items/weapons.md#信号爆弹) · `flare_bomb` | 一次性 | 8 / 3 格半径 | 0.5 / 0.45 / 1 秒 | 2 件 | 灼烧 2 秒；照明 6 秒 | 1%（1 件） | — |
| [火焰喷射器](../items/weapons.md#火焰喷射器) · `flamethrower` | 8 次 | 3 / 5 × 1.5 格火带 | 单击或每 0.5 秒一次 | 4 次 | 灼烧 2 秒，最远 5 格；引燃树木，可用汽油装填 | 7.5%（1 件） | — |
| [火球术卷轴](../items/weapons.md#火球术卷轴) · `fireball_scroll` | 一次性 | 5 / 2 格半径 | 0.5 / 0.4 / 1 秒 | 2 件 | 灼烧 1.5 秒，最远 11 格；引燃树木与沿途照明 | 7.5%（1 件） | 原卷轴＋莎草纸＋羽毛笔 1 次可复制 |
| [冰冻术卷轴](../items/weapons.md#冰冻术卷轴) · `freeze_scroll` | 一次性 | 4 / 2.5 格半径 | 0.5 / 0.4 / 1 秒 | 3 件 | 冰冻 2 秒，最远 11 格；稳定湖面 15 秒 | 7.5%（1 件） | 原卷轴＋莎草纸＋羽毛笔 1 次可复制 |

## 食品与饮料

| 物品及 ID | 恢复或状态 | 使用条件 | 每箱出现 | 其他获取 / 价格 |
| --- | --- | --- | --- | --- |
| [方便面](../items/foods.md#方便面) · `instant_noodles` | 饱食度 +2.5 | 需火，长按 0.5 秒 | 10%（1 件） | 小怪 2.5% |
| [速冻饺子](../items/foods.md#速冻饺子) · `dumplings` | 饱食度 +4 | 需火，长按 0.5 秒 | 12%（1 件） | — |
| [冷冻牛肉](../items/foods.md#冷冻牛肉) · `beef` | 饱食度 +5 | 需火，长按 0.5 秒 | 12%（1 件） | — |
| [沙丁鱼罐头](../items/foods.md#沙丁鱼罐头) · `sardines` | 饱食度 +3 | 需火，长按 0.5 秒 | 10%（1 件） | 小怪 0.5% |
| [奥利奥](../items/foods.md#奥利奥) · `oreos` | 饱食度 +1.5 | 即食，长按 0.5 秒 | 10%（1 件） | 小怪 3.5%；爬行者 5% |
| [压缩饼干](../items/foods.md#压缩饼干) · `compressed_biscuits` | 饱食度 +4 | 即食，长按 0.5 秒 | 8%（1 件） | 小怪 1% |
| [可乐](../items/foods.md#可乐) · `cola` | 饱食度 +2 | 即食，长按 0.5 秒 | 8%（1 件） | 小怪 2.5%；[自动售货机](../building/machines.md#自动售货机) 1 金币 → 1 件 |
| [榴莲](../items/foods.md#榴莲) · `durian` | 饱食度 +3 | 即食，长按 0.5 秒 | 3%（1 件） | — |
| [巧克力](../items/foods.md#巧克力) · `chocolate_bar` | 饱食度 +2 | 即食，长按 0.5 秒 | 5%（1 件） | [自动口粮机](../building/machines.md#自动口粮机) 4 金币 → 1 件 |
| [牛肉干](../items/foods.md#牛肉干) · `beef_jerky` | 饱食度 +3.5 | 即食，长按 0.5 秒 | — | [自助食品脱水机](../building/machines.md#自助食品脱水机) 1 冷冻牛肉＋1 木材 → 1 件 |
| [混合坚果](../items/foods.md#混合坚果) · `mixed_nuts` | 饱食度 +3 | 即食，长按 0.5 秒 | 6%（1 件） | [自动口粮机](../building/machines.md#自动口粮机) 8 金币 → 1 件 |
| [小鱼干](../items/foods.md#小鱼干) · `dried_fish` | 饱食度 +2.5 | 即食，长按 0.5 秒 | — | [自助食品脱水机](../building/machines.md#自助食品脱水机) 1 沙丁鱼罐头＋1 木材 → 1 件 |
| [燕麦粥](../items/foods.md#燕麦粥) · `oatmeal` | 饱食度 +4.5 | 需火，长按 0.5 秒 | — | [自动口粮机](../building/machines.md#自动口粮机) 4 金币 → 1 件 |
| [八宝粽](../items/foods.md#八宝粽) · `festival_dumpling` | 饱食度 +6 | 需火，长按 0.5 秒 | 1%（1 件） | — |
| [伏特加](../items/foods.md#伏特加) · `vodka` | 30 秒体感 30°C | 长按 0.5 秒 | 2%（1 件） | — |

## 弹药包

| 物品及 ID | 每包弹量 | 兼容武器 | 每箱出现 | 其他获取 / 价格 |
| --- | --- | --- | --- | --- |
| [轻弹包](../items/weapons.md#轻弹包) · `light_ammo` | 12 发 | [手枪](../items/weapons.md#手枪)、[老式左轮](../items/weapons.md#老式左轮) | 16%（1 件） | [弹夹机](../building/machines.md#弹夹机) 2 金币 → 1 件 |
| [步枪弹包](../items/weapons.md#步枪弹包) · `rifle_ammo` | 8 发 | [步枪](../items/weapons.md#步枪)、[猎人步枪](../items/weapons.md#猎人步枪)、[固定机枪](../building/outdoor-facilities.md#固定机枪) | 9%（1 件） | [弹夹机](../building/machines.md#弹夹机) 3 金币 → 1 件 |
| [霰弹包](../items/weapons.md#霰弹包) · `shotgun_ammo` | 4 发 | [霰弹枪](../items/weapons.md#霰弹枪) | 9%（1 件） | [弹夹机](../building/machines.md#弹夹机) 3 金币 → 1 件 |

## 工具、装备与创造道具

| 物品及 ID | 主要数值或用途 | 每箱出现 | 其他获取 / 价格 |
| --- | --- | --- | --- |
| [护甲片](../items/tools.md#护甲片) · `armor_plate` | 受到的怪物伤害 ×0.8 | 2.4%（1 件） | — |
| [长柄套](../items/tools.md#长柄套) · `axe_handle` | 斧头近战半径 +0.75 格 | 2%（1 件） | — |
| [建筑法杖](../items/tools.md#建筑法杖) · `building_wand` | 铺 1×3 木墙，滚轮或触屏按钮切换横竖，每成功一格耗 1 木材 | 2%（1 件） | — |
| [伐木护符](../items/tools.md#伐木护符) · `chain_charm` | 斧头砍树有 35% 概率触发半径 5 格连锁，含首棵最多 5 棵 | 3%（1 件） | — |
| [指南针](../items/tools.md#指南针) · `compass` | 随身携带时，红针指向最近的合格屏外建筑区块 | 2%（1 件） | — |
| [除颤器](../items/tools.md#除颤器) · `defibrillator` | 长按 1.5 秒，救起 2 格内的队友至 36°C、至少 10 饥饿 | 2%（1 件） | [队友救援补给机](../building/machines.md#队友救援补给机) 12 金币 → 1 件 |
| [羽绒服](../items/tools.md#羽绒服) · `down_coat` | 体感温度 +6°C | — | [防寒装备裁缝机](../building/machines.md#防寒装备裁缝机) 8 金币＋4 木材 → 1 件 |
| [野外补给袋](../items/tools.md#野外补给袋) · `field_supply` | 长按 1 秒，2 次，体温 +8°C，饥饿 +2 | 0.6%（1 件） | — |
| [引火棒](../items/tools.md#引火棒) · `firestarter` | 点火 3 次，每次另耗木材 | — | [自助火种补给机](../building/machines.md#自助火种补给机) 3 金币 → 1 件 |
| [急救包](../items/tools.md#急救包) · `first_aid_kit` | 长按 0.5 秒，1 次，体温回到 36°C，补到至少 10 饥饿 | 3.9%（1 件） | [自动医疗柜](../building/machines.md#自动医疗柜) 8 金币 → 1 件 |
| [地板法杖](../items/tools.md#地板法杖) · `floor_wand` | 铺 3×3 木地板，每成功一格耗 1 木材 | 2%（1 件） | — |
| [燃料补给包](../items/tools.md#燃料补给包) · `fuel_pack` | 长按 1 秒，1 次，产出 5 木材 | 1.2%（1 件） | [木材压缩打包机](../building/machines.md#木材压缩打包机) 5 木材＋1 金币 → 1 件；[木材压缩打包机](../building/machines.md#木材压缩打包机) 10 木材＋1 金币 → 2 件 |
| [汽油](../items/tools.md#汽油) · `gasoline` | 8 次，可分次点火；装填消耗整件，按剩余耐久补充喷射次数 | 12%（1 件） | — |
| [葡萄糖补给](../items/tools.md#葡萄糖补给) · `glucose_vial` | 长按 0.5 秒，1 次，饥饿 +3 | — | [自动医疗柜](../building/machines.md#自动医疗柜) 2 金币 → 1 件 |
| [暖宝宝贴](../items/tools.md#暖宝宝贴) · `heat_patch` | 长按 0.5 秒，1 次，体温回到 36°C | 2.9%（1 件） | [自动医疗柜](../building/machines.md#自动医疗柜) 4 金币 → 1 件 |
| [保鲜饭盒](../items/tools.md#保鲜饭盒) · `insulated_lunchbox` | 自然饥饿消耗 ×0.8 | 2.6%（1 件） | — |
| [手提灯](../items/tools.md#手提灯) · `lantern` | 选中后照亮 6 格内迷雾，附近玩家共享光照 | 7.5%（1 件） | — |
| [打火机](../items/tools.md#打火机) · `lighter` | 点火 20 次，每次另耗木材 | 4%（1 件） | 新玩家自带 |
| [火柴](../items/tools.md#火柴) · `matches` | 点火 1 次，每次另耗木材 | 4%（1 件） | [自助火柴机](../building/machines.md#自助火柴机) 1 金币 → 1 件 |
| [莎草纸](../items/tools.md#莎草纸) · `papyrus` | 复制卷轴每次消耗 1 张，可堆 16 张／格 | 30.63%（1–4 件） | — |
| [口袋暖炉](../items/tools.md#口袋暖炉) · `pocket_stove` | 长按 0.5 秒，3 次，体温 +12°C | 4.5%（1 件） | — |
| [羽毛笔](../items/tools.md#羽毛笔) · `quill` | 6 次，消耗莎草纸复制随身卷轴 | 7.5%（1 件） | — |
| [维修扳手](../items/tools.md#维修扳手) · `repair_wrench` | 12 次，每修一次自然设备另耗 1 零件 | 2.5%（1 件） | [自动售货机](../building/machines.md#自动售货机) 3 金币 → 1 件 |
| [救援信标](../items/tools.md#救援信标) · `rescue_beacon` | 长按 2.5 秒回原点附近，1 次 | 2.2%（1 件） | [远行应急补给站](../building/machines.md#远行应急补给站) 4 金币＋2 木材 → 1 件 |
| [裂纹回城石](../items/tools.md#裂纹回城石) · `return_stone` | 长按 2 秒回原点附近，3 次 | — | [远行应急补给站](../building/machines.md#远行应急补给站) 10 金币＋3 木材 → 1 件 |
| [复苏针](../items/tools.md#复苏针) · `revival_syringe` | 长按 3 秒，救起 1 格内的队友至 36°C、至少 10 饥饿 | 0.4%（1 件） | [队友救援补给机](../building/machines.md#队友救援补给机) 8 金币 → 1 件 |
| [安全头盔](../items/tools.md#安全头盔) · `safety_helmet` | 受到的怪物击退 ×0.75 | 1%（1 件） | — |
| [雪地靴](../items/tools.md#雪地靴) · `snow_boots` | 选中时移速 ×1.5 | 3.7%（1 件） | [防寒装备裁缝机](../building/machines.md#防寒装备裁缝机) 5 金币＋3 木材 → 1 件 |
| [零件](../items/tools.md#零件) · `spare_part` | 每次维修消耗 1 件，可堆 16 件／格 | 35%（1–3 件） | [自动售货机](../building/machines.md#自动售货机) 1 金币 → 1 件 |
| [火绒盒](../items/tools.md#火绒盒) · `tinder_box` | 点火 8 次，每次另耗木材 | 3.6%（1 件） | [自助火种补给机](../building/machines.md#自助火种补给机) 8 金币 → 1 件 |
| [羊毛围巾](../items/tools.md#羊毛围巾) · `wool_scarf` | 体感温度 +3°C | 4.8%（1 件） | [防寒装备裁缝机](../building/machines.md#防寒装备裁缝机) 4 金币＋2 木材 → 1 件 |
| [创造食品](../items/tools.md#创造食品) · `creative_food` | 饥饿锁定 10 | — | 管理员 `creative` / `give` |
| [创造存钱罐](../items/tools.md#创造存钱罐) · `creative_piggy_bank` | 购物免金币，实物交易材料照常消耗 | — | 管理员 `creative` / `give` |
| [创造鞋](../items/tools.md#创造鞋) · `creative_shoes` | 移速 ×2 | — | 管理员 `creative` / `give` |
| [创造工具](../items/tools.md#创造工具) · `creative_tool` | 合成免材料，回收栅栏照常消耗 | — | 管理员 `creative` / `give` |
| [创造保温套](../items/tools.md#创造保温套) · `creative_warm_suit` | 体温锁定 36°C | — | 管理员 `creative` / `give` |

## 材料、货币、建筑与机器

| 物品及 ID | 主要功能 | 每箱出现 | 其他获取 / 价格 |
| --- | --- | --- | --- |
| [篝火](../building/machines.md#篝火) · `campfire` | 每份木材燃烧 120 秒，可取暖、做饭，燃烧时周围 3.5 格内持续驱雾 | — | 放置后按拆除规则处理；合成 1 木材 → 1 件；[营地建材售货机](../building/machines.md#营地建材售货机) 1 金币 → 4 件 |
| [箱子](../building/machines.md#箱子) · `chest` | 自然房屋战利品 / 存储 | — | 房屋自然生成 1–2 个；取空可拆取；合成 2 木材 → 1 件；[营地建材售货机](../building/machines.md#营地建材售货机) 1 金币 → 3 件 |
| [硬币](../building/economy.md#金钱属性) · `coin` | 钱包货币，不占格 | — | [怪物掉落](monsters.md#死亡掉落总表)；[自动售货机](../building/machines.md#自动售货机) 10 木材 → 1 金币；[自助火柴机](../building/machines.md#自助火柴机) 10 木材 → 1 金币 |
| [木门](../building/building.md#木门) · `door` | 可开关，关闭时挡人和热量 | — | 放置后按拆除规则处理；合成 2 木材 → 1 件 |
| [木栅栏](../building/building.md#木栅栏) · `fence` | 挡人，可回收为木材 | — | 放置后按拆除规则处理；合成 1 木材 → 2 件 |
| [木地板](../building/building.md#木地板) · `floor` | 可通行，提供地板保温 | — | 放置后按拆除规则处理；合成 1 木材 → 1 件；[营地建材售货机](../building/machines.md#营地建材售货机) 1 金币 → 6 件 |
| [地雷](../building/building.md#地雷) · `landmine` | 触发一次，3 格内怪物基础伤害 20 | 2%（1 件） | — |
| [小猪存钱罐](../building/machines.md#小猪存钱罐) · `piggy_bank` | 共享金币存取，可搬运的实体存钱罐 | — | 房屋生成 5%（需空位）；可拆取 |
| [木墙](../building/building.md#木墙) · `wall` | 挡人和视线，封闭房间 | — | 放置后按拆除规则处理；合成 1 木材 → 1 件；[营地建材售货机](../building/machines.md#营地建材售货机) 1 金币 → 6 件 |
| [木材](../building/building.md#木材) · `wood` | 建造材料、燃料、交易物 | 50%（1–5 件） | 砍密林外的普通树 1–3；拆除部分建筑；雪狐怪 15%；燃料补给包拆出 5 个；合成 2 木栅栏 → 1 件；[自动售货机](../building/machines.md#自动售货机) 1 金币 → 10 件；[自助火柴机](../building/machines.md#自助火柴机) 1 金币 → 10 件；[废材拆解回收机](../building/machines.md#废材拆解回收机) 2 木墙 → 1 件；[废材拆解回收机](../building/machines.md#废材拆解回收机) 2 木地板 → 1 件；[废材拆解回收机](../building/machines.md#废材拆解回收机) 1 箱子 → 1 件；[废材拆解回收机](../building/machines.md#废材拆解回收机) 1 手枪 → 3 件；[废材拆解回收机](../building/machines.md#废材拆解回收机) 1 霰弹枪 → 5 件；[废材拆解回收机](../building/machines.md#废材拆解回收机) 1 步枪 → 10 件 |
| [营地建材售货机](../building/machines.md#营地建材售货机) · `building_supply_machine` | 4 种兑换 | — | 房屋生成 1.4%（需空位）；可拆取 |
| [远行应急补给站](../building/machines.md#远行应急补给站) · `expedition_machine` | 2 种兑换 | — | 房屋生成 0.2%（需空位）；可拆取 |
| [自助食品脱水机](../building/machines.md#自助食品脱水机) · `food_dehydrator` | 2 种兑换 | — | 房屋生成 1.5%（需空位）；可拆取 |
| [木材压缩打包机](../building/machines.md#木材压缩打包机) · `fuel_packer` | 2 种兑换 | — | 房屋生成 1.2%（需空位）；可拆取 |
| [弹夹机](../building/machines.md#弹夹机) · `gun_machine` | 3 种兑换 | — | 房屋生成 2%（需空位）；可拆取 |
| [自助火种补给机](../building/machines.md#自助火种补给机) · `ignition_dispenser` | 2 种兑换 | — | 房屋生成 1.5%（需空位）；可拆取 |
| [自助火柴机](../building/machines.md#自助火柴机) · `match_machine` | 3 种兑换 | — | 房屋生成 2%（需空位）；可拆取 |
| [自动医疗柜](../building/machines.md#自动医疗柜) · `medical_dispenser` | 3 种兑换 | — | 房屋生成 0.8%（需空位）；可拆取 |
| [防寒装备裁缝机](../building/machines.md#防寒装备裁缝机) · `outfitter_machine` | 3 种兑换 | — | 房屋生成 0.6%（需空位）；可拆取 |
| [自动口粮机](../building/machines.md#自动口粮机) · `ration_dispenser` | 3 种兑换 | — | 房屋生成 1.8%（需空位）；可拆取 |
| [队友救援补给机](../building/machines.md#队友救援补给机) · `rescue_dispenser` | 2 种兑换 | — | 房屋生成 0.5%（需空位）；可拆取 |
| [废材拆解回收机](../building/machines.md#废材拆解回收机) · `salvage_machine` | 6 种兑换 | — | 房屋生成 1%（需空位）；可拆取 |
| [自动售货机](../building/machines.md#自动售货机) · `vending_machine` | 5 种兑换 | — | 房屋生成 4%（需空位）；可拆取 |

## 自然固定设施

不能作为背包物品。查看[户外座位与固定武器](../building/outdoor-facilities.md)、[设施图鉴](../building/machines.md)和[群系地图](../world/world.md#地形与房屋)。

| 设施 | 获取位置或概率 | 作用 |
| --- | --- | --- |
| [公园椅子](../building/outdoor-facilities.md#公园椅子) | 每个自然空地区块 2% | 休息座位 |
| [固定机枪](../building/outdoor-facilities.md#固定机枪) | 每个自然空地区块 1% | 80 发，5 伤、0.15 秒，穿透怪物 |
| [待维修机枪](../building/outdoor-facilities.md#待维修机枪) | 区块独立 1.8% 且有空位；另有区块 (-2, 0) | 修理后可装整包步枪弹，5 伤、0.15 秒，穿透怪物 |
| [固定供暖机](../building/machines.md#固定供暖机) | 区块独立 1.8% 且有空位；另有区块 (2, 0) | 维修后每份木材 150 秒 |
| [林间索道](../building/biome-devices.md#林间索道) | 密林固定成对点位 | 维修任一端后双向通行 |
| [路灯](../building/biome-devices.md#路灯) | 迷雾固定点位 | 维修后照亮半径 10 格 |
| [桥墩](../building/biome-devices.md#桥墩) / [桥面](../building/biome-devices.md#桥面) | 冰湖预设桥墩，维修后生成一段桥面 | 逐段恢复通行，桥面可承托篝火 |

数据以[物品与交易常量](../../cold_world_game/constants.py)、[扩展物品](../../cold_world_game/expansion.py)、[交易机器](../../cold_world_game/room_machines.py)和[自然掉落实现](../../cold_world_game/procedural.py)为准。
