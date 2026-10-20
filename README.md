# NekoSous

N.E.K.O 的《胡闹厨房 2》连接面板。通过 Hosted TSX 面板手动连接游戏端
`ws://127.0.0.1:48930/neko`，提供中英双语界面、游戏进程状态、握手、心跳和断线重连。

## 使用

当前支持 Windows。游戏进程通过 Python 标准库 `ctypes` 调用 Windows 进程快照接口检测，
无需安装 `psutil`，不读取游戏内存。不支持的平台会显示检测不可用，不会误报游戏未启动。
运行时仅依赖 `websockets`；其原生加速模块为可选项，无法加载时使用内置纯 Python 实现。
已验证禁用加速模块后握手、心跳、重连和模式同步测试通过。此回退机制不代表已验证其他操作系统。

1. 确保游戏端 NekoSous 已安装并启用 WebSocket 服务，监听 `127.0.0.1:48930/neko`。
2. 在 N.E.K.O 插件管理器中启动本插件，打开面板。插件启动和查看面板均不会自动连接。
3. 启动《胡闹厨房 2》，点击“连接”。客户端先检测 `Overcooked2.exe` 进程，再建立 WS 连接。
4. 收到 `welcome` 后，服务状态显示“已连接”。若游戏未启动，会弹窗提示先启动游戏后重试。
5. 意外断线后按 1、2、4、8、最多 10 秒的间隔自动重试。游戏退出时等待其重新启动。
6. 点击“断开连接”停止会话和自动重连。插件停止时也会释放连接。

面板每 2 秒更新状态，以胶囊标签区分游戏未启动、已启动，以及服务未连接、连接中、
已连接、重连中、等待游戏启动。检测权限不足会显示“检测不可用”，不会误报游戏未启动。
同一错误持续重试时不会反复弹窗；错误弹窗提供对应语言的说明，详细异常记录在插件日志。
面板语言跟随插件管理器，支持 `zh-CN` 和 `en`。

## 协议与范围

### 陪伴模式与陪玩模式

面板提供两种模式，默认选中陪伴模式。连接后，只有服务端在 `welcome.payload.capabilities`
中声明 `mode_switch`，才允许切换。旧游戏端仍可正常连接，但切换按钮会禁用并提示更新。
客户端通过 `set_mode` 请求切换，收到对应 `mode_changed` 确认后才更新选中状态。
等待确认时按钮禁用；切换失败保留原模式并显示错误。断线或手动断开时恢复陪伴模式，
重连从新会话的 `welcome.payload.mode` 获取实际模式，不会重发上次的陪玩选择。

两种模式均接收游戏事件并提供播报，目前均未启用游戏控制。

### 游戏事件与播报

游戏端声明 `game_events` 能力、且已保存的事件订阅偏好为开启时，客户端在握手后发送
`subscribe_events`，收到 `events_subscribed` 确认后显示已连接。关闭订阅仍可正常连接和切换模式。
旧游戏端未声明此能力时保留连接和模式切换，
不会发送订阅请求，也不会播报游戏状态。

所有 WebSocket 消息由同一个接收任务分发，心跳、模式确认和主动事件可以交错到达。
播报提交使用独立任务，不阻塞接收和心跳。订阅超时会重新连接；播报提交失败则保留连接，
在面板提示查看插件日志。

播报范围：

- 稳定场景：世界地图、主菜单、大厅或厨房关卡；加载场景不播报。
- 开场：本关总时长、整关菜单种类数。无限计时会说明没有固定倒计时。
- 倒计时：剩余 30 秒、10 秒时各提醒一次。
- 结算：本局分数及实际星级。没有星级的模式不补造星级，对战模式区分两队分数。

场景只使用已确认的本地化分类，未知场景不直接念资源名，也不根据内部关卡 ID 猜测关卡编号。
插件按事件 ID、本局 ID 和事件阶段去重；新场景、新局或结算会清理过时的待播报事件。
本地排队超过 2 秒的提醒、超过 5 秒的其他事件会丢弃。断线后丢弃队列，重连重新订阅，
不回放上次会话的数据。

