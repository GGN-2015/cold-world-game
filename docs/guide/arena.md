# 武器试验场 / Weapon arena

## 启动

```sh
uv run cold-world-game arena --host 127.0.0.1 --port 5001
uv run cold-world-game arena --host 0.0.0.0 --port 5001 --password your-password
uv run cold-world-game arena --history-dir ./arena-history
uv run cold-world-game arena --help
```

浏览器打开 `http://127.0.0.1:5001/`。这是与 `game` 分开的服务器：不打开、不迁移、不写入正式存档，不需要 `benchmark` 依赖或外部任务服务。Windows/Linux 使用同一命令；桌面与手机浏览器使用同一页面。

`--max-monsters` 设置页面允许的怪物上限，默认 256，可配置范围 1–1000；`--max-sessions` 限制同时连接的页面，默认 4，可配置范围 1–32。每个页面的模拟运行在独立子进程。公开到共享网络时请设置 `--password`。

历史默认保存在 `~/.cold-world-arena/history`，Windows 通常为 `C:\Users\用户名\.cold-world-arena\history`，与正式存档默认目录 `~/.cold-world-game` 独立。`--history-dir` 可指定其他目录，同一个历史目录同时只能由一个 arena 服务使用。

## 使用

1. 点击物品栏中的格子，在搜索框输入中文或英文名称、物品 ID 或效果描述。点击结果放入该格；点格子右上角的 × 清空。选中物品的完整介绍显示在搜索区下方。
2. 物品按正式配置生成完整弹药或耐久，最多 10 格，没有可使用的背包。重复物品分别占格。
3. 设置存活怪物上限 N、随机种子和环境温度；种子支持有符号 64 位整数，包括 0。N 可以为 0。环境温度支持 -100～100°C，默认 -15°C，整场固定。默认勾选“自动消耗饥饿值”，取消后关闭自然饥饿消耗，仍然不允许进食。
4. 如需开局机枪，勾选后输入初始弹药，范围 0–1000000。
5. 点击侧栏最上方的“开始/重新模拟”，在战斗画面旁点击“暂停模拟”或“继续模拟”。暂停冻结整个模拟，不只是画面。运行中、暂停中或结束后都可以重新模拟，旧场次会结束，新场次按当前配置从零开始。
6. AI 体温低于 5°C 时倒地并停止，页面保留坚持时间。倒地后不能继续，可以修改配置开始新一场。关闭页面或断线会结束本场模拟，保存已经记录的帧。
7. 战斗区的“音效”和“音乐”开关每次打开页面默认开启，可随时切换，互不影响。首次点击或按键解锁浏览器音频，失焦、后台或暂停时停止播放。

“坚持时间”按模拟 tick 计算，不包含暂停、网络延迟或服务器处理等待。负载较高时画面可能较慢，但不会跳过模拟 tick。配置随时可编辑，修改只在点击“开始/重新模拟”后生效，不改变正在进行的场次；继续模拟也不会应用未提交的修改。

“模拟时间上限（秒）”默认留空（N/A），表示无上限。填写不小于 0.05 的有限秒数后，到达上限会自动停止并保存历史，标记“达到时间上限”，不能继续该场模拟，但可以回放或重新开始。暂停与观看历史不计入上限；模拟按 0.05 秒步长计算，非整步长的上限在达到它的第一个 tick 结束。提前倒地仍以倒地结束。

## 战斗规则

