# 第 28 章：会话与对话

## 核心思想
会话日志（Session log）是一份由类型化 `SessionEvent` 组成的仅追加日志，是 agent 交互历史的唯一真源；模型看到的 `Message[]` 从它**派生**、从不单独存储。压缩、客户端视图、搜索、标题、遥测都只是沿同一份日志做的不同折叠，所以判断一个会话层设计是否站得住只需问一句：它有没有偷偷引入第二条真源。

## 框架与方法

- **仅追加事件日志（append-only `SessionEvent`）**
  - 何时用：任何需要记住「agent 侧发生了什么」的场合。
  - 怎么做：`seq` 恒等于日志长度（严格连续），`data` 必须无损 JSON——`Session.append` 用 `isJsonValue` 在入口校验，坏事件在 append 处失败而不等落盘；`SessionEventMap` 可经 declaration merging 扩展（compaction 加 `compaction/*`，钩子桥接加 `hook/*`）。未知事件默认**必需**，只有纯信息性记录才标 `ignorable: true`——读取器遇到不认识的必需事件必须拒绝重建，忘记标记只会多拒绝，不会悄悄恢复出被掏空的会话。

- **表面操作（`SurfaceOp` / `SurfaceIntent`）**
  - 何时用：任何会出现在模型上下文里的事件。
  - 怎么做：`SurfaceEventType` 只有五种（`system/message`、`developer/message`、`user/message`、`assistant/message`、`tool/result`），必须声明如何进 surface：`'append'`，或 `{ op: 'replace', startSeq, endSeq }` 替换闭区间节点，且 `sourceEventSeqs` 必须含每一个被遮蔽节点。`assistant/message` 例外——它内嵌精确 provider stream，禁止引用来源事件；非 surface 事件在编译期即被拒绝该参数。

- **派生历史（`deriveMessages()` / `deriveEventMessage()`）**
  - 何时用：每轮组装请求、在 DSH 之外重建同一段历史。
  - 怎么做：逐节点纯函数加缓存——纯尾部增长只花 O(新增节点)，`replace` 或插件消息改动才整段重建；返回数组每次新建，元素共享且深冻结，「改历史」在类型上写不出来。只有四类事件产出消息，`turn/*`、`step/*`、`assistant/attempt` 是结构信息；内容为空的 `assistant/message` 也跳过，故 max-tokens 截断的空步不污染 transcript，而 `usage` 仍从内嵌 stream 展开。

- **插件拥有的消息投影（message projection）**
  - 何时用：把既有消息换一种表示（如图片卸载），而非追加新消息。
  - 怎么做：事件用 `@messageProjection` 标记，经 `ctx.sessions.registerMessageProjection()` 注册纯 `project(event, context)`，返回以原始 seq 为键的被改动消息。Session 提交前校验完整决策、应用不可变更新并推进 `contentGeneration`；缺处理器一律拒绝，恢复与独立折叠也不例外。

- **投影 seam（`ctx.sessionProjections`）与零工作量不变式**
  - 何时用：某个派生状态要被客户端看到，或要被便宜地缓存。
  - 怎么做：三方分工是硬约束——Service Definition 与注册表、领域贡献方（每领域一个纯单元）、载体。**框架驱动、领域计算**：注册表只订阅一次 `session/event`，把每个已提交事件折进每个单元；领域不持有订阅，客户端从不折叠领域事件。单元 = `key` + `stateSchema` + `init` + 纯 `apply` + 可选 `wire` + `stateVersion`，全部同步（异步会撕开一致性切口），state 必须纯 JSON。`apply` 对不关心的事件必须**返回同一个引用**：注册表按 `Object.is` 判变化，引用不变即零下游工作——这是契约，不是优化。

