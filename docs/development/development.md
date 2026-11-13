# 开发与内容维护

[返回项目首页](../../README.md) · [手册目录](../README.md) · [本组目录](README.md)

## 开发环境

运行 `uv sync --frozen` 安装锁定依赖，`uv run cold-world-game game` 启动。`uv run python -m cold_world_game game` 使用同一入口。Windows与Linux命令相同；浏览器ES modules直接加载，不需要前端打包器或CDN。新增持久字段提供缺省值，不重置旧地图；地图生成变化遵守[生成与存档约束](../world/world.md#地图生成与存档)。

## 测试入口

所有性能测试通过 `uv run cold-world-game test <名称> ...` 运行，追加 `--help` 查看该项参数。根命令与 `test` 不带具体名称时只列帮助，避免误开游戏或误跑长测试。三个测试都使用临时世界，不读取游戏的正式存档。

| 命令 | 用途 | 依赖与输出 |
| --- | --- | --- |
| `uv run cold-world-game test terrain` | 同图地形协议处理、流量和SQLite体积对照 | 基础依赖；终端JSON，可设置 `--players`、`--radius`、`--steps` |
| `uv run cold-world-game test sync` | 同一批权威战斗帧的JSON与紧凑协议对照 | 基础依赖；终端JSON，`--capture` 可保存同帧数据；可设置 `--players`、`--radius`、`--frames` |
| `uv run --frozen --group benchmark cold-world-game test combat` | 真实多人同屏战斗、延迟、桌面/手机画面与容量阶梯 | 需 `benchmark` 依赖组及浏览器；默认在当前目录的 `benchmark-results/combat-时间戳` 输出报告，支持 `--output` |

战斗测试的安装、完整命令和指标见[压测手册](combat-benchmark.md)。压力测试由用户手动运行，代理只提供命令、解读报告；功能、兼容性和单元验证不受此限制。测试实现与浏览器观察脚本随Python包一起分发，内部子服务器也通过 `python -m cold_world_game test combat` 启动，不依赖仓库的绝对位置。`tools/benchmark_*.py` 仅为脚本调用提供转发，不维护另一套参数或测试逻辑。

## 规则与资源源文件

| 内容 | 源文件 | 维护边界 |
| --- | --- | --- |
| 通用数值、配方、物品分类 | `cold_world_game/constants.py` | 当前运行规则 |
| 物品机制数据 | `cold_world_game/expansion.py` | 名称、概率、机制、效果及用法；文件名不构成手册分组 |
| 房屋加工/交易机器数据 | `cold_world_game/room_machines.py` | 独立概率、描述与配方 |
| 怪物与户外设施数据 | `cold_world_game/wildlife.py` | 六种属性、威胁分数、座位独立概率与有限弹药 |
| 确定性地图与稀疏覆盖 | `cold_world_game/procedural.py`、`cold_world_game/terrain_stream.py` | 固定生成算法、版本配置、格子初始内容、区块订阅，见[地图实现](terrain.md) |
| 浏览器地图缓存 | `cold_world_game/static/js/terrain-worker.js`、`terrain-cache.js` | 后台生成、校验、IndexedDB、订阅合并与故障回退 |
| 统一命令入口 | `cold_world_game/cli.py` | `game` 与 `test combat/terrain/sync` 的参数、帮助与分发 |
| 一致性后台保存 | `cold_world_game/persistence.py` | 合并批次、锁外提交、重试/超时暂停及最终保存；同步调试不启用 |
| 共享状态发布 | `cold_world_game/publication.py`、`cold_world_game/server.py` | 公共实体捕获、连接视野裁剪、命令序号栅栏与地图修订补齐 |
| 同图性能回放 | `cold_world_game/benchmarks/terrain.py` | 临时世界、两种协议的处理耗时/字节与SQLite体积；不替代实际浏览器延迟测试 |
| 战斗传输与同帧回放 | `cold_world_game/wire.py`、`cold_world_game/static/js/wire.js`、`cold_world_game/benchmarks/sync.py` | 紧凑二进制、子弹轨迹、格子差分及同一批权威帧的字节/编码耗时对照 |
| 多人同屏容量压测 | `cold_world_game/benchmarks/combat/` | 隔离世界、真实协议/浏览器、延迟代理、阶梯加压与报告，见[压测手册](combat-benchmark.md) |
| 基础界面双语 | `cold_world_game/static/js/i18n.js` | 每键中文/English，同步修改两种语言 |
| PNG与清单 | `tools/generate_assets.py` 及其绘图模块 | 独立资源及离线预烘焙动画，见[美术](assets.md) |
| WAV与清单 | `tools/generate_audio.py` | 见[音效](audio.md) |
| 钢琴BGM与来源 | `tools/generate_music.py`、`tools/music/` | 公版MIDI、来源哈希、自行合成、CC0演奏，见[配乐](music.md) |
| 分类图鉴 | `tools/generate_manuals.py` | 食品、武器、工具和全部设施统一条目结构 |

## 手册维护

手册只描述当前玩法，按用户任务与领域归类。不要把一批加入的内容包装成独立“扩展图鉴”，不要按引入顺序追加章节，也不写“某版起”的说明。

`docs/README.md` 是总目录，主题页放在对应子目录，每个子目录用自己的 `README.md` 导航：

| 子目录 | 职责 |
| --- | --- |
| `guide/` | 安装、输入操作、背包和转移 |
| `world/` | 世界生成、季节、生存、怪物与战斗 |
| `items/` | 食品、武器、工具与装备图鉴 |
| `building/` | 采集制作、建筑、设施与经济 |
| `server/` | 部署、存档、管理员与通信协议 |
| `development/` | 代码维护、性能、美术、音效与配乐 |

新增页面先选择已有领域，保持相对链接与同类条目结构；不要在 `docs/` 根目录堆放主题页。跨目录图片和链接须以当前页面为起点，生成器会把物品图鉴写入 `items/`，把设施图鉴写入 `building/`，不会重新生成扁平目录。

- 世界册只写坐标、地形、自然生成与季节；物品/设施概率与作用在对应图鉴维护。
- 食品、武器、工具与装备分别成册；箱子、篝火、存钱罐及全部机器统一在设施册。
- 图鉴条目统一使用名称与标识、获取方式、效果与数值、操作方式、消耗与限制，附实际PNG；机器再列相同结构的兑换表。
- 同一规则有唯一主说明，其他页面用相对链接，不复制参数表或保留迁移补丁。

```sh
uv run python tools/generate_manuals.py
uv run python tools/generate_manuals.py --check
uv run --with pillow python tools/generate_assets.py
uv run --no-sync --with numpy --with mido tools/generate_music.py
uv build
```

生成器从游戏定义读取数值、概率、配方与名称，不改变运行规则、种子或已生成区块；覆盖物品图鉴前修改生成源，不手工改生成结果。美术生成也调用同一图鉴生成器，不能重新产出按批次分组的文档。`--check` 只比较、不写文件；所有手册和生成脚本包含在源码包中。

验证相对链接和锚点、目录可达性、全部物品及怪物PNG、条目覆盖、重复生成一致性。逻辑变动还需验证旧存档、旧区域不变、新区域当前内容、满格拒绝、内存操作回滚，以及SQLite提交失败整次回滚并保留后台批次、重试/暂停/恢复和Ctrl+C最终保存；UI验证桌面与手机中英、长按和高延迟，见[实时性回归](performance.md#回归场景)。

## 前端代码入口

- `templates/index.html`：登录页、游戏 HUD、操作帮助的页面结构。
- `static/css/game.css`：登录页、面板、物品栏与响应式布局。
- `static/css/roster.css`：可折叠玩家列表、在线/离线卡片与手机布局，不改变世界场景尺寸。
- `static/js/roster.js`：独立低频名单更新、键控卡片复用、服务器真实时间与整数登录间隔、中英状态文案。
- `static/js/game.js`：初始化、按键与鼠标、连接事件和动画循环。
- `static/js/music.js`：登录界面预载压缩音频、可见威胁低频评分、双声部原生交叉淡入淡出；游戏中不补载音乐。
- `static/js/network.js`：WebSocket 握手、命令确认、超时与重连。
- `static/js/sync.js`：按版本原子应用字段/实体差分，保留未变建筑数组与碰撞缓存，缺少基线时重连。
- `static/js/combat.js`：本机即时挥斧与刀风预览、冷却、确认去重及失败取消，不预测伤害或掉落。
- `static/js/renderer.js`：雪地背景缓存、PNG 绘制、插值位置呈现、光照与放置预览。缓存保留世界格子纹理，移动越出边界或窗口缩放时重建，不改变 PNG 替换方式。
- `static/js/missiles.js`：按服务器锁定与时间参数绘制短直线/曲线导弹，使用平滑目标位置与八方向PNG，不索敌或预测伤害。
- `static/js/motion.js`：远端角色位置历史插值、自适应显示缓冲、有界补帧、实际显示速度与独立即时子弹通道，支持断流停止和重连/后台/位置跳变重置；不修改服务器状态或预测玩法结果。
- `static/js/storage.js`：按连接命令序号重放物品转移预览，识别已确认快照、冲突和失败回滚；不修改权威数组或持久存档，不生成物品 ID。
- `static/js/animation.js`：玩家与怪物的四向朝向、按实际行进距离推进的跑动帧、站立/倒地/暂停处理及逐角色动画状态清理。
- `static/js/effects.js`：攻击、拆除、受击、医疗和死亡的六帧 PNG 特效、动作姿态、屏幕受伤提示和事件去重。
- `static/js/ui.js`：独立 30 格背包、10 格物品栏、左侧说明、中央背包及右侧合成/容器面板、拖放、箱子、篝火与提示；即时转移预览，复用物品格和容器布局以保留滚动、焦点和触控事件。操作界面相对于整个浏览器窗口布局，不受雪原画面宽高比限制，小屏可滚动查看全部格子与配方。
- `static/js/catalog.js`：按当前语言提供物品名、季节、物品详情与错误提示，以及贴图路径。
- `static/js/i18n.js`：中英双语文案、登录页及游戏内语言切换、本机偏好保存与页面属性翻译。每个文案键对应 `[中文, English]`，新增界面文案应在这里同时补齐两种语言；`data-i18n-html` 只用于字典内可信的静态富文本，不得插入玩家输入或服务端文本。
- `static/js/audio.js`：动作音效、静音、距离衰减和事件去重，资源说明见 [音效资源](audio.md)。

前端不使用打包器和 CDN，修改文件后刷新即可。物品转移先即时预览，再按服务器确认序号与快照接管；失败或断线撤销预览，不改动真实物品与原子存档。拖放附来源物品 ID，防止格子已经变化时转移了错误物品。制作、兑换等产出操作仍等待服务器确认，不在客户端生成物品或预测随机结果。

语言切换只刷新界面文案，不重载页面、不发送游戏指令、不切换玩家身份。玩家 ID 和服务端协议标识保持原样；每个窗口可独立使用一种语言，最近一次选择会保存在当前浏览器，供下次打开页面使用。禁用本地存储不影响本次切换或游玩。
