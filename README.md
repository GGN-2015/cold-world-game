# cold-world-game

寒境：基于Python Flask与WebSocket的多人俯视角雪地生存游戏。直接用浏览器探索、收集、制作、建造和战斗，支持Windows/Linux、桌面键鼠、手机横竖屏及中英切换。

## 快速启动

需要Python 3.11或更高版本与uv：

```sh
uv sync --frozen
uv run cold-world-game --host 0.0.0.0 --port 5000
```

本机浏览器打开 `http://127.0.0.1:5000/`；其他设备用服务器局域网IP替换127.0.0.1。终端显示游戏口令，未指定 `--password` 时每次启动随机生成。输入玩家ID和口令即可进入，无需单独启动前端。

固定口令、存档和管理员示例：

```sh
uv run cold-world-game --host 0.0.0.0 --password your-password --save-path ./saves --admin neko
```

新角色携带手枪、斧头和打火机；先采木材、制作并点燃篝火，再探索房屋。手机自动显示双摇杆与大号操作按钮，不要求解锁屏幕方向。详见[安装与开始](docs/quick-start.md)。

## 手册树

完整入口：[游戏与服务器手册](docs/README.md)。手册按玩法职责归类，同类内容统一结构，不按加入批次组织。

| 领域 | 手册 |
| --- | --- |
| 开始与操作 | [安装与开始](docs/quick-start.md) · [界面与操作](docs/controls.md) |
| 世界与生存 | [世界、地图与季节](docs/world.md) · [体温、饥饿与状态](docs/survival.md) · [怪物与战斗](docs/combat.md) |
| 随身物品 | [背包与转移](docs/inventory.md) · [食品与饮料](docs/foods.md) · [武器图鉴](docs/weapons.md) · [工具与装备](docs/tools.md) |
| 营地与经济 | [采集、制作与建造](docs/building.md) · [容器、篝火与全部机器](docs/machines.md) · [金币与共享经济](docs/economy.md) |
| 服务器 | [联机、存档与部署](docs/server.md) · [管理员命令](docs/admin.md) |
| 开发与资源 | [开发维护](docs/development.md) · [后端协议](docs/protocol.md) · [实时性与性能](docs/performance.md) · [PNG美术](docs/assets.md) · [音效](docs/audio.md) |

物品图鉴附实际PNG、获取方式、效果、操作和限制；设施统一列出全部兑换配方。已有SQLite世界可继续使用：旧区域不重刷，未探索区域使用当前生成规则，不需要删档或换种子。

## 项目结构

- `cold_world_game/`：Flask服务端、世界模拟、事务存档及内置浏览器客户端。
- `cold_world_game/static/assets/`：可独立替换的PNG、动画图集与清单。
- `cold_world_game/static/audio/`：可替换WAV与清单。
- `docs/`：按领域组织的完整手册树。
- `tools/`：美术、音效和分类图鉴生成脚本，见[开发维护](docs/development.md)。