- 初始体温 36°C、饥饿 10，从春季 21:00 开始；使用配置的固定环境温度，保留正式体温变化、保暖装备与饥饿效果。勾选自动消耗时按正式饥饿消耗及装备倍率计算；取消时不自然扣除饥饿值。
- 关闭自然饥饿消耗不取消正式受击造成的饥饿损失，也不会让 AI 自动吃东西。
- 雪地没有随机建筑和树木，除可选的固定机枪外不生成其他设施。
- 当存活怪物数小于 N，每个 tick 调用正式刷怪机制，最多生成 1 只怪物；仅随机角度，半径固定为刷怪环内缘 20 格，不抽样外环或环带面积，保留随机类型、碰撞与生成位置校验。
- 玩家 AI 与所有怪物均使用自身居中的 32×18 格逻辑视野。目标碰撞箱（以正式 `BODY_RADIUS` 构造的包围盒）与视野交叠面积达到 30% 才可见，边缘和四角采用同一面积判定。AI 不选择屏外目标，也不预判屏外弹丸。
- 怪物始终清醒，出生时沿固定的向内方向前进，进入视野后直接追击；离开视野后只向最后所见位置移动，不读取屏外玩家的最新位置。保留正式 8 秒目标记忆，不运行 A* 寻路；碰撞、速度、攻击、远程弹丸、冰冻、燃烧、击退仍使用正式规则。
- 击杀后继续补怪，不存在“清场胜利”。AI 倒地、没有可用武器或达到配置的模拟时间上限时结束。
- 可用武器按当前 AI 的选武器规则判定：物品栏内支持使用且弹药、耐久未耗尽的武器，以及仍有弹药的固定机枪。食物、被动装备和此 AI 不会使用的道具不算武器。开局没有可用武器时在 0 秒结束；最后一件武器耗尽时在该 tick 结束，不继续结算后续在途弹丸。历史标记为“武器耗尽”，可回放或重新开始，不能继续模拟。
- 禁止拾取与额外补给，不生成可利用的掉落。AI 不进食、不治疗、不建造、不交易、不复活。
- 食物等仍可放入物品栏，但搜索结果会标注“此 AI 不主动使用”。被动装备按正式规则生效，需持用的移动装备只在没有可用武器时使用。金币武器没有额外金钱供应，不主动使用。
- 战斗画面与逻辑视口均固定为 32×18 格并等比缩放；手机大小、窗口尺寸、网络快慢不会改变感知范围和弹丸射程。

## 冒进型 AI

只有 `bold` 一种策略：优先使用有弹药且可安全入座的固定机枪；弹药耗尽后离座使用物品栏。受击被迫离座时遵守正式入座安全规则，不能强行坐回被怪物包围的机枪。

固定机枪阻挡怪物子弹并播放金属弹开音效，坐在机枪上的玩家免疫怪物子弹。最后一发射出后自动下座到右侧一格，空机枪不能再入座；原物品栏武器保持不变。右侧只允许铺地板，旧障碍在入座时自动拆除，容器物品保留为掉落。正式 game 使用同一套规则。

优先视野内最近目标，近战范围内优先近战，其他情况按格位顺序选用可用远程武器。远程通常保持 3.2～6 格交战距离，过远会主动贴近，近战仍主动进入攻击范围。

周围 5.5 格内出现夹击、近身拥挤或原后撤方向被堵时，从 16 个方向评估短距离突围路线，考虑可见敌人的速度、伤害、预计碰撞和来袭弹道，并轻微保持原方向减少左右摇摆。突围不打断仍在射程内的攻击，不追求无限拉远；脱围后结束短暂避险，恢复接近和交火。所有判断只读取可见敌人，自动追踪武器和怪物受击后的锁定也遵守相同视野约束。按正式操作区分半自动点击、自动连射、近战挥砍和投掷蓄力，不直接施加伤害。

结果由配置、种子、正式规则版本和 AI 版本共同决定。同版本、同配置、同种子可复现；仅同种子但装备或数值不同，不保证同一结果。

## 回看与历史管理

