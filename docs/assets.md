# PNG 美术资源与前端结构

[返回项目首页](../README.md) · [手册目录](README.md)

## 可直接替换的贴图

全部 111 张贴图位于 `cold_world_game/static/assets/`，包含 63 张静态贴图、8 张四向角色动画图集、12 张基础动作特效图集、24 张方向挥斧/挥杖图集、3 张怪物死亡图集和 1 张大怪起立图集，是已经导出的真实 PNG 文件，不依赖外部图床或在线图像服务。当前美术使用手工编排的像素图样和统一色板生成，无第三方素材依赖。

静态图片为 96 × 96 像素，四向动画图集为 480 × 384 像素，动作特效与死亡图集为 576 × 96 像素，每帧仍为 96 × 96。原始图样按每帧 32 × 32 像素编排，再最近邻放大 3 倍。除雪地外使用透明 RGBA 背景；画面通过 Canvas 2D 绘制，关闭平滑插值。世界中的大小和落脚位置由渲染器决定，而不是图片像素尺寸。

| 类别 | PNG 文件 |
| --- | --- |
| 雪地 | `snow_0.png`、`snow_1.png`、`snow_2.png` |
| 场景与建筑 | `tree.png`、`wall.png`、`floor.png`、`fence.png`、`chest.png` |
| 篝火 | `campfire.png`（未点燃）、`campfire_lit.png`（燃烧） |
| 售货机与兑换物品 | `vending_machine.png`、`coin.png`、`cola.png`，均为独立 96 × 96 透明 PNG；硬币图用于地面掉落、金钱状态栏和兑换图标，不占玩家物品格 |
| 自助火柴机 | `match_machine.png`，独立 96 × 96 透明 PNG，由 `match_machine` 绘图函数生成；黄铜色机壳与火柴盒展示窗区别于红色售货机，出售的火柴沿用 `matches.png` |
| 除颤器 | `defibrillator.png`，独立 96 × 96 透明 PNG，手持电极与心电图显示屏，由 `defibrillator` 生成；救援成功复用 `fx_heal.png` 医疗光圈与加号 |
| 自动枪械机与新武器 | `gun_machine.png` 为军绿机壳与武器展示窗；`grenade.png`、`coin_launcher.png`、`flame_staff.png` 均为独立 96 × 96 RGBA 图标，由 `arsenal_equipment` 生成 |
| 火焰与爆炸 | `fx_flame_sweep.png` 及八张 `fx_flame_sweep_e/se/s/sw/w/nw/n/ne.png` 暖色挥杖图集；`fx_burning.png` 是全部灼烧怪物共享的小火苗，`fx_explosion.png` 是手榴弹与榴弹炮共用爆炸动画，均为六帧独立 PNG |
| 自己与其他玩家四向动画 | `player_motion.png`、`player_other_motion.png` |
| 玩家旧版静态图（保留） | `player.png`、`player_back.png`、`player_other.png`、`player_other_back.png` |
| 倒地玩家 | `player_downed.png` |
| 玩家列表 | `roster.png` 为名单按钮图标；`roster_online.png`、`roster_offline.png` 为在线暖色与离线冷色头像，均为独立 96 × 96 透明 PNG，由 `roster_icons` 生成 |
| 怪物四向动画 | `monster_small_motion.png`、`monster_big_motion.png`、`monster_fast_motion.png` |
| 冰冻怪物 | `monster_small_frozen.png`、`monster_big_frozen.png`、`monster_fast_frozen.png`，分别有同名 `_motion.png` 四向五帧图集；蓝色冰晶独立导出，非运行时滤镜 |
| 寒冰法杖与挥动 | `ice_staff.png` 为独立 96 × 96 图标；`fx_ice_sweep.png` 为六帧半圆刃光，`fx_ice_sweep_e/se/s/sw/w/nw/n/ne.png` 是八张 1152 × 192 图集，轨迹和范围与斧头一致 |
| 怪物死亡动画 | `monster_small_death.png`、`monster_big_death.png`、`monster_fast_death.png` |
| 快速怪静态图 | `monster_fast.png`；与跑动、死亡图集一起，由 `fast_monster_tint` 对小怪图样做紫色色相转换，保留透明度、轮廓、帧布局与落脚点，分别导出为独立 PNG |
| 动作特效 | `fx_axe_sweep.png`（180° 扇形群攻）、`fx_slash.png`（采集挥斧）、`fx_claw.png`（爪痕）、`fx_impact.png`（受击）、`fx_debris.png`（木屑）、`fx_muzzle.png`（枪口闪光） |
| 白天休眠与拍雪起立 | `monster_big_sleep.png`、`monster_fast_sleep.png` 为独立 96 × 96 休眠 PNG；`monster_big_rise.png` 为 576 × 96 六帧拍雪起立图集，时长 1 秒 |
| 怪物旧版静态图（保留） | `monster_small.png`、`monster_big.png` |
| 材料与工具 | `wood.png`、`axe.png`、`lighter.png`、`matches.png` |
| 医疗物品与恢复动画 | `first_aid_kit.png` 为独立 96 × 96 急救包图标；`fx_heal.png` 为 576 × 96 六帧透明图集，呈现扩散暖色光圈和上浮红色医疗加号 |
| 回城法杖与传送动画 | `return_staff.png` 为独立 96 × 96 水晶法杖图标；`fx_teleport.png` 为 576 × 96 六帧透明图集，紫青色法阵、旋转符文、光柱和星光，时长 1 秒；施法中循环，离开倒放收束，到达正放绽放 |
| 枪械 | `handgun.png`、`shotgun.png`、`rifle.png` |
| 液体火种 | `gasoline.png`、`diesel.png`、`kerosene.png` |
| 食物 | `instant_noodles.png`、`dumplings.png`、`wontons.png`、`pork_trotters.png`、`beef.png`、`lamb.png`、`sardines.png`、`tuna.png`、`beef_balls.png`、`hotpot_vegetables.png`、`oreos.png`、`compressed_biscuits.png` |
| 装饰与界面 | `snowflake.png`、`spark.png`、`footprint.png`（预留脚印图样） |

