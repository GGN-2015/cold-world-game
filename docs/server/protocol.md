# 后端协议

[返回项目首页](../../README.md) · [手册目录](../README.md) · [本组目录](README.md)

## HTTP与连接生命周期

| 路径 | 用途 |
| --- | --- |
| `GET /` | 内置浏览器游戏与登录页 |
| `GET /api/server` | 服务信息 |
| `GET /api/info` | 规则目录、协议标识、配方与价格 |
| `GET /health` | 健康状态与 `persistence` 保存年龄/失败次数；故障暂停时HTTP 503 |
| `/static/` | 同源PNG、WAV、JavaScript与CSS |
| `/ws` | 实时WebSocket，HTTPS站点用WSS |

10秒内发送首条消息：

```json
{"type":"join","player_id":"玩家甲","password":"服务器口令","quiet_inputs":true,"client_movement":true,"state_deltas":true,"compact_state":1,"procedural_terrain":1,"player_roster":true}
```

成功返回 `welcome`，含 `player_id`、`protocol:1`、附近完整 `state` 和差分基线 `state_revision:0`。玩家ID为1～64字符，不全为空白、不含控制字符；身份绑定连接，后续不能指定他人。错误口令、同名在线或无法出生时发错误并关闭。默认只允许同源浏览器，额外Origin须服务端显式允许；非浏览器可不带Origin。

## 地图订阅

`welcome.navigation_config`独立于地形差分协商，包含`seed`（字符串）、`size`（区块边长）、`algorithm`（共享类型算法）及`legacy`（`[chunk_x,chunk_y,is_building]`旧生成器区块类型表）。这是一次性只读导航元数据，指南针不发送寻向请求、不订阅远方区块。后续状态不重复发送该字段。

`procedural_terrain:1`仅在同时启用`state_deltas:true`时生效。服务端在`welcome`附加`terrain_config`（会话标识、字符串种子、按区块版本索引的生成配置）和`terrain`，常规`state.structures`为空，动态外观放在`state.structure_states`。没有协商此能力的连接保持原有建筑快照与字段差分，不要求旧客户端理解种子地图。

`terrain`包含`add`和`remove`。`remove`是退订区块的`"x,y"`标识；`add`中完整区块包含`id/x/y/version/revision/hash/add/remove`，内部`add`是当前外观覆盖记录，内部`remove`是已删除自然对象的ID。共享生成区块用本地基底叠加覆盖；旧区块的`hash`为空、`add`为完整现有外观，不进行推测生成。

已订阅区块的近期变化可以表示为`{id,revision,patch:true,add,remove}`，仅增删变化对象；没有基底时不能应用这种补丁。修订记录不足时服务端重新发送完整区块覆盖。区块无变化时不发送`terrain`；附近订阅范围是5×5区块，不广播全图。每次重新握手重建订阅基线，不跨会话比较修订号。

`structure_states`只传点燃、占座、机枪弹药与怪物拆除等动态外观；容器实际内容仍从服务端交互状态读取，不由默认地图推算。浏览器异步加载区块后更新渲染与碰撞索引，不用空基底接受权威修改。实现与缓存故障回退见[确定性地图](../development/terrain.md)。

客户端上行每条消息最多32768字节JSON文本，拒绝NaN/Infinity；下行状态可协商二进制。每连接持续60命令/秒、突发120；超限断开。带 `seq` 的请求收到对应 `ack` 或 `error`，错误含机器码与英文消息，浏览器按代码翻译。连接级无 `seq` 错误通常随后关闭。`ping` 返回当前 `elapsed`。断线重新握手拿完整状态，不重放物品修改命令。

可选能力均只作用当前连接：`quiet_inputs` 省略不带seq的input/stop成功回执；`client_movement` 启用本机算移动、服务器汇总坐标；`state_deltas` 启用差分；`player_roster` 订阅名单。未协商的客户端仍有完整状态和服务端移动模式。

## 紧凑状态传输

`compact_state:1`要求同时开启`state_deltas:true`，可与种子地图独立协商。握手、确认和错误仍是JSON；成功握手额外返回`wire_config`，之后状态与名单增量使用MessagePack二进制帧。浏览器设置`binaryType='arraybuffer'`；未返回配置时继续使用JSON，解码或修订失败时重新握手回退，不重放交易命令。

