# 后端协议 v1

内置浏览器客户端由 `GET /` 提供，PNG 与 JavaScript/CSS 位于 `/static/`，无需独立前端服务器。原服务信息 JSON 位于 `GET /api/server`；`/api/info` 与 `/health` 保持原有用途。

## 连接和身份

连接服务器的 `/ws`（随站点使用 `ws` 或 `wss`）。10 秒内发送首条消息：

```json
{"type":"join","player_id":"玩家甲","password":"服务器口令"}
```

成功响应 `{"type":"welcome","player_id":"玩家甲","protocol":1,"state":{...}}`。口令错误、同 ID 已在线或出生点暂时被怪物占用时，发送 `error` 并断开。ID 为 1～64 个字符，不能全为空白或包含控制字符。身份绑定到该连接，后续命令不能指定其他玩家。每个窗口建立独立连接；断线重连需要重新握手，不重新发放初始装备。

浏览器默认只允许同源连接。开发独立前端时用服务端 `--allowed-origin` 明确允许其 Origin。非浏览器客户端可以不发送 Origin。每条消息为最多 32768 字节的 JSON 文本；拒绝 NaN 和 Infinity。每连接最多持续 60 条命令/秒，突发容量 120 条，超限断开。

内置客户端按当前页面选择 WS/WSS，约每 65 毫秒发送输入，失焦时发送 `stop`。断线采用退避重连，重新接收完整快照，不重放物品变更命令。无 `seq` 的连接级 `error` 表示即将断开，浏览器收到后发起正常关闭握手；带 `seq` 的操作错误通常不关闭连接。

`/api/info` 的 `movement` 提供 `player_speed: 4.0` 与 `monster_speed: 1.2`，单位为世界坐标单位/秒。饥饿值下限为 0，不设 10 点上限；当前饥饿值大于 10 时禁止进食，等于 10 时仍可吃，食物完整加值。客户端不得把服务器快照中的饥饿值截断到 10。

`axe` 提供斧头攻击参数：`range: 3`、`interval: 0.5`、`damage: 4`。范围为玩家与怪物中心的欧氏距离，间隔单位为世界运行秒数，均由服务器校验。

`storage` 提供 `inventory_slots: 10`、`backpack_slots: 30`、`drop_distance: 2.0`、`pickup_radius: 0.75`。每格按 1 米计；距离均为中心之间的欧氏距离，`drop_distance` 是丢弃距离上限，受阻时实际距离缩短。

## 瞬时动作反馈

快照额外包含 `event_sequence` 和 `events`。`event_sequence` 是当前服务进程内的全局递增序号；`events` 是最近 1.5 秒、当前玩家附近的动作列表，最多保留 256 条，不是持久操作日志。例如：

```json
{"id":42,"type":"shot","actor":"玩家甲","kind":"rifle","x":1.0,"y":2.0,"time":123.4}
```

`type` 为 `shot`、`eat`、`place` 或 `hurt`，前三种事件的 `kind` 是枪械、食物或建筑种类；大怪开火的 `kind` 为 `monster`。受击事件的 `actor` 是受伤玩家 ID，`kind` 为 `player`，坐标为受伤玩家的位置；怪物近战、怪物子弹和玩家子弹共用这一事件，霰弹枪同一次射击命中同一玩家只发布一条受击事件。`time` 使用世界累计运行秒数。事件在对应事务成功后才发布；事务包含持久状态变更时先保存再发布，失败回滚不发布事件。霰弹枪的五枚弹丸合计只发布一条开枪事件。

同一事件会出现在多份快照中。客户端应按序号去重，并推进到快照的全局 `event_sequence`，避免走近时补播旧事件；首次登录或重连时以 welcome 快照的序号为基线，不播放历史事件。事件不写入存档，服务器重启会重新计数。它们只用于音效等表现，不能作为背包变化或伤害结算的依据。

## 返回消息

- `welcome`：登录完成，附完整的当前可见状态。
- `state`：每 0.1 秒推送一次当前玩家附近的完整快照；不是增量补丁，离开快照的实体应从客户端移除。
- `ack`：`{"type":"ack","seq":12,"result":{...}}`。物品变更已经原子保存；输入类 ack 仅表示已接收意图，实际效果看后续 state。
- `error`：`{"type":"error","seq":12,"code":"out_of_range","message":"..."}`，该操作没有成功。

命令可以附带非负安全整数 `seq`，只用于匹配响应，不是持久幂等键。ack 丢失时，应以重连后的快照确认结果，不要盲目重复制作或转移命令。转移可附 `item_id` 防止来源格子变化后误取另一物品。

