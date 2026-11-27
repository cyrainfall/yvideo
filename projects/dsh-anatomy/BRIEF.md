# BRIEF — 拆开 DSH（系列）

- **产物**：一个系列视频，源码级解释 `/Users/cyx/repo/deepseek-harness` 的工作原理；第一集先交付。
- **观众**：会写一点代码、想搞清 agent 框架到底在做什么的人；不假设读过 Cordis 或插件系统。
- **目标**：看完第一集，能用自己的话说清「harness 是什么、dsh 为什么长成一棵树、一次请求要过哪六站」。
- **语气**：冷静、精确，像拆机器；不做产品宣传，不用 AI 陈词。
- **语言**：中文。1920×1080，30fps。有人声旁白与字幕。
- **事实来源**：只允许来自仓库本身 —— `docs/architecture.zh.md`、`docs/cordis-primer.zh.md`、
  `packages/bundle/base/cordis.patch.yml`、`packages/core/agent-loop/src/agent.ts`、
  `packages/core/tools/src/events.ts`。屏幕上出现的路径与数必须能在仓库里找到。
- **不含**：安装教程、性能数字、与其它框架的对比。

## 系列

| 集 | 标题 | 一句话 |
|---|---|---|
| 01 | 模型只会说话 | 为什么需要 harness；dsh 的答案是一棵插件树；一次请求要过六站 |
| 02 | 一切皆插件 | Cordis 五件套：ctx / inject / 事件 / 可逆副作用；写一个二十行的插件 |
| 03 | 把树拼出来 | profile、bundle、patch 如何叠成运行中的插件树；`--dump-config` |
| 04 | 一轮对话 | turn 是排空循环、step 是请求加工具、只追加的日志与 surfaceOp、deriveMessages 投影 |
| 05 | 工具：模型的手 | 工具注册表、scope、pre/execute/post 三段流水线、审批与沙箱 |
| 06 | 改它 | 加一个工具、一个命令、一个面板，然后热重载 |
