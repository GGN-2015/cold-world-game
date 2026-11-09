# PNG 美术资源与前端结构

## 可直接替换的贴图

全部 42 张贴图位于 `cold_world_game/static/assets/`，是已经导出的真实 PNG 文件，不依赖外部图床或在线图像服务。当前美术使用手工编排的像素图样和统一色板生成，无第三方素材依赖。

每张图片为 96 × 96 像素，原始图样按 32 × 32 像素编排，再最近邻放大 3 倍。除雪地外使用透明 RGBA 背景；画面通过 Canvas 2D 绘制，关闭平滑插值。世界中的大小和落脚位置由渲染器决定，而不是图片像素尺寸。

| 类别 | PNG 文件 |
| --- | --- |
| 雪地 | `snow_0.png`、`snow_1.png`、`snow_2.png` |
| 场景与建筑 | `tree.png`、`wall.png`、`floor.png`、`fence.png`、`chest.png` |
| 篝火 | `campfire.png`（未点燃）、`campfire_lit.png`（燃烧） |
| 自己与其他玩家 | `player.png`、`player_back.png`、`player_other.png`、`player_other_back.png` |
| 倒地玩家 | `player_downed.png` |
| 怪物 | `monster_small.png`、`monster_big.png` |
| 材料与工具 | `wood.png`、`axe.png`、`lighter.png`、`matches.png` |
| 枪械 | `handgun.png`、`shotgun.png`、`rifle.png` |
| 液体火种 | `gasoline.png`、`diesel.png`、`kerosene.png` |
| 食物 | `instant_noodles.png`、`dumplings.png`、`wontons.png`、`pork_trotters.png`、`beef.png`、`lamb.png`、`sardines.png`、`tuna.png`、`beef_balls.png`、`hotpot_vegetables.png`、`oreos.png`、`compressed_biscuits.png` |
| 装饰与界面 | `snowflake.png`、`spark.png`、`footprint.png`（预留脚印图样） |

木墙和柱子共用 `wall.png`；`wood.png` 对应配方中的“木材”，不是木地板 `floor.png`。

替换时保留文件名即可，无需改 Python 或 JavaScript。建议保持 96 × 96、透明背景和当前图像的底部落脚位置；更高分辨率图片也会缩放到原来的世界尺寸。替换后强制刷新浏览器，避免使用缓存。不要把不透明背景色画进角色、树木或建筑贴图。

`manifest.json` 是渲染器的预加载清单，记录资源名、文件名与尺寸。仅替换现有文件不需要修改清单；增加新资源时需登记清单，并按需要修改渲染或物品目录代码。物品栏直接按物品 kind 寻找同名 PNG，因此不建议仅在清单中更改现有文件名。

## 修改源图样

源脚本为 `tools/generate_assets.py`，色板位于 `PALETTE`，每类素材由对应绘图函数生成。它只在重新导出美术时需要 Pillow，游戏运行不需要 Pillow：

```sh
uv run --with pillow python tools/generate_assets.py
```

Windows 与 Linux 命令相同，脚本根据自己的路径定位项目，不依赖当前工作目录。脚本会覆盖 `static/assets/` 下的同名 PNG 和清单；如果手工替换过贴图，请先备份，再执行导出。

## 前端代码入口

- `templates/index.html`：登录页、游戏 HUD、操作帮助的页面结构。
- `static/css/game.css`：登录页、面板、物品栏与响应式布局。
- `static/js/game.js`：初始化、按键与鼠标、连接事件和动画循环。
- `static/js/network.js`：WebSocket 握手、命令确认、超时与重连。
- `static/js/renderer.js`：雪地场景、PNG 绘制、角色插值、光照与放置预览。
- `static/js/ui.js`：背包、拖放、箱子、篝火、制作与提示。
- `static/js/catalog.js`：中文物品名、贴图路径与中文错误提示。
- `static/js/audio.js`：动作音效、静音、距离衰减和事件去重，资源说明见 `docs/audio.md`。

前端不使用打包器和 CDN，修改文件后刷新即可。所有物品操作等服务器确认并等待新快照后再解锁界面，不在客户端先加减物品；拖放附来源物品 ID，防止格子已经变化时转移了错误物品。