二进制包是`[1, reset, added, payload]`。配置的`fields`表把对象字段名映射为从0开始的整数；未知字符串字段保留原名。`references`指定可压缩的ID字段，字符串引用编码为`-index-1`，非负事件序号保持原值；`added`按索引顺序追加UTF-8字符串。引用表达到16,384条时，下一个包的`reset`清空表；已解码的客户端状态保留原始ID，不受重置影响。地图种子仍是字符串，金币、次数、弹药和修订号保留整数精度。

`scales`指定数值的通信倍率，编码取整、解码除以倍率。远端坐标与速度精度为1/256格，时间为1毫秒，方向向量为1/4096；不修改数据库、服务器坐标或碰撞判定。自己的坐标保留完整浮点精度，避免碰撞边界被量化到障碍物内；自己的体温、饥饿也保持精确，用于本机移动与使用条件。附近玩家血条按0.1度更新，世界时钟显示按游戏分钟更新。

紧凑状态保留普通差分的`base/revision`约束，并增加以下语义：

| 数据 | 传输方式 |
| --- | --- |
| 物品栏、背包、容器 | `slot_changes:{inventory:[[index,item]],backpack:[...],slots:[...]}`只替换变更格；空格值为`null`，整包验证后原子应用 |
| 建筑动态外观 | `entities.structure_states`按ID增删与字段更新，不因一个火堆变化重发整组 |
| 普通子弹 | 首次可见发送轨迹锚点`x/y/flight_at`、速度和发射信息，客户端按世界时间推导位置；离开范围、碰撞终止或消失时移除 |
| 战斗事件 | `state.events`只含上次状态之后新增的附近事件；客户端按时间结束动画，不为过期事件发送删除列表 |
| 玩家名单 | 初始`roster`完整；之后`roster_delta`含独立`base/revision`、`server_time`、`entries:[{id,fields}]`和`remove`，未变账号不重发；仅排序变化时附短ID的`order`列表，保持在线优先与离线登录时间排序 |

普通子弹不公开`hit_targets`、伤害账本等内部结算信息。追踪弹与投掷物仍同步其必要目标和轨迹信息；伤害、穿透、冷却、弹药、掉落和阻挡统一由服务器计算。首次加入或重连补足当前活动子弹，不补播此前战斗事件。客户端始终按顺序解码全部差分，只把同一绘制帧前的多次画面发布合并；其间的新事件一起保留，不能丢弃有基线依赖的消息。

## 规则目录

目录只加载一次，不随10Hz世界状态重复发送。以下字段按机制分组：

| 字段 | 内容 |
| --- | --- |
| `movement`、`storage` | 速度、碰撞半径、10格物品栏/30格背包、丢弃和拾取距离 |
| `recipes` | 制作配方：`inputs`、`output`、`count` |
| `foods`、`ready_to_eat_foods`、`drinks` | 饥饿增量、即食集合、状态饮料参数 |
| `guns`、`melee_weapons`、`explosive_weapons`、`axe` | 弹药、次数、伤害、半径、扇形角、冷却及状态参数 |
| `healing_items`、`revival_items`、`return_items` | 自用恢复、队友救援、回城的长按时长和次数 |
| `igniters`、`passive_items`、`equipped_items` | 点火次数、携带被动和选中装备倍率 |
| `machine_offers`、`vending_offers` | 全机器兑换表及售货机兼容字段，统一配方结构 |
| `room_machines`、`terrain` | 自然设施与各箱内稀有物品的独立概率 |
| `currency`、`knockback`、`projectiles` | 金钱上限、击退系数、弹道阻挡与视野射程规则 |
| `expansion_items` | 物品分类/概率的补充索引，实际机制读取上面对应目录，不形成另一套玩法 |

`guns` 中 `automatic` 控制持续按住，`instant` 表示按下边沿立即产生首发（子弹仍按弹速飞行），`pellets/spread` 为散布；`melee_weapons` 的 `arc_degrees`、`range` 决定实际扇形，`effect` 指向离线PNG。恢复物品无 `hunger` 即不改饥饿，`temperature_delta/hunger_delta` 表示增量，`supplies` 表示拆包产物；`uses` 表示有限次数。目录与服务端定义一致，客户端不能自报交易价格或产物。

