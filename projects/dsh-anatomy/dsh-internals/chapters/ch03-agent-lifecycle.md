# 第 3 章：Agent 生命周期与会话格式

## 核心思想

一个**轮次**（turn）包含零个或多个**步骤**（step），每一步是一次模型请求加上它调用的工具；持久事实全部落在 `session/event`，实时控制与状态全部留在 `agent/*`。与之配套的第二条纪律是：会话格式只有一个手工维护的写入器常量，历史通过不可变的相邻迁移链逐级转换，发布与否由「定稿记录 + 发布记录」两条独立记录判定。两条纪律共用同一个判据——回放。

## 框架与方法

- **轮次与步骤（turn / step）**：步骤是一次模型请求加上它调用的工具；轮次包含零个或多个步骤，在领取首条输入之前打开，在不再欠下任何工作时关闭。
  - 何时用：读任何 `turn/*`、`step/*` 事件之前，先把这两个层次分清。
  - 怎么做：把轮次看成一张欠账清单——只要「工具还欠一次请求」或「又来了下一步输入」就再领一个步骤，两者都没有才收尾。首次领取被拒绝或为空时仍留下不花步骤的持久轮次。
- **双通道纪律（`session/event` vs `agent/*`）**：持久的回放事实保存在 `session/event` 中，实时控制与状态保存在 `agent/*` 中。
  - 何时用：需要决定「这个信息放哪」时。
  - 怎么做：需要可回放 transcript 数据的消费方（例如 SDK 用户）只消费 `session/event`；`agent/*` 是用于队列与状态、提示词拦截、请求构造、steering（中途引导）、继续执行和错误处理的实时协调接口。
- **准入三连（resolve / assemble / pre-step）**：驱动器为每个提议步骤解析一次工具集，组装系统提示词，然后让 `agent/pre-step` waterfall（瀑布式事件）给出权威裁决。
  - 何时用：任何想「拦一下这次请求」的插件。
  - 怎么做：`resolve({ agent, modelSelection, signal })` 每个提议步骤调用一次；`system-prompt/assemble` 携带该步骤的工具集；`agent/pre-step` 返回 `reject` 或 `enter(messages)`。以返回的决策为准，包装 `next()` 的监听器会保留下游消息与 `startsRequestSeries`，除非有意替换。`enter` 决策可设置 `startsRequestSeries`，循环据此记录新的 `request/header`（原因为 `series`，或在封装同时变化时为携带 `startsSeries: true` 的 `change`）。
- **提交与取消（admission / cancel）**：`step/start` 之后，`agent/request` waterfall 在不改变提供方、模型或推理强度选择的前提下调整控制参数，`prepareCall(config, signal)` 绑定适配器，随后是一次同步准入。
  - 何时用：要判断「取消之后到底提交了什么」时。
  - 怎么做：在任一异步阶段取消，都不提交系统候选与已接纳用户消息。准入后按节点顺序写 `system/message`，逐条写 `user/message`，按需写 `request/header` 与 `request/context`，再从日志派生并冻结请求；循环发送不可变请求，同时保持取消有效。
- **流的持久化（`assistant/message` / `assistant/attempt`）**：`assistant/message` 记录每次成功的提供方调用，包括返回空内容或以 `max-tokens` 结束的调用，并嵌入精确的紧凑带时间 stream；空内容不进入派生历史。
  - 何时用：处理失败、重试、取消与流错误时。
  - 怎么做：失败、重试、取消或 stream error 的 attempt 到达 settlement 时，若没有 surface message，就把 stream 记录为 `assistant/attempt`（不添加模型历史），然后发出 committed end，再由 `agent/request-error` waterfall 决定返回重试动作还是保留原始错误。实时 `agent/assistant-stream` 的 chunk frame 是瞬态数据；回放只读任一种持久 settlement，进程若在 settlement 前硬中断，则不会留下持久 attempt stream。
- **重试与压缩（retry / compaction）**：`dsh-compaction-basic` 在派生请求之前通过 `agent/pre-step` 处理压力，而 `agent/request-error` 仅用于规范的上下文溢出。
  - 何时用：上下文压力或提供方返回溢出错误时。
  - 怎么做：任一触发条件满足后，先执行可选的工具结果剪枝，再选择摘要；恢复发生在仍打开的步骤内，只有剪枝或摘要生成推进了 surface replacement generation 才重试，否则仍以原始请求错误为准。每次重试都会准备调用，并在派生请求之前协调保留的已渲染组装结果——不重复组装、不重复 `pre-step`、不重复用户消息准入。
