---
workflow: faceless-explainer
flow: automation
storyboard: yes
message: "一次点击要走完六个阶段，画面才回到你眼前——链路上没有魔法"
destination: youtube
aspect: 1920x1080
language: zh
length: 60s
angle: concept
---

## Intent

给 dsh-ydesk 做一条工作原理讲解片：不演安装步骤，也不做产品宣传，而是**跟着一个鼠标动作走完全程**。观众看到的是同一个事件在链路里一次次改变形状——手、归一化坐标、WebSocket 的字节、被重新注入的 `SendInput`、飞回来的画面帧——六次变形对应六个阶段（采集 → 封装 → 传输 → 解码 → 注入 → 画面回程），最后远端画面第一次亮起，揭示这一切发生在另一台机器上。

基调：冷静、精确、有一点工程上的傲气。像一份带旁白的实测记录，不像广告片。观众默认是会装 DSH 的开发者；不解释什么是远程桌面，直接讲这条链路为什么长这样。

## Assets

- `/Users/cyx/repo/dsh-ydesk/README.md` — 唯一事实来源。全片技术数字、协议字段、实测值只能来自这里。
- `/Users/cyx/repo/dsh-ydesk/docs/shot-*.png` — 12 张真实面板截图（1080p60 面板、局域网列表、重连、剪贴板输入、深浅色对比）。**可选**材料：只在"结尾画面亮起"或"参数面板"需要真实质感时使用；方案一的默认视觉是自造的，不必为了用素材而改结构。
- `/Users/cyx/repo/dsh-ydesk/index.js`、`client.js`、`lib/*` — 需要确认某个行为时读源码，不要猜。

## Customizations

- 终端窗口与参数面板用注册表里现成可改样式的场景块（方案一已点名），不手搓终端皮肤。
- 结尾的"远端画面亮起"是一次揭示式转场，不是淡入；`/hyperframes-registry` 里优先找现成转场原语。

## Notes

- **数字不许编**。可用范围只有 README 里出现过的：1920×1080 / 60fps / 6M 默认档；编码 60fps 但真实内容更新只有 8–11fps；BitBlt 110–123ms 且与区域大小无关；ffmpeg 任何容器 muxer 只有 ~12.5fps；live-edge 缓冲 290ms → 70–95ms；输入→像素中位 75–210ms、最快 22ms；实测码率 1.8–4Mbps。
- 不要真人出镜、不要 stock footage、不要"两台笔记本之间飞数据包"的通用动画——那正是这个题材的反模式。
- 中文文案；坐标、报文、键名用等宽字体，与叙事字体分开。
- 全片 60 秒左右，六个阶段每个 8–10 秒，片头片尾各约 4 秒。
- 工程注记：`npx hyperframes skills update faceless-explainer` 本次因 CLI 侧 GitHub 抓取不可达而失败（curl 经 7890 代理可通，CLI 的 fetch 不走代理）。当前使用的是本地已安装的 faceless-explainer 契约，技能新鲜度未校验。