## 连续输入与界面命令

`input` 包含移动向量 `move`、世界坐标 `aim`、可选 `target_id`；本机移动模式还上报 `position`、`velocity`、`movement_epoch`。数组长度和数值须有效，移动修正序号须非负安全整数。服务器不对本机模式重复积分或做速度反作弊。约50毫秒合并上报，攻击/放置/丢弃前立即上报最终位置与瞄准。

紧凑连接省略未变的方向、瞄准、目标和视口；静止无变化时约250毫秒发送一次完整输入心跳。位置、速度与移动修正序号作为一组上报，不能只发位置而省略修正序号。移动中仍按约50毫秒上报；关键命令后清空输入缓存，不让省流影响停止、转屏或长按操作。

`viewport:[width,height]` 单位为世界格，不是像素，有限正数且各≤64；缺省沿用本连接值，首次32×18。转屏/缩放随输入更新，用于普通子弹消失边界。

| 命令 | 参数与行为 |
| --- | --- |
| `select` | `slot:0..9`，换格取消长按、不重置冷却 |
| `attack` | `pressed:true/false` 按下/松开边沿，非自动武器不能重复按下模拟连发 |
| `stop` | 失焦、转屏等立即停止移动与长按 |
| `ui` | `open:true/false`，菜单打开取消长按，UI点击不再攻击场景 |
| `open`、`close` | 按设施 `id` 打开，或关闭；超距/视线阻挡自动关闭 |
| `dismantle_container` | 打开同一空设施、选斧头，`pressed:true` 开始，`false` 取消；连续1.5秒回收同种方块 |

`dismantle_chest` 是只针对空箱子的兼容别名。全部设施统一窗口拆除，篝火燃料和火种须空，存钱罐余额须0；普通 `attack` 不能绕开。受击、换格、关窗、倒地、超距或重新放入内容物取消进度。`interaction.target/progress` 用于显示长按，不替换正在按住的按钮。

食品、医疗、饮料、回城、救援与投掷均复用 `attack` 边沿和目录时长，不为每个物品增加命令。救援目标通过瞄准及 `target_id` 识别其他在线倒地玩家，持续校验距离/视线。状态饮料不受食品饥饿门槛限制，倒地允许恢复、救援与回城但不能攻击。

## 户外座位与怪物类型

`{"type":"sit","id":"structure-id"}`切换公园椅子/固定机枪占座；移动输入自动起身。坐上固定机枪后仍用`attack`的`pressed`边沿和`aim_x/aim_y`方向长按连射，不需要物品栏中有枪。占座冲突为`seat_occupied`，附近有怪物为`seat_unsafe`，无效设施为`invalid_seat`；服务器串行确认，不能双人同时占座。

`you.seated`/`players[].seated`为设施类型或`null`，`you.seat_id`为设施ID；远端`seat_direction`为八方向编号。户外设施建筑带`occupant`和`ammo`，机枪弹药通过现有建筑字段差分更新，不重传全地图。`monsters[].species`区分六种怪物，`max_hp`与`move_speed`供血条和本地平滑移动使用；`big`/`fast`兼容字段仍保留。目录返回`monster_types`、`outdoor_features`以及`terrain.chest_landmine_chance`。

新增持久结构字段`ammo`/`owner`均有缺省值；未保存弹药的固定机枪按200读取，其他建筑为`null`。旧怪物未保存`species`时按原`big`/`fast`标记解析，不改写原血量与位置。座位状态不持久化，重连按最近可落脚格安置。BGM只在客户端读取本地静态清单，不新增同步消息。

本册按接口职责组织，不按物品加入批次组织。玩法数值以 `/api/info` 为准；物品和机器的用户说明分别见[食品](../items/foods.md)、[武器](../items/weapons.md)、[工具](../items/tools.md)、[设施](../building/machines.md)。

## 制作、放置、点火与丢弃

```json
{"type":"craft","recipe":"recycle_fences","seq":10}
{"type":"place","x":3,"y":-2,"seq":11}
{"type":"light","id":"篝火结构ID","seq":12}
{"type":"drop","slot":4,"seq":13}
```