- **工具批次与收尾（batch / turn-stopping）**：模型成功后按其 `executionMode` 分类待执行调用，在 barriers 与有界滚动池中运行，启动前重新分类。
  - 何时用：要理解「哪些工具并行、结果按什么顺序落」。
  - 怎么做：`tool/call` 先记录，再有序列 `pre`、并发 `execute`、就绪即按模型顺序 `post`，然后写 `tool/result`。步骤结束写 `step/end` 并 dispose 该步骤工具集。自然停止且下一步 inbox 为空时，`agent/turn-stopping` 作为 serial 终检点触发；还有 pending 输入则先认领再回到 `agent/pre-step`。最后写 `turn/end`，状态回 `idle`。
- **写入器版本单一真源（`SESSION_FORMAT_VERSION`）**：核心 Session 类型中的这个常量是代码里唯一手工维护的当前写入器版本号。
  - 何时用：任何涉及格式升版本的改动。
  - 怎么做：目录生成器推导 codec 顺序，并检查相邻迁移是否到达该版本。包版本、codec 导出名称、fixture 文件名或投影缓存版本都不是写入器版本的权威来源。
- **双记录治理（finalization / release records）**：定稿记录标识已接受的兼容性基线，发布记录标识已发布的格式，两者独立验证。
  - 何时用：想知道「这个格式能不能改」时。
  - 怎么做：满足读取器兼容性规则并记录所需评审时，schema 变更可以保留 V4；升版本决策要求更高的写入器版本及自身的头版本转换，不能复用已接受的 3→4 转换。不另行维护 released 布尔值——比较写入器常量与已核实的发布记录即可：相等表示已发布，写入器更高表示记录尚未收录。
  - 义务面：alpha、beta 或 release-candidate 发布都会确立已发布格式的义务，GitHub 的 prerelease 标记不会让持久用户数据变成可丢弃数据；缺少发布记录也不代表尚未发布。
- **不可变代际与相邻迁移（generation / migration）**：JSONL v0 使用 `session.jsonl[.zstd]`，v1 及后续版本使用小写 `session.vN.jsonl[.zstd]`；已提交 generation 路径绝不重命名、替换或删除。
  - 何时用：`open` 一个旧会话，或写一个新会话时。
  - 怎么做：只 header 的 `stat` 与 `list` 重新扫描每个 Session 目录、选择数值最高的规范 generation，并在不加载事件、不发布后继的情况下转换受支持的历史 header。`open` 选择同一 generation、拒绝未来版本，或只 Decode 并组合一次构建时静态确定的相邻迁移链，再返回校验过的当前逻辑事件。只读 `open` 直接使用这份内存结果、不发布后继；写 `open` 先编码、校验，并在未改变源的旁边排他发布最终版本命名的后继。JSONL provider 负责物理 framing、压缩、generation 选择与排他发布，每个相邻迁移包只负责一个 `vN -> vN+1` 步骤。

## 关键概念

- **轮次（turn）**：从领取首条输入到不再欠下任何工作的一个区间，可包含零个步骤。
- **步骤（step）**：一次模型请求加上它调用的工具，是工具集与提示词组装的单位。
- **inbox 与认领（claim）**：输入统一经同一个 inbox 到达驱动器；`agent/inbox/claimed { message, turn }` 逐条报告认领结果，持久 `inbox` 投影使待处理输入在没有活跃 Agent 时仍可读。
- **`agent/pre-step` 决策**：waterfall 给出的权威 `reject` 或 `enter(messages)`；`startsRequestSeries` 是它携带的序列声明。
- **settlement**：一次 attempt 的终局；决定它落成 `assistant/message` 还是 `assistant/attempt`。
- **surface replacement generation**：压缩改写表面时推进的代际；只有它被推进，重试才成立。
- **`SESSION_FORMAT_VERSION`**：唯一手工维护的写入器版本常量；它的数值以代码为准，记录只用来判定发布状态。
- **规范 generation（canonical generation）**：同一 Session 目录下数值最高、格式受支持的已提交产物。
- **相邻迁移链**：构建时静态确定的 `vN -> vN+1` 步骤序列，每个包只负责一步。

## 心智模型