播报通过公开 SDK 的 `push_message(parts=..., visibility=[], ai_behavior="respond")`
将事实交给当前角色自然表达，不把技术消息直接显示成用户聊天。共享 `coalesce_key`
让宿主在忙碌时合并尚未处理的旧提示。SDK 返回的 `submitted` 仅表示本地提交成功，
不代表模型已回复或语音已播放；已经交给宿主的消息及正在播放的语音无法由本插件撤回。
需要 N.E.K.O 当前角色和语音链路正常工作。

面板的“陪伴设置”可实时切换事件订阅、主动搭话和频率。事件订阅等待游戏端确认，
失败不假定切换成功；保存失败会尝试恢复原订阅。关闭事件订阅会取消服务端推送并清理
本地待播报内容，连接、心跳、模式切换继续工作。关闭主动搭话仍保留关键播报。
离线可以保存偏好，下次手动连接或重连后应用，不会自动建立连接。

设置通过 SDK 配置接口持久保存。`plugin.toml` 的 `[broadcast]` 提供初始值：

```toml
[broadcast]
events_enabled = true
chatter_enabled = true
frequency = "balanced" # quiet、balanced、lively
locale = "zh-CN" # 可选 zh-CN、en；与面板语言独立
```

只会在手动连接后订阅。插件启动、打开面板不会自动连接，亦不会补播已经过去的开场或提醒。

### 主动搭话

新版游戏端声明 `game_state` 能力后，客户端在订阅请求中带上 `include_state: true`，
接收约每 5 秒一次的轻量快照。快照只用于更新局势和选择搭话时机，不直接触发播报。
旧游戏端的关键事件播报仍可使用，主动搭话需更新游戏端。

| 档位 | 安静多久后考虑搭话 | 每局上限 |
| --- | --- | --- |
| 安静陪伴 quiet | 60～80 秒 | 1 次 |
| 适度互动 balanced（默认） | 35～50 秒 | 2 次 |
| 活跃陪伴 lively | 18～25 秒 | 5 次 |

活跃陪伴开场至少等待 20 秒，其他档位至少等待 35 秒；最后 35 秒不主动搭话。
暂停或计时受抑制时不搭话，状态超过 8 秒
未更新也会停止。搭话前查询公开 SDK 的近期对话记录，有近期对话则延后；查询失败跳过。
插件无法直接观察实时麦克风和完整语音播放状态，最终播放时机由宿主已有的语音调度处理。
已提交宿主的消息仍受上述不可撤回限制。

搭话只参考当前分数、这段时间的分数变化和剩余时间，不推测失误、漏单、火情或画面内容。
普通搭话和关键事件共用宿主的合并键，关键事件到达会延后普通搭话，结算或退出会清理
本地旧提醒。每局次数不会因为切换开关或重连而立即重置；新局建立新的计数。

### 出餐、交付失败和超时反馈

游戏端声明 `order_events` 时，客户端在订阅请求中增加 `include_orders: true`，接收
`order_delivered`、`delivery_failed` 和 `order_expired`。旧游戏端仍可使用原有关键播报。
这些事件受“游戏事件订阅”总开关控制，与“主动搭话”开关独立。

面板提供出餐鼓励、订单超时、交付失败、连单中断四个独立开关，默认全部开启。
开关筛选 N.E.K.O 端播报，游戏端继续正常采集数据。关闭分类立即清除该类待播报内容，
重新开启不补播关闭期间的事件；离线设置会保存并用于下一次手动连接。

出餐鼓励为本局每队首次成功出餐、连续成功 3 / 6 / 10 单，之后在 14 / 18 / 22……单触发。
这些节点和每次漏单都独立排队，不受普通反馈的冷却、5 秒过期及最后 35 秒限制。
倒计时提醒优先，随后继续处理待播报节点。结算、退出、断线或取消订阅清理旧内容。
连单中断仍是有效出餐，不归为交付失败。
判定同时使用服务器结果中的 `was_combo` 和处理前后的 combo、multiplier，确认之前有加成
且本次成功交付后归零。不会把本来没有加成的普通出餐误报为连单中断。
交付失败保留普通反馈的 20 秒冷却；连单中断有独立的 20 秒冷却。
交付失败在 2 秒窗口内合并，等待超过 5 秒的旧提示会丢弃。
每次订单超时单独排队播报，不受 20 秒冷却、5 秒过期和最后 35 秒限制；倒计时提醒优先处理后继续播报漏单。
漏单和出餐节点使用各自独立的消息合并标识，避免被后续消息覆盖。
结算、退出及取消订阅会清理待反馈内容，最后 35 秒停止普通订单反馈。
普通搭话按实际成功提交的事件播报让出时间，关闭分类的原始事件不推迟搭话。
最近一分钟每多一次事件播报，下一次搭话间隔增加 25%，最多翻倍；每次播报重新安排空档。
事件稀少时恢复所选等级的频率，每局搭话次数上限不变。

