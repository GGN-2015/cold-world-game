# 十种房屋功能机器

[返回项目首页](../README.md) · [手册目录](README.md) · [基础交易规则](trading.md)

## 设计与获取

十种机器均为独立建筑物品，直接出现在新生成房屋的室内，而不是箱子里的额外掉落。概率按每间自然房屋、每种机器独立判定，使用 `room_machine:<kind>:v1` 确定性随机流。每种每房至多一台；判定成功但没有合规空位时跳过，不移动原有墙、入口、箱子或其他机器。实际出现率可能略低于表内判定概率。

所有机器是有偿加工设施，不会按时间产出物资、补贴、金币或利息，也不提供免费耐久/弹药重置。可以重复交易，但每次都必须重新付费。机器无可领取的初始库存，搬走再放置、重连或保存重启都不会赠送物品。

## 机器一览

| 建筑 / English / ID | 每房独立概率 | 功能与取舍 |
| --- | --- | --- |
| ![自动口粮机](../cold_world_game/static/assets/ration_dispenser.png) 自动口粮机 / Ration dispenser / `ration_dispenser` | 1.8% | 出售小份即食巧克力、节省格子的坚果和需要篝火的燕麦粥，不免费供餐。 |
| ![自助食品脱水机](../cold_world_game/static/assets/food_dehydrator.png) 自助食品脱水机 / Food dehydrator / `food_dehydrator` | 1.5% | 每份鲜牛肉或沙丁鱼加1木材，分别加工成牛肉干或小鱼干；牺牲部分饱腹量，换取不用篝火的即食食品。 |
| ![自动医疗柜](../cold_world_game/static/assets/medical_dispenser.png) 自动医疗柜 / Medical dispenser / `medical_dispenser` | 0.8% | 4金币买暖宝宝贴，8金币买急救包，2金币买葡萄糖补给；产物仍需自己长按使用，不会在开柜时自动治疗。 |
| ![队友救援补给机](../cold_world_game/static/assets/rescue_dispenser.png) 队友救援补给机 / Rescue supply station / `rescue_dispenser` | 0.5% | 8金币买一次性复苏针，12金币买一次性除颤器；需要亲自靠近倒地队友施救，不提供远程复活。 |
| ![木材压缩打包机](../cold_world_game/static/assets/fuel_packer.png) 木材压缩打包机 / Wood packing press / `fuel_packer` | 1.2% | 每次收1金币，将5或10木材打包成1或2份燃料补给包。只是压缩携带体积，拆包木材总量不增加。 |
| ![自助火种补给机](../cold_world_game/static/assets/ignition_dispenser.png) 自助火种补给机 / Ignition supply station / `ignition_dispenser` | 1.5% | 3金币买3次引火棒，8金币买8次火绒盒；每次点火价格与火柴相同，优势只是多次火种只占一格。 |
| ![营地建材售货机](../cold_world_game/static/assets/building_supply_machine.png) 营地建材售货机 / Camp construction depot / `building_supply_machine` | 1.4% | 每1金币可买6木墙、6地板、3空箱子或4熄灭篝火；不如买木材自行制作划算，换取少格位、即买即放的便利。 |
| ![废材拆解回收机](../cold_world_game/static/assets/salvage_machine.png) 废材拆解回收机 / Salvage recycler / `salvage_machine` | 1% | 有损回收随身建材与旧枪换木材；手枪/霰弹枪/步枪分别只换3/5/10木材，剩余弹药一并报废，不退金币。 |
| ![防寒装备裁缝机](../cold_world_game/static/assets/outfitter_machine.png) 防寒装备裁缝机 / Winter outfitter / `outfitter_machine` | 0.6% | 4金币加2木材买羊毛围巾，8金币加4木材买羽绒服，5金币加3木材买雪地靴；原有不叠加、选中才加速等限制不变。 |
| ![远行应急补给站](../cold_world_game/static/assets/expedition_machine.png) 远行应急补给站 / Expedition supply station / `expedition_machine` | 0.2% | 4金币加2木材买一次救援信标，10金币加3木材买3次裂纹回城石；必须长按使用，不提供免费传送或无限充能。 |

