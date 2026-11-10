# PNG 美术资源与前端结构

## 可直接替换的贴图

全部 59 张贴图位于 `cold_world_game/static/assets/`，包含 48 张静态贴图、4 张四向角色动画图集、5 张动作特效图集和 2 张怪物死亡图集，是已经导出的真实 PNG 文件，不依赖外部图床或在线图像服务。当前美术使用手工编排的像素图样和统一色板生成，无第三方素材依赖。

静态图片为 96 × 96 像素，四向动画图集为 480 × 384 像素，动作特效与死亡图集为 576 × 96 像素，每帧仍为 96 × 96。原始图样按每帧 32 × 32 像素编排，再最近邻放大 3 倍。除雪地外使用透明 RGBA 背景；画面通过 Canvas 2D 绘制，关闭平滑插值。世界中的大小和落脚位置由渲染器决定，而不是图片像素尺寸。

| 类别 | PNG 文件 |
| --- | --- |
| 雪地 | `snow_0.png`、`snow_1.png`、`snow_2.png` |
| 场景与建筑 | `tree.png`、`wall.png`、`floor.png`、`fence.png`、`chest.png` |
| 篝火 | `campfire.png`（未点燃）、`campfire_lit.png`（燃烧） |
| 售货机与兑换物品 | `vending_machine.png`、`coin.png`、`cola.png`，均为独立 96 × 96 透明 PNG；硬币图用于地面掉落、金钱状态栏和兑换图标，不占玩家物品格 |
| 自己与其他玩家四向动画 | `player_motion.png`、`player_other_motion.png` |
| 玩家旧版静态图（保留） | `player.png`、`player_back.png`、`player_other.png`、`player_other_back.png` |
| 倒地玩家 | `player_downed.png` |
| 玩家列表 | `roster.png` 为名单按钮图标；`roster_online.png`、`roster_offline.png` 为在线暖色与离线冷色头像，均为独立 96 × 96 透明 PNG，由 `roster_icons` 生成 |
| 怪物四向动画 | `monster_small_motion.png`、`monster_big_motion.png` |
| 怪物死亡动画 | `monster_small_death.png`、`monster_big_death.png` |
| 动作特效 | `fx_slash.png`（挥斧）、`fx_claw.png`（爪痕）、`fx_impact.png`（受击）、`fx_debris.png`（木屑）、`fx_muzzle.png`（枪口闪光） |
| 怪物旧版静态图（保留） | `monster_small.png`、`monster_big.png` |
| 材料与工具 | `wood.png`、`axe.png`、`lighter.png`、`matches.png` |
| 枪械 | `handgun.png`、`shotgun.png`、`rifle.png` |
| 液体火种 | `gasoline.png`、`diesel.png`、`kerosene.png` |
| 食物 | `instant_noodles.png`、`dumplings.png`、`wontons.png`、`pork_trotters.png`、`beef.png`、`lamb.png`、`sardines.png`、`tuna.png`、`beef_balls.png`、`hotpot_vegetables.png`、`oreos.png`、`compressed_biscuits.png` |
| 装饰与界面 | `snowflake.png`、`spark.png`、`footprint.png`（预留脚印图样） |

木墙和柱子共用 `wall.png`；`wood.png` 对应配方中的“木材”，不是木地板 `floor.png`。

替换时保留文件名即可，无需改 Python 或 JavaScript。静态贴图建议保持 96 × 96、透明背景和当前图像的底部落脚位置；更高分辨率静态图片也会缩放到原来的世界尺寸。动画图集必须遵循下方的格子布局，改变单帧尺寸时同步修改清单。替换后强制刷新浏览器，避免使用缓存。不要把不透明背景色画进角色、树木或建筑贴图。

`manifest.json` 是渲染器的预加载清单，记录资源名、文件名、尺寸、`animations` 四向动画配置和 `effects` 动作特效配置。按原尺寸替换现有文件不需要修改清单；增加新资源时需登记清单，并按需要修改渲染或物品目录代码。物品栏直接按物品 kind 寻找同名 PNG，因此不建议仅在清单中更改现有文件名。

## 四向立绘与跑动差分

四套图集分别对应自己（橙色外套）、其他玩家（蓝色外套）、小怪和大怪，每套包含 20 个差分，共 80 个姿态。每张图集是 **5 列 × 4 行**，从左上角开始，无间距或边框：

| 行（从 0 开始） | 方向 | 列 0 | 列 1～4 |
| --- | --- | --- | --- |
| 0 | 下 `down` | 向下站姿 | 向下跑动 4 帧 |
| 1 | 左 `left` | 向左站姿 | 向左跑动 4 帧 |
| 2 | 右 `right` | 向右站姿 | 向右跑动 4 帧 |
| 3 | 上 `up` | 向上站姿 | 向上跑动 4 帧 |

跑动帧实际改变摆臂、迈腿与身体姿态，不是只移动整张站姿图。各帧保留一致的落脚基准和透明留白；左右使用侧面轮廓，上下分别呈现背部与正面。倒地仍使用独立的 `player_downed.png`。