- **水位线、读阶梯与摘要投影**
  - 何时用：载体切页、列表行、冷读——同一个值要按不同代价取到。
  - 怎么做：`snapshot(session, keys?)` **完全同步**（载体在同一 tick 切页面切片，`asOfSeq` 是所有值都反映到的最后一个事件 seq，空日志 `-1`），值出门前过 `viewSchema`。四级读阶梯共用一条配方（缓存状态 + 尾部回放 + `view`）：`viewCheckpoint` 零 I/O → `cachedSnapshot` 取列表缓存 → `restore` 从行起步只回放尾段 → 全量从 `init` 重折；`restoreFloor` 返回「最低可用水位线再往下一格」，这一格承重，尾部读从它起才能识破崩溃修复截短日志后的旧行。列表行只吃摘要键：`SessionProjectionSummaryExcluded<T>` 是类型级排除标记，`wire.summary: false` 决定运行时键集合，`summaryKeys()` 返回**稳定实例**喂给同一组带 key 的读面——不存在摘要专用读取面。

- **查询 seam（`ctx.sessionQuery`）与 surface 三分类**
  - 何时用：不恢复 Agent 就读冷会话、跨会话搜内容、查血缘与事件因果。
  - 怎么做：语料库 live-preferred。过滤器数组内 AND、子句内值 OR、范围两端包含；`text` 是对**语义文本**做字面量、忽略大小写、容忍空白的扫描——含消息、工具调用与结果、待办、失败与状态详情，不含推理块、被拦下的提示词、结构事件与流分片。分类 `'current'`/`'shadowed'`/`'log-only'` 走与 `deriveMessages()` 同一个 `foldSurface()`。

- **跨会话引用（`session-reference`）**
  - 何时用：提示词里 `@` 另一个会话。
  - 怎么做：`SessionReferenceInput` 只带 `sessionId` 与可选 `label`——**id 才有权威性**。`prepare(...)` 用目标路由的上下文容量定预算，返回去掉 mention token 的 `content` 加最多一个聚合 `additionalContext`。`capturedThroughSeq` 是**被引用会话原始 generation 里的坐标**，绝不重解释为当前会话 seq；候选发现只从投影读标题（回落 id），绝不搜 transcript。

- **压缩：锁、位置跨度、先剪枝（`compaction/*`）**
  - 何时用：`pressure` / `context-overflow` 触发的自动策略，以及空闲时的手动缩减。
  - 怎么做：三个事件全部仅写日志、有意不扩展 `SurfaceEventType`——摘要承载在另一条带 `replace` 的 `user/message` 上。锁括住整个操作且在**最后**释放，中途崩溃就留下「有 start 无 end」的可检测遗留锁；较新 `session/end-seed` 之前的未匹配 start 是上个生命周期的陈旧证据，直接忽略。`shadowedRange` 是**表面位置**首尾而非数值区间：先前一次 `replace` 会把高 seq 的新摘要放到老位置，`start` 可能大于 `end`，判据永远用按表面顺序的 `shadowedSeqs`。区域两端必须 balanced（`toolPairingBalancedBefore/After`），保持工具配对但不保持整个轮次；够条件后先 `ctx.toolResultPruner` 剪枝、`ctx.tokenMeter` 重测再决定是否摘要；失败恢复走 `compaction/summary-error`。

- **spill 存储（`ctx.spillStore`）**
  - 何时用：结果太大不值得进上下文，但仍要能取回。
  - 怎么做：唯一操作 `saveText → SpillRef{locator, bytes, retrievalHint}`。请求带 `owner.sessionId`、`source`（`tool` 或 `session-reference`，描述性来源、**绝非访问控制**）、`suggestedName`（消毒成单个安全路径段，是提示不是路径）。`SpillLocator` 是品牌化不透明句柄，本地后端渲染成路径、远程后端可以是 URI，消费方只按 `retrievalHint` 渲染、绝不解析。本地后端根私有 `0700`、会话子目录 `sha256(sessionId)`、以 `open(...,'wx',0o600)` 排他写入防预置符号链接。存储失败时它拒绝，降级由消费方定：策略消费方保留内联结果，绝不把成功调用变成 `isError`。

