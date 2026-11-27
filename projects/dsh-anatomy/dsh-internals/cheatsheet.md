# 决策速查

## 改动落点

| 想做的事 | 落点 | 禁止 |
|---|---|---|
| 加工具 | `defineTool` + `ctx.tools.register` + `inject:['tools']` | 手写 JSON Schema、手校验 `args` |
| 换实现 | 能力图里标 `seam` 的角色 | 动 `core` / `service`；fork 提供方 |
| 只加了消费方 | 驳回：Definition / Provider / Consumer 一起设计 | 单角色当 seam |
| 策略（先读后编辑、spill 阈值、审批询问） | 配套插件或 `tools/*` 监听者 | 写进工具体（换实现即漂移） |
| 执行前拦截 / 最终拒绝 | 守卫或审批策略 | 后置翻案（拿不到产物） |
| 结果观测 | 监听 `tools/result`（不可变快照） | 注册者自己 `console.log` 兼当观察者 |

- 层序：profile → 其 `cordis.patch.yml` → home patch → `--patch`；绕过 launcher 挂应用被 `verify-application-entrypoints` 拒。
- 能挂监听器就别造机制；映射表里没有一行需要改循环本身。
- 流水线顺序即契约：`pre-execute` → 单调守卫 → `execute` → 工具体 → `projectContent` → `post-execute` → `finalizeContent` → `tools/result`。

## 接缝、Context、Service 与配置

- 消费方只写能力名，**不 import 提供方**；提供方缺席是合法状态 → 走 `unavailable`。
- `inject` = 硬依赖 + 启动顺序契约；「最好有」用 `ctx.get()`（`inject` 会永久 PENDING）；`ctx.inject()` 是"服务变则**重载**"。
- 自建服务加前缀（避开 `tools`、`llm`）；`super(ctx, name)` 即注册、卸载即注销；重活放 `[Service.init]`；`[Service.check]` 恒 `true` = 放弃可用性语义。
- 经 Cordis API 建的是 effect，卸载自动撤销；自管资源（timer / 连接 / watcher）必须 `ctx.effect()` + disposer，否则热重载一轮多一份回调。
- disposer 顺序与注册**相反**，重复调用 no-op；有顺序依赖就合并进同一 disposer 顺序 `await`；卸载后继续注册 → `INACTIVE_EFFECT`。

- Context：`extend` 自有属性遮蔽（非深合并）；`isolate(name)` 同 `label` 才共享，读父级**抛错**；`intercept` 改解析链（注入在前、祖先在后）；父上下文永不修改，所有权归 fiber；判上下文用 `Context.is`（`instanceof` 跨 realm 失效）。
- 判活性看 `state`，不看 `effectiveConfig`（激活前 `undefined`、卸载后仍可读）。
- `dsh-tools` 与 `dsh-system-prompt` 必须成对，缺一个 = **静默 PENDING**。
- `Config` = 类型 + 运行时 schema（普通对象不工作），失败即 FAILED + 字段路径 + 非零退出。
- volatile 只给「每次操作都读」的字段；结构性配置**不**标；声明必须在固定对象路径（数组元素 / union 分支 / transform 内直接拒）。
- `cordis.yml` 每条写 `id`（否则改一行可能整条重挂载）；停用用 `disabled: true` 不删条目；组管启停，`isolate` 管服务隔离；HMR 需 logger + timer + tsx。

## 事件与分发

| 模式 | 语义 | 返回值 | 短路 | 误用症状 |
|---|---|---|---|---|
| `emit` | 观测广播 | 否 | 否 | 异步失败无人看，只在负载下偶发 |
| `waterfall` | 接缝 / 链 | 是 | 不调 `next()` 即否决，连内置行为一起跳过 | 当 `emit` 用 |
| `serial` | 有序响应 | 是 | 首个非空截断 | 顺手 `return` 有用值 → 后续监听器整段不跑 |
| `parallel` | 并行扇出 | 收集 | 否 | 做「先问 A 再问 B」 |
| `bail` | 授权短路 | 是 | 是，且不 await | 当普通拦截（**全表唯一，勿新增**） |