### 厨房提醒

游戏端声明 `kitchen_events` 时，订阅请求增加 `include_kitchen: true`，接收
`food_ready`、`food_overcooking`、`fire_started`；快照中的 `cooking` 和 `fires` 用于
取消过时提示。旧游戏端保持已有功能，面板提示更新厨房事件支持。

面板新增「着火提醒」「烹饪完成」「快糊了提醒」三个独立开关，默认开启。
与订单分类一样，关闭后清理该类待播内容，重新开启不补播旧事件，不影响游戏端采集。
这些提醒不受普通反馈的 20 秒冷却和最后 35 秒限制。

厨房提示独立放在 `kitchen.py`：火情和快糊优先于订单反馈，煮好随后处理，普通搭话最后。
火情和快糊等待约 0.3 秒合并同期对象，煮好等待约 0.8 秒；合并后用一句说明数量。
紧急提示超过 2 秒、完成提示超过 5 秒会丢弃，避免播报已经处理的情况。
端离加热区域、进入下一烹饪周期、烧糊、灭火、物体消失或关卡结束会清除对应待播提示。
取消只影响插件尚未提交的提醒，已经交给宿主的语音不能撤回。
实际提交厨房播报后也会延后普通搭话；不猜菜名、屏幕方位、玩家身份或剩余烧糊秒数。

### 搅拌提醒

游戏端声明 `mixing_events` 时，订阅增加 `include_mixing: true`，接收
`mixing_ready`（搅拌完成）、`mixing_warning`（快搅过头）、`mixing_ruined`（已经搅坏）。
面板提供对应的三个独立开关，默认开启，保存、离线设置和总订阅开关规则与其他分类相同。
旧游戏端仍可使用已有播报，面板会提示升级搅拌事件支持。

搅拌完成在约 0.8 秒内合并同期容器；警告和搅坏在约 0.3 秒内合并，不受普通反馈冷却
或最后 35 秒限制。完成提示最多保留 5 秒，警告最多 2 秒，已搅坏提示最多 5 秒。
新状态会覆盖尚未提交的旧阶段提示；`mixing` 快照用于在取出、停机、清空或进入新周期时
取消不再相关的提醒。已经搅坏即使机器自动停转仍可提醒，但清空后不再提交旧提示。
警告明确表示尚可取用，已经搅坏才提示倒掉重做，不复用“快糊了”的措辞。
实际提交这些提醒后同样延后普通搭话，本功能不操作角色或设备。

交付失败只表示未匹配到有效订单，不猜测菜做错在哪里；超时次数也不等于不同订单数量，
同一订单可以重置计时后再次超时。游戏端的连续成功次数与游戏 combo 分开处理。
不根据菜谱内部 ID 猜测菜名，也不把队伍事件归因到某位玩家。中途连接不会将之后的第一盘
误说成本局第一盘，实际是否为首单以游戏同步的累计成功交付次数为准。

- 使用协议版本 1，发送 `hello`（客户端名称 `neko_sous`、版本 `0.1.0`），严格校验
  `welcome.reply_to`、会话 ID 和服务端心跳参数。
- 按 `welcome` 声明的间隔发送应用层 `ping`，验证 `pong.reply_to`；无响应时主动断开并重连。
- 使用本地回环地址，关闭代理与压缩，单条接收消息限制为 64 KiB。
- 进程检测在线程中执行，不阻塞插件事件循环；检测到进程不代表游戏内 WS 服务已经就绪。
- 游戏状态来自游戏端主动上报，不读取游戏进程内存、不启动游戏，也不发送游戏操作指令。
- 插件为被动插件，不向 AI 自动发现连接动作；通过面板显式操作。

