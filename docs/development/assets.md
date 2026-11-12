# PNG美术资源与替换

[返回项目首页](../../README.md) · [手册目录](../README.md) · [本组目录](README.md)

## 可直接替换的贴图

全部 298 张贴图位于 `cold_world_game/static/assets/`，包含 169 张静态贴图、16 张四向角色动画图集、26 张基础动作特效图集、80 张方向近战挥动图集、6 张怪物死亡图集和 1 张大怪起立图集，是已经导出的真实 PNG 文件，不依赖外部图床或在线图像服务。当前美术使用手工编排的像素图样和统一色板生成，无第三方素材依赖。

静态图片为 96 × 96 像素，四向动画图集为 480 × 384 像素，常规动作特效与死亡图集为 576 × 96 像素，睡眠飘字图集为 2304 × 96 像素，每帧仍为 96 × 96。原始图样按每帧 32 × 32 像素编排，再最近邻放大 3 倍。除雪地外使用透明 RGBA 背景；画面通过 Canvas 2D 绘制，关闭平滑插值。世界中的大小和落脚位置由渲染器决定，而不是图片像素尺寸。

| 类别 | PNG文件与定位 |
| --- | --- |
| 地表与基础建筑 | `snow_0/1/2.png`、`tree.png`、`wood.png`、`wall.png`、`floor.png`、`fence.png` |
| 容器与机器 | 所有设施均为 `<建筑ID>.png`，包括箱子、篝火、存钱罐与全部机器；篝火另有 `campfire_lit.png`，完整ID与图标见[设施图鉴](../building/machines.md) |
| 食品与饮料 | 全部为 `<物品ID>.png`，见[食品图鉴](../items/foods.md) |
| 武器 | 全部为 `<物品ID>.png`，见[武器图鉴](../items/weapons.md)；爆炸与刃光另用动作图集 |
| 工具与装备 | 全部为 `<物品ID>.png`，见[工具图鉴](../items/tools.md)；医疗和传送复用共享光效 |
| 户外方块 | `landmine.png`、`park_bench.png`、`mounted_gun.png`；机枪另有 `_e/se/s/sw/w/nw/n/ne.png` 八方向贴图 |
| 金币 | `coin.png`，用于地面、钱包和交易，不占随身格 |
| 玩家 | `player.png`、`player_back.png`、`player_other.png`、`player_other_back.png`、`player_downed.png` 及两套 `_motion.png`；坐姿另有 `player_seated.png`、`player_other_seated.png` 和各自四向图集 |
| 怪物 | `monster_small/big/fast/crawler/armored/stalker.png`，对应 `_motion`、`_frozen`、`_frozen_motion`、`_death`，以及大怪/快速怪 `_sleep` 和大怪 `_rise`；见[怪物图鉴](../world/combat.md#怪物图鉴) |
| 界面图标 | `roster.png`、`roster_online.png`、`roster_offline.png`、`snowflake.png` 等 |
| 攻击与受击 | `fx_axe_sweep`、`fx_chainsaw_sweep`、`fx_ice_sweep`、`fx_flame_sweep`及各近战八方向图集，`fx_claw`、`fx_impact`、`fx_muzzle` |
| 采集、医疗与传送 | `fx_slash`、`fx_debris`、`fx_heal`、`fx_teleport`、进食与拆包共享图集 |
| 持续状态与爆炸 | `fx_sleep_zzz` 为休眠怪物共享飘字；`fx_burning` 为灼烧怪物共享火苗；`fx_explosion`、冰霜/火焰/脉冲范围动画用于对应攻击 |

表中合并写法仅便于查找，实际每张PNG均独立保存，文件名及尺寸以 `manifest.json` 为准。

## 四向立绘与跑动差分

十六套图集分别对应自己（橙色外套）、其他玩家（蓝色外套）、六种怪物及各自冰冻姿态，另有两种玩家坐姿；每套含四向五列，共320个帧位。坐姿各方向保持静止，不循环跑动。每张图集是 **5 列 × 4 行**，从左上角开始，无间距或边框：

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

`effects` 中的图集均为从左到右排列，单行、无边距，使用 `frame_width`、`frame_height`、`frames`、`duration` 配置；常规动作与死亡动画为六帧，睡眠飘字为24帧。挥斧、爪痕、红色受击、木屑和枪口闪光分别使用独立 PNG；六种怪物死亡图集展示逐步倾倒、落下、透明消散，时长 0.65 秒。替换时保留透明背景和一致的落脚基准。

`fx_axe_sweep` 持续 0.3 秒，提供八张已烘焙方向 PNG：`fx_axe_sweep_e.png`、`fx_axe_sweep_se.png`、`fx_axe_sweep_s.png`、`fx_axe_sweep_sw.png`、`fx_axe_sweep_w.png`、`fx_axe_sweep_nw.png`、`fx_axe_sweep_n.png`、`fx_axe_sweep_ne.png`。每张 1152×192，含六个 192×192 帧，斧头与半圆刃光已合成；运行时只选择方向和帧并贴图，不实时旋转刃光或计算斧头轨迹。`directions` 记录方向资源名，`direction_frame_width/height` 记录帧尺寸，`radius_ratio:0.46875` 让图像宽高 `range / radius_ratio` 对应实际 3 格攻击半径。实际命中使用原始瞄准向量，不量化为八方向。保留基础 `fx_axe_sweep.png` 作为旧资源兼容后备。

图中完整半圆底色和外弧表示范围，亮刃从一侧扫向另一侧；一次群攻只绘制一份，不按命中数复制。本机先在下一渲染帧播放，服务器确认后不会再播一遍；其他玩家的挥斧由已确认事件驱动。`monster_big_rise` 由快照世界时间驱动，替代正常角色绘制而非叠加粒子；休眠和起立期间不播放跑动差分。

`effects.js` 按动作事件逐帧贴图，攻击朝向只在事件创建时计算一次；短暂抖动受击目标和正在拆除的建筑。死亡特效使用事件里的位置、大小与击退位移独立绘制，因此服务器立即移除怪物后仍能播完动画，不保留碰撞或攻击能力。玩家受伤时另有 Canvas 屏幕边缘闪红。初次登录、重连、后台恢复不补播旧特效，同一事件在多份快照中出现也不重复播放。

## 物品图标与共享特效

所有食品、武器、道具、材料和设施各有独立96×96 PNG，形状、色板和符号用于区分物品。近战分别有六帧扇形与八方向图集；冰霜、火焰、脉冲、医疗、拆包、进食和睡眠飘字等使用共享图集。当前资源清单包含298张PNG，运行时只按时间选帧贴图，不为每个怪物实时生成粒子。

`tools/generate_assets.py` 统一调用绘图脚本并更新清单；`tools/expansion_assets.py` 生成物品与特效图样及对应双语数据，`tools/machine_assets.py` 生成机器图样及双语数据。脚本的实现分工不决定手册分类：所有条目均按玩法职责进入食品、武器、工具和设施图鉴。

## 修改源图样

手册直接用相对路径引用游戏独立PNG，不复制另一套插画。替换图片后，相应图鉴同步显示。食品、工具、武器、设施图鉴由 `tools/generate_manuals.py` 读取当前定义生成，条目字段一致；材料与怪物图鉴在各自手册维护。生成与一致性检查见[开发维护](development.md#手册维护)。

`arsenal_equipment` 绘制枪械机、手榴弹、金币榴弹炮和烈焰法杖；`flame_tint` 离线产生暖色刃光，`directional_weapon_sweeps` 同样导出八方向六帧 1152 × 192 图集。`arsenal_effects` 生成共享火苗（0.5 秒循环）和爆炸（0.65 秒、显示宽 6 格对应半径 3）。火苗只在怪物现有位置上叠加一次贴图，不新增怪物立绘；无需旋转的 PNG 直接 `drawImage`，不执行 Canvas 保存/旋转矩阵或实时粒子计算。投出手榴弹按固定起落点和时间做线性插值叠加抛物线高度，不发送逐帧坐标。

`sleeping_monster_frame` 和 `monster_resting` 生成积雪覆盖的休眠立绘与拍雪起立图集，快速怪休眠图继续由小怪图样调成紫色；`combat_effects` 中的 `fx_axe_sweep` 和 `fx_ice_sweep` 生成相同范围、轨迹的半圆刃光，`directional_weapon_sweeps` 离线合成斧头/寒冰法杖并分别导出八方向六帧 PNG。`ice_staff` 绘制冰晶法杖，`ice_tint`、`frozen_monster_image` 与 `frozen_monsters` 离线生成偏蓝色、带冰晶裂纹的三类怪物静态和四向差分；运行时只选择已有 PNG，休眠或起立时不使用冰冻图。各PNG的布局以资源清单为准。

`monster_sleep_effect` 生成独立的[睡眠飘字图集](../../cold_world_game/static/assets/fx_sleep_zzz.png)：24帧、每帧96×96、2.4秒循环，三个大小递增的“z”斜向排列，预先绘制上浮、轻摆和透明渐变。所有休眠怪物复用同一张PNG，资源在进入游戏前加载；客户端按本地渲染时间选帧，并用坐标错开循环。每只屏幕内休眠怪物仅增加一次贴图，不实时排字、不创建粒子、不增加同步字段；起立、醒来或死亡后不再绘制。

急救包由 `first_aid_kit()` 生成；医疗图集在 `combat_effects()` 中以 `fx_heal` 独立导出，清单 `effects.fx_heal` 指定六帧、每帧 96 × 96、总时长 0.9 秒。`heal` 事件在成功保存后触发，使用角色当前画面位置绘制；替换 PNG 不改变治疗判定。重连、重复快照、切后台和保存失败都不会误播。

回城法杖由 `return_staff()` 生成；`combat_effects()` 中的 `fx_teleport` 生成传送法阵图集，清单 `effects.fx_teleport` 指定六帧与 1 秒时长。施法中的循环预览及成功后的离开/到达动画共享此 PNG，事件动画固定在各自世界坐标，不跟随传送后的玩家。修改法杖或传送视觉只需替换这两个 PNG，不需要改变游戏规则。

户外方块、坐姿及雪地爬行者、冰甲怪、雪狐怪的独立像素图样由`tools/outdoor_assets.py`生成，包含正常/冰冻四向图集和独立死亡图集，不在实时渲染中给原怪物染色。机枪瞄准仅选择八张预绘PNG。

源脚本为 `tools/generate_assets.py`，色板位于 `PALETTE`，每类素材由对应绘图函数生成。角色差分由 `traveler_frame`、`monster_frame` 绘制，`WALK_POSES` 定义站立与四个跑动姿态，`actor_animations` 组装图集并写入动画配置。它只在重新导出美术时需要 Pillow，游戏运行不需要 Pillow：

```sh
uv run --with pillow python tools/generate_assets.py
```

Windows 与 Linux 命令相同，脚本根据自己的路径定位项目，不依赖当前工作目录。脚本会覆盖 `static/assets/` 下的同名 PNG 和清单；如果手工替换过贴图，请先备份，再执行导出。
