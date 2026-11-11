# cold-world-game

冰天雪地中的多人浏览器生存游戏，使用 Python Flask/WebSocket 服务端与原生浏览器前端。支持 Windows/Linux、电脑和手机浏览器、中英双语、SQLite 世界存档。

## 快速启动

需要 Python 3.11+ 和 uv，在项目目录执行：

```sh
uv sync --frozen
uv run cold-world-game
```

浏览器打开 `http://127.0.0.1:5000`，输入玩家名称和终端显示的服务器口令即可游玩。不提供 `--password` 时，每次启动自动生成随机口令。

局域网联机（手机与电脑连接同一网络）：

```sh
uv run cold-world-game --host 0.0.0.0 --port 5000 --password your-server-password --save-path ./saves
```

其他设备访问服务器电脑的局域网 IP，例如 `http://192.168.1.10:5000`，并放行防火墙端口。无需独立前端、Node.js 或浏览器插件。按 Ctrl+C 保存并停止服务。

## 手册树

**[完整手册目录](docs/README.md)**

- 入门：[安装与开始游戏](docs/quick-start.md) · [电脑/手机界面与操作](docs/controls.md)
- 世界：[地图、房屋、季节与年份](docs/world.md) · [体温、饥饿与急救](docs/survival.md)
- 物品：[背包与物品栏](docs/inventory.md) · [采集、配方与建造](docs/building.md)
- 联机玩法：[机器交易与金币](docs/trading.md) · [武器、怪物与战斗](docs/combat.md)
- 维护：[服务器、参数与存档](docs/server.md) · [HTTP/WebSocket 协议](docs/protocol.md)
- 自定义：[PNG 贴图与动画](docs/assets.md) · [WAV 音效](docs/audio.md)

## 游玩提示

- WASD 移动，数字键/滚轮选择物品，B 打开独立 30 格背包与制作；手机使用专用摇杆和操作按钮，横竖屏均可玩。
- 选中斧头单击近处怪物攻击，长按砍树拆除；箱子、售货机、火柴机须在面板内长按拆除按钮。左键放置，Q 朝鼠标方向丢弃。
- 注意体温与饥饿，点燃篝火取暖。可乐、奥利奥、压缩饼干不用火也能吃；急救包长按使用，无需篝火，恢复到 36°C、饥饿至少 10，并播放光圈和红色医疗加号。
- 自然房屋的每个箱子独立有 2% 概率生成一个急救包。旧世界已生成区域不重刷，未探索区域使用新版生成规则。
- 回城法杖独立以 2% 概率出现在自然箱子中，初始 20 次；长按使用 1.5 秒返回离原点最近的空地，同距优先远离怪物，带独立 PNG 法阵与传送动画。
- 物品栏与背包独立保存，物品转移采用即时预览和服务端原子存档；全员离线后世界暂停，个人离线时不消耗状态。

## 项目结构

- `cold_world_game/`：Flask 服务端、规则、SQLite 存档与内置网页。
- `cold_world_game/static/assets/`：独立 PNG、角色/特效图集与清单，便于替换。
- `cold_world_game/static/audio/`：本地 WAV 音效。
- `tools/`：贴图与音效生成脚本。
- `docs/`：完整玩法、运行维护及开发手册；更新兼容约束见 [AGENTS.md](AGENTS.md)。
