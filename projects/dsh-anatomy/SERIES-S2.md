# 拆开 DSH · 第二季 系列大纲

> 十二集，每集 3:00–4:30（硬顶 5:00）。第一季看机器怎么转；这一季下到深水区，看每个承重结构为什么长成这样。
> 每集只回答一个问题；屏幕上每个名字、数字、行号以仓库当前版本为准（`/Users/cyx/repo/deepseek-harness`，本季基线 HEAD `d98f5d6851` / DSH `0.2.3-alpha.1`）。
> 策划案与取舍依据见 `SERIES-S2-PLAN.md`；本文件只承接已开工集的滚动更新。

## EP07 接缝：两百个插件，为什么没长成意大利面 ✅

**问题**：一个「一切皆插件」的仓库，凭什么插件越多越有序？
**答案链**：插件多 ≠ 随便挂，一个能力要三角色齐全——定义（抽象类拥有 `ctx.<key>`，一个上下文一个名额）+ 提供方（`bash-local` / `bash-sandbox`，后者继承前者再换执行世界）+ 消费方（`tool-bash` 只认键，定义包只在 peer，提供方不在运行期依赖里）→ 五种注册形态发布时就得选对（命名注册表 `ctx.llm` / 单槽 `ctx.browserUse` / 有序尝试 认证链 / 每上下文一实例 `ctx.shell` / 注册即绑定 `ctx.credentials`）→ 判据：缺席分两种，硬 `inject` 缺席停 PENDING，可选 `ctx.get` 缺席才 `unavailable`；重复加载抛错是 cordis 的标准行为，不是包的守卫。
**现场演示**：`cordis_inspect` 取运行中的 `shell` 合约（`access` 双通道 + "loading a second throws"）→ `Config.listConfigs` 取插件行（本机 `bash-sandbox` 在列、`tool-bash` 为 `inactive`）→ 回源码钉死装配。收据在 `demo/receipts-s2/E01-inspect/`。
**证据**：`packages/shell/shell/src/index.ts:30-32,64-66`；`packages/shell/bash-local/src/index.ts:97-98`；`packages/shell/bash-sandbox/src/index.ts:45-46`；`packages/shell/tool-bash/src/index.ts:36,251,320` + `package.json:36,49-51,60`；`packages/llm/llm/src/index.ts:336-337,383,425`；`packages/browser-use/browser-use/src/index.ts:16,35-38`；`packages/client/connection/src/authentication.ts:44-55`；`packages/credentials/credentials/src/index.ts:205-214`；`vendor/cordis/src/reflect.ts:326`；`docs/capability-seams.md:709-829`（生成文件）。
**成片**：`renders/ep07-接缝.mp4`（4:25.2，两轮英文读法修正后重渲）· 工作区归档 `episodes/ep07/`（含 `NOTE.md` 与 `voice/读法规则.md`）· 封面 `publish/ep07/cover.png`。
**发布**：`BV1vj1tzNENa`（2026-11-28 00:05 投稿 · aid 117689251070826）· 分区 科技/计算机技术 · 声明 含AI生成内容 · 标签 10 个 · 回执 `publish/ep07/result.json`。
**留的钩子**：消费方不 import 提供方，那插件之间怎么「听见」彼此？→ 事件。

## EP08 事件的三张地图：插件之间怎么说话 ⬜

**问题**：几十个插件协作，为什么没有 import 地狱？
**答案链**：事件分三域（`session/event` 持久事实 / `agent/*` 实时协调 / `fs/*`、`tools/*` 能力策略）→ 分发模式是公开契约（`emit` / `waterfall` 必须 `next()` / `serial` 首个非空截断 / `parallel` 扇出 / `bail` 授权短路）→ `bail` 全库只有一处（`webserver/authorize`）→ 观察型 waterfall 监听器不调 `next()` 是静默否决。
**证据**：ch06、ch18、ch23、`cheatsheet.md` 分发模式表（开工前回仓库核 file:line）。

## EP09 可逆的世界：热重载凭什么不漏 ⬜

**问题**：改一行配置就重挂载，凭什么不多出一份回调？
**答案链**：effect 带回 disposer、逆序清理 → `inject` 不满足停 PENDING → Config 双重身份与三态 → `.volatile()` → HMR = 卸载旧实例再加载；裸 timer 不进 `ctx.effect()` 就一轮多一份回调。
**现场演示**：同一插件两个版本，裸 timer 版三轮 1→2→3，effect 版 1→1→1。