- 当不确定一个信息该不该持久时，问一句「回放这次会话还需要它吗」——需要就是 `session/event`，不需要就是 `agent/*`。
- 把 `agent/*` 看成控制面、`session/event` 看成数据面：控制面可以丢，数据面不能丢。
- 把轮次看成欠账清单，把步骤看成一次结账：欠着请求或工具结果就不能关轮次。

## 反模式

- **用 `agent/*` 承载可回放数据**：实时事件在进程内，重载后不存在；SDK 侧要 transcript 就必须消费 `session/event`。
- **把失败 attempt 塞进模型历史**：`assistant/attempt` 明确不添加模型历史；把失败写进历史会让下一次请求看到模型从未见过的内容。
- **直接改已提交的 generation 文件**：路径绝不重命名、替换或删除；改写只能通过排他发布新代际完成。
- **升版本时复用旧的相邻迁移**：升版本决策要求更高的写入器版本及自身的头版本转换，已接受的 3→4 转换不可复用。
- **在产品发布前推进发布记录，或把记录降低**：发布记录只在产品首次发布更高格式时前进一次，开发主干上的记录绝不降低。

## 代码/配置示例

一次轮次的事件骨架（`->` 为持久会话事件，`~~>` 为实时事件）：

```text
followup(content)
  ~~> agent/inbox/spliced ; agent/inbox/inserted { message }
  ~~> agent/status running
  -> turn/start
     claim pending next-step input + one queued prompt
     ~~> agent/inbox/claimed { message, turn }
     resolve({ agent, modelSelection, signal })   // 每个提议步骤一次
     system-prompt/assemble                        // waterfall，携带该步骤工具集
     agent/pre-step                                // waterfall -> reject | enter(messages)
     -> step/start
        agent/request                              // waterfall
        llm.prepareCall(config, signal)             // 两个异步阶段，取消即不提交
        -> system/message (按节点顺序) ; -> user/message (逐条)
        -> request/header / request/context (按需)
        derive + freeze request from the log
        llm/stream                                  // waterfall
          ~~> agent/assistant-stream chunk*
        -> assistant/message | assistant/attempt
        -> tool/call* -> tools/pre-execute -> tools/execute -> tools/post-execute -> tool/result*
     -> step/end ; dispose step tool set
     agent/turn-stopping                            // serial 终检，无 next()
  -> turn/end
  ~~> agent/status idle
```

格式记录（原文的机器可读块）：

```yaml
# session-format-finalization
latestFinalizedVersion: 4

# session-format-release
latestReleasedVersion: 4
evidenceTag: dsh-v0.2.0-rc.2
# 该标签的写入器路径：packages/core/session/src/types.ts
```

## 参考表

事件归属与语义：

| 事件 | 域 | 性质 |
|---|---|---|
| `turn/start`、`turn/end` | 会话 | 持久；轮次边界 |
| `step/start`、`step/end` | 会话 | 持久；步骤边界 |
| `system/message` | 会话 | 持久；按节点顺序协调 |
| `user/message` | 会话 | 持久；逐条已接纳消息 |
| `request/header`、`request/context` | 会话 | 持久；按需记录 |
| `assistant/message` | 会话 | 持久；含内嵌紧凑带时间 stream |
| `assistant/attempt` | 会话 | 持久；不加模型历史 |
| `tool/call`、`tool/result` | 会话 | 持久；单条模型可见结果 |
| `session/event` | 会话 | 广播通道；回放数据的入口 |
| `agent/inbox/spliced`、`inserted`、`claimed` | agent | 实时；队列变化与认领 |
| `agent/status` | agent | 实时；`running` / `idle` |
| `agent/assistant-stream` | agent | 进程本地；瞬态 chunk 与 committed end |
| `system-prompt/assemble` | agent | waterfall |
| `agent/pre-step` | agent | waterfall；权威 `reject` / `enter` |
| `agent/request` | agent | waterfall；只调控制参数 |
| `llm/stream` | agent | waterfall |
| `agent/request-error` | agent | waterfall；返回重试动作或保留原错误 |
| `agent/turn-stopping` | agent | serial；无 `next()` |

格式真源对照：

