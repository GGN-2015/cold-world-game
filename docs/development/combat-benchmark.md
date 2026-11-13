# 多人同屏战斗压测

[项目首页](../../README.md) · [手册总目录](../README.md) · [开发目录](README.md) · [实时性与性能](performance.md)

本工具用真实 WebSocket 客户端和完整浏览器，在隔离世界里持续战斗，寻找指定机器上稳定的同屏怪物数量。它同时记录服务端处理、网络同步、浏览器绘制和本机攻击反馈，不把自然刷怪上限当成性能上限。

## 安装与启动

在项目根目录运行。Windows PowerShell、Linux shell 使用相同命令：

```sh
uv sync --frozen --group benchmark
uv run --frozen --group benchmark python -m playwright install chromium
uv run --frozen --group benchmark cold-world-game test combat
```

Linux 若缺少浏览器系统库，可由有系统安装权限的用户运行 `uv run --frozen --group benchmark python -m playwright install --with-deps chromium`。

Windows 已安装 Microsoft Edge 时，可以省略 Chromium 下载，改用：

```sh
uv run --frozen --group benchmark cold-world-game test combat --browser-channel msedge
```

工具自动启动临时服务器，分配本机空闲端口，不需要预先启动游戏。不会连接正在运行的正式服务器，也不会读取或改写正式存档。临时 SQLite 世界在结束时清理；报告和服务器日志保留。

所有测试使用 `cold-world-game test`，游戏服务器使用 `cold-world-game game`；不带子命令只显示帮助。报告默认放在运行命令时所在目录的 `benchmark-results/combat-时间戳`，不写入Python安装目录。内部子服务器通过同一个包入口启动，测试逻辑与观察脚本随安装包分发。

English quick start: use `cold-world-game game` to play and `cold-world-game test combat` to benchmark. The benchmark starts its own disposable server. `--latency-ms 300` adds 300ms round-trip propagation delay; runs shorter than 30 seconds are smoke tests, not capacity measurements.

## 默认负载

| 设置 | 默认行为 |
| --- | --- |
| 玩家 | 总共16人；3个完整浏览器加13个协议机器人，不是额外增加3人 |
| 浏览器 | 桌面1280×800、手机横屏844×390、手机竖屏390×844，手机像素比为2 |
| 世界 | 固定种子43，预生成半径20，共1,681个区块；中央战斗场和行进通道专门清空 |
| 怪物阶梯 | 0、35、70、100、140、200、280、400、560；0用于测无怪物基线 |
| 网络 | 直连及额外300ms RTT；代理在上下行各加入150ms传播延迟 |
| 时间 | 每个用例预热30秒，正式采样120秒；预热、登录及地图生成不计入正式采样 |
| 场景 | 空地战斗、障碍寻路/拆墙、多武器特效、同行跨区块 |
| 细化 | 存在通过/失败区间时，以10只为步长进一步测量 |
| 推荐值 | 全部用例通过的最大值乘0.8，再向下取整到10的倍数；小于10时保守推荐1 |

每档默认有8个用例，仅预热和正式采样就需要约20分钟；再加世界准备、登录和细化，完整扫描可能持续数小时。非零怪物档发现失败或无效后停止继续加压。零怪物基线仅有性能超标或同屏条件不满足时，继续测后续档作诊断，但保留基线失败且不输出容量推荐；基线出现断线、角色倒地、负载生成器故障或异常战斗等负载失真时停止扫描。按 `Ctrl+C` 中断会保留已完成报告并关闭测试客户端和子服务器。

### 四种场景

| 名称 | 行为与目的 |
| --- | --- |
| `open` | 玩家在小范围内移动，斧头群攻、步枪连发，持续补充真实怪物，测基础战斗负载 |
| `obstacles` | 增加有缺口的木墙/栅栏列，测真实寻路、拥堵及大怪拆除处理 |
| `effects` | 混合斧头、步枪、霰弹枪、冰/火法杖、追踪导弹与金币榴弹炮，测弹道、状态和爆炸 |
| `march` | 16人向同一移动中心靠拢并穿越区块，怪物跟随，测视野订阅、地图更新和实体插值 |