- 进度条在模拟暂停或结束后可拖动，查看已经记录的帧；拖动不改变模拟状态、种子、消耗或统计。继续模拟会回到最新进度，“返回当前模拟”只切换观看位置。
- 页面最下方管理历史记录。先暂停当前模拟，再点“观察”打开历史；进度条下提供“播放回放 / 暂停回放”和 0.5x、1.0x、1.25x、1.5x、2.0x 倍速选项，暂停时可拖动进度条。回放不会重新运行 AI，因此保留当时的战斗结果。
- 记录逐帧保留角色朝向，拖动时恢复对应帧的攻击姿态及子弹方向，不使用实时网络预测。旧版试验场历史在首次打开时自动补齐朝向，不影响正式游戏存档。
- 倒地、武器耗尽、达到时间上限、重新模拟、页面关闭或断线都会结束并保存该场次，分别标记为“倒地结束”“武器耗尽”“达到时间上限”或“已停止”。服务异常退出的记录在下次启动时恢复为“意外中断”，保留已提交的帧。
- 每场独立 SQLite 文件，记录配置、AI 版本、当时的目录数值与约 10Hz 的压缩状态帧，包含开始、暂停和最终帧。按需读取最多 100 帧，浏览器只缓存一小段，不一次加载整场。
- “删除”经确认后永久删除所选历史，正在记录的场次不能删除。记录不会自动过期，请定期清理以释放磁盘空间；正式游戏存档不会被历史删除操作访问。
- “删除所有历史记录”二次确认后清除已结束的场次，保留正在模拟的记录、目录锁和非试验场文件。删除正在观看的记录会退出该回放；已结束场次的最后画面可以保留，但不能再拖动读取已删除的历史。
- 设置 `--password` 后，历史读取和删除也需要相同口令。共享口令的用户可以管理同一历史目录中的记录。

## 开发边界

- `cold_world_game/arena/simulation.py`：配置校验、内存存储、试验场世界与固定步长模拟。
- `cold_world_game/arena/ai.py`：策略注册表 `AI_TYPES`；新增 AI 通过独立策略类注册，保留 `step(world, player_id)`、`has_usable_weapon(world, player_id)`、`decision` 和 `version` 接口。可用武器判定应与该策略的选武器规则共用实现。
- `cold_world_game/arena/perception.py`：统一视野判定。新增玩家策略通过 `world.visible_monsters(player)` 和 `world.visible_projectiles(player)` 获取可见目标；怪物通过 `monster_perceives` 使用同一规则。
- `cold_world_game/arena/server.py`：独立 Flask 服务、WebSocket、受限子进程和清理。
- `cold_world_game/arena/history.py`：独立历史目录锁、压缩帧存储、异常恢复与删除。
- `static/js/arena-replay.js`：暂停拖动、历史分段读取、播放和管理；不会回滚服务器的模拟。
- `static/js/arena.js`、`arena-search.js`：配置编辑、双语相关性搜索和实时显示；复用正式 `WorldRenderer`、物品图鉴、翻译和 PNG 资源清单。
- `models.identifier_scope` 只在模拟内部启用确定性 ID，正式游戏仍使用 UUID。`World.input_expired` 保留正式输入超时行为，试验场以 tick 为准，不使用墙钟时间决定 AI 行为。

正式世界新增的掉落物 `unseen_since` 字段在旧存档中默认 `null`。为新生成机枪预留右侧出口，地图版本递增到 `TERRAIN_VERSION = 22`，旧区块保留自己的版本，不重新生成。功能和兼容性验证不等于压力测试；压力测试仍由用户手动执行。

## English quick guide

The bold AI uses short, directional breakouts when flanked or when its retreat is blocked. It evaluates 16 headings using only visible enemies and incoming shots, keeps attacking in range, and returns to combat afterward. Ranged engagements normally stay within 3.2–6 tiles; melee still closes in rather than fleeing indefinitely. AI policy version 4 includes this behavior.

"Delete all history" asks for confirmation and removes completed arena recordings only. Active recordings, unrelated files and game saves remain untouched. Deleting the replay being watched exits playback; deleted history can no longer be scrubbed.

Weapon depletion also ends and saves a run. Usable weapons follow the selected AI's weapon-selection rules: supported inventory weapons with remaining ammunition/durability, or a loaded mounted gun. Food, passive items and unsupported tools do not count. An empty starting loadout without a loaded mounted gun ends at zero seconds. Consuming the final usable weapon ends at that tick, without continuing in-flight projectiles. The saved record is labeled "Weapons depleted" and cannot resume.