制作按 `recipes` 一份结算，共同读取背包/物品栏，扣料后须能装下全部产物。放置使用选中建筑，整数目标须在3格内、已生成、空位且不重叠、不破坏出生通路；不检查放置视线。全部容器/机器互相八邻域不相邻，不只限某几种机器。

点火须已打开对应篝火，有燃料和可用火种。丢弃默认选中格，按 `input.aim` 方向最远2格、首个障碍前回退，保留物品ID和剩余次数；方向无效/完全受阻不丢。**`axe` 不允许丢弃**，包括 `drop` 和任何以 `ground` 为目标的 `transfer`，返回 `item_not_droppable`，不更改来源；允许存入箱子。

## 原子物品转移

```json
{"type":"transfer","from":{"kind":"backpack","slot":0},"to":{"kind":"inventory","slot":3},"item_id":"物品ID","seq":20}
```

端点包括 `inventory`、`backpack`、`chest`、`fuel`、`igniter`、`ground`、`wallet`；容器端点带设施 `id`，地面来源带掉落物 `id`，地面目标按当前瞄准计算落点。随身格从0开始，箱子按实际slots长度校验，不截断自然箱额外格。目的格必须空，火种/燃料还需符合种类与容量。`item_id` 防止源格变化后移动错物品，冲突返回 `stale_item`。金币进入随身区域时转换为钱包入账。

