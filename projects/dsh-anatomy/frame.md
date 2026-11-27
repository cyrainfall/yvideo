---
version: 1.0
name: Substrate — 拆开 DSH 系列视觉规范（frame layer）
description: >
  一个给「源码级讲解」用的深色工程台系统。单位是帧（1920×1080）。整套只有一种彩色：
  DeepSeek 蓝，只在「模型 / 正在发生的那一件事」上出现；其余全部是墨底、暖白字、1px 发丝线
  和等宽铬件。没有卡片、没有圆角、没有阴影、没有渐变光斑。结构靠线，层级靠字号与字重。
unit: the frame — 1920×1080
principle: 一个彩色焦点 · 结构靠线 · 数字与文件名必须是真的

colors:
  canvas: "#0A0B0D"        # 帧底：近黑，偏冷
  surface: "#101319"       # 极少数情况下抬起的一层
  line: "#232833"          # 发丝线，结构
  line-strong: "#39404E"   # 强调分隔
  text: "#EDEAE3"          # 主文字：暖白，不是纯白
  text-muted: "#9BA2AD"
  text-faint: "#5B6370"
  accent: "#4D6BFE"        # 唯一的彩色：DeepSeek 蓝
  accent-soft: "rgba(77,107,254,0.14)"
  accent-line: "rgba(77,107,254,0.42)"
  paper: "#E9E4D8"         # 「已经落盘」的字：暖纸白

typography:
  display:  { family: "Inter", weight: 900, cqw: 7.2, tracking: "-0.045em", lineHeight: 0.95 }
  headline: { family: "Inter", weight: 800, cqw: 4.4, tracking: "-0.035em", lineHeight: 1.12 }
  lead:     { family: "Inter", weight: 500, cqw: 1.9, tracking: "-0.01em", lineHeight: 1.55 }
  body:     { family: "Inter", weight: 400, cqw: 1.25, tracking: "0", lineHeight: 1.6 }
  code:     { family: "JetBrains Mono", weight: 400, cqw: 1.15, tracking: "0", lineHeight: 1.5 }
  label:    { family: "JetBrains Mono", weight: 500, cqw: 0.68, tracking: "0.18em", upper: true }

spacing:
  pad-x: "6cqw"
  pad-y: "7cqw"
  gap-lg: "3cqw"
  gap-md: "1.6cqw"
  gap-sm: "0.8cqw"

components:
  chrome:
    rule: "顶部 1px line 横线，左上 mono 标签（EP.01 / 拆开 DSH），右上当前文件名"
    description: "只有信息帧才出现；封面与收尾帧不加铬件。"
  station:
    rule: "1px 竖线 + 上方 mono 序号 + 下方中文站名"
    description: "六站地图的唯一骨架；激活时整条线变 accent，未激活是 line。"
  code-line:
    rule: "等宽字；行号在左、text-faint；当前行行号变 accent"
    description: "引用真实文件行时的标准形态，必须能对得上仓库。"
  tree-node:
    rule: "mono 名字 + 1px 左边线；插件行激活时左边线变 accent"
    description: "插件树只用缩进与发丝线表达层级，不用方框。"

motion:
  grammar: "全部 power3.out；元素间距 0.06–0.10s 的 stagger；不做回弹、不做呼吸循环"
  pacing: "按旁白节奏揭示：说到哪个词，才放出哪个元素；禁止前 25% 倒完再冻住"
  transitions: "硬切为主；只有第 5 帧进入时用一次 8 帧的横向位移揭示"

negative:
  - 机器人、大脑、神经网络光斑等 AI 陈词
  - 紫蓝渐变、玻璃拟态、发光卡片
  - 带红黄绿圆点的假终端窗口
  - 圆角、阴影、3D 透视
  - 编造的数字、文件名、配置字段
---

# Substrate

## 它是什么

给一个「拆开源码」的系列片用的视觉系统。观众要相信屏幕上的每个名字都真在仓库里，
所以这套系统把装饰压到接近零：一根 1px 线、一个等宽标签、一个字号差，就构成层级。
唯一的彩色是 DeepSeek 蓝——它只回答一个问题：**这一刻，什么是活的。**

## 规则

1. **一帧一个蓝焦点。** 同一帧里第二个需要强调的东西，用 line-strong 或字重解决，不开新色。
2. **所有代码、路径、配置字段必须是仓库真值。** 写不出来就不上屏。
3. **结构靠线。** 分组用 1px line，不用盒子；抬升用 surface，不用阴影。
4. **留白即呼吸。** 主视觉占画布 ≥ 40%，四周至少 6cqw 的边。
5. **字幕安全区。** 画面底部 17%（y > 900px）留给字幕胶囊，正文收在 900px 以上。
6. **中文与拉丁同重。** Inter 的字重与中文回退字体视觉重量要对齐；中文不做斜体。