The optional simulation time limit is entered in seconds and defaults to blank (N/A, unlimited). A finite duration of at least 0.05 seconds ends and saves the run when reached, excluding pauses. Simulation uses 0.05-second steps and stops at the first tick reaching the limit; earlier AI death takes precedence. A finished run cannot resume, but can be replayed or restarted. Older configurations without this field remain unlimited.

Saved replays have dedicated play/pause controls and 0.5x, 1.0x, 1.25x, 1.5x and 2.0x playback speeds below the timeline. Seeking restores recorded actor facing, attack poses and projectile headings without live network prediction. Older arena recordings are upgraded on first access; game saves are unaffected.

Run `uv run cold-world-game arena --port 5001` and open `http://127.0.0.1:5001/`. Add `--host 0.0.0.0 --password your-password` for password-protected LAN access. No game save is opened and no benchmark dependencies are needed.

Select one of ten inventory slots, search either language by name or description, and select an item. Full selected-item details appear below the search area. Configure the living-monster cap, signed 64-bit seed, optional mounted-gun ammunition and fixed ambient temperature (-100 to 100°C, default -15°C). Natural hunger drain is enabled by default; uncheck it to disable natural consumption without allowing eating. Damage still reduces hunger under normal combat rules. The top sidebar button starts or restarts a run, including while running or paused. Edits apply only on start/restart, not on resume. Restart saves the old run and resets time and statistics. Pausing freezes simulation time. A downed AI cannot resume; start a new run instead. Disconnecting ends and saves the run.

Sound and music start enabled on each page visit and have independent switches in the battle header. Browser audio unlocks after interaction and is suspended while paused or in the background. Mounted guns absorb hostile bullets with a metallic ricochet sound and protect seated players from hostile bullets. Empty guns cannot be occupied; the last round ejects the player one tile to the right without consuming inventory weapons. Only flooring may be placed on that exit tile. Old obstructions are automatically removed on seating, preserving container items as ground drops. These mounted-gun rules also apply to normal game servers.

Pause to scrub previously recorded frames. Resuming returns to the live edge without rewinding the simulation. The bottom history manager opens saved runs for playback and seeking, and deletes selected records after confirmation. Completed, restarted and disconnected runs are saved automatically; interrupted recordings are recovered on server restart. History defaults to `~/.cold-world-arena/history`, separate from `~/.cold-world-game`; override it with `--history-dir`. Each run stores compressed state frames and its original catalog in a separate SQLite file. Frames are fetched in small batches. Recordings remain until deleted, and an active recording cannot be deleted. A configured arena password also protects history access and deletion.

The bold AI prioritizes the mounted gun, then available inventory weapons. It targets the nearest visible enemy, uses melee at close range, retreats around 3.2 tiles and dodges visible incoming bullets. It never eats, heals, builds, trades or picks up drops. Unsupported items are labeled in search results.

At most one monster spawns per tick while below the cap, at a random angle exactly 20 tiles from the player on the inner circumference; current species probabilities and collision checks are retained. All AI observers, including monsters, use a centered 32×18 tile viewport and require at least 30% of a target's collision bounding-box area inside it. Monsters initially move in their fixed inward spawn direction, then pursue visible targets without pathfinding. After losing sight they follow only the last seen position, with the engine's eight-second memory. Attacks, collision and status effects use the shared game engine. Defeated monsters are replaced until death, weapon depletion or the time limit ends the run. Survival time excludes pauses and processing delays.

Identical configuration, seed, rules and AI version reproduce the outcome. The battle canvas scales the same fixed 32×18 viewport on desktop and mobile; browser size does not change perception or projectile range. Each connected page has an isolated worker process; `--max-sessions` defaults to 4 and `--max-monsters` to 256.