## 全部兑换配方

输入和输出均不可堆叠；金币从玩家金钱属性扣除，不占背包格。带次数的产物以物品原设定次数创建，既有食品的篝火、饥饿上限以及装备选中/不叠加限制全部保留。

### 自动口粮机

![自动口粮机](../cold_world_game/static/assets/ration_dispenser.png)

| 兑换ID | 完整输入 | 输出 |
| --- | --- | --- |
| `chocolate` | 1 金币 | 1 巧克力 |
| ![燕麦粥](../cold_world_game/static/assets/oatmeal.png) `oatmeal` | 1 金币 | 1 燕麦粥 |
| `nuts` | 2 金币 | 1 混合坚果 |

### 自助食品脱水机

![自助食品脱水机](../cold_world_game/static/assets/food_dehydrator.png)

| 兑换ID | 完整输入 | 输出 |
| --- | --- | --- |
| ![木材](../cold_world_game/static/assets/wood.png) ![冷冻牛肉](../cold_world_game/static/assets/beef.png) `jerky` | 1 鲜牛肉 + 1 木材 | 1 牛肉干 |
| ![小鱼干](../cold_world_game/static/assets/dried_fish.png) ![沙丁鱼罐头](../cold_world_game/static/assets/sardines.png) ![木材](../cold_world_game/static/assets/wood.png) `dried_fish` | 1 沙丁鱼 + 1 木材 | 1 小鱼干 |

### 自动医疗柜

![自动医疗柜](../cold_world_game/static/assets/medical_dispenser.png)

| 兑换ID | 完整输入 | 输出 |
| --- | --- | --- |
| ![暖宝宝贴](../cold_world_game/static/assets/heat_patch.png) `heat_patch` | 4 金币 | 1 暖宝宝贴 |
| `first_aid` | 8 金币 | 1 急救包 |
| `glucose` | 2 金币 | 1 葡萄糖补给 |

### 队友救援补给机

![队友救援补给机](../cold_world_game/static/assets/rescue_dispenser.png)

| 兑换ID | 完整输入 | 输出 |
| --- | --- | --- |
| `syringe` | 8 金币 | 1 复苏针 |
| ![除颤器](../cold_world_game/static/assets/defibrillator.png) `defibrillator` | 12 金币 | 1 除颤器 |

### 木材压缩打包机

![木材压缩打包机](../cold_world_game/static/assets/fuel_packer.png)

| 兑换ID | 完整输入 | 输出 |
| --- | --- | --- |
| ![木材](../cold_world_game/static/assets/wood.png) `pack_one` | 5 木材 + 1 金币 | 1 燃料补给包 |
| ![木材](../cold_world_game/static/assets/wood.png) `pack_two` | 10 木材 + 1 金币 | 2 燃料补给包 |

### 自助火种补给机

![自助火种补给机](../cold_world_game/static/assets/ignition_dispenser.png)

| 兑换ID | 完整输入 | 输出 |
| --- | --- | --- |
| ![引火棒](../cold_world_game/static/assets/firestarter.png) `firestarter` | 3 金币 | 1 引火棒 |
| `tinder` | 8 金币 | 1 火绒盒 |

### 营地建材售货机

![营地建材售货机](../cold_world_game/static/assets/building_supply_machine.png)

| 兑换ID | 完整输入 | 输出 |
| --- | --- | --- |
| `walls` | 1 金币 | 6 木墙 |
| `floors` | 1 金币 | 6 地板 |
| `chests` | 1 金币 | 3 空箱子 |
| `fires` | 1 金币 | 4 熄灭篝火 |

### 废材拆解回收机

![废材拆解回收机](../cold_world_game/static/assets/salvage_machine.png)