| 项 | 位置 | 当前值 |
|---|---|---|
| 工作区写入器 | `packages/core/session/src/types.ts` 的 `SESSION_FORMAT_VERSION` | 以代码常量为准 |
| 定稿记录 | `session-format-finalization` 块 + `persistence-changes/finalized/v4.json` | `latestFinalizedVersion: 4` |
| 发布记录 | `session-format-release` 块 | `latestReleasedVersion: 4`，`evidenceTag: dsh-v0.2.0-rc.2` |
| 物理产物 | JSONL provider | v0 `session.jsonl[.zstd]`；v1+ `session.vN.jsonl[.zstd]` |
| 权威性 | 上述之外的一切 | 包版本、codec 导出名、fixture 名、投影缓存版本均非权威 |

## 实例演练

场景：打开一个已发布的 v4 会话，追加一次 followup，并观察它落盘成什么。

第一步，`open`。消费方只了解当前逻辑格式，因此 `open` 选择数值最高的规范 generation；如果目录里只有 v3 产物，它拒绝「未来版本」这条路不适用，而是只 Decode 并组合一次构建时静态确定的相邻迁移链（`v3 -> v4` 一步），再返回校验过的当前逻辑事件。因为这次是只读打开，它直接使用内存结果，不发布后继——磁盘上仍是 v3。

第二步，认领。followup 让 inbox 发生变化，实时侧先报 `agent/inbox/spliced` 与 `agent/inbox/inserted { message }`，驱动器被队列唤醒，状态转 `running`，写 `turn/start`，认领「待处理的下一步输入 + 一条排队消息」，逐条报告 `agent/inbox/claimed { message, turn }`。

第三步，准入。每个提议步骤先 `resolve` 一次工具集，再 `system-prompt/assemble`，随后 `agent/pre-step` 裁决；若监听器把消息改写成两条并保留 `startsRequestSeries`，循环就按改写后的消息进入。

第四步，提交。写 `step/start` 后，`agent/request` 只调控制参数，`prepareCall` 绑定适配器。同步准入写 `system/message`（按节点顺序）与 `user/message`（逐条），按需写 `request/header`、`request/context`，再从日志派生并冻结请求。若此时用户取消，两个异步阶段任一处被取消都不提交系统候选与已接纳用户消息。

第五步，流与结算。`llm/stream` 产出 chunk，实时侧发 `agent/assistant-stream`；成功后写 `assistant/message` 并发 committed end。提供方以 `max-tokens` 返回空内容时它仍会被记录，但空内容不进派生历史。

第六步，工具与收尾。待执行调用按 `executionMode` 分类，在有界滚动池里跑；`tool/call` 先记录，有序 `pre`、并发 `execute`、按模型顺序 `post`，再写 `tool/result`，`step/end` 后 dispose 工具集。工具还欠请求就再领一个步骤，否则在 inbox 为空时触发 `agent/turn-stopping`，写 `turn/end`，状态回 `idle`。

若第一步用的是写打开，落盘顺序相反：先编码、校验，再在未改变源的旁边排他发布最终版本命名的后继；已提交的 v3 路径一个字节都不动。

## 关键要点

1. 轮次可含零个步骤；被拒绝的首批仍留下持久轮次，但不花步骤。
2. 判据只有一条：回放需要 → `session/event`；实时协调 → `agent/*`。
3. `agent/pre-step` 的返回是权威的；包装 `next()` 时要显式保留消息与 `startsRequestSeries`。
4. 成功调用进 `assistant/message`（含空内容与 `max-tokens`），失败/重试/取消进 `assistant/attempt`，且都不污染派生历史。
5. 取消发生在异步阶段时不提交系统与用户消息；请求一旦发出即不可变。
6. 格式版本只有一个权威常量；发布状态靠比较常量与发布记录得出，不维护布尔值。
7. 已提交 generation 永不改名；历史靠构建时静态确定的相邻迁移链逐级升版，只读打开不落盘。

## 关联

- **第 1 章**：架构总览给出轮次流程图与「模型可见即已记录」的纪律，本章把它展开成时序与落盘。
- **第 4 章**：`tool/call` 之后的三瀑布流水线细节。
- **第 6 章**：`agent/*` 与 `session/event` 的生产者／消费者矩阵。
- **第 28 章**：会话日志、投影、压缩与 spill 的子系统视角。
- **第 39 章**：新增会话格式版本的分步手册（用 N / N+1 表示相邻版本）。
- **外部概念**：事件溯源（event sourcing）——会话日志是事实流，`deriveMessages()` 是投影，迁移链是只增不改的 schema 演进。
