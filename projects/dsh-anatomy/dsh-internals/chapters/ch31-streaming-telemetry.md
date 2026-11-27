# 第 31 章：模型流式与可观测

## 核心思想

流式与可观测是同一问题的两面：**哪些事实必须留存，哪些只是运输途中的瞬态**。delta 是瞬态，`block-end`、`usage`、`finish`、`assistant/attempt` 是事实；中间层可以折叠，但折叠必须可逆（`expandAssistantStream()`），因为计费、追踪、重放都从持久记录重算，而不是从内存回调。

## 框架与方法

- **`StreamChunk`：封闭的可辨识联合 + `index` 关联**
  - 何时用：写适配器、写 waterfall listener、或要从流里读某条事实。
  - 怎么做：七个变体——`block-start`（`index`、`blockType`）、`text-delta`、`reasoning-delta`、`tool-call-delta`（`index`、`id`、可选 `name`、`argumentsDelta`）、`block-end`（携带组装好的 `ContentBlock`）、`usage`、`finish`（`reason` + 可选 `replayState`）。`index` 把交错 delta 归到所属块，`block-end` 交付成品，消费方不必重组。联合**封闭**：`switch` 以 `assertNever` 收尾，新增变体会在每个消费方编译失败。`arguments` 全程是**原始 JSON 字符串**。

- **适配器约定：九条消费方可以依赖的规则**
  - 何时用：新增适配器，或 review 实现是否合规。
  - 怎么做：① `usage` 在 `finish` 之前、其后无任何分片（两者都推迟到提供方的流结束标记，尾部 usage-only 分片才不违序）；② `arguments` 保持原始 JSON 字符串；③ 错误两条路径共用一个 `LlmFailure`——从 `stream()` 抛出，或以 `finish {kind:'error'|'aborted', failure}` 结束流；④ **一次调用=一次提供方尝试**，适配器禁用库重试，恢复靠 agent 层另开持久带编号轮次；⑤ `streamIdleTimeoutMs`（默认五分钟）只约束未完成的 `next()`，自身到期→`TIMEOUT`，更早的调用方中止→`ABORTED`；⑥ 溢出只有 `CONTEXT_WINDOW_EXCEEDED`，按 code 路由而**不读提供方文本**；⑦ 空 completion 是可重试的 `EMPTY_RESPONSE`，不是成功；⑧ 每个 HTTP 请求带 `attributionHeaders()` 作 `User-Agent` 基线；⑨ 回放状态归适配器，只有切分共享。

- **`ReplayEnvelope`：元数据与内容共用同一次保留/丢弃决定**
  - 何时用：把提供方私有状态带进持久 assistant 消息，或排查"回放数据与内容不一致"。
  - 怎么做：`finish` 可带 `{ response, blocks? }`——`response` 是不透明响应级元数据，`blocks` 与发射块序列**按 index 对齐**：丢块时同位置条目一并丢弃，长度不匹配则**整份丢弃**。`LlmRuntime` **仅在历史提供方与目标提供方当前注册到同一适配器实例**时传递它；无法使用的已存状态只把该消息降级为提供方无关转换并带出诊断，**不让请求失败**。

- **`BlockAssembler`：唯一共享的 fold 实现**
  - 何时用：需要组装结果又不想重写 fold；或要判断被中断的流能安全收尾哪些块。
  - 怎么做：`push(chunk)` 逐片喂入，读侧取 `blocks()` / `message(source)` / `usage` / `finish` / `replayState`。它对 delta-only 协议宽容；对已被 `block-end` 关闭的 index 再来的 delta **直接忽略**（畸形流）。`max-tokens` 丢弃每个工具调用（被截断的调用不能安全执行）并在同位置裁剪 `replayState`。中断时 `interruptedBlocks()` 只留 text/reasoning 且有非空白内容的块、**省略工具调用**（中断先于分派，保留它就得伪造结果）；流无 `finish` 即结束时返回 `{kind:'stop'}`。

