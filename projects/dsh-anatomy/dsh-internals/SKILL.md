---
name: dsh-internals
description: "DeepSeek Harness (DSH) 内部架构知识库，源自其 118 篇中文设计文档。当需要在 DSH 仓库里改动 packages/、新增工具/插件/Remote API/会话格式、理解 capability seam 与 Cordis 插件模型、排查 agent loop / 工具流水线 / 沙箱 / 会话日志 / 审批策略，或引用其架构决策与工程纪律时使用。"
---

<!-- argument-hint: [主题、框架名或章号，如 ch28 / capability seam / 沙箱] -->

# DeepSeek Harness 内部架构
**来源**：`deepseek-harness/docs` 118 篇文档（20 篇顶层概念 + 70 篇子系统 + 14 篇手册 + 14 篇 Cordis 教程与 API） | **章节**：40 | **生成**：2026-11-22

## 怎么用

- **不带参数** —— 加载下面的核心框架，够回答「这该改哪」。
- **带主题** —— 说 `沙箱`、`capability seam`、`会话日志`，我会先读对应章节再答。
- **带章号** —— 说 `ch28`，我直接读那一章。
- **要落地步骤** —— 说「新增一个工具」「加一个 Remote 方法」，我会读 ch38 / ch39。

核心框架覆盖不了的问题，一律先读章节文件再回答，不要凭印象补。

---

## 核心框架

**1. 插件即产品（Cordis 插件模型）**
DSH 没有特权内核：模型适配器、工具注册表、会话日志、agent loop 本身都是插件，因此每一项都能从配置替换。扩展方式是把插件挂到其他插件旁边，**注册是副作用，随插件卸载撤销**。服务占据稳定的 `ctx.<key>`，消费方按 key 查找而不是 import 实现。

**2. 能力接缝（capability seam）——全库最重要的概念**
一个 seam = **三角色齐全**的完整能力：声明契约的 **Service Definition**（拥有 `ctx.<key>` 的 Cordis `Service`，绝不是 TS `interface`）、一个或多个 **Service Provider**、一个或多个 **Consumer**（通常是面向模型的工具）。规范范例：`dsh-shell`（定义）+ `dsh-bash-local`/`dsh-bash-sandbox`（提供方）+ `dsh-tool-bash`（消费者）。
- **seam 不是其中任一角色**。只有一个实现类、或只有一个 tool，都不是 seam。
- 替换一个提供方就能改变整个产品：文件系统与进程共享同一个**执行世界（execution world）**，把它们指向远程沙箱，Bash、PTY、LSP 就一起搬过去了。
- 注册形态不止「命名注册表」：还有单槽（`register(name)` 占唯一提供方）、有序尝试、每上下文一实例、注册即绑定。选错形态会导致「第二个提供方注册成功」这类竞态。

**3. 三域事件 + 分发模式**
事件分三个域，用途不同，混用是常见错误：
- **会话事件**（`session/event`）：持久事实，重载后仍在 → 用它记录。
- **Agent 事件**（`agent/*`）：实时协调（inbox、步骤、状态、请求、续跑）→ 用它观察/拦截进行中的工作。
- **能力事件**（`fs/*`、`tools/*`、`telemetry/*`）：无需 import 循环地附加策略与适配器。

分发模式是**公开契约的一部分**：`emit`（旁听）、`waterfall`（可改写，必须 `next()`）、`parallel`、`serial`、`bail`（停在首个 bail 值）。默认不要给新事件选 `bail` —— 它意味着单方短路整条路径。

**4. 轮次 / 步骤（turn / step）与双通道纪律**
**步骤** = 一次模型请求 + 它调用的工具；**轮次** = 零或多个步骤，在领取首条输入前打开、不再欠工作后关闭。
- 持久回放事实进 `session/event`；实时控制与状态进 `agent/*`。
- 需要可回放 transcript 的 SDK/UI 只消费 `session/event`。
- 取消发生在任一异步阶段（组装、`prepareCall`）时，**系统消息与用户消息都不提交**。

**5. 会话日志：模型可见即已记录**
日志是模型上下文的**唯一真源**，`deriveMessages()` 从中投影历史。每个模型请求都必须能从日志重建；**新增模型可见输入就必须新增会话事件**。每个 `assistant/message` 内嵌产生它的精确紧凑 stream；`assistant/attempt` 保留失败/重试/取消，但不进模型历史。改消息内容要注册**纯消息投影**，独立读取器必须显式传同一处理器。

**6. 工具执行流水线（三瀑布夹心）**
`tools/pre-execute` → 单调守卫（只准 deny 或弃权，身份受保护）→ `tools/execute`（超时/重试/指标的环绕点）→ 工具体 → `projectContent` → `tools/post-execute` → `finalizeContent` → `tools/result`（同步、冻结、权威）。策略跨工具族靠事件挂载，工具本身不与策略服务耦合。`ctx.approval` 的一次性询问发生在单调守卫**之前**；不可回答即拒绝。