- 观察型 `waterfall` 监听器**必须** `next()`；终止判据是非 `null` / `false` / `undefined`——`0` 与 `''` 也截断链。
- 域二分：重载后还要存在或改模型可见输入 → `session/event`（可见即已记录）；只协调实时队列 → `agent/*`（重载即失）；失败 / 重试 / 取消 → `assistant/attempt`（**不进模型历史**）；成功调用（含空内容、`max-tokens`）→ `assistant/message`。
- 已提交 generation 不改名 / 不替换 / 不删除，改写 = 排他发布新代际；升格式要新写入器版本 + 自身头转换（3→4 不可复用）。
- 热路径：`session/event` 监听方数十，禁每事件重算；`waterfall` 链上禁重活。

## 会话、日志与存储

判据只有一句：**它有没有偷偷引入第二条真源**。消息历史永远从日志派生，缓存只缓存投影。

- 新增事件先定三件事，任一含糊即磁盘格式破坏性变更：是否 surface、`ignorable` 有理由、payload 无损 JSON。
- 投影单元不能 async；`apply` 必须保引用不变式——返回新对象 ≠ 没变化（`Object.is` 判不出语义相等）。
- `replace` 的 `sourceEventSeqs` 必须覆盖全部被遮蔽节点，`shadowedSeqs` 才是不出"幽灵上下文"的判据；改 `apply` 语义必须升 `stateVersion`（schema 通过 ≠ 语义等价）。
- 读路径三选一：`stateOf` / `snapshot`、`viewCheckpoint`、`restore`（冷会话）；与会话同序拆除用 `prepare` + `enter` + `announce`。
- 存储先分 seam：会话日志 → `SessionPersistence`，其余 → `ctx.storage` + 领域声明；后端拥有介质、领域拥有语义；产品包不得 import 某后端。
- `append` 的 resolve ≠ 持久化成功（后端可缓冲），要熬过崩溃一律 `flush`；就地改返回的记录不是写入，须整体 `put`/`update`。
- `unknown-state` 后停止写入 → `close()` → 重开；`compatibleVersions` 只发解码通行证，旧解码分支等记录重写验证后再删——手工改小版本戳"回滚"是假象。

## 编排与协作

| 层 | 决定 | 硬边界 |
|---|---|---|
| 委派 | 谁执行 | `prepareContinuable` 在 → 本地可继续；不在 → 外部一次性 |
| 团队 | 多执行者共享任务 | 并发靠 `revision` CAS + 无环 DAG，**不靠锁**；`writeScopes` 只是提示 |
| 计划 | 约束当前轮次 | 软性指引；`plan/mode` 仅日志，**绝不进 transcript** |
| 目标 | 约束跨轮次 | `phase` 说发生了什么，activation 说能否再跑一轮 |
| 待办 | 最小账本 | 无 id、整表替换、last-write-wins |

- 五层同形：日志是真相、投影是读模型、准入在**步骤边界**而非调用边界；子级失败是 `stopReason`，只有基础设施故障才 reject。
- 团队任务变更**不唤醒** agent，要处理就发消息；`blocked` 的 `resume` 只在轮次预算仍有容量时生效。
- `agent/pre-step` 的返回是权威；包装 `next()` 要显式保留消息与 `startsRequestSeries`。
- 后台任务边界是**拥有者会话**而非 id（`<kind>-<short-uuid>` 可预测）；id 用 `{ kind: 'background', jobId }`，不从自然语言解析；`done` = 资源已释放。

## 工具与审批

- 三道门正交：注册与作用域（存在吗 / 有这个能力吗）、审批与策略（这一次允许吗）、调度（什么时候跑）。**用审批补作用域的洞 = 每次调用加人工闸**。
- 询问永远在守卫之前；审批只放行一次（唯一许可 `allowed-once`）；`rejected`/`cancelled`/`unavailable` 全按拒绝；缺应答方 = **拒绝**。
- `never` 不是"全部批准"：两者都是不问，但 `never` 在分发应答者前确定性返回 `rejected`——无人值守是关闭。权限预设只写 `sandbox/mode` 与 `approval/policy`，不做强制。
- 不要自己发 `tool/result`（一次调用会得到两条结果）；PTC 子调用不加 `additionalContexts`。
- 条件注册离开步骤即不可用；并行组不得写父级状态。
- 不调模型验证工具：`ctx.tools.execute` 走真实流水线；`tools/result` 早于 `execute` 的 promise 兑现 = 流水线走对了。
- 加工具包成本在契约：`execute()` 逐项过；`presentCall` 必须纯、对坏输入软失败；三层分离（模型内容 / 卡片数据 / UI 状态），别只为 UI 把 diff、相对路径塞进规范值。