客户端可依请求序号先预览转移，确认后以快照接管，操作拒绝时撤销，不创建权威物品或改随机数。确认表示内存原子结算成功；后台把背包、物品栏、容器、地面与金额的同一份快照在SQLite事务中提交。恢复后只能全部生效或全部回退，不能留下半份目标；崩溃可能回到最近完整提交。写盘失败保留待保存批次重试，而非撤销已确认命令，详见[保存策略](server.md#保存与故障处理)。

## 交易与公共存款

```json
{"type":"trade","id":"机器结构ID","offer":"buy_cola","seq":21}
{"type":"bank","id":"存钱罐结构ID","operation":"deposit","amount":5,"seq":22}
```

交易必须已打开正确机器，项目读取 `machine_offers[kind][offer]`，不能跨种类使用专属项目。输入全部扣除后空间必须容纳全部产物；金币直接从 `money` 扣，产物优先背包再物品栏。空间不足或结算失败整次回退，不往地上发部分产物；持久化遵循同一快照的原子提交。

`bank.operation` 为 `deposit/withdraw`，amount是1至 `currency.max_coins` 的JSON整数，拒绝布尔/浮点/负数；返回操作、数量、余额及玩家money。共享 `container.balance` 只向实际打开者发送，不放附近建筑列表。服务器串行检查最新余额；不足返回 `insufficient_money/insufficient_bank_balance`，越上限 `balance_limit`，非空拆除 `bank_not_empty`。

## 状态快照与差分

完整状态包含自己的 `you`、附近建筑/玩家/怪物/投射物/掉落物、环境、交互进度和实际打开的容器；不泄露离线坐标及其他玩家完整背包。饥饿不截断到10。怪物字段表达 `resting/rising`、冰冻和灼烧期限，显示不能改变受伤或掉落判定。个人 `excitement_remaining` 仅在线递减。

约10Hz差分格式为 `{"type":"delta","base":0,"revision":1,"state":{},"objects":{},"entities":{}}`。`state` 是变化顶层字段；`objects` 为you/environment/movement/interaction/container的 `fields/unset` 补丁。实体集合 structures/players/monsters/projectiles/ground/events 各有add完整实体、update的id/fields/unset、remove的ID列表。未变数组与建筑不重复编码，区块列表仅附近变化时发送。

每份必须整次应用到base指定基线，之后再发布给画面，不能显露半份物品变化。差分不连续或实体缺失时关闭并重新握手取完整基线，不重放产出命令。服务器锁内取附近状态，锁外编码差分；客户端保留未变静态网格与角色历史。

`movement_epoch` 防止旧位置上报抵消击退、站起和传送；`teleport_epoch` 只标记真正传送。普通更新不能重置角色历史或被误判为瞬移；`players[].move_speed` 支持装备变速，缺失时使用基础速度。算法与时间预算见[实时性手册](../development/performance.md)。

## 投射物状态

普通子弹标记 `owner`、`hostile`、`origin_x/y`、`spawned_at`；原点等于射手坐标。服务端`hit_targets`记录已伤害的玩家/怪物，shot_hits/shot_impacts去重一次射击的玩家伤害与反馈；紧凑连接不传这些账本。`range_player/range_x/range_y/range_radius` 表示跟随玩家的视野半对角线销毁圆，越界飞行段先截断再判伤害；普通JSON状态的remaining为到圆边界的剩余距离，紧凑连接由客户端推导显示值。

树挡双方普通弹，全部容器与机器仅挡hostile弹，墙可穿透；以 `projectiles.blockers/monster_blockers` 为准。`weapon_kind` 关联武器冰冻/灼烧参数；旧字段缺省不改变保存的飞行位置和速度。投掷物通过起点、目标和引爆时间显示抛物线，伤害只在服务器爆炸时结算。

`kind:"homing_missile"` 的 `target_id` 在发射时锁定最近存活怪物；origin/spawned_at/detonates_at及初始velocity确定短直线接曲线，target_x/y更新目标位置。它不进入普通直线碰撞和视野射程通道，只伤唯一目标；目标死亡就移除，不重新索敌。命中explosion事件radius仅控制小型特效，不做范围伤害。

## 瞬时事件与即时反馈

`event_sequence` 是进程内递增序号；events为附近最近1.5秒动作、最多256条，不是持久日志。浏览器按事件ID去重，首次加入和重连不补播旧动作；只在内存事务成功后发布反馈，不等待后台磁盘提交。状态公共数据统一约10Hz捕获，命令序号与对应数据一起冻结，不能用更新的序号确认旧库存。

| 事件 | 用途 |
| --- | --- |
| `shot`、`melee` | 枪口、弹迹、扇形刃光和挥动音效 |
| `hit`、`hurt`、`death` | 命中、受伤与怪物倒下/死亡音效 |
| `chop`、`break`、`place`、`eat`、`unpack` | 采集过程/完成、放置、食用和拆包反馈 |
| `heal` | 医疗光圈，actor为受治疗玩家，source可指施救者 |
| `teleport_out`、`teleport_in` | 回城与管理员传送两端的法阵 |
| `throw`、`explosion` | 投出动作、投掷物爆炸或追踪弹的小型命中特效 |
| `ricochet` | 怪物子弹撞击固定机枪后的弹开音效；坐标为接触点，target为机枪ID |

`attack_id` 可附1～64个可打印字符，成功近战返回 `swing:true` 且melee事件回传同标记；未挥动返回false。客户端先播放本机八方向PNG与音效，匹配服务器事件只确认、不重复播；拒绝、断线取消未确认预览。伤害、掉落与他人表现仍由服务器决定。

## 名单订阅与管理员

名单约1Hz独立发送 `roster`，含服务器Unix真实时间和每个账号id/online/hunger/temperature/money/last_login_at，不进入10Hz世界状态。在线优先；离线按最后成功登录倒序，未知记录为null。客户端用server_time加单调时钟计算“刚刚/整分钟/整小时/整天”，不依赖本机日期，详见[玩家列表](../guide/controls.md#玩家列表)。

`you.is_admin` 仅在当前启动指定的管理员ID登录时为true，目录与接口不接受客户端自报管理员身份。管理员使用 `admin` 请求，命令字符串语法与英文错误见[专用手册](admin.md)；治疗和传送复用同类事件及移动修正。访问限制仍在服务端执行，隐藏按钮不是权限校验。

## 嵌入与存档边界

Python中使用 `cold_world_game.create_app(...)`；关闭时调用 `app.extensions["cold_world_game"].close()` 等待最终保存、释放线程及存档锁，不要每次HTTP请求后关闭世界。`start_engine=False` 可用于确定性调试，通过runtime.world.tick(seconds)手动推进；此模式保持同步提交。调用runtime.start()后启用与生产相同的模拟、共享发布及后台保存。显式等待后台落盘可在世界锁外调用runtime.persistence.flush()，不要在持有世界锁时等待保存线程。

个人离线仅冻结该人，全员离线或停机冻结整个世界，不补算离线时间。存储结构、旧存档缺省、备份和安全部署属于[服务器手册](server.md)，地图独立随机流与未探索区域更新属于[世界手册](../world/world.md#地图生成与存档)。
