---
format: 1920x1080
duration: 61.64s
message: "一次点击要走完六个阶段，画面才回到你眼前——链路上没有魔法"
arc: how-to-process
audience: 会装 DSH 的开发者
mode: collaborative
music: none
---

## Video direction

- **palette**：`frame.md` 的两个 register 只用 dark 一种——ground `ink-black #111111`、正文 `cream #F0ECE5`、唯一强调 `fire-orange #E85D26`、分隔线 `border-dark #282826`。橙色每帧只许给**一个**焦点；需要第二层时用 `cream-muted #888880` 降级，不加新色相。全程不出现纯黑 `#000` 或纯白 `#FFF`。
- **type**：Barlow 显示层（700–900、负字距、字形即图形）＋ IBM Plex Mono 铬件（大写、0.14em 字距）承担坐标、报文、步骤编号与帧标签。中文主字形靠 Barlow 的拉丁骨架承重、中文交给同字重回退，两边视觉重量必须一致。
- **motion grammar**：全部长尾缓动（`power3` 默认，宁滑不弹）。每帧遵守 **VO 节奏揭示**——t=0 只出现旁白当时正在说的东西，之后每说出一个词才放出对应元素，揭示集中在后 50%。禁止把整块版面前 25% 倒完再冻住。
- **rhythm / held frames**：第 6 帧（解码，7.6s 之后）与第 8 帧（回程，7.6s 之后）是**持留帧**——数字停住后不再动，揭示亮起后整幅静止。其余六帧都在揭示。全片只允许这两次"不动"。
- **layering**：每帧 ≥3 层——1px 发丝网格/刻度（背景）＋ 主视觉（中景）＋ 铬件标签（前景）。主视觉占画布 ≥40%。
- **caption keep-out**：画布底部 17% 留给字幕胶囊，主视觉与关键文字一律收在顶部 83% 内；居中式英雄锚在 y≈0.42×H（≈454px），不落画布正中。背景层可以满幅。
- **negative list**：不要真人、不要 stock 素材、不要真实浏览器 chrome 与滚动条、不要圆角卡片、不要紫蓝渐变与浮动光斑、不要"飞数据包"的通用链路动画、不要幻灯片式（前置铺满）与屏保式（所有元素各自乱飘）两种动效失败模式。

## Frame 1 — 光标停在屏幕边缘

- scene: 墨黑平面上只有一只光标，停在画面右下三分线；左下角等宽坐标读数 (1492, 611) 缓慢走字
- duration: 3.882s
- poster: 2.4s
- transition_in: cut
- status: animated
- src: compositions/frames/frame-01.html
- type: hook
- persuasion: Imagine/scenario + Concretization
- beat: 好奇与轻微的悬置感
- blueprint: kinetic-type-beats (Adapt)
- focal: 那只橙色光标 + 它下面的坐标读数
- roles: 光标 = foreground subject（唯一彩色对象）· 坐标读数 = supporting（等宽、cream-muted）· 墨黑平面与右下三分线 = background
- sfx: click-soft @0.46（光标落位）