协议机器人还会周期性执行物品栏与背包往返转移、放置栅栏及长按拆除。放置冲突属于真实游戏拒绝，计入错误码而不是伪造成功。报告单独记录实际放置、拆除、受击和死亡；`coverage_warnings` 表示该用例未覆盖的事件，尤其不能用没有拆除成功的短测声称拆除性能已验证。

零怪物基线只执行移动、转移和建造/拆除，不对空地持续开枪或挥砍；无目标时立即松开攻击。若基线出现开枪或玩家互伤，标记 `baseline_has_unexpected_combat`，不能拿这种失真的负载出具容量结论。存在怪物时，普通枪械选择避开队友的射线，霰弹枪考虑扩散；游戏原有玩家互伤、击退及怪物伤害规则不修改，实际仍发生的互伤单独记录为 `friendly_fire_hits`。

每次切换场景，所有客户端先收到当前传送序号的重置快照，再开始操作，避免300ms链路上的旧坐标污染新用例。主观察玩家位于编队中央，避免站在角落压缩一侧的怪物可见范围。各端使用同一阶段时钟和紧凑编队目标；机器人按延迟、速度和位置误差逐渐修正移动，不再全速来回追逐过期坐标。建造点放在编队侧面，尽量不阻挡队友；`formation_error_max_m` 记录每个tick最偏离编队目标的角色距离，不通过服务器强制拉回角色来维持阵型。

默认3个浏览器通过真实鼠标/键盘及手机双摇杆指针输入移动和攻击。机器人使用生产协议支持的服务端移动模式，完整浏览器使用正常客户端移动预测，两者在报告中区分。`--browser-clients 16` 可让全部玩家渲染，但不再有机器人执行自动建造/转移负载，适合补充渲染战斗压力，不能替代默认混合负载的建造覆盖。

## 常用命令

### 快速确认环境

```sh
uv run --frozen --group benchmark cold-world-game test combat --browser-channel msedge --levels 16 --latency-ms 0,300 --scenarios open --radius 3 --warmup 3 --seconds 5 --refine-step 0
```

非 Windows 或未安装 Edge 时，去掉 `--browser-channel msedge`。此命令仍然有16个真实连接、桌面及横竖屏手机模拟，但只作冒烟测试，不输出可采信的容量上限。若短测已经触发性能阈值，会如实标为 `fail` 而不是隐藏问题。

### 复测战斗计算与锁等待

```sh
uv run --frozen --group benchmark cold-world-game test combat --browser-channel msedge --players 16 --levels 0,10,20,35 --latency-ms 0,300 --radius 20 --warmup 30 --seconds 120 --refine-step 0
```

保留16人、1,681区块、种子43、四种场景、直连/额外300ms RTT和桌面/手机横竖屏三个完整浏览器。先验证零怪物基线，再以10、20、35只逐档定位，避免直接从零跳到35只后无法判断较低档位。关闭自动细化便于与相同用例对照，不改变通过阈值。每档8个用例，预热与采样约20分钟，完整四档约80分钟，另加准备开销；失败或负载无效时按原规则停止后续加压。

测试由用户手动运行。请保留整个结果目录，至少提供`report.json`和`report.md`；只看终端的tick P95不能判断锁等待、命令、浏览器帧率和负载有效性。等价性回归通过不等同于容量提升，实际收益以此轮报告与相同条件的历史报告比较，不预先填写可支持的怪物数量。

子服务器启用与正式游戏一致的后台合并保存与共享状态发布，不关闭落盘来制造通过。报告记录保存策略及10Hz公共发布配置。优先比较 `sqlite_save_ms.count`、`save_capture_ms`、`background_save_ms`、`publication_capture_ms`、`publication_ms`、`simulation_lock_wait_ms` 与TPS，再检查帧间隔及状态到达间隔。保存次数是实际提交尝试，不是游戏动作数；写盘移出模拟线程后仍单独计时，不计作消失的工作量。正常120秒采样可能跨越不同数量的后台提交，长时间保存上限另做不少于210秒的用例，例如在上面的命令中改为 `--levels 10 --scenarios open --seconds 210`，保留0/300ms条件。