木墙和柱子共用 `wall.png`；`wood.png` 对应配方中的“木材”，不是木地板 `floor.png`。

替换时保留文件名即可，无需改 Python 或 JavaScript。静态贴图建议保持 96 × 96、透明背景和当前图像的底部落脚位置；更高分辨率静态图片也会缩放到原来的世界尺寸。动画图集必须遵循下方的格子布局，改变单帧尺寸时同步修改清单。替换后强制刷新浏览器，避免使用缓存。不要把不透明背景色画进角色、树木或建筑贴图。

`manifest.json` 是渲染器的预加载清单，记录资源名、文件名、尺寸、`animations` 四向动画配置和 `effects` 动作特效配置。按原尺寸替换现有文件不需要修改清单；增加新资源时需登记清单，并按需要修改渲染或物品目录代码。物品栏直接按物品 kind 寻找同名 PNG，因此不建议仅在清单中更改现有文件名。

## 四向立绘与跑动差分

八套图集分别对应自己（橙色外套）、其他玩家（蓝色外套）、小怪、大怪、快速怪（紫色小怪），以及三种怪物各自的冰冻姿态；每套包含 20 个差分，共 160 个姿态。每张图集是 **5 列 × 4 行**，从左上角开始，无间距或边框：

| 行（从 0 开始） | 方向 | 列 0 | 列 1～4 |
| --- | --- | --- | --- |
| 0 | 下 `down` | 向下站姿 | 向下跑动 4 帧 |
| 1 | 左 `left` | 向左站姿 | 向左跑动 4 帧 |
| 2 | 右 `right` | 向右站姿 | 向右跑动 4 帧 |
| 3 | 上 `up` | 向上站姿 | 向上跑动 4 帧 |

跑动帧实际改变摆臂、迈腿与身体姿态，不是只移动整张站姿图。各帧保留一致的落脚基准和透明留白；左右使用侧面轮廓，上下分别呈现背部与正面。倒地仍使用独立的 `player_downed.png`。

动画由服务器快照中的实际位移决定，不根据按键或鼠标朝向假定正在移动。停止后回到最后朝向的站姿，碰墙时不会原地跑，失温倒地不播放跑动。斜向运动按主轴选择朝向，接近对角线时保留当前匹配方向，避免抖动。新出现的角色、重新连接和大幅位置跳变不会被当成跑动；暂停或连续 0.5 秒渲染时间没有新快照时回到站姿。

