# STORYBOARD — EP06《改它》

时长目标 3:30（约 210 s）· 7 帧 · 一帧一个问题
视觉规范见 `frame.md`；本集新增的组件（收据块、双通道日志图、slot 卡片）都在帧内样式里，不扩展系统。

| 帧 | 标题 | 起点 / 时长 | 旁白 | 这一帧回答什么 |
|---|---|---|---|---|
| 01 | 从哪下手 | 0.000 / 27.215 | 9 句 | 加东西是加一个包，包有三个出口 |
| 02 | 三个入口 | 27.215 / 33.748 | 7 句 | 工具与命令怎么注册 |
| 03 | 两种产物 | 60.963 / 36.008 | 8 句 | 工具进模型历史，命令只进日志 |
| 04 | 界面留的空位 | 96.971 / 40.983 | 8 句 | 客户端半边怎么挂到 slot 上 |
| 05 | 一个包 | 137.954 / 33.218 | 6 句 | manifest + patch 就是一次安装 |
| 06 | 真装一次 | 171.172 / 48.060 | 9 句 | 真装收据、落点与热更新边界 |
| 07 | 卸下来 | 219.232 / 29.729 | 8 句 | 卸载干净 + 系列收束 |

总长 **248.961 s（4:09.0）**；帧时长 = 旁白 + 0.5 s，末帧 +1.2 s（按 `voice_takes.json` 回填）。

## 现场演示（本集唯一的「真跑一次」）

在 `demo/greet/` 造一个真包：一个工具、一条命令、一个 dock 面板，
用 `plugin_manager install_bundle` 装进本机 `web` profile，再用 `remove_bundle` 卸掉。
收据存在 `demo/receipts/`：

| 文件 | 内容 | 上屏位置 |
|---|---|---|
| `install.json` | `application: "applied"`、`changed: true`、`warnings: []` | F6 |
| `slot-before.json` | dock 的 7 个占位里有 `{ id: "greet", order: 50, active: true }` | F6 |
| `tool-entry.json` | 工具清单里多出的那一项 | F6 |
| `remove.json` | `stage: "remove"`、`application: "applied"` | F7 |
| `slot-after.json` | 回到 6 个占位，没有 greet | F7 |

**一句实话**：第二集的 `greet` 用的是教学用的最小注册表（`ctx.toolbox.register`）；
这一集用真 API（`ctx.tools.register`）重写了同一个名字。名字是连续的，代码不是同一份。

## 逐帧

### F1 从哪下手

- 画面：左侧五集山脊（EP01–EP05 一句话标题，细线相连）；右侧一个「包」的剖面，三个出口分别指向 `模型` / `人` / `界面`，出口名是 `tools` / `commands` / `slots`。下方一行真实文件：`package.json`、`cordis.patch.yml`、`index.js`、`client.js`。
- 旁白落点：说到「加一个包」时包体出现；说到「三个地方」时三个出口点亮（只有一个蓝焦点，其余用 line-strong）。
- 上屏真值：三个服务键 `ctx.tools` / `ctx.commands` / `ctx.slots`。
- 出处：`packages/core/tools/src/index.ts:128`、`packages/interaction/commands/src/index.ts:285`、`packages/client/ui-slots/src/index.ts:1269`。

### F2 三个入口

- 画面：两块代码板。A 是工具：`ctx.tools.register({` + `name` + `parameters` + `execute`；B 是命令：`ctx.commands.register({` + `name: 'goal'` + `input` + `handler`。中间一条竖线，上部标 `模型`，下部标 `人`。
- 旁白落点：说到「交三样东西」时三行依次点亮；说到「一条斜杠命令」时 B 板的 `name` 与 `handler` 点亮。
- 上屏真值：`defineTool` 的参数表；`command-goal` 的真实注册对象（`name: 'goal'`、`input.hint`）。
- 上屏引用：`tools/src/index.ts:128` · `commands/src/index.ts:285`。
- 出处：`packages/core/tools/src/index.ts:128`；`packages/goal/command-goal/src/index.ts:193`；`packages/interaction/commands/src/index.ts:285`。