| 兑换ID | 完整输入 | 输出 |
| --- | --- | --- |
| ![木墙](../cold_world_game/static/assets/wall.png) `walls` | 2 木墙 | 1 木材 |
| ![木地板](../cold_world_game/static/assets/floor.png) `floors` | 2 地板 | 1 木材 |
| ![箱子](../cold_world_game/static/assets/chest.png) `chest` | 1 空箱子 | 1 木材 |
| ![手枪](../cold_world_game/static/assets/handgun.png) `handgun` | 1 手枪 | 3 木材 |
| ![霰弹枪](../cold_world_game/static/assets/shotgun.png) `shotgun` | 1 霰弹枪 | 5 木材 |
| ![步枪](../cold_world_game/static/assets/rifle.png) `rifle` | 1 步枪 | 10 木材 |

### 防寒装备裁缝机

![防寒装备裁缝机](../cold_world_game/static/assets/outfitter_machine.png)

| 兑换ID | 完整输入 | 输出 |
| --- | --- | --- |
| ![木材](../cold_world_game/static/assets/wood.png) `scarf` | 4 金币 + 2 木材 | 1 羊毛围巾 |
| ![木材](../cold_world_game/static/assets/wood.png) `coat` | 8 金币 + 4 木材 | 1 羽绒服 |
| ![木材](../cold_world_game/static/assets/wood.png) `boots` | 5 金币 + 3 木材 | 1 雪地靴 |

### 远行应急补给站

![远行应急补给站](../cold_world_game/static/assets/expedition_machine.png)

| 兑换ID | 完整输入 | 输出 |
| --- | --- | --- |
| ![木材](../cold_world_game/static/assets/wood.png) `beacon` | 4 金币 + 2 木材 | 1 救援信标 |
| ![木材](../cold_world_game/static/assets/wood.png) `stone` | 10 金币 + 3 木材 | 1 裂纹回城石 |

## 防套利与游戏平衡

- 不增加免费刷新、定时分红、无限武器或弹药恢复服务；所有输出都消耗金币或不可返还的实物。
- 木材压缩只改变携带体积：5木材仍只解出5木材，额外手续费不能取回；一包只能拆一次，拆包仍须完整容纳5木材。
- 食品脱水额外消耗木材，而且牛肉5饱腹变3.5、沙丁鱼3变2.5，以饱腹损失换无需火；没有反向加工配方。
- 机器出售的墙、地板和箱子按原制作成本折算，最多只相当于每金币6木材，低于基础售货机每金币10木材；就算再拆解出售也无法盈利。
- 废枪回收摧毁剩余弹药，只返3/5/10木材，分别远低于3/5/10金币购买新枪的成本；旧枪不会被自动换成满弹同款。
- 引火棒和火绒盒每次点火仍需1金币，只节省携带格位。防寒装备同属性不叠加，雪地靴仍需选中才能加速。
- 医疗和回城物品价格较高且使用后消耗或扣次数；救援必须接近队友，远行补给站本身不直接传送。

## 放置、操作与拆除

单击机器打开背包和兑换面板，手机点机器或瞄准后点使用。材料同时读取30格背包和10格物品栏，产物优先放背包。每次交易只有全部成功或全部回退，不会在空间不足时丢到地上或只领取一部分。

与箱子、篝火、小猪存钱罐及全部机器保持八邻域不相邻；自然生成也遵守此限制，并保留入口、已有可走地面与所有容器的通路。怪物不能拆机器，怪物子弹被机器挡住，玩家普通子弹仍能穿透；追踪导弹保持原本的穿透规则。

搬运时选中斧头，在机器窗口长按拆除按钮1.5秒；松开即取消。成功后只掉落同一种机器方块，不掉木材、不退货款。重新放置沿用左键/手机放置按钮和3格放置距离限制。

## 旧世界与美术

本次地图生成版本15；旧区块及其 `chunk_versions`、玩家修改、箱子内容和被采集对象保持原样，缺少版本记录的旧区按1读取。只有未生成区域使用新生成器，不重刷旧房间。机器不引入持久库存或每日计数，新旧SQLite无需删除、重建或换种子。

每种机器各有一张独立96×96透明PNG，由 `tools/machine_assets.py` 生成，再由 `tools/generate_assets.py` 统一写入清单；机器名称和说明同时生成中英文数据。机器没有逐帧生产、全地图扫描或额外粒子动画，复用已有交易、放置与拆除反馈。设计与价格源文件为 `cold_world_game/room_machines.py`。