## 沙箱与执行

| `SandboxMode` | 含义 | 消费方 |
|---|---|---|
| `read-only` | 文件只读（`/dev/null` 接收器也要显式授予） | `ctx.sandbox` |
| `workspace-write` | 仅工作树可写 | `ctx.sandbox` |
| `danger-full-access` | 不进 `ctx.sandbox`，消费方直接 spawn 原始 argv | 消费方 |

- `SandboxMode` 只管辖**文件效果**；网络与进程可见性另立词汇；策略权威只有 `ctx.sandboxPolicy.resolve()`。
- `enforcement: 'partial'` 是后端报告的**事实**（旧内核 ABI、Windows ACL 缺口），要绝对边界必须拒绝它。
- 归因固定顺序 runner failure → denial → 进程失败；先剥 `informationalLines` 再匹配致命签名。
- `timeoutMs` 不是保险丝：没观察 `exec.signal` 的工具体，超时后照旧产生副作用。
- 目录三层：cwd 是执行边界（只有 Host 能改），worktree 是改它的手段，workspace 是纯记录；`registerWritableRoot()` 运行时专属，resume / fork 后必须重注册。

## 流式与计量

- 瞬态 = delta（可折叠）；事实 = `block-end`、`usage`、`finish`、`assistant/attempt`；折叠必须可逆（`expandAssistantStream()`），否则计费、追踪、重放全失真。
- 适配器只做三件事：wire → `StreamChunk`、错误 → `LlmFailure`、私有回放 → `ReplayEnvelope`；组装 / 重试 / 计量都在 core；共享注册用 `prepareCall()`。
- 错误路由只认 `code`；溢出只有 `CONTEXT_WINDOW_EXCEEDED`；`providerRetryAfterMs` 只是建议，决策归 `ResolvedRetryPolicy`；空 completion 必须 `EMPTY_RESPONSE` 且默认重试。
- 计数口径：`TokenMeasurement` 是**可重放快照**不是计数器（每次 `measure()` 从日志重放，代价 O(surface)）；`TokenUsage` 逐调用记账且**计数互不重叠**——`inputTokens` 只含未缓存输入，缓存单列；`heuristicTokens` 是与路由无关的影子价。
- `projectedTokens` / `contextPressure` 是 last-wins 显示值，**不能当准入门槛**；`emit()` 返回只代表入队。

## 协议与 Remote

| 要传的东西 | 通道 |
|---|---|
| 一元、单请求单结果、Host→Client 流 | `@Remote` / `@RemoteScope` |
| 会话事件流、分页、增量 reduce、投影 | 独立协议，不伪装成 Remote |
| 复杂对象 | `TypertLookupMap` + `register()` 默认 resolver |

- 参数禁：泛型、可选、解构、默认值、rest（构建期拒绝）；改约定必须 `build:lib`，先 Host 后 Client。
- 失败面收敛成一个 `RemoteError` + 码表 `<域>/<理由>`，自有码原样上 wire，未归类才折 `gateway/internal`；Client 只判 `code`。
- 扩展字段必须在 `messages`、系统提示词、工具 schema **之外**，每字段自持版本。
- 只有 2xx 才接受；2xx ≠ SSE 完整 ≠ 远端已持久化。水位只折叠同 session id + 同 generation 的最大 `throughSeq`，fork 从零；允许重复、禁止缺口。
- 系统消息显式 `interpolate: false`（默认 `true`）；配置用 `Volatile` + `.volatile()`，跨字段校验用 `.check()`。
- 升 Session 版本前先证明"不升不行"；迁移用 Stage，截点是逻辑事件数，未知不公开、**不以零替代**；旧 codec 不得为兼容当前功能放宽。

## 扩展面：Web、多模态、账号

- MCP 一服务器一连接；名字作用域内唯一；工具名带前缀；共享服务须独立于单个连接。
- 动态插件三级身份 Plugin / Package / Run；只停激活不删版本，`undefine` 才真删；跨半调用按 `pluginRunId` 授权；`probe()` 与 `mount()` 两条路径，清理不完整宁可阻塞。
- 多模态五通道：共享服务只登记名字，工具与限制归 provider，**同名第二次注册必须失败**；按 Agent / Session 计租，fork 与 reload 得全新状态；二进制先持久化后追加事件（只放内容寻址引用）；转写不是提交，不得直写会话；office 转换不创建 Session 事件。