- **`llm/stream` waterfall 与 `prepareCall()`：让注册绑定跨越整个调用**
  - 何时用：拦截请求（重试、回放、路由、短路），或需要模型解析与分派同属一个适配器代际。
  - 怎么做：`llm/stream(this, options, next)` 环绕每一次流式调用——调 `next()` 到达被解析适配器的流，或 yield 自己的分片短路；**适配器查找在终端 continuation**，所以 listener 能在查找前短路。循环构建的请求带进程本地 loop 标识并**深度冻结**（改动即抛），内容是日志的纯函数。要让日志记录与分派共享注册，用 `prepareCall()` → `PreparedLlmCall`（`retryPolicy`、`context`、`adapterDefaults`、`stream()` 等）：只能派发一次，复用或不符即 `INVALID_PREPARED_CALL`；直接分派走 `resolveCallConfig()`，只在 `maxTokens` 缺失时填默认并校验推理强度，**不钳制、不改名**。

- **`AssistantStreamAccumulator`：紧凑表示而非有损压缩**
  - 何时用：要从持久记录读首 token 时间、可见内容或最后一次 chunk。
  - 怎么做：每个 `StreamChunk` 与原始安全整数时间戳配对；同块连续的 text／reasoning／tool-argument delta 合成一条 record（`time0` + 精确间隔 + 每个原始 delta 一个成员），其余保留为带时间戳的 raw record。它去掉重复 event envelope，但**不合并 token 边界，不丢弃 terminal、usage、block、failure 或 replay 事实**，`expandAssistantStream()` 严格校验后可重建精确序列。日志把它嵌入 `assistant/message` 或 `assistant/attempt`；记录级读取器提前退出，大历史每次结算为 **O(records) 而非 O(members)**。

### 可观测三条线

- **Token 计量：`TokenMeasurement` 是可重放的快照，不是累加计数器**
  - 何时用：压缩压力、上下文占用、表层定价，或判断下次请求大概多贵。
  - 怎么做：`measure(session, requestHeader?)` 沿持久尾部重放，返回 `{ logRevision, baseline, surfaceDeltaTokens, totalTokens, surfaceTokens, nodes[] }`。`logRevision` 是生成每个字段时消费的持久事件数；`baseline.kind === 'usage'` 表示最近一次成功调用有**相同的规范请求 envelope** 且总量不低于其完整路由定价锚点，否则 `estimated`；`totalTokens` 是请求与响应压力，`surfaceTokens` 是节点价之和。成本 O(surface)。
  - 节点 `TokenSurfaceNode { seq, tokens, heuristicTokens }`：`tokens` 按**被测路由**定价（图片用路由声明的视觉价加模型可见文本）；`heuristicTokens` 与路由无关，**影子价格协议**用它给替换定价，使 O(1) 的投影 fold 与自己的 append 一致。表层顺序有权威性——替换节点的 `seq` 可高于位置在它后面的节点。
  - 显示与计价必须分开：`contextPressure()` 读最新 `pressureTokens`（未缓存输入 + 缓存读写，**不含输出**）与 `contextWindow`，客户端派生 `projectedTokens`（该压力 + 自采样以来表层增减的重定价，所以压缩遮蔽一段时立刻下降——压缩不报告 usage）。两者**故意不是一次原子观测**，各是不同时刻的 last-wins；它是参考值而非计费输入——**计价请用 `measure()`**，图片定价则由 `imageRequestPricing()` 声明、`llm.imageRequestPricing()` 同步解析，实现**不得做 I/O**。

- **OTel：共享工厂，不共享通道**
  - 何时用：把普通事件或 Session 日志送到 OTLP，且多个上报目标互不干扰。
  - 怎么做：`ctx.otel` 只持有传输与 SDK 聚合实现，提供 `createEventReporter(options)`（按计数批量）与 `createSessionLogReporter(options)`（按字节上限）。调用方自备 transport、resource、scope 与诊断选项并负责关闭；通道之间**不共享队列或请求**，关闭后不得复用；只挂载服务不分配 provider——不建队列、身份或连接。Session 日志通道先授权后脱敏：UI 反馈经 Remote API 到反馈服务，记录反馈后适配器才获得规范日志前缀的捕获授权。