- **遥测（ledger / ops 与脱敏 waterfall）**
  - 何时用：把会话事件送去外部可观测性后端；上报数据永不进模型请求。
  - 怎么做：每条权威事件一一镜像为有序 `ledger` 记录；`ops` 通道只承载 `agent-error`、`shutdown` 两个无日志归属的信号，并**刻意不带 `event.seq` 那类身份**以免被误当 ledger 行。游标标记「已交接」而非「已送达」，故 ledger 按 `(session.id, session.format_version, event.seq)` 去重，ops 重复被容忍。`session-telemetry/record` 是脱敏 waterfall，**自身不带任何规则**：不挂监听器时记录原样到达后端，导出数据有多干净等于部署方挂了什么规则；抛异常的监听器 fail-closed 扣下那条。

- **后写覆盖的标题（`session/title` + provider）**
  - 何时用：列表、`@` 候选等需要人可读名字处。
  - 怎么做：`SessionTitleEventData` 记 `title`、生成它所用的**精确人类消息 seq 集合**（显式重命名为空）、`source`（`fallback`/`provider`/`user`）；投影键 `title` 的版本 1 状态与客户端视图只存字符串或 `null`，旧缓存行仍可读。用户重命名写 `source: user` 并**钉住**标题：在飞生成被取代、后续消息不再调度，只有显式 `refresh()` 才是刻意解钉。

- **Conversation 组装（`ui-conversation`）**
  - 何时用：让一类事件在 Chat / Trajectory 里显示成卡片。
  - 怎么做：入口只有 `{type:'event'}` 或 `{type:'transient'}` 两种 entry，不另开 history stream；每 Session 一个 `ConversationNodeAssembler`，为每个 view target 发布独立 source。`match(event)` 是**身份提取器而不是 fold**：只收当前一个事件，返回内部 id 与 `start`/`update` 角色；最早 start 初始化 State，只有 update 时 Context 保持 pending 直至更早分页补上 start；`exclusive: true` 在某 target 上认领事件，结果与注册顺序无关。渲染是 keyed renderer，只读 `node.data` 与受控 Location hook，不得扫描事件窗口。四条更新路径（replace / prepend / append / flush 失败重建）必须长出同一份结果；一条新事件 = D 次匹配 + 一次常数时间查找。

## 关键概念

- **`SessionEventMap`**：仅追加的事件词汇表，每键是一个事件类型与 payload 形状，可经 declaration merging 扩展。
- **`SurfaceOp`**：事件进入 surface 的方式——`'append'`，或带闭区间 `startSeq`/`endSeq` 的 `replace`。
- **`deriveMessages()`**：把日志投影为模型所见的 `Message[]`，缓存在 surface 节点上；每次返回新建数组、共享深冻结消息。
- **`contentGeneration`**：位置替换与插件消息改动的单调计数，增量消费方据此区分「纯尾部增长」与「重写」。
- **`asOfSeq`**：一次投影快照的水位线，即所有值都反映到的最后一个事件 seq，空日志为 `-1`。
- **`ProjectionDefinition`**：一个领域的纯折叠单元（`key`、`stateSchema`、`init`、`apply`、可选 `wire`、`stateVersion`）。
- **`shadowedSeqs`**：被替换遮蔽的 surface 节点 seq，按表面顺序——判据，而非数值区间。
- **`SpillLocator`**：品牌化的不透明模型句柄，消费方只按 `retrievalHint` 渲染、不解析。
- **`ConversationNodeDefinition`**：Client 侧把一个 `(kind, id)` 事件族折成 State 与 target node 的声明。

## 心智模型

- 把日志看成**唯一账本**，`deriveMessages()` 看成一次报表计算：报表可重算、可缓存、可冻结，但绝不能被当成账本本身去改。
- 当你要加一条会出现在模型眼前的记录，先回答「它怎么进 surface」：答不出 `append` 还是 `replace`，说明还没想清这是新增上下文还是改写上下文。
- 把投影 seam 看成**一次订阅、多方受益**：注册表订阅一次，每个领域只贡献一个纯函数；在领域里自己订阅日志，就是在复制驱动逻辑。
- 把读阶梯看成**同一配方调不同火候**：零 I/O 读行、按 header 取缓存、从行起步回放尾段、全量重折，四条路必须产出同一个值。