`command_ms` 覆盖取得世界锁与执行命令；`received_command_ms` 从应用取出该条消息开始到确认/错误回复结束，不包含消息此前在接收缓冲区的等待。`inbound_backlog` 记录取包时缓冲区剩余条数；端到端确认RTT仍由客户端测量，能看出“服务端函数很快但队列等了几秒”的情况。`unsaved_age_seconds`、`save_failures` 及每秒监控中的 `persistence` 用于核对保存没有被无限推迟。以上新增观测不放宽原有通过标准。

### 指定阶梯与重复验证

```sh
uv run --frozen --group benchmark cold-world-game test combat --levels 0,20,40,60,80,100,140 --seeds 43,97,2026 --repeats 2 --warmup 30 --seconds 120
```

种子、场景、网络及重复次数的全部组合必须完成并通过，才将该档计为通过；未完成矩阵不会产生容量结论。此命令每档有48个用例，耗时明显增加。

### 单独复测无怪物基线

```sh
uv run --frozen --group benchmark cold-world-game test combat --browser-channel msedge --levels 0 --warmup 5 --seconds 30 --refine-step 0
```

保留默认16人、1,681区块、四场景和0/300ms网络组合，每个正式采样30秒。此命令验证基线，不测怪物上限；正式容量测试仍使用默认120秒或更长采样。没有Edge时去掉相应参数。

### 仅测服务器

```sh
uv run --frozen --group benchmark cold-world-game test combat --browser-clients 0
```

不需要安装浏览器。此结果只能说明服务器承载，不证明客户端帧率、同屏可见数量或触屏体验。建议先测服务器，再用默认3浏览器复测，最后在真实设备复核。

### 长时间确认推荐档

```sh
uv run --frozen --group benchmark cold-world-game test combat --soak-seconds 1800
```

扫描得到推荐值后，对该数量再执行整套用例，每个采样30分钟，不是所有用例合计30分钟；默认8个用例额外需要约4小时。长测任一用例不通过，清空推荐值并设置 `soak_passed: false`。没有通过档时不运行此步骤。

### 自动化回归与全部参数

```sh
uv run --frozen --group benchmark cold-world-game test combat --levels 40 --refine-step 0 --fail-on-regression
uv run --frozen --group benchmark cold-world-game test combat --help
```

容量探索中发现极限是正常结果，默认进程退出码为0；加 `--fail-on-regression` 后，任一失败或无效用例退出1。启动/运行异常退出2，中断退出130。`--output` 可选择新报告目录；已有 `report.json` 的目录禁止覆盖。

## 如何判定卡顿

以下阈值是本工具的验收标准，而不是所有设备的人体感知定律。百分位采用0.1单位的向上分桶；`P95` 表示95%的采样不超过该值，`P05` 用于检查大部分时间是否维持实际负载。

| 指标 | 通过要求 |
| --- | --- |
| 模拟 tick 耗时 | P95 ≤35ms，P99 ≤50ms；目标20Hz |
| 采样期和最差10秒窗口 TPS | 均≥19 |
| 模拟线程等待世界锁 | P99 ≤10ms |
| 服务器命令处理 | P95 ≤50ms，P99 ≤100ms；与含网络传播的确认RTT分开记录 |
| 已锁定目标但无路径的规划等待 | P95 ≤500ms，结束时最长未完成等待≤1秒；正常规划冷却不计入 |
| 桌面帧间隔 | P95 ≤20ms，P99 ≤33ms |
| 手机模拟帧间隔 | P95 ≤33ms，P99 ≤50ms |
| 本地挥斧首帧 | 桌面P95 ≤33ms，手机模拟P95 ≤50ms；从输入到实际方向PNG首次绘制 |
| 浏览器状态到达间隔 | P95 ≤150ms，P99 ≤200ms；不把固定300ms传播误当成每帧间隔 |
| 主线程长任务 | 不出现超过100ms的任务 |
| 异常瞬移 | 跟踪最多48个实体，按速度和帧间隔估算上限；排除击退、传送、起立与倒地切换后不得出现超限跳变 |