- **产品埋点：只有提交，没有送达承诺**
  - 何时用：新增分析事件，或判断某字段能否采集。
  - 怎么做：`emit(record)` 同步入队即返回；`ProductTelemetryRecord` 要求事件名、字符串 body、Unix 毫秒时间戳，属性是标量或标量的**单层**对象，严重程度默认 INFO。入队**不代表送达**：SDK 批量重试，失败只留本地诊断。导出器**不自动采集** Session 数据或标识——桌面消费方自选事件、补缓存环境与可用身份、遵守启动开关，普通 Web 客户端不采集。`ctx.productAnalytics` 是鉴权入口：`enabled()`、`watchPolicy(signal)`、`report(event)` 本地提交后即返回。

### 跨 wire 的类型标识（Typert）

- **声明合并的空 map 定义"什么可以跨 wire"**
  - 何时用：某包要把 Host 对象或作用域上下文暴露给远程调用方。
  - 怎么做：业务包通过声明合并扩展 `TypertLookupMap`（Host 对象类型 ↔ wire identity）与 `TypertContextMap`（作用域上下文类别 ↔ wire identity），descriptor 引用这些 key。跨 wire 的不是对象而是**被声明过的 identity**：`InvocationDescriptor` 是本地反射、不是 wire message，请求只发 endpoint 与具名 `args`，参数 `source` 只有 `'json'` 与 `'lookup'`。

- **声明持久、resolver 瞬态：本章主线的类型侧对应**
  - 何时用：排查"提供方卸载后参数为什么没退化成普通 JSON"。
  - 怎么做：lookup resolver 卸载后注册表**仍保留其 wire 声明**（`key`、`wire`、两种 type symbol），SRC 发现过程继续把该参数当 lookup 并因不可用而失败，**而不是把 wire 值当普通业务对象接受**。三样东西不进 `args`：取消（带外 signal）、流式上行项（`RemoteStream<Out, In>` 的 `In` 只是类型标记，descriptor 只带 `uplink.codec`，经 `invocation.uplink()` 读取）、调用身份（`PeerScope.principal` 由进程内 Host 代码固定，**没有 wire 字段能设置它**）。

- **codec 两态、资源读取顺序与失败码**
  - 何时用：需要跨 wire 传字节，或判断一条调用会碰哪些资源。
  - 怎么做：`TypertCodec` 是 `strict`（带 schema factory 与 `typeSymbol`，可把字节投影成 RPC 附件）或 `src-json`（不恢复结构类型，只强制 JSON 安全值）。`TypertResourceMap` 让拥有身份类型的包声明 resource kind，`global` 是内置无身份资源、**从不作为 kind**；身份是 wire 值，**在任何 lookup 或 Context 解析之前**读取——非 owner 调用在参数校验后、lookup 前解析资源并问 `ctx.remoteAccess.decide()`，而**访问控制从不检查读者漏掉的资源**。`gateway/*` 码就是普通 `RemoteError` 码。

## 关键概念

- **`StreamChunk`**：适配器发射的原始流式协议，封闭七变体联合。
- **`LlmFailure`**：可序列化、提供方无关的失败 payload（`code`、可选 `status`、`providerRetryAfterMs`、`requestId`）。
- **`providerRetryAfterMs`**：经校验、由提供方请求的正数延迟，**是事实不是重试决策**。
- **`ReplayEnvelope`**：响应级不透明元数据 + 可选逐块元数据；切分是共享词汇，内容是适配器私有。
- **`TokenUsage`**：逐调用记账，**计数互不重叠**——`inputTokens` 只含未缓存输入，缓存单列。
- **`AssistantStreamRecord`**：与原始时间戳配对的紧凑流记录，遥测、记账与 Host 折叠直接读它。
- **`TokenMeasurement`**：某日志修订点上的压力与表层定价快照，不可变、不随 fold 增长。
- **`TokenSurfaceNode`**：表层节点；`tokens` 按被测路由定价，`heuristicTokens` 是与路由无关的影子价。
- **`ContextPressureProjection`**：面向状态显示的近似占用，字段故意非原子，不是计费输入。