## 反模式

- **把消息历史另存一份**：一旦有第二条真源，`replace`（压缩）、插件消息投影、fork 边界都会在两侧产生无法对齐的偏差，回放也不再能复现同一个上下文。
- **在 `apply` 里返回新对象当作「没变化」**：`Object.is` 判不出语义相等，于是每个事件都被当成变更推送，变更流形同虚设。
- **把投影单元写成 async**：载体「同一 tick 的一致切口」被撕开，`asOfSeq` 与 `values` 不再来自同一个日志位置。
- **用 `create()` 建一个必须与自己的 loop 同序拆除的会话**：应改用 `prepare` + `enter` + `announce` 折进同一个 `ctx.effect`，否则 fiber 卸载时发布钩子可能先于收尾事件被移除。
- **改了 `apply` 语义却不升 `stateVersion`**：按旧语义折出的缓存行仍被当作可用；schema 能通过不等于语义等价。

## 代码/配置示例

投影单元的契约形状（同步、纯、引用不变即零工作量）：

```ts
interface ProjectionDefinition<K extends string, S> {
  key: K
  stateSchema: ZodType<S>            // 校验持久化状态，之后才允许作为折叠起点
  init(header: SessionHeader, inheritedEventCount: SessionLogOffset): NoInfer<S>
  apply(state: NoInfer<S>, event: SessionEvent): NoInfer<S> // 不关心就返回同一个引用
  wire?: {                           // 客户端视图；host 专用单元省略
    viewSchema: ZodType<SessionProjectionViewValue<SessionProjectionMap[K]>>
    view(state: NoInfer<S>): SessionProjectionViewValue<SessionProjectionMap[K]>
    summary?: boolean
  }
  stateVersion: number
}
```

表面操作与派生历史：

```ts
session.append('user/message', msg, { surfaceOp: 'append' })

// 压缩用替换：遮蔽 startSeq..endSeq 的全部 surface 节点
session.append('user/message', summaryMessage, {
  surfaceOp: { op: 'replace', startSeq, endSeq },
  sourceEventSeqs: shadowedSeqs,   // 必须覆盖每一个被遮蔽节点
})

const messages = session.deriveMessages() // 冻结的派生历史
```

## 参考表

核心事件类型与表面身份：

| 事件 | 是 `SurfaceEventType` | 投影为消息 | 作用 |
| --- | --- | --- | --- |
| `turn/start` / `turn/end` | 否 | 否 | 轮次边界，`turn/end` 带 `TurnEndReason` |
| `step/start` / `step/end` | 否 | 否 | 一次模型调用及其工具执行的边界 |
| `user/message` | 是 | 是 | 人类提示词、注入上下文、目标续轮，靠 `source` 区分 |
| `developer/message` | 是 | 是 | 增量会话变更，可带 `headerSeq` 指向工具定义 |
| `system/message` | 是 | 是（空节点不产消息） | 系统指令与通告，节点 0 由首次装配保留 |
| `assistant/message` | 是 | 是（内容为空则跳过） | 内嵌精确 provider stream 与可选 `usage` |
| `assistant/attempt` | 否 | 否 | 未提交任何表面消息的模型尝试 |
| `tool/call` / `tool/result` | 后者是 | 后者是 | 工具调用（原始 JSON 串）与结果（可带 `error`、`meta`） |
| `request/header` / `request/context` | 否 | 否 | 请求信封快照与路由元数据 |
| `session/end-seed` | 否 | 否 | 种子历史与实时工作的分界标记 |

压缩事件与职责：