动画由服务器快照中的实际位移决定，不根据按键或鼠标朝向假定正在移动。停止后回到最后朝向的站姿，碰墙时不会原地跑，失温倒地不播放跑动。斜向运动按主轴选择朝向，接近对角线时保留当前匹配方向，避免抖动。新出现的角色、重新连接和大幅位置跳变不会被当成跑动；暂停或连续 0.3 秒渲染时间没有新快照时回到站姿。

跑动帧按画面实际行进距离推进，与渲染帧率无关，受冷或饥饿减速时动画也随之放慢。`animations` 中的 `stride` 是一个完整跑动循环对应的格数：玩家为 1.5，小怪为 1，大怪为 1.35。角色移动速度和所有服务器判定保持不变；这些参数只调整视觉步频。`frame_width` / `frame_height` 指单帧像素尺寸，`directions` 指行序，`idle_frame` 和 `walk_frames` 指列号。

## 攻击、受击与死亡图集

`effects` 中的七张图集均为从左到右排列的六帧，单行、无边距，使用 `frame_width`、`frame_height`、`frames`、`duration` 配置。挥斧、爪痕、红色受击、木屑和枪口闪光分别使用独立 PNG；大小怪死亡图集展示逐步倾倒、落下、透明消散，时长 0.65 秒。替换时保留透明背景和一致的落脚基准。

`effects.js` 按服务器动作事件逐帧播放，并旋转攻击特效、短暂抖动受击目标和正在拆除的建筑。死亡特效使用事件里的位置、大小与击退位移独立绘制，因此服务器立即移除怪物后仍能播完动画，不保留碰撞或攻击能力。玩家受伤时另有 Canvas 屏幕边缘闪红。初次登录、重连、后台恢复不补播旧特效，同一事件在多份快照中出现也不重复播放。

## 修改源图样

源脚本为 `tools/generate_assets.py`，色板位于 `PALETTE`，每类素材由对应绘图函数生成。角色差分由 `traveler_frame`、`monster_frame` 绘制，`WALK_POSES` 定义站立与四个跑动姿态，`actor_animations` 组装图集并写入动画配置。它只在重新导出美术时需要 Pillow，游戏运行不需要 Pillow：

```sh
uv run --with pillow python tools/generate_assets.py
```

Windows 与 Linux 命令相同，脚本根据自己的路径定位项目，不依赖当前工作目录。脚本会覆盖 `static/assets/` 下的同名 PNG 和清单；如果手工替换过贴图，请先备份，再执行导出。

## 前端代码入口

- `templates/index.html`：登录页、游戏 HUD、操作帮助的页面结构。
- `static/css/game.css`：登录页、面板、物品栏与响应式布局。
- `static/css/roster.css`：可折叠玩家列表、在线/离线卡片与手机布局，不改变世界场景尺寸。
- `static/js/roster.js`：独立低频名单更新、键控卡片复用、服务器真实时间与整数登录间隔、中英状态文案。
- `static/js/game.js`：初始化、按键与鼠标、连接事件和动画循环。
- `static/js/network.js`：WebSocket 握手、命令确认、超时与重连。
- `static/js/renderer.js`：雪地背景缓存、PNG 绘制、插值位置呈现、光照与放置预览。缓存保留世界格子纹理，移动越出边界或窗口缩放时重建，不改变 PNG 替换方式。
- `static/js/motion.js`：基于服务器时间的玩家、怪物及子弹快照插值，自适应显示缓冲、断流停止及重连/后台/位置跳变重置；不修改服务器状态或预测玩法结果。
- `static/js/animation.js`：玩家与怪物的四向朝向、按实际行进距离推进的跑动帧、站立/倒地/暂停处理及逐角色动画状态清理。
- `static/js/effects.js`：攻击、拆除、受击和死亡的六帧 PNG 特效、动作姿态、屏幕受伤提示和事件去重。
- `static/js/ui.js`：独立 30 格背包、10 格物品栏、背包与合成双栏面板、拖放、箱子、篝火与提示。操作界面相对于整个浏览器窗口布局，不受雪原画面宽高比限制，小屏可滚动查看全部格子与配方。
- `static/js/catalog.js`：按当前语言提供物品名、季节、物品详情与错误提示，以及贴图路径。
- `static/js/i18n.js`：中英双语文案、登录页及游戏内语言切换、本机偏好保存与页面属性翻译。每个文案键对应 `[中文, English]`，新增界面文案应在这里同时补齐两种语言；`data-i18n-html` 只用于字典内可信的静态富文本，不得插入玩家输入或服务端文本。
- `static/js/audio.js`：动作音效、静音、距离衰减和事件去重，资源说明见 `docs/audio.md`。

前端不使用打包器和 CDN，修改文件后刷新即可。所有物品操作等服务器确认并等待新快照后再解锁界面，不在客户端先加减物品；拖放附来源物品 ID，防止格子已经变化时转移了错误物品。

语言切换只刷新界面文案，不重载页面、不发送游戏指令、不切换玩家身份。玩家 ID 和服务端协议标识保持原样；每个窗口可独立使用一种语言，最近一次选择会保存在当前浏览器，供下次打开页面使用。禁用本地存储不影响本次切换或游玩。