**7. profile 与组合包的分层装配**
运行中的 `dsh` 是一棵插件树：按序叠加 **profile 的组合包 → 它的 `cordis.patch.yml` → home patch → `--patch` overlay**。patch 按 `id` 定位条目并替换整个 config，或插入新条目。`dsh --profile web --dump-config` 打印出的每一条都可以被自己的 patch 替换 —— 这是「不存在需要打补丁的内核」的实证。

**8. 工程纪律（会真的挡住你）**
- Host / Client 是两个独立的 `ts.Program`：**根 solution 永不作为种子**，新包只登记进一个 aggregate。
- 测试**优先真实实现**，只 mock 昂贵或不确定的边界（LLM、网络、时钟）；e2e **验证外部世界而不是自我报告**（重跑命令、重读文件，不信 agent 自己的输出）。
- 覆盖率按文件 100% 是门禁；未覆盖的行通常是该死代码，不是待补测试。
- 回归守卫必须能**变红**：引入回归、观察失败、再回退，否则等于没有守卫。

**9. 术语纪律（写代码与写文档同样适用）**
一个概念一个词：`turn` / `step` / `Round` 三层不可互换；`scope` 只有扁平两层（全局 / 带作用域），**不向下继承**，子树行为用 `lineage` 数据表达；`seam` 只指三角色齐全的能力。

**10. 新行为该挂在哪（速查）**
模型提供方 → `ctx.llm` 适配器；面向模型的能力 → `ctx.tools`；shell 后端 → `ctx.shell`；持久终端 → `ctx.terminals`；用户命令 → `ctx.commands`；后台任务 → `ctx.jobs`；文件策略 → `ctx.fs` 提供方或 `fs/*` 事件；进程限制 → `ctx.sandbox` 后端包装 argv；拦截请求/工具/轮次 → 对应 `agent/*`、`tools/*` 事件；新增模型可见上下文 → `agent.inject()`；持久会话状态 → 扩展 `SessionEventMap`。

---

## 章节索引