| 附件准入上限（先于规范化） | 值 |
|---|---|
| 每消息 | ≤ 20 张、总字节 ≤ 200 MiB |
| 单张源图 | ≤ 50 MiB、≤ 64,000,000 像素、单边 ≤ 65,535 像素 |
| 规范化默认 | 长边 ≤ 2048 像素、编码 ≤ 4 MiB |

- 失败方向是关闭（fail-closed）：无 provider / 无权限 / 被拒绝三种都给**明确失败**，不静默降级。
- Web：状态归 Client model、位置归 Slots、跨包行为归注入 service、声明只走 `import type`；入口 `dsh.client` + `exports["./client"]`，缺 bundle 组合期报错；多提供方未配 id 抛 `WEB_PROVIDER_AMBIGUOUS`。
- `available()` 只做廉价本地检查，"能不能发出去"归 `ready(llmProvider)`。**安全**：`web_fetch` 不归文件沙箱管，loopback / 内网 / 云元数据主机都可达 → 靠网络隔离、`tools/pre-execute` 或不挂载抓取工具。
- 账号：凭证只在 Host 解析，消费方只说目标地址，撤销靠 `revoked`；分享 = 档位 + 独立开关 + 上限名单，`fork` 与 `view` / `write` 正交，任何环节不推断出 `write`；展示面数据走仅写日志事件，UTC+8 偏移 `28800`。

## 构建、门禁与评审

- 环境：Node **24.9+**（CI 覆盖 24.9 / 最新 24 / 26），须启用 TS 类型剥离；pnpm 经 Corepack 固定 `pnpm@11.28.5`；Git 2.26+。命令链：`pnpm install` → `doc-sync` → `constraints` / `typecheck` / `lint` → `build` / `hygiene`。

| 改动面 | 最小命令集 |
|---|---|
| 单包源码 | 该 aggregate 的 build / check（先判 Host 还是 Client） |
| 只要类型 | `build:check`，但必须在最近一次 `build:artifacts` 之后 |
| 新 worktree | 先 `build`，否则 `hygiene`、`lib/*.js` 检查全假失败 |
| 跨两侧 | 两侧都跑（只有共享 leaf 与七个拆分包跨侧） |
| 共享主机 | 压低 `DSH_GATE_CONCURRENCY`（默认取宿主 CPU，非容器配额） |

- 覆盖率门禁 `pnpm run test:coverage`：`packages/*/*/src` **按文件 100%**，必要非充分；未覆盖行优先按**死代码删除**；`packages/shell/pwsh-local/src` 需真实 `pwsh`。
- 新守卫必须证明能变红：引入回归 → 观察红 → 回退；两种情况都通过的守卫什么也守不住。
- mock 只放 LLM 适配器 / 网络 / 时钟；e2e 断言外部世界（重跑命令、重读文件、逐字节比对），不打真实入口（`lib/bin.js`）等于没测；`workspace.expected/` 绝不被改写。
- CLI：换组合用 `--profile`；`--dump-config` 与 `--dump-default-config` 求差；`--public-url` + `--trusted-host` 成对；`--tls-cert` 与 `--tls-key` 互要求；`--host` 拒通配；launcher flag 在 app 参数**之前**。
- 评审：每条意见落到**引入它的那层**（在错误层级修 = 对上游评审者隐藏问题）；每项修复一个独立 commit；改写推送用 rerere + lease，不用 `--force`；改写后必重读线程与可合并性。

## 气味速查

| 信号 | 你以为 | 实际 |
|---|---|---|
| 换 provider 就得改消费方 | 实现问题 | 消费方按名字分支了 |
| 插件静默 PENDING | 加载失败 | `inject` 无人提供，或漏了 `dsh-tools` / `dsh-system-prompt` |
| 热重载一轮多一份回调 | 内存泄漏 | 裸 timer 没进 `ctx.effect()` |
| 加了监听器但行为没变 | 顺序问题 | `emit` 想改结果，或 `waterfall` 忘了 `next()` |
| 一次工具调用两条结果 | 模型抽风 | 工具体自己发了 `tool/result` |
| `deny` 怎么也放宽不了 | 权限 bug | 后置阶段拿不到产物 |
| 回放复现不出上下文 | 回放 bug | 出现了第二条真源 |
| `cordis.yml` 改一行运行态全丢 | 玄学 | 条目缺 `id`，或 `Config` 没 schema |