## 开发验证

运行时依赖在本插件的 `pyproject.toml` 中声明，通过下述命令生成 `vendor/`：

```powershell
uv run neko-plugin sync neko_sous --clean
uv run neko-plugin check neko_sous
uv run pytest plugin/plugins/neko_sous/tests -q --confcutdir=plugin/plugins/neko_sous
node frontend/plugin-manager/scripts/check-hosted-tsx.mjs plugin/plugins/neko_sous
node plugin/plugins/neko_sous/tests/test_panel.cjs
```

界面测试使用插件管理器的开发依赖及 Playwright Chromium；也可设置
`NEKO_SOUS_BROWSER_CHANNEL=chrome` 使用本机 Chrome。客户端测试使用本地模拟 WS 服务，
不要求启动游戏。实际游戏联调仍需运行游戏端 NekoSous。

官方 Hosted UI 文档：[使用 Hosted TSX 构建插件界面](https://project-neko.online/zh-CN/plugins/hosted-ui)。

## Development

The plugin source and its Git repository live at:

```text
N.E.K.O/plugin/plugins/neko_sous
```

插件源码及其 Git 仓库直接位于：

```text
N.E.K.O/plugin/plugins/neko_sous
```

プラグインのソースと Git リポジトリは次の場所にあります：

```text
N.E.K.O/plugin/plugins/neko_sous
```

When publishing to the plugin market, use this GitHub repository name:

发布到插件市场时，请使用以下 GitHub 仓库名：

プラグインマーケットへ公開する際は、次の GitHub リポジトリ名を使用してください：

```text
n.e.k.o_plugin_neko_sous
```

From this plugin repository root:

```bash
uvx ruff==0.12.4 check --ignore-noqa --config ruff.toml .
```

From the N.E.K.O repository root / 在 N.E.K.O 仓库根目录中 / N.E.K.O リポジトリのルートで：

```bash
uv run neko-plugin sync neko_sous --clean
uv run neko-plugin check neko_sous
uv run neko-plugin check -r neko_sous
```

Python runtime dependencies are declared in `pyproject.toml` and synced into
`vendor/` for packaging. The generated `vendor/` directory is not committed;
local builds and CI recreate it before release checks.

Python 运行时依赖声明在 `pyproject.toml` 中，并在打包时同步到 `vendor/`。
生成的 `vendor/` 不提交；本地构建和 CI 会在发布检查前重新生成它。

Python ランタイム依存関係は `pyproject.toml` に宣言し、パッケージ化時に
`vendor/` へ同期します。生成された `vendor/` はコミットせず、ローカルビルドと
CI が公開前チェックで再生成します。

## Market release / Market 发布 / Market 公開

Publish the version declared in `plugin.toml`. By default this pushes the Git
tag, waits for the standard GitHub Release, and notifies the plugin market.

发布 `plugin.toml` 中声明的版本。默认会推送 Git tag、等待标准 GitHub
Release，然后通知插件市场。

`plugin.toml` で宣言されたバージョンを公開します。既定では Git tag を
push し、標準 GitHub Release を待ってからプラグインマーケットへ通知します。

```bash
uv run neko-plugin publish neko_sous
```

To run only one half explicitly / 如需仅执行一部分 / 一方のみを実行する場合:

```bash
uv run neko-plugin publish github neko_sous
uv run neko-plugin publish market https://github.com/owner/repo/releases/tag/v0.1.0
```

The generated `.github/workflows/release.yml` builds and uploads
`neko_sous.neko-plugin`. The market independently verifies that Release
before publishing it.

生成的 `.github/workflows/release.yml` 会构建并上传插件包；Market 会独立验证
该 Release 后再发布。

生成された `.github/workflows/release.yml` がプラグインパッケージをビルドして
アップロードし、Market はその Release を独立検証してから公開します。

## Entry

```toml
entry = "plugin.plugins.neko_sous:NekoSousPlugin"
```