## EP10 一台机器的五个刻度：多智能体怎么编 ⬜

**问题**：委派、团队、计划、目标、待办——是五个功能，还是一台机器？
**答案链**：一条栈；委派路由看方法在不在（`prepareContinual` / `start`）；团队 CAS 不用锁（`revision`、`blockedBy`、`writeScopes` 只是提示）；子级失败是 `stopReason` 不是异常；`plan/mode` 只进日志不进 transcript；目标 = 两套状态叠一个修订号。

## EP11 token 的河道：一次回复在代码里是什么形状 ⬜

**问题**：模型吐出的那条「河」，代码里怎么接、怎么数、怎么重放？
**答案链**：封闭七变体 `StreamChunk` → 四件套事实 → `expandAssistantStream()` 必须可逆 → 适配器三件事 → `TokenMeasurement` 是可重放快照 → `TokenUsage` 互不重叠 → `projectedTokens` 只是显示值。

## EP12 执行世界：read-only 模式下的 rm -rf ⬜

**问题**：受限模式里一条危险命令跑出去，到底发生什么？
**答案链**：沙箱是 argv 包装器不建进程 → `SandboxMode` 只管文件效果 → 归因三步 → 拒绝签名是后端方言（bwrap EROFS / Landlock EACCES / Seatbelt EPERM）→ `enforcement: 'partial'` 是事实 → 会话 cwd 即边界 → SSH 换的是整个执行世界。

## EP13 不会撒谎的日志：熬过崩溃与版本更迭 ⬜

**问题**：为什么敢说「模型可见即已记录」，还敢升级格式不丢老会话？
**答案链**：`append` resolve ≠ 持久化，flush 才是承诺 → 崩溃留痕可检测 → 已提交代际不可变 → `SESSION_FORMAT_VERSION` 单一真源 → 迁移链每包只管 `vN→vN+1` → 水位只折叠同 session + 同 generation。

## EP14 两个程序的世界：Host 与 Client 隔空握手 ⬜

**问题**：一份真相在 Node 里，浏览器要用，中间隔着什么？
**答案链**：两个独立 `ts.Program` → `@Remote` 构建期生成严格契约 → 参数表禁泛型/可选/解构/默认/rest → wire identity → 失败面收敛成一个 `RemoteError` + 域码 → 流不伪装成 Remote → 改约定先 `build:lib` 先 Host 后 Client。

## EP15 浏览器那一半：屏幕上的像素归谁管 ⬜

**问题**：一个对话页面几十个包往里塞东西，凭什么不乱？
**答案链**：六层所有权（状态 / 位置 / 跨包行为 / 声明）→ `WebBootGraph` + `dsh.client` + `exports["./client"]` → `ctx.slots.inject` + `register`，同 dock 多提供方未配 id 抛 `WEB_PROVIDER_AMBIGUOUS` → HMR 跟随模块图 → 视觉纪律：整页审查单位、发丝线、圆角选档。

## EP16 模型的第三方器官：MCP、技能与 LSP ⬜

**问题**：第三方工具接进一棵有纪律的树，边界画在哪？
**答案链**：三元结构 + 分层注册表 + 闭合联合 → MCP 一服务器一连接、名字带前缀 → 动态插件三级身份（Plugin / Package / Run）→ 多模态五通道只登记名字 → 附件准入先于规范化 → 先持久化后追加事件 → 失败方向是关闭。

## EP17 会变红的守卫：AI 改的代码怎么测 ⬜

**问题**：一个 agent 大量参与开发的仓库，测试凭什么可信？
**答案链**：七层各答一问 → 只 mock 三类昂贵边界（LLM / 网络 / 时钟）→ e2e 验证外部世界，不做关键词探测 → 测试真实入口 `lib/bin.js` → 覆盖率按文件 100% 是门禁，未覆盖行优先删死代码 → 回归守卫必须先制造一次红 → CI 强制 `DSH_SNAPSHOT=replay`。

## EP18 一概念一个词：118 篇文档怎么不散架 ⬜

**问题**：40 个章节、99 条术语、上百个包——凭什么每一处说的是同一件事？
**答案链**：一概念一术语（`turn` / `step` / `Round` 不可互换）→ 一个事实一个家（tier 划归属层）→ 文档预算三级裁决 Relocate → Condense → Raise → rescope 只改名守不变量 → 评审堆叠回引入层 → 失败面 fail-closed → 收束：把 E01–E10 摆回一张图，打结回接缝。
