---
format: 1920x1080
duration: 124.8s
message: "模型只会吐 token；把它变成行动的，是外面那台机器——而 dsh 的这台机器，是一棵你能改的树"
arc: concept
audience: 会写一点代码、想搞清 agent 框架到底在做什么的人
mode: autonomous
music: none
---

# STORYBOARD — 拆开 DSH · EP01

## Video direction

- **palette**：`frame.md` 的 Substrate 系统，只用一种彩色 `accent #4D6BFE`（DeepSeek 蓝），且一帧只给一个焦点；地面 `canvas #0A0B0D`，主文字 `text #EDEAE3`，结构靠 1px `line #232833`。全片不出现纯黑 `#000` 与纯白 `#FFF`。
- **type**：Inter（400/500/800/900，负字距，字形承担冲击）＋ JetBrains Mono（大写、0.18em 字距）承担文件名、行号、事件名、站名编号。中文回退系统黑体，与 Inter 同字重对齐。代码与路径一律等宽，且**必须是仓库里的真值**。
- **motion grammar**：`power3.out` 长尾；元素之间 0.06–0.10s stagger；不做回弹与循环呼吸。除第 8 帧外，每帧都在揭示——说到哪个词，才放出哪个元素。
- **rhythm / held frames**：第 4、5 帧是同一根「六站轨道」的两半，节奏一致：每站约 6 秒，站亮 → 细节条换行 → 下一个站。第 8 帧是唯一持留帧：信息全部落定后静止 2 秒。
- **layering**：每帧 ≥3 层——1px 发丝结构（背景）＋主视觉（中景）＋mono 铬件（前景）。主视觉占画布 ≥40%。
- **caption keep-out**：底部 17%（y>900px）留给字幕；所有正文收在 900px 以上。
- **negative list**：不要机器人/大脑/神经网络光斑；不要紫蓝渐变与发光卡片；不要带红黄绿圆点的假终端窗；不要圆角与阴影；不要编造文件名、数字、配置字段。

## Frame 1 — 你只说了一句话

- scene: 一条用户输入，和三行它「看起来做了」的动作；最后收束成唯一真正发生的事
- duration: 12.2s
- poster: 6.5s
- transition_in: cut
- status: animated
- src: compositions/frames/frame-01.html
- type: hook
- persuasion: Concretization
- beat: 熟悉感 → 轻微的失重
- blueprint: kinetic-type-beats (Adapt)
- focal: 右侧不断下落的 token 列
- roles: 用户那句话 = subject（Inter 800）· 三行动作 = supporting（mono，逐行压暗）· token 列 = foreground payoff（唯一蓝色）

## Frame 2 — 模型的三处不能

- scene: 三条横排陈述，编号 01/02/03，每条一句结论 + 一行具体例子
- duration: 15.15s
- poster: 8.0s
- transition_in: cut
- status: animated
- src: compositions/frames/frame-02.html
- type: concept
- persuasion: Enumeration
- beat: 逐步收紧
- blueprint: stacked-list (Adapt)
- focal: 「没有手 / 没有记忆 / 没有时间」三个大字
- roles: 三个结论 = subject · 例子行 = supporting（muted mono）· 每条上方的发丝线与编号 = background chrome

## Frame 3 — 缺的那台机器

- scene: 左边是模型，右边是你的电脑，中间一道空；空里长出一台机器，机器没有内核，裂成四个插件节点
- duration: 18.6s
- poster: 11.0s
- transition_in: cut
- status: animated
- src: compositions/frames/frame-03.html
- type: concept
- persuasion: Before/after + Concretization
- beat: 缺口 → 填上 → 再拆开
- blueprint: diagram-build (Adapt)
- focal: 中间那块从虚线长成实体的 harness，最后裂成四个节点
- roles: 模型块/电脑块 = supporting · harness 块 = subject（唯一蓝色描边）· 四个插件节点 = payoff

## Frame 4 — 前三站

- scene: 一根横贯画面的六站轨道亮起，前三站依次点亮，下方细节条给出该站的真实证据
- duration: 18.55s
- poster: 9.0s
- transition_in: cut
- status: animated
- src: compositions/frames/frame-04.html
- type: process
- persuasion: Sequence
- beat: 秩序感
- blueprint: horizontal-timeline (Adapt)
- focal: 被点亮的站与轨道上的蓝色进度
- roles: 六站轨道 = structure · 激活站 = subject · 细节条（mono 代码 + 文件路径）= evidence

## Frame 5 — 后三站

- scene: 同一根轨道，后三站点亮；第六站之后，一条弧线把日志送回第二站
- duration: 19.85s
- poster: 12.0s
- transition_in: cut
- status: animated
- src: compositions/frames/frame-05.html
- type: process
- persuasion: Sequence + Payoff
- beat: 闭合
- blueprint: horizontal-timeline (Adapt) + return-arc
- focal: 从第六站回到第二站的那条蓝弧 + 右侧落盘的日志列
- roles: 轨道 = structure · 弧线 = subject · 日志列 = evidence（paper 白）

## Frame 6 — 连循环也是插件

- scene: 粒度收紧到配置文件里的三行；agent-loop 那一行被虚线框住、抬起、留下一个洞
- duration: 12.4s
- poster: 7.0s
- transition_in: cut
- status: animated
- src: compositions/frames/frame-06.html
- type: reveal
- persuasion: Reversal
- beat: 反转
- blueprint: code-zoom (Adapt)
- focal: 被拎起来的 `- id: agent-loop` 那一行
- roles: 三行 YAML = structure · 高亮行 = subject · 洞（虚线残影）= payoff

## Frame 7 — 撑住这棵树的框架

- scene: 2×2 四格，ctx / inject / events / effect，每格一行中文 + 一段真代码
- duration: 18.05s
- poster: 10.0s
- transition_in: cut
- status: animated
- src: compositions/frames/frame-07.html
- type: concept
- persuasion: Definition ×4
- beat: 收束
- blueprint: quadrant-grid (Adapt)
- focal: 四格里依次亮起的 mono 键名
- roles: 十字发丝线 = structure · 四个键名 = subject · 中文一行 = supporting

## Frame 8 — 一棵你能改的树

- scene: 收尾卡：系列名、集数、下一集、仓库地址
- duration: 10.0s
- poster: 6.0s
- transition_in: cut
- status: animated
- src: compositions/frames/frame-08.html
- type: end
- persuasion: Return
- beat: 落下
- blueprint: end-card (Adapt)
- focal: 「一棵你能改的树」这一行
- roles: 系列名 = subject · 下一集与仓库 = supporting（mono）
