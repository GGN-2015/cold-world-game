# 背景音乐

[返回项目首页](../../README.md) · [手册目录](../README.md) · [本组目录](README.md)

## 开关与音量

右上角的BGM按钮独立于音效开关；手机显示♫，关闭后显示♫×。选择保存在当前浏览器。第一次点击、触屏或按键后才解锁播放，不依赖浏览器自动播放权限；切到后台、离开游戏或断开连接时停止播放，返回后自然淡入。

配乐主增益为0.10，较原来的0.075略微提高，低于动作音效主增益0.45，不用音乐掩盖枪声、受击和交互提示。正式游戏和武器试验场共用此设置，音效音量保持不变。BGM是可选功能，加载失败、浏览器不支持或被关闭均不影响加入、移动、战斗和存档。

The game and arena share a music master gain of 0.10 (previously 0.075). Sound-effect gain remains unchanged at 0.45.

## 屏幕内威胁与切换

仅统计摄像机当前画面中的存活怪物，不按全地图数量或玩家距离统计。休眠倒地、起立动画中的怪物计0分；画面外计0分。

| 怪物 | 分数 |
| --- | --- |
| 小怪、雪地爬行者 | 1 |
| 活动快速怪 | 2.5 |
| 活动大怪 | 4 |
| 冰甲怪 | 3 |
| 雪狐怪 | 2 |

| 屏幕总分 | 曲目组 |
| --- | --- |
| ≤6.5 | 舒缓 |
| >6.5且≤12.5 | 中等 |
| >12.5 | 高强度 |

客户端每0.5秒检查一次。威胁升档持续2秒后切换，降档持续6秒后切换，避免怪物在屏幕边缘反复进出导致频繁换曲。旧曲和新曲交叉淡入淡出2.5秒；一曲结束后可有约2秒安静片段。白天为06:00～18:00，舒缓组选择明亮的巴赫和莫扎特，不播放《月光》；中等组白天也不选《致爱丽丝》。激战时的高强度配乐不受白天舒缓选曲限制。

## 曲目表

全部为钢琴独奏或钢琴缩编。游戏使用自行合成的演奏，不使用网上下载的商业演奏录音；较长作品取不超过3分钟的片段。

| 强度 | 作曲家与曲目 | 时段 | 公版乐谱来源 |
| --- | --- | --- | --- |
| 舒缓 | 巴赫：C大调前奏曲 BWV 846 | 昼夜 | [Mutopia 5](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=5) |
| 舒缓 | 莫扎特：F大调小步舞曲 K.2 | 昼夜 | [Mutopia 1770](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=1770) |
| 舒缓 | 德彪西：月光 | 夜间 | [Mutopia 1778](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=1778) |
| 中等 | 莫扎特：土耳其进行曲 | 昼夜 | [Mutopia 108](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=108) |
| 中等 | 巴赫：F大调二部创意曲 BWV 779 | 昼夜 | [Mutopia 61](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=61) |
| 中等 | 贝多芬：致爱丽丝 | 夜间 | [Mutopia 931](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=931) |
| 高强度 | 贝多芬：第五交响曲（命运）钢琴缩编 | 昼夜 | [Mutopia 497](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=497) |
| 高强度 | 贝多芬：热情奏鸣曲第三乐章 | 昼夜 | [Mutopia 937](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=937) |
| 高强度 | 贝多芬：悲怆奏鸣曲第一乐章快板段 | 昼夜 | [Mutopia 299](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=299) |

源项目将所选乐谱标为Public Domain。下载的MIDI、来源元数据与SHA-256保存在`tools/music/`；生成脚本验证许可与哈希。项目自行生成的MP3演奏采用CC0-1.0，完整署名及声明见[`LICENSE.txt`](../../cold_world_game/static/music/LICENSE.txt)。替换音乐时需要同时确认作品、编曲和演奏录音的权利，不能仅凭作曲家去世年代认定某个录音可以自由使用。

## 预加载与性能

九首音乐合计约10MB压缩音频。只在登录界面顺序预加载，舒缓、中等、高强度交错优先；进入游戏立即取消未完成的音乐下载，不在战斗期间下载或补载大资源。不要求等音乐下载完才能加入：提前加入时只使用已缓存的曲目，没有适合曲目则保持安静，回登录界面后继续预载。

曲目缓存为压缩Blob，不在JavaScript主线程把九首解码为完整PCM。最多两个原生音频元素交叉播放，淡入淡出交给Web Audio时间线，不逐帧计算波形、不修改服务器模拟频率，不增加游戏通信包。手机同样支持BGM开关与手势解锁。

## 资源生成与替换

客户端资源位于`cold_world_game/static/music/`，`manifest.json`记录强度、时段、时长、许可、来源及文件哈希。音乐工具依赖不进入游戏运行时：

```sh
uv run --no-sync --with numpy --with mido tools/generate_music.py
```

需要系统可调用FFmpeg。脚本根据随源码提供的公版MIDI离线合成钢琴，不依赖采样库或声卡，Windows/Linux使用相同命令。只有主动更新来源时才加`--download`；正常部署或游玩不访问外部音乐网站。修改曲目后同时更新来源、清单、许可和本册，测试前台/后台、静音、慢速预加载和交叉淡入淡出。动作音效另见[音效手册](audio.md)。