| # | 标题 | 关键框架 |
|---|------|----------|
| [ch01](chapters/ch01-architecture-overview.md) | 架构总览与模块图谱 | Cordis 插件模型、profile/bundle、四层 patch |
| [ch02](chapters/ch02-capability-seams.md) | 能力接缝 | 三角色契约、四类服务角色、五种注册形态 |
| [ch03](chapters/ch03-agent-lifecycle.md) | Agent 生命周期与会话格式 | turn/step、双通道纪律、准入三连 |
| [ch04](chapters/ch04-tool-pipeline.md) | 工具执行流水线 | 三瀑布夹心、单调守卫、审批位置 |
| [ch05](chapters/ch05-api-gateway.md) | API 网关 | `@Remote`/`@RemoteScope`、wire identity、严格生成 |
| [ch06](chapters/ch06-event-bus.md) | 事件生产者与消费者矩阵 | 事件矩阵、派发模式、bail 稀缺性判据 |
| [ch07](chapters/ch07-development.md) | 开发工作流 | Host/Client 双聚合、paths 门面、拆分 compiler face |
| [ch08](chapters/ch08-testing.md) | 测试体系 | 七层测试、真实实现优先、验证外部世界 |
| [ch09](chapters/ch09-cli.md) | CLI 与命令面 | profile 作为启动单元、分层组合 |
| [ch10](chapters/ch10-rescope.md) | 范围重塑 rescope | 名字映射、改名不碰什么 |
| [ch11](chapters/ch11-glossary.md) | 术语表与词汇纪律 | 一概念一术语、seam 分解、scope 扁平两层 |
| [ch12](chapters/ch12-doc-standard.md) | 文档规范 | 一个事实一个家、文档预算三级裁决 |
| [ch13](chapters/ch13-protocol-extensions.md) | 协议扩展与实验性持久化 | 命名空间与版本、事务式贡献、水位与至少一次 |
| [ch14](chapters/ch14-ui-system.md) | UI 设计与样式系统 | 整页审查单位、三种嵌套几何、圆角选档 |
| [ch15](chapters/ch15-cordis-intro.md) | Cordis 入门与第一个插件 | 五个核心概念、分发模式、waterfall 中间件 |
| [ch16](chapters/ch16-cordis-lifecycle.md) | 生命周期与副作用 | `ctx.effect()`、Fiber 状态机、依赖驱动加载 |
| [ch17](chapters/ch17-cordis-services.md) | 服务 | 运行时注册 + 声明合并、`inject` 硬依赖 |
| [ch18](chapters/ch18-cordis-events.md) | 事件 | `interface Events` 合并、五种分发、否决 |
| [ch19](chapters/ch19-cordis-config.md) | 配置 | Config 双重身份、`!!js` 求值、volatile |
| [ch20](chapters/ch20-cordis-composition.md) | 组合与 HMR | 条目 `id`、`disabled`、group + isolate |
| [ch21](chapters/ch21-cordis-harness.md) | 进入 Harness | 一次注册两处所有权、`defineTool` 四段契约 |
| [ch22](chapters/ch22-context-api.md) | Context API | `extend`/`isolate`/`intercept`、服务存储五件套 |
| [ch23](chapters/ch23-events-api.md) | Events API | `DispatchMode`、bail value、serial vs bail |
| [ch24](chapters/ch24-fiber-api.md) | Fiber API | `ctx.effect`、配置三态 |
| [ch25](chapters/ch25-inherited-api.md) | Inherited API | 继承的 `ctx` 面、三层来源读法 |
| [ch26](chapters/ch26-registry-api.md) | Registry API | `ctx.plugin`、`ctx.inject`、同一回调=同一 Runtime |
| [ch27](chapters/ch27-service-api.md) | Service API | 构造即注册、`Service.init`、`Service.check` |
| [ch28](chapters/ch28-session.md) | 会话与对话 | 仅追加日志、表面操作、派生历史、投影 seam |
| [ch29](chapters/ch29-agent-orchestration.md) | Agent 编排 | 委派 activation、三条所有权边界、stopReason |
| [ch30](chapters/ch30-tools-approval.md) | 工具、审批与调度 | 作用域注册、`defineTool`、审批位次 |
| [ch31](chapters/ch31-streaming-telemetry.md) | 模型流式与可观测 | StreamChunk 联合、适配器九条规则、Token 计量 |
| [ch32](chapters/ch32-sandbox-runtime.md) | 沙箱与执行环境 | argv 包装、策略三级优先级、fail-closed |
| [ch33](chapters/ch33-storage-settings.md) | 存储、设置与凭据 | 存储 seam、迁移边界、启动装配 |
| [ch34](chapters/ch34-extension-surface.md) | 扩展面 | 三元结构、分层注册表、闭合联合 |
| [ch35](chapters/ch35-desktop-multimodal.md) | 桌面与多模态 | 只注册名称、Session 所有权、权限三件套 |
| [ch36](chapters/ch36-web-client.md) | Web 客户端 | 六层所有权、WebBootGraph、类型化槽位 |
| [ch37](chapters/ch37-account-collab.md) | 账号、协作与其他 | 请求凭据、任务输出环、分享档位 |
| [ch38](chapters/ch38-adding-tool-package.md) | 新增工具、包与插件 | `defineTool` 六条、前台/后台信号 |
| [ch39](chapters/ch39-remote-api-format.md) | 远程 API、格式与适配器 | Remote 五步、单一失败类、版本轴分开 |
| [ch40](chapters/ch40-review-contribution.md) | 评审与贡献 | 堆叠 PR 五规则、修复归属在引入层 |

## 主题索引

- **附件与图片** → ch35；**审批** → ch04, ch30；**Cordis 内核** → ch15–ch27
- **capability seam** → ch02, ch11；**CLI** → ch09；**配置** → ch19, ch33
- **事件（三域 / 分发）** → ch06, ch18, ch23；**Fiber / effect** → ch16, ch24
- **agent loop（turn/step）** → ch03, ch28；**Agent 编排 / subagent** → ch29
- **会话日志 / 格式迁移** → ch03, ch28, ch39；**压缩与 spill** → ch28
- **工具流水线 / 守卫** → ch04, ch30, ch38；**MCP / 技能 / LSP** → ch34
- **沙箱 / 子进程 / 终端** → ch32；**存储 / 凭据 / 设置** → ch33
- **Remote / API 网关 / Typert** → ch05, ch31, ch39
- **测试 / 门禁 / 开发流程** → ch07, ch08, ch40
- **文档规范 / 术语** → ch11, ch12；**rescope / vendor** → ch10
- **UI / 圆角 / 样式** → ch14, ch36；**Office / 浏览器 / 桌面** → ch35
- **可观测 / 遥测 / token 计量** → ch31；**账号 / 协作 / 任务** → ch37

## 配套文件

- [glossary.md](glossary.md) — 全库术语与精确定义
- [patterns.md](patterns.md) — 可复用的工程技术与设计模式
- [cheatsheet.md](cheatsheet.md) — 决策规则、阈值与气味信号

## 范围与限制

本 skill 覆盖 `docs/` 下的**设计与规范文档**，不含 `packages/` 源码实现细节；涉及具体实现时请直接读仓库代码。文档标注为实验性的部分（browser-use、computer-use、forge 等）可能变更。原文没有配图，全部章节由纯文本蒸馏而来；`docs/` 中的生成式目录（config-catalog、persistence-catalog、tool-catalog、module-graph）体量过大且为机器生成，未纳入本知识库 —— 需要精确字段时读原文件。