### F3 两种产物

- 画面：双通道日志图。上通道 `tool/call → tool/result`，标 `surface`；下通道 `command/run → command/done`，标 `log-only`。中间一条粗线 = 同一本日志。
- 下通道右端接一个「模型历史」的框，一根线被切断（×），说明命令不进模型。
- 下半：两行分层示意（`global` / `agent · child`），箭头「近的盖住远的」。
- 上屏真值：事件名、`Log-only (never model surface)` 注释原文、`CommandResult` 的两种 kind。
- 上屏引用：`commands/src/types.ts:105`。
- 出处：`packages/interaction/commands/src/types.ts:34`、`:105`、`:112`；`packages/interaction/commands/src/index.ts:263`（全局 vs agent 作用域）。

### F4 界面留的空位

- 画面：左 `client.js` 真代码（`window.__ModuleLoader__.load` → `factory` → `inject: ['slots']` → `ctx.slots.inject` → `ctx.slots.register`）。右一张 slot 卡片：`conversation.composer.dock`，字段 `id` / `order` / `label`，下面一行 `Ambient entries below the composer card`。
- 旁白落点：「只注册一个工厂」时工厂那行亮；「两句话」时 inject 与 register 两行依次亮；「一个 id，一个顺序」时卡片里 id / order 亮。
- 上屏真值：slot 名、注册字段、slot 用途原文。
- 上屏引用：`ui-slots/src/index.ts:1269`。
- 出处：`packages/client/ui-slots/src/index.ts:1269`；`packages/client/modules/README.md`（懒加载、只注册工厂）；`templates/decoration/client.js`（dsh-doc 技能的 UI 模板）。

### F5 一个包

- 画面：三段解剖。左 `package.json`（`name` / `exports` / `dsh.bundle.patch` / `dsh.client.platform`）；中 `cordis.patch.yml`（`- insert:` / `id: greet` / `name: '@local/greet'`）；右 插件树里多出的一行（`include:greet`）。
- 下方一条装配线：`包 → node_modules → patch 插一条 → loader 行 → apply()`。
- 旁白落点：说到「patch 插哪一条」时中间亮；说到「树再长出来」时右侧行出现；说到「install_bundle」时装配线末端亮。
- 上屏真值：demo 包的 manifest 字段与 patch 原文。
- 上屏引用：`demo/greet/package.json`。
- 出处：`demo/greet/package.json`、`demo/greet/cordis.patch.yml`；`packages/boot/plugin-manager/src/index.ts:1364`（reload → reconcileProfile）。

### F6 真装一次

- 画面：上方一张收据（等宽，逐行揭示）：`"bundle": "@local/greet"` / `"version": "1.0.0"` / `"changed": true` / `"application": "applied"` / `"warnings": []`。中部两个落点卡片：工具清单里的 `greet`、dock 里的 `{ id: "greet", order: 50, active: true }`。右侧边界清单：五种退回重启的理由（`no-hmr` / `package-moved` / `host-module` / `unmanaged-plugin` / `module-comparison`），下方一行 `页面跟着模块图走：装一个卸一个，不用刷新`。
- 旁白落点：「applied」时那一行变纸白；「多了一个 greet」时工具卡片亮；「五种情况」时清单逐条出现；「不用刷新」时底行亮。
- 上屏真值：安装收据、工具条目、slot 占位、五种 reason 常量。
- 上屏引用：`plugin-manager/src/types.ts:52`。
- 出处：`demo/receipts/install.json`、`slot-before.json`、`tool-entry.json`；`packages/boot/plugin-manager/src/types.ts:52`；`packages/boot/hmr/src/index.ts:937`；`packages/client/hmr/README.md`。

### F7 卸下来