跑动帧按画面实际行进距离推进，与渲染帧率无关，受冷或饥饿减速时动画也随之放慢。`animations` 中的 `stride` 是一个完整跑动循环对应的格数：玩家为 1.5，小怪和快速怪为 1，大怪为 1.35。快速怪因自身每秒行进 4.8 格，步频高于普通小怪；动画参数只调整视觉步频，不改变移动速度和服务器判定。`frame_width` / `frame_height` 指单帧像素尺寸，`directions` 指行序，`idle_frame` 和 `walk_frames` 指列号。

## 攻击、医疗与死亡图集

同时活跃的动作特效最多 96 个。超过上限时优先丢弃部分重复命中特效，保留群攻刃光和死亡表现，避免一次击杀大量怪物反而看不到挥斧。受击姿态每帧集中计算一次后按实体 ID 查表，不对每只怪物重复扫描全部特效；活跃特效超过 32 个时省略死亡时附带的装饰木屑，保留完整倒下消散图集。

`effects` 中的十六张图集均为从左到右排列的六帧，单行、无边距，使用 `frame_width`、`frame_height`、`frames`、`duration` 配置。挥斧、爪痕、红色受击、木屑和枪口闪光分别使用独立 PNG；三种怪物死亡图集展示逐步倾倒、落下、透明消散，时长 0.65 秒。替换时保留透明背景和一致的落脚基准。

`fx_axe_sweep` 持续 0.3 秒，提供八张已烘焙方向 PNG：`fx_axe_sweep_e.png`、`fx_axe_sweep_se.png`、`fx_axe_sweep_s.png`、`fx_axe_sweep_sw.png`、`fx_axe_sweep_w.png`、`fx_axe_sweep_nw.png`、`fx_axe_sweep_n.png`、`fx_axe_sweep_ne.png`。每张 1152×192，含六个 192×192 帧，斧头与半圆刃光已合成；运行时只选择方向和帧并贴图，不实时旋转刃光或计算斧头轨迹。`directions` 记录方向资源名，`direction_frame_width/height` 记录帧尺寸，`radius_ratio:0.46875` 让图像宽高 `range / radius_ratio` 对应实际 3 格攻击半径。实际命中使用原始瞄准向量，不量化为八方向。保留基础 `fx_axe_sweep.png` 作为旧资源兼容后备。

图中完整半圆底色和外弧表示范围，亮刃从一侧扫向另一侧；一次群攻只绘制一份，不按命中数复制。本机先在下一渲染帧播放，服务器确认后不会再播一遍；其他玩家的挥斧由已确认事件驱动。`monster_big_rise` 由快照世界时间驱动，替代正常角色绘制而非叠加粒子；休眠和起立期间不播放跑动差分。

`effects.js` 按动作事件逐帧贴图，攻击朝向只在事件创建时计算一次；短暂抖动受击目标和正在拆除的建筑。死亡特效使用事件里的位置、大小与击退位移独立绘制，因此服务器立即移除怪物后仍能播完动画，不保留碰撞或攻击能力。玩家受伤时另有 Canvas 屏幕边缘闪红。初次登录、重连、后台恢复不补播旧特效，同一事件在多份快照中出现也不重复播放。

## 修改源图样

`arsenal_equipment` 绘制枪械机、手榴弹、金币榴弹炮和烈焰法杖；`flame_tint` 离线产生暖色刃光，`directional_weapon_sweeps` 同样导出八方向六帧 1152 × 192 图集。`arsenal_effects` 生成共享火苗（0.5 秒循环）和爆炸（0.65 秒、显示宽 6 格对应半径 3）。火苗只在怪物现有位置上叠加一次贴图，不新增怪物立绘；无需旋转的 PNG 直接 `drawImage`，不执行 Canvas 保存/旋转矩阵或实时粒子计算。投出手榴弹按固定起落点和时间做线性插值叠加抛物线高度，不发送逐帧坐标。