`state` 包含 `tick`、累计世界运行秒数 `elapsed`、`environment`（季节、季节内第几天、游戏小时、室外温度）、`you`（完整物品栏、背包和玩家状态）、附近的 `players`、`structures`、`monsters`、`projectiles`、`ground`、已生成 `chunks`、当前打开的 `container` 和 `interaction` 进度。`you.inventory` 为独立的 10 格物品栏，`you.backpack` 为独立的 30 格背包，`you.selected` 仅索引物品栏，背包物品必须先转入物品栏才能使用。旧存档缺少 `backpack` 时初始化 30 个空格，不移动原物品栏物品。坐标为世界坐标；`you.tile` 与 `you.offset` 表示格子中心和格内偏移。其他玩家只包含公开状态，不暴露物品栏或背包；离线玩家不出现在快照中。木墙和柱子的 `kind` 均为 `wall`，不另发 `pillar`。

结构的 `monster_demolition` 标记表示怪物正在拆除；篝火结构的 `lit` 表示燃烧。打开的容器快照包含箱子 `slots` 或篝火的 `fuel`、`igniter`、`burn_remaining`。`burn_remaining` 为当前燃烧单位剩余的现实运行秒数。每格是 `null` 或 `{kind,id,ammo,uses}`；物品不堆叠，木材缓冲区除外。

## 连续输入和鼠标操作

至少每 250 毫秒（建议 10～20Hz）更新一次输入，输入停止超过 1 秒时服务器停止移动和长按操作。WebSocket 的 ping 不代替输入心跳。

```json
{"type":"input","move":[1,0],"aim":[10.5,-2],"target_id":null,"seq":1}
{"type":"select","slot":0,"seq":2}
{"type":"attack","pressed":true,"shift":false,"seq":3}
{"type":"attack","pressed":false,"seq":4}
```

- `move` 各分量在 [-1,1]，超过单位长度时归一化；客户端不能直接提交玩家位置。`aim` 是鼠标对应的世界坐标。
- `target_id` 可指定斧头目标怪物/结构的 ID，`null` 时按鼠标位置判定。更新目标时应一并更新 aim；射击始终按 aim 定向。
- `select.slot` 为 0～9。切换物品取消长按，不重置射击冷却。
- `attack` 必须对应鼠标按下和松开边沿；手枪/霰弹枪长按不连发，步枪由服务器持续连发，不要循环发送“按下”模拟自动枪。
- 斧头对怪物在 `pressed:true` 的首次按下边沿立即尝试攻击，中心距离不超过 3 格且视线可达时命中；不等待下一 tick，也不要求长按。成功命中间隔至少 0.5 秒，冷却内点击丢弃，不补打；连续重复 `pressed:true` 或保持长按不会再次攻击。砍树和拆除结构仍按服务器累计的连续长按时间判定，松开或换目标后重新计时。
- 对箱子/篝火普通按下优先打开窗口；Shift 按下才尝试用斧头拆除。进食时瞄准空地，并满足靠近已点燃篝火的规则。
- `{"type":"stop"}` 用于窗口失焦，立即停止移动和长按。重新聚焦必须重新按下攻击键。
- `{"type":"ui","open":true}` 打开制作/背包等界面并取消长按；`open:false` 关闭。UI 点击不应再发送世界攻击消息。
- `{"type":"open","id":"结构ID"}` 打开容器；`{"type":"close"}` 关闭。走远或被墙挡住时服务器自动关闭容器窗口。

失温玩家不能移动、射击、砍树或拆除，但可以操作物品、进食、制作和放置篝火；所有客户端预览均以服务器最终判定为准。

## 制作、建造、丢弃与点火

```json
{"type":"craft","recipe":"fence","seq":10}
{"type":"craft","recipe":"recycle_fences","seq":11}
{"type":"place","x":3,"y":-2,"seq":12}
{"type":"drop","slot":4,"seq":13}
{"type":"light","id":"篝火结构ID","seq":14}
```

配方 ID：`fence`、`wall`、`floor`、`chest`、`campfire`、`recycle_fences`。最后一个消耗 2 个木栅栏，产出 1 个 `wood`，即用户所说的木材/木板。完整材料和产出数量由 `/api/info` 的 `recipes` 返回。制作单次执行一份配方，优先从背包再从物品栏扣材料，产物也优先放背包再放物品栏；扣材料后两个区域总空位不足时整次失败。浏览器 B 键同时打开背包与合成界面，I 为兼容快捷键。