- 画面：左收据 `stage: "remove"` / `changed: true` / `application: "applied"`；右 before/after 两列：dock 7 → 6、工具有 → 无、树行在 → 不在。下方收束：`五集拆 · 一集装`，再一行 `没有内核，所以可以变成任何形状`。
- 旁白落点：「条目没了」时 after 列三条依次熄灭；「可逆副作用」时左上角回引 EP02 一句；最后两句时收束区淡入。
- 上屏真值：卸载收据、占位数变化。
- 出处：`demo/receipts/remove.json`、`slot-after.json`；EP02 的「注册是可逆的」。

## 事实核对（EP06）

| 画面 | 出处 |
|---|---|
| `ctx.tools.register()` 与参数/返回值契约 | `packages/core/tools/src/index.ts:128` |
| `ctx.commands.register()` 与 `CommandResult` | `packages/interaction/commands/src/index.ts:285`；`types.ts:34` |
| 命令是 `log-only`、成对写 `command/run` / `command/done` | `packages/interaction/commands/src/types.ts:105`、`:112` |
| 命令分层：全局 / agent 作用域，近的盖住远的 | `packages/interaction/commands/src/index.ts:263` |
| 真实命令注册对象（`/goal`） | `packages/goal/command-goal/src/index.ts:193` |
| slot 注册：`{ id, order, label }` + 组件 | `packages/client/ui-slots/src/index.ts:1269`；`conversation.composer.dock` 的线上目录 |
| 客户端包：`dsh.client`、只注册工厂、懒加载 | `packages/client/modules/README.md`；`templates/decoration/package.json` |
| bundle：`dsh.bundle.patch` + `- insert: id/name` | `demo/greet/package.json`、`demo/greet/cordis.patch.yml` |
| 安装结果 `application: applied` / `restart-required` | `packages/boot/plugin-manager/src/types.ts:174` |
| 五种重启理由 | `packages/boot/plugin-manager/src/types.ts:52` |
| HMR 重新组合 profile | `packages/boot/hmr/src/index.ts:937` |
| 页面跟随模块图、启用/禁用不用刷新 | `packages/client/hmr/README.md` |
| 真装置收据与落点 | `demo/receipts/*.json`（本机 2026-11-22 实测） |

## 已知取舍

- 面板只验证到「注册成功」：`cordis_inspect` 的 slot 目录里出现 `greet` 且 `active: true`；浏览器里的像素没有截（本机 Web 入口需要 launch token）。分镜里用 slot 卡片 + 真实目录数据表示，不伪造截图。
- `greet` 包只在演示期间存在，装/卸各一次，profile 已复原（`package.json`、`cordis.patch.yml`、`node_modules/@local/` 均无残留）。

## 成片校验（2026-11-22）

- `renders/ep06-改它.mp4`：248.967 s（4:09.0）、28.9 MB、1920×1080@30、h264 + aac 48 kHz 立体声。
- `check`：**0 error / 0 warning**（8 个等距采样 + 帧边界定点 60.7 / 95.3 / 136.3 / 169.5 / 217.6 / 247，以及 33.5 / 118.5 / 150 / 157 / 160 / 205 / 214 / 218 / 220）。
- 音画：成片音轨与按 `audio_meta.json` 重建的旁白轨包络相关 **1.0000 @ lag 0**（整轨响度归一，无漂移、无缺帧）。
- 字幕：抽帧对点（218 s 屏幕上「页面跟着 Host 的模块图走」对应旁白 213.85–216.2 s），无早出/晚出。
- 抽帧与接触表：`snapshots/ep06-final/`，全部取自最终 mp4。
- 英文复核：`tools/en_check.py`（静态 + whisper 抽检）。下划线标识符（install_bundle / remove_bundle / node_modules）与斜杠事件名（tool/result）已改成口语形态并重配，复核通过；字幕用显示映射还原真名。剩余 2 句在 ASR 复听清单里（F2 的 `ctx.commands.register`、F5 的 `package.json`），属 base 模型对混合语流的误听，需人耳确认。