`invalid` 与性能 `fail` 不同：玩家离线/倒地、浏览器错误、负载生成器跟不上、怪物密度不足等会让用例无效。服务端活跃怪物数P05、第一浏览器实际可见活跃怪物数P05均至少为目标的90%；第一浏览器还要持续看到全部16人。其他手机视口的实际人数与怪物数单独记录，不能把桌面同屏容量宣称为手机同屏容量。采样足够长且有怪物的用例必须真正命中怪物；本地攻击首帧缺失也不会误报通过。

用例总体 `status`、`server_status`、`browser_status` 分开判定：角色离开观察视野、浏览器缺帧或缺少本地攻击采样属于 `scene_invalid_reasons`，不会直接把服务器判成无效；服务器故障、玩家不足、负载生成器错误和怪物密度不足等记入 `server_invalid_reasons`。无浏览器时 `browser_status` 为 `not_measured`。锁等待、tick与命令耗时阈值保持独立，视觉无效不能掩盖真实的服务器超标。

若全部所测档位通过，`upper_bound_found` 为 `false`，只说明“至少支持最大已测档”，不是找到了极限。`baseline_status` 和 `baseline_server_status` 说明基线是否成立；`largest_server_passed` 不因单纯观察视野无效而丢失。`first_failed_level` 记录第一个有效性能失败档；只有存在较低的通过档，`first_failed_above_pass` 才有值，不能把基线失败解释为“最多支持零只怪物”。基线未通过时不输出推荐，也不宣称找到了容量上界。无效档位不作为性能上限；应先查看原因，再换负载位置、档位或设备复测。机器内存超过92%、服务器故障或持续严重掉速时会安全中止当前用例并标为无效。

## 报告和隔离边界

默认输出到 `benchmark-results/combat-时间/`，目录不纳入 Git：

- `report.md`：各档总体/服务器/浏览器状态、tick、锁等待、帧间隔、实际同屏人数/怪物数、互伤次数及逐项失败原因。
- `report.json`：全部参数、机器配置、逐客户端百分位、网络流量、错误码、跳变样本、覆盖警告、服务器组件耗时、CPU/RSS/SQLite体积与每秒监控。
- `worker-*.log`：每个临时子服务器的日志，用于排查启动或运行故障。

服务端细分包括怪物逻辑、子弹、灼烧、快照、存档准备、SQLite提交、紧凑差分编码及锁等待。报告持续落盘，异常退出仍保留已完成用例。浏览器完整性能轨迹和录像不在默认采集范围内，以免采集本身显著拖慢被测页面。

终端每个用例同时打印服务器和浏览器判定，并列出无效/失败原因；无需仅凭 `tickP95` 或手动打开JSON猜测失败原因。

夹具只作用于独立子进程：绕过自然刷怪上限，保持夜间AI活跃，补充武器次数/弹药和怪物，低体温时恢复角色，让战斗可以持续。怪物使用正常属性、夜间种类比例、透视概率、伤害、击退、寻路、掉落及SQLite事务；夹具耗时也计入tick，而不是从报告里扣除。已有区域不变、旧存档升级等功能回归不能由此压力测试代替。

默认客户端、服务器与代理运行在同一台电脑，报告明确记录该条件；结果同时受CPU、GPU、浏览器调度与本机资源竞争影响。16个同机浏览器不能代表16台独立设备。手机是触屏/视口模拟，不是实体手机的性能认证。部署验收应保留这份可复现报告，并在实际服务器和真实手机上补充游玩验证。
