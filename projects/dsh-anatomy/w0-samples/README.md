# W0 帧样张 · 四张新图形（独立样张项目）

第二季的新图形先在这里试做，**不进 `compositions/frames/`**（那里是 EP06 的成片）。
这份项目可以单独 `check` / `snapshot`：四个 8 s 场景串成 32 s，只验图，不带旁白与音频。

## 文件

```
w0-samples/
  hyperframes.json          # paths.blocks=frames, components=frames/components, assets=../assets
  index.html                # 1920×1080 · 四个 scene，0/8/16/24 起，各 8 s
  frames/frame-s2-01..04.html
  out/frame-00..03-at-*.png # 四张 1920×1080 静帧（--at 7.6,15.6,23.6,31.6）
  assets -> ../assets       # 符号链接；dev-server 根就是本目录，字体只能从这里进
```

每帧沿用 `compositions/frames/frame-01.html` 的契约：`<template>` 包住样式与脚本、根 `div#id` 带
`data-composition-id`、内层 `class="clip"`、自己的作用域 id（`#s1`…`#s4`）、`cqw` 单位、
`window.__timelines["frame-s2-0X"]` 一个 paused 时间线、底部 2px 进度条。

## 四张样张

| 样张 | 落在 | 这一帧要回答 | 压测的视觉规则 |
|---|---|---|---|
| `frame-s2-01` 三角色接缝 | 弧 A · S2E01（EP07） | 一个能力为什么必须三方齐全 | **三点一面的读法**：定义方在上、两个提供方从左侧接入接缝、消费方只接那个 key 的末端；`× no import` 画出"缺的那条边"，不用虚线糊 |
| `frame-s2-02` 三域事件地图 | 弧 A · S2E02（EP08） | 三个域怎么在一张图上分开 | **不用第二彩色分域**：实线 / 虚线 / 点线区分持久事实、实时协调、能力策略；唯一的蓝给"总线"这条竖轴 |
| `frame-s2-03` 五刻度栈图 | 弧 B · S2E04（EP10） | 五个刻度是一台机器的五个位置 | **用长度表达"管多宽"**：五段带端帽的 1px 范围条做成阶梯；蓝焦点是左侧 2px 栈轴加它的五个齿 |
| `frame-s2-04` 六层所有权剖面 | 弧 C · S2E09（EP15） | 屏幕上的像素归谁管 | **一条边界当焦点**：六层剖面里只有 03/04 之间那条边界是蓝的，配一条硬判据；入口描述与四条归属判据分居两侧 |

## 事实口径

E01 的每条断言都按 `episodes/ep07/FACTS.md` 表 A 对过，**章节号不上屏**（`ch02`、`ch29`、`ch36` 是知识库索引，不是证据）：

- 定义方：`ShellExecutor` 拥有 `ctx.shell`——**没有具名注册表，一个上下文一个名额**（第二个实现装载由 cordis 抛错）。
  出处 `packages/shell/shell/src/index.ts:64`。
- 提供方：`dsh-bash-local` 本地执行器、`dsh-bash-sandbox` 沙箱执行器；后者 **`extends LocalBashExecutor`**，不是并列重写抽象类。
- 消费方：`dsh-tool-bash` 把 `shell` 当**硬依赖**（`packages/shell/tool-bash/src/index.ts:36`）——所以缺席分两态：
  **硬 `inject` 缺席 → 停 PENDING**；**可选 `ctx.get` 缺席 → `unavailable`**。上一版把两态压成一句"缺席走 unavailable"，是错的。
- 其余真名：`session/event` `agent/*` `fs/*` `tools/*`；`prepareContinuable` `start` `revision` `blockedBy` `writeScopes`
  `plan/mode` `GoalPhase` `stopReason`；`WebBootGraph`(rev/entries/batches) `dsh.client`(`platform: 'web'`)
  `exports["./client"]` `window.__DSH_BOOT__` `WEB_PROVIDER_AMBIGUOUS` `webserver/authorize`。
  没有编造的数字、字段、包名或 file:line。

## 复现

```bash
cd projects/dsh-anatomy
node ~/.agents/skills/hyperframes/scripts/plugin-cli.mjs check w0-samples
node ~/.agents/skills/hyperframes/scripts/plugin-cli.mjs snapshot w0-samples \
  --at 7.6,15.6,23.6,31.6 --no-end --output-dir w0-samples/out --timeout 60000
```

`check` 当前结果：lint / runtime / layout / motion **0 error 0 warning**，contrast **95/95 通过**。
craft 只剩一条 `film_silent`——样张项目本来就没有音轨（旁白要到成片才配），不是版式问题；
接上旁白后自动消失。不为了消警告塞一条静音音轨。

## 版式口径

- 颜色只用 `frame.md` 的 token：`#0A0B0D` / `#EDEAE3` / `#9BA2AD` / `#5B6370` / `#232833` / `#39404E` / `#4D6BFE` / `#E9E4D8`。
- **一帧一个蓝焦点**：01 是那条接缝（含 `ctx.shell`、keyhole、引到消费方的那根线）；02 是总线竖轴；
  03 是栈轴（2px）+ 五个齿；04 是 03/04 之间那条边界。
- 6cqw 边距；正文全部收在 y < 900 的字幕安全区之上（最下一行盒子底 ≈ 880）。
- 无圆角、无阴影、无渐变；层级只靠字号、字重与 1px 线。
- 动效只有 `power3.out`；同组 stagger 0.06–0.10 s，组与组按旁白节拍散到 4.5 s 之后，不出现"前 25% 倒完再冻住"。
- 文本下限 28 px（1.5cqw）：除 chrome 那行 mono 铬件外，所有正文与 mono 标签都在 1.5cqw 以上。
- 字体从 `assets -> ../assets` 取 `Inter-Variable.woff2` 与 `JetBrainsMono-Variable.woff2`；页面不出现无 `@font-face` 的字体名。