`sleeping_monster_frame` 和 `monster_resting` 生成积雪覆盖的休眠立绘与拍雪起立图集，快速怪休眠图继续由小怪图样调成紫色；`combat_effects` 中的 `fx_axe_sweep` 和 `fx_ice_sweep` 生成相同范围、轨迹的半圆刃光，`directional_weapon_sweeps` 离线合成斧头/寒冰法杖并分别导出八方向六帧 PNG。`ice_staff` 绘制冰晶法杖，`ice_tint`、`frozen_monster_image` 与 `frozen_monsters` 离线生成偏蓝色、带冰晶裂纹的三类怪物静态和四向差分；运行时只选择已有 PNG，休眠或起立时不使用冰冻图。旧 PNG 不因新增动画而改变布局。

急救包由 `first_aid_kit()` 生成；医疗图集在 `combat_effects()` 中以 `fx_heal` 独立导出，清单 `effects.fx_heal` 指定六帧、每帧 96 × 96、总时长 0.9 秒。`heal` 事件在成功保存后触发，使用角色当前画面位置绘制；替换 PNG 不改变治疗判定。重连、重复快照、切后台和保存失败都不会误播。

回城法杖由 `return_staff()` 生成；`combat_effects()` 中的 `fx_teleport` 生成传送法阵图集，清单 `effects.fx_teleport` 指定六帧与 1 秒时长。施法中的循环预览及成功后的离开/到达动画共享此 PNG，事件动画固定在各自世界坐标，不跟随传送后的玩家。修改法杖或传送视觉只需替换这两个 PNG，不需要改变游戏规则。

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
- `static/js/sync.js`：按版本原子应用字段/实体差分，保留未变建筑数组与碰撞缓存，缺少基线时重连。
- `static/js/combat.js`：本机即时挥斧与刀风预览、冷却、确认去重及失败取消，不预测伤害或掉落。
- `static/js/renderer.js`：雪地背景缓存、PNG 绘制、插值位置呈现、光照与放置预览。缓存保留世界格子纹理，移动越出边界或窗口缩放时重建，不改变 PNG 替换方式。
- `static/js/motion.js`：远端角色位置历史插值、自适应显示缓冲、有界补帧、实际显示速度与独立即时子弹通道，支持断流停止和重连/后台/位置跳变重置；不修改服务器状态或预测玩法结果。
- `static/js/storage.js`：按连接命令序号重放物品转移预览，识别已确认快照、冲突和失败回滚；不修改权威数组或持久存档，不生成物品 ID。
- `static/js/animation.js`：玩家与怪物的四向朝向、按实际行进距离推进的跑动帧、站立/倒地/暂停处理及逐角色动画状态清理。
- `static/js/effects.js`：攻击、拆除、受击、医疗和死亡的六帧 PNG 特效、动作姿态、屏幕受伤提示和事件去重。
- `static/js/ui.js`：独立 30 格背包、10 格物品栏、背包与合成双栏面板、拖放、箱子、篝火与提示；即时转移预览，复用物品格和容器布局以保留滚动、焦点和触控事件。操作界面相对于整个浏览器窗口布局，不受雪原画面宽高比限制，小屏可滚动查看全部格子与配方。
- `static/js/catalog.js`：按当前语言提供物品名、季节、物品详情与错误提示，以及贴图路径。
- `static/js/i18n.js`：中英双语文案、登录页及游戏内语言切换、本机偏好保存与页面属性翻译。每个文案键对应 `[中文, English]`，新增界面文案应在这里同时补齐两种语言；`data-i18n-html` 只用于字典内可信的静态富文本，不得插入玩家输入或服务端文本。
- `static/js/audio.js`：动作音效、静音、距离衰减和事件去重，资源说明见 [音效资源](audio.md)。

前端不使用打包器和 CDN，修改文件后刷新即可。物品转移先即时预览，再按服务器确认序号与快照接管；失败或断线撤销预览，不改动真实物品与原子存档。拖放附来源物品 ID，防止格子已经变化时转移了错误物品。制作、兑换等产出操作仍等待服务器确认，不在客户端生成物品或预测随机结果。

语言切换只刷新界面文案，不重载页面、不发送游戏指令、不切换玩家身份。玩家 ID 和服务端协议标识保持原样；每个窗口可独立使用一种语言，最近一次选择会保存在当前浏览器，供下次打开页面使用。禁用本地存储不影响本次切换或游玩。