## 心智模型

- 当你想在流里顺手算点什么，先问这条信息是 delta 还是事实：delta 只属于本次运输，事实必须落进 `usage`、`finish`、`block-end` 或持久 record。
- 把 `ReplayEnvelope` 看成"内容与元数据的配对不变量"：任何丢块都必须在同位置丢条目，否则宁可整份丢弃。
- 把 `prepareCall()` 看成给调用盖时间戳：拿到句柄的一刻，本代适配器的能力与端点就被锁死。
- 把 `TokenMeasurement` 看成重新称重而非计数器读数：每次 `measure()` 都从日志重放，因此永远与当前表层自洽，代价是 O(surface)。

## 反模式

- **在适配器里做库重试**：破坏"一次调用=一次提供方尝试"这个计量与恢复基准，重试次数与失败事实全部失真。
- **让消费方自己拼 delta**：`block-end` 就是为了消灭这件事；自己拼会重复实现 fold，并与 `max-tokens` 丢弃工具调用的规则打架。
- **把空 completion 当成功**：静默的空 `stop` 让上层以为模型答了话；它必须是 `EMPTY_RESPONSE` 并被默认重试。
- **把 `projectedTokens` 当准入门槛**：它是 last-wins 的显示值，换模型时会把新容量与旧压力配在一起。
- **在 `imageRequestPricing` 里发网络请求**：计量每次都要同步解析，I/O 会让计量变成阻塞点。

## 代码/配置示例

```ts
// 封闭联合：新增变体会让每个消费方编译失败
type StreamChunk =
  | { type: 'block-start'; index: number; blockType: ContentBlockType }
  | { type: 'text-delta'; index: number; text: string }
  | { type: 'reasoning-delta'; index: number; text: string }
  | { type: 'tool-call-delta'; index: number; id: ToolCallId; name?: string; argumentsDelta: string }
  | { type: 'block-end'; index: number; block: ContentBlock }
  | { type: 'usage'; usage: TokenUsage }
  | { type: 'finish'; reason: FinishReason; replayState?: ReplayEnvelope }
```

```ts
// 一次请求的三种事实来源：日志（可重建）、waterfall（可拦截）、assembler（可折叠）
const prepared = await ctx.llm.prepareCall({ provider, model, ...controls }, signal)
const stream = prepared.stream({ ...request, provider, model })   // 只能派发一次
for await (const chunk of stream) assembler.push(chunk)
assembler.blocks()      // 块；max-tokens 时工具调用已被丢弃
assembler.usage         // TokenUsage
assembler.finish        // FinishReason，缺省 { kind: 'stop' }
assembler.replayState   // 与 blocks 同步裁剪过的 ReplayEnvelope
```

```ts
// 观测：显示用投影，计价用 measure
const { pressureTokens, contextWindow } = ctx.tokenMeter.contextPressure(session)
const measured = ctx.tokenMeter.measure(session, header)   // O(surface)
measured.nodes.map(n => [n.seq, n.tokens, n.heuristicTokens])
```

## 参考表

| 事实 | 载体 | 是否可折叠 | 谁读它 |
|---|---|---|---|
| 逐字 delta 与相对时间 | `AssistantStreamRecord[]` | 可合成 record，不可丢成员 | 遥测、token 记账、Host 折叠 |
| 组装后的内容块 | `block-end` / `assistant/message` | 不可 | 下一轮请求、UI 回放 |
| token 计数 | `usage` → `TokenUsage` | 不可 | 计量、计费、压缩压力 |
| 结束原因 | `finish` → `FinishReason` | 不可 | agent loop、重试策略 |
| 适配器私有回放数据 | `ReplayEnvelope` | 随块裁剪，失配则整份丢弃 | 同实例适配器 |
| 失败事实 | `LlmFailure` | 不可 | 重试路由、诊断 |

三条观测线的分工与各自的边界：