`place` 使用当前选中的物品栏建筑物品，x、y 必须是整数格子中心；放置前关闭 UI。`drop` 缺省 slot 为当前选中的物品栏格。先发送包含当时鼠标世界坐标的 `input.aim`，服务器沿玩家到 aim 的归一化方向，寻找 2 格范围内最远的可达落点：无遮挡时为 2 格；遇到树、墙、栅栏、箱子、篝火或未生成区域时，截到首个障碍边界前，保留 0.000001 格间隙，不能穿过障碍或从斜角越墙。木地板不阻挡。aim 与玩家重合或该方向没有可用落点时才拒绝并保留物品。拖到场景的 `transfer` 地面目标也采用同一规则。点火必须先打开对应篝火。

## 原子物品转移

每次转移一件物品或一单位缓冲木材。目标格必须为空，不自动交换，也不堆叠；挪动占用格需先把它移到空格。`inventory` 物品栏格 0～9，`backpack` 背包格 0～29，`chest` 箱子格 0～29，三者是独立区域。

```json
{"type":"transfer","from":{"kind":"inventory","slot":3},"to":{"kind":"chest","id":"箱子ID","slot":8},"item_id":"物品ID","seq":20}
{"type":"transfer","from":{"kind":"chest","id":"箱子ID","slot":8},"to":{"kind":"inventory","slot":3},"seq":21}
{"type":"transfer","from":{"kind":"inventory","slot":3},"to":{"kind":"fuel","id":"篝火ID"},"seq":22}
{"type":"transfer","from":{"kind":"fuel","id":"篝火ID"},"to":{"kind":"inventory","slot":3},"seq":23}
{"type":"transfer","from":{"kind":"inventory","slot":2},"to":{"kind":"igniter","id":"篝火ID"},"seq":24}
{"type":"transfer","from":{"kind":"igniter","id":"篝火ID"},"to":{"kind":"ground"},"seq":25}
{"type":"transfer","from":{"kind":"ground","id":"掉落物ID"},"to":{"kind":"inventory","slot":5},"seq":26}
{"type":"transfer","from":{"kind":"inventory","slot":3},"to":{"kind":"backpack","slot":29},"seq":27}
{"type":"transfer","from":{"kind":"backpack","slot":29},"to":{"kind":"inventory","slot":3},"seq":28}
{"type":"transfer","from":{"kind":"chest","id":"箱子ID","slot":8},"to":{"kind":"backpack","slot":0},"seq":29}
```

两个随身区域内部整理和彼此转移也使用 transfer。涉及箱子/篝火的端点必须对应当前已打开且仍在交互范围内的容器。燃料只接受 `wood`，上限 16；火种槽只接受剩余次数大于 0 的火种。缓冲木材按数量保存，不使用稳定物品 ID，因此从 `fuel` 取出时不传 `item_id`。地面来源 ID 是 `ground` 实体 ID，不是其中物品的 ID。地面取物要求距离不超过 0.75 米且路径可见，不能使用显式转移绕过距离检查。自动拾取只进入 30 格背包，背包满时不拾取，即使物品栏有空位也不例外；显式转移仍可指定物品栏空格。自己的手动丢弃物在 1 秒后才能取回。

来源扣除、目标写入、剩余弹药/火种次数和掉落物增删一起保存在同一事务中；转移失败时保持操作前状态。需要原子保存的自动拾取、制作、建造、射击耗弹、点火和拆除掉落也通过同一机制提交。

## HTTP 与生命周期

- `GET /`：后端名称、版本和接口地址，不返回游戏画面。
- `GET /health`：健康状态，故障暂停时返回 HTTP 503。
- `GET /api/info`：协议版本、tick 率、物品属性和配方。
- `{"type":"ping","seq":30}`：得到当前 elapsed 的 ack。

无在线玩家时模拟完全暂停，所有世界计时器停留；单个玩家离线只冻结该玩家。正常关闭保存世界，重新启动不补算关闭期间的时间。每次启动若未指定 `--password` 就生成新口令，客户端缓存的旧随机口令届时应提示用户更新。

嵌入 Python 应用时调用 `cold_world_game.create_app(...)`；关闭时调用 `app.extensions["cold_world_game"].close()` 释放模拟线程和存档锁。不要对每次 HTTP 请求关闭运行时。工厂的 `start_engine=False` 可用于确定性调试，此时通过 `runtime.world.tick(seconds)` 手动推进。