| 事件 | 载荷要点 | 作用 |
| --- | --- | --- |
| `compaction/start` | `{ turn }`，`null` 表示独立手动尝试 | 获取日志记录的锁 |
| `compaction/summary` | 摘要、`shadowedRange`、`shadowedSeqs`、token 估算、provider/model | 记录选中范围与被遮蔽节点 |
| `compaction/end` | `{ turn, error? }` | 用相同归属值释放锁 |

投影读取的四个档位：

| 档位 | 入口 | I/O | 新鲜度 |
| --- | --- | --- | --- |
| 零 I/O 读行 | `viewCheckpoint(rows, keys)` | 无 | 与行同旧，但不会错 |
| 列表页缓存 | `cachedSnapshot(meta, keys)` | 无 | 与最近一次 checkpoint 同旧 |
| 行起步回放 | `restore(checkpoint, events, baseSeq, …)` | 只读尾段 | 到日志末 |
| 全量重折 | 同上，`baseSeq = 0` | 读全日志 | 到日志末 |

## 实例演练

场景：压缩生效，而客户端正打开着这个会话。

1. 压缩插件追加 `compaction/start` 取锁，生成摘要，写 `compaction/summary`（记 `shadowedRange` 与 `shadowedSeqs`），再追加带 `replace` 的 `user/message` 承载摘要，最后才 `compaction/end` 释放锁。
2. `SurfaceManager` 提交前校验候选：两端都是当前 surface 节点、来源集合完整、位置替换合法；通过后 `replaceGeneration` 与 `contentGeneration` 各 +1。
3. `deriveMessages()` 见 `contentGeneration` 变化，放弃缓存重建：被遮蔽节点从派生历史消失，新节点在原位置出现，`usage` 仍从内嵌 stream 展开。
4. 投影注册表收到同一个 `session/event`，把替换折进每个单元；只有 `view` 结果真的按 `Object.is` 变了的单元触发 `onChanged`。载体切页时 `snapshot(session)` 的 `asOfSeq` 就是这条替换的 seq——页面里不会出现「一半旧历史、一半新摘要」的裂缝。
5. 离线读者走 `session-query`，用同一个 `foldSurface()` 打上 `current` / `shadowed` / `log-only`，所以「这条命中已不在模型上下文里」与派生侧判断一致；列表行只取 `summaryKeys()` 那一小块。

## 关键要点

1. 消息历史永远从日志派生，别存第二份；要缓存就缓存投影，别缓存真源。
2. 新增事件先定三件事：是否 surface、`ignorable` 是否有理由、payload 是否无损 JSON；任一件含糊都是磁盘格式的破坏性变更。
3. `apply` / `view` 的引用不变式同时决定性能与正确性，写单元时第一优先保证它。
4. 读已占用的投影走 `stateOf` / `snapshot`，读已存的行走 `viewCheckpoint`，读冷会话走 `restore`——不要自己拼第三条路。
5. `replace` 的 `sourceEventSeqs` 必须完整覆盖被遮蔽节点，`shadowedSeqs` 才是判据；这是不出「幽灵上下文」的唯一保险。
6. 摘要键集合只由 `summaryKeys()` 定义，读面复用同一组带 key 的入口。
7. 需要与会话同序拆除时用 `prepare` + `enter` + `announce`，不要用 `create()`。

## 关联

- **第 6 章**：`session/event`、`session/flush`、`session/created` 在事件矩阵里的模式决定了你能在这条日志上做什么。
- **第 21 章**：Cordis 服务与生命周期是 `ctx.sessions`、`ctx.sessionProjections`、`ctx.sessionQuery` 这些 seam 的注册地基。
- **持久化章节**：日志「如何落盘」（JSONL、崩溃恢复、迁移）是兄弟文档职责；本章只约定后端无损保存每个事件且 `seq` 连续。
- **subagent / fork**：`buildForkSeed`、`inheritedEventCount`、`session/end-seed` 是子会话继承父历史的机制。
- **capability seam**：压缩、spill、遥测都遵循「Service Definition + Provider + Consumer」的三方分工。