| 线 | 服务 | 何时产生 | 持久锚点 | 明确的"不知道" |
|---|---|---|---|---|
| token 计量 | `ctx.tokenMeter` | 按需 `measure()` 重放 | `logRevision` + 生效 request header | 无 usage 锚点时降级为 `estimated` |
| OTel | `ctx.otel` | 调用方建通道后提交 | 通道内批量队列 | 挂载≠已配置；关闭后不得复用 |
| 产品埋点 | `ctx.productTelemetry` / `ctx.productAnalytics` | 消费方决定时机与字段 | 入队记录 | 入队≠送达≠仓库确认 |

## 实例演练

一次请求被拦下、失败、再被重试：

1. 循环从已记录的 `EpochHeader` 构建请求并派生历史，然后 `prepareCall()`：解析器返回分离的 `LlmCallConfig` 与 `ResolvedRetryPolicy`，并填入 `adapterDefaults`（如 `maxTokens`）；这些默认值在 waterfall 开始前被移除，所以提议里不含它们。请求冻结后进入 `llm/stream`，listener 只读，适配器查找发生在终端 continuation。
2. 适配器发出 `block-start`(0,text)、若干 `text-delta`，再 `block-start`(1,tool-call)、`tool-call-delta`……提供方返回 429 带 `Retry-After`，适配器规范化为 `LlmFailure { code, status: 429, providerRetryAfterMs, requestId }` 并从 `stream()` 抛出。
3. `LlmRuntime.stream()` 把异常规范化为终态 `error` finish，保留被抛出的确切 `Error`，并把不可变事实与实际服务注册对应的重试策略挂到这次调用（`llmRetryPolicyOf(stream)` 可读回，此后替换路由也改不了它）。
4. agent loop 先把 attempt stream 提交为 `assistant/attempt`，再关闭失败步骤，把错误、事实、**先前已重试的失败事实**、实际策略与轮次信号交给 `agent/request-error`。listener 修好后返回 `{ kind: 'retry' }`；未恢复则结构化失败成为轮次错误，这次 attempt **不**提交 surface assistant 消息或工具副作用。
5. 重试不是库行为：agent 层另开持久带编号轮次回到步骤 1，`prepareCall()` 重新捕获当前注册——这是"恢复策略不可变、能力可换代"的分界。

## 关键要点

1. 只把 `block-end`、`usage`、`finish` 当事实；delta 可折叠，但折叠必须能被 `expandAssistantStream()` 严格还原。
2. 适配器只做三件事：wire → `StreamChunk`、错误 → `LlmFailure`、私有状态 → `ReplayEnvelope`；组装、重试、计量都在 core。
3. 错误路由只认 `code`；`providerRetryAfterMs` 是建议，决策由捕获的 `ResolvedRetryPolicy` 做。
4. 一次调用只派发一次：要跨日志与分派共享注册就用 `prepareCall()`，别用裸 `ctx.llm.stream()`。
5. 计量永远从日志重放：显示值（`contextPressure`）与计价（`measure`）不要混用。
6. 上报通道自持：`ctx.otel` 不给默认 transport，`emit()` 不保证送达。

## 关联

- **第 13 章（协议扩展）**：`ctx.deepseekLlmApiExtensions` 与 request-header 扩展是同一套"提供方特定字段注册表"模式。
- **第 28 章（Session）**：`EpochHeader`、`assistant/attempt`、`assistant/message` 是本章所有事实的持久落点。
- **第 23 章（Events API）**：`llm/stream` 是 waterfall 的标准用例——`next()` 之前可完全替换结果。
- **第 39 章（Remote API 格式）**：`productAnalytics.report` / `watchPolicy` 是 `@Remote` 方法，跨进程形状由该章定义。
- **可重建性（reconstructability）**：请求内容为会话日志的纯函数，这是冻结与"listener 只读"的根因，也让 `EpochHeader` 成为可审的请求账本。
- **OpenTelemetry（外部概念）**：`ctx.otel` 不藏 OTel 语义——resource、scope 与 OTLP transport 按原样暴露。
