# 第 4 章：工具执行流水线

## 核心思想

内置执行器负责原始批次解析、调度、取消和 Session 调用／结果日志；真正把关的是一条**共享调用流水线**。`tools/pre-execute` 瀑布先执行，然后是单调守卫，再是 `tools/execute` 与 `tools/post-execute` 瀑布——三个瀑布都可以**转换调用**，而无需改动循环。这条流水线把策略、钩子、沙箱、文件系统守卫、结果改写、最终结果观测和 UI 呈现都收进同一处，代价是顺序不可随意调整。

## 框架与方法

- **三瀑布夹心（pre-execute / guards / execute / post-execute）**：调用依次穿过 `tools/pre-execute`（钩子、权限、沙箱）→ 已注册的单调守卫 → `tools/execute`（环绕分发：超时、重试、指标）→ 工具体 → `tools/post-execute`（接受、阻断、替换、追加上下文）。
  - 何时用：判断「一个拦截该写在哪一层」时。
  - 怎么做：通用的前置／后置 waterfall 承载钩子与审批策略；`tools/execute` 承担超时这类**环绕分发**关注点（它包住工具体，而不是替换工具）；`tools/post-execute` 是唯一能改写结果内容的地方。三者都能转换调用，所以不要在两个阶段做同一件事。
- **守卫只有一个方向（monotonic guards）**：守卫可以 `deny` 或 `abstain`，且身份受保护——它是一道只能往严里收的闸门，不是第二套允许列表。
  - 何时用：有安全边界、所有者策略这类「不得重新排序」的规则时。
  - 怎么做：把这类策略注册成守卫；`ctx.approval` 在守卫**之前**处理询问，因此「先问人、再过闸」是固定次序。守卫抛异常不会让调用通过，而是进入规范化。
- **询问的位置（`ctx.approval` one-shot）**：`pre` 的 `ask` 分支进入一次性审批提示，`allowed-once` 回到守卫，`rejected`、`cancelled` 或 `unavailable` 一律进入拒绝路径。
  - 何时用：工具需要人工放行时。
  - 怎么做：不要自己造询问通道；`absent or unanswerable` 的语义就是 `deny`，因此在无人值守环境里「没有回答方」等于拒绝，而不是放行。
- **内容三明治（`projectContent` / 后置策略 / `finalizeContent`）**：定义拥有的 `projectContent` 在后置策略**之前**安装准备好的内容（执行准备好的文本与图片），`finalizeContent` 与 `tools/result` 在**之后**执行。
  - 何时用：要决定「谁有最后一次改写结果的机会」时。
  - 怎么做：`projectContent` 负责把工具产物变成模型可读的形态；`post-execute` 可以在其上做策略性接受／阻断／替换／追加上下文；`finalizeContent` 是最后一个、同步且仅限内容的不变式。顺序错一步，后置策略就会看到未经投影的原始产物，或者不变式会被之后的改写破坏。
- **无损快照与冻结结果（lossless snapshot / frozen outcome）**：注册表会对候选结果进行无损快照；如果快照失败，则先把失败规范化，之后再由「可见定义中已随快照固定」的 `finalizeContent` 回调强制执行其同步、仅限内容的不变式；随后 `tools/result` 观察的是不可变、可由 JSON 无损表示的结果。
  - 何时用：要解释「为什么 hooks 拿到的 result 不能再改」时。
  - 怎么做：把 `finalizeContent` 看成快照的收尾步骤而不是另一个钩子——它在快照固定的定义上运行，所以插件热替换不会让同一次调用前后看到两个不同实现。
- **拒绝也要走完后半程（denied path）**：`pre` 的 `deny`、守卫的 `deny`、审批被拒或不可用，都会跳过工具体，但流程继续走 `projectContent` → `post-execute` → `finalizeContent`。
  - 何时用：写拒绝语义、或调试「为什么被拒的调用还有结果」时。
  - 怎么做：让拒绝产出与成功同构的结果对象（内容交给 `projectContent`，`isError` 由规范化决定），这样模型侧与 UI 侧只有一条结果通路，不需要第二套渲染。
- **规范化（invocation pipeline normalization）**：`pipeline/result` 快照抛出、守卫抛出、审批抛出、`pre` 抛出、`projectContent` 抛出、`tools/execute` 包装器抛出、`post-execute` 抛出，全部汇入同一个规范化节点，把异常变成 `isError` 结果。
  - 何时用：任何一处新增可能抛错的钩子。
  - 怎么做：不要在每个阶段各写一套 try/catch；把异常交给规范化，让 `finalizeContent` 与 `tools/result` 仍在确定的路径上运行。
- **批次与调度（batch / barriers / rolling pool）**：执行器接收原始调用批次与并发上限，按 `executionMode` 分类待执行调用，在有界滚动池里运行，并在启动前重新分类。
  - 何时用：解释「为什么两个工具一个并行一个串行」时。
  - 怎么做：`pre` 与 `post` 保持模型顺序，`execute` 并发；`tool/call` 在执行前先记录并立即出 pending 卡，`tool/result` 是单条模型可见结果。批次全部结算（记录的 `tool/result` 齐全）后，活跃批次的 `additionalContexts` 以 FIFO 顺序作为 `user/message` 注入，且**在已记录的 tool 结果之后**。
- **工具自有事件（tool-owned events）**：`todo/write`、`fs/observed`、`hook/invoked`、`hook/result`、`tool/ptc-dispatch` 由工具在体内发出，落在 `tool/call` 与 `tool/result` 之间。
  - 何时用：工具需要留下自己领域的持久事实时。
  - 怎么做：走这些已有事件名，而不是新增通用字段；它们与调用／结果日志相邻，回放时顺序天然正确。
- **文件系统守卫（`fs/write-intent` / `fs/edit-intent`）**：只在 `tool-fs` 的变更路径上触发；先读后编辑的检查位于 `tool-fs` 之下，通过 `fs/*` 事件实现。
  - 何时用：要加路径级或读序级约束时。
  - 怎么做：挂在 `fs/*` 事件上，而不是塞进流水线节点；这样约束对所有走 `ctx.fs` 的工具一致。
- **PTC 模式**：保留的 `run_code` 传输与其序列化子调用都被送入流水线；子调用携带父级 token、记录 `tool/ptc-dispatch`、把拒绝呈现为具有约束力的驳回，并省略 `additionalContexts`，以保持调用与结果相邻。
  - 何时用：解释「代码模式里的工具调用为何与普通调用同权」时。
  - 怎么做：子调用不要另开流水线，也不要注入额外上下文——相邻性是 PTC 的语义前提。

## 关键概念

- **ToolExecutor**：被选中的执行器，接收原始批次、Agent 与可选的日志步骤，负责解析、调度、取消与记录。
- **`tools/pre-execute`**：第一个瀑布，承载钩子、权限与沙箱判断，可 `allow`、`deny`、`ask`，也可转换调用。
- **单调守卫（monotonic guard）**：只能 `deny` 或 `abstain` 的闸门，身份受保护，位于审批询问之后、执行之前。
- **`tools/execute`**：环绕分发瀑布，包住工具体，承担超时、重试、指标这类横切关注点。
- **`tools/post-execute`**：结果侧瀑布，可接受、阻断、替换内容或追加上下文。
- **`projectContent`**：定义拥有的内容投影钩子，在后置策略之前把执行产物变成准备好的文本与图片。
- **`finalizeContent`**：最后一个同步、仅限内容的不变式，在已随快照固定的定义上执行。
- **规范化（normalization）**：把各阶段抛出的异常统一折算为 `isError` 结果的节点。
- **`additionalContexts`**：活跃批次上的附加上下文，FIFO 注入为 `user/message`，位于已记录的 tool 结果之后。
- **PTC（programmatic tool calling）**：`run_code` 模式下的子调用，与普通调用共用同一条流水线。

## 心智模型

- 把流水线看成「两堵墙夹一段自由代码」：`pre` 之前是策略，`post` 之后是呈现，墙内是工具自己的世界。
- 把拒绝看成一次正常结果，而不是一条捷径：它照样被投影、被后置处理、被冻结。
- 把守卫看成只能投反对票的评审——它永远不能把 `deny` 翻成 `allow`，只能弃权。
- 把 `tools/result` 看成按下快门的瞬间：之后发生的一切都只是展示，不再是事实。

## 反模式

- **在工具体里做策略**：工具与某个策略服务耦合后，钩子就无法跨越不同工具系列；这正是通用前置／后置 waterfall 存在的理由。
- **用后置阶段去推翻一个 `deny`**：拒绝已经跳过工具体，`post-execute` 也拿不到执行产物；想放宽就得改守卫或审批策略。
- **自己发 `tool/result`**：结果是单条模型可见事实，由流水线在 `finalizeContent` 之后统一发出；工具自发布会造成一条调用两个结果。
- **在 `post-execute` 里改身份或授权**：身份受保护，守卫的方向是单向收紧；授权判断属于守卫与审批，不属于结果改写。
- **依赖未冻结的结果对象继续变更**：`tools/result` 观察的是不可变、可 JSON 无损表示的快照；持有旧引用继续改只会改到没人看的副本。
- **给 PTC 子调用加 `additionalContexts`**：它被刻意省略，用来保持调用与结果相邻；强行注入会打乱模型侧的顺序假设。

## 代码/配置示例

流水线的阶段序列（`->` 正常流，`-.>` 异常流，`[]` 为分支）：

```text
assistant message 内的 tool-call block
  -> ToolExecutor.execute(raw batch, Agent, optional logging step)
    -> session event: tool/call            (执行前记录)
       -> UI pending card: presentCall(args)
       -> tools/pre-execute                [allow | deny | ask]
          [ask] -> ctx.approval one-shot   [allowed-once -> guards | rejected/cancelled/unavailable -> denied]
          [allow] -> registered monotonic guards   [allow | deny | abstain]
             -> tools/execute (around dispatch: timeout, retry, metrics)
                -> tool execute() body
                   -> fs/write-intent | fs/edit-intent   (仅 tool-fs 变更)
                   -> tool-owned events: todo/write, fs/observed, hook/invoked, hook/result, tool/ptc-dispatch
          -> ToolDefinition.projectContent    (执行准备好的 text + images)
             -> tools/post-execute            [accept | block | replace | add context]
                -> ToolDefinition.finalizeContent   (最后一个仅内容不变式)
                   -> tools/result            (同步通知，冻结的权威结果)
                      -> session event: tool/result   (单条模型可见结果)
                         -> UI completed card: presentResult(args, result)
                         -> batch settled -> additionalContexts FIFO -> user/message
  -.> 任一阶段抛出 -> normalization (pipeline/result snapshot throws become isError) -> finalizeContent
```

定义侧的两个内容钩子（契约结构，非源码）：

```text
ToolDefinition {
  projectContent : 在后置策略之前安装 "execution-prepared text and images"
  finalizeContent: 在后置策略与规范化之后，执行 "last content-only invariant"
                   —— 同步，且绑定在已随快照固定的定义上
}
```

## 参考表

| 阶段 | 机制 | 可否转换调用 | 抛出/失败后果 |
|---|---|---|---|
| 记录 | `session event: tool/call` | 否 | 在 UI pending 卡之前落盘 |
| 前置 | `tools/pre-execute`（hooks、permission、sandbox） | 是 | 抛出入规范化 |
| 询问 | `ctx.approval` one-shot | 否（只放行一次） | 无回答方即 `deny` |
| 守卫 | 已注册单调守卫 | 只能 `deny` / `abstain` | 抛出入规范化 |
| 环绕 | `tools/execute`（timeout、retry、metrics） | 是 | 包装器抛出入规范化 |
| 工具体 | 注册的 `execute()` | 否 | 产物交 `projectContent` |
| 文件守卫 | `fs/write-intent` / `fs/edit-intent`（仅 `tool-fs`） | 由 `fs/*` 事件决定 | 拒绝即中止变更 |
| 投影 | `ToolDefinition.projectContent` | 是（内容形态） | 抛出入规范化 |
| 后置 | `tools/post-execute` | 是 | 抛出入规范化 |
| 规范化 | `pipeline/result` 快照异常 → `isError` | 是（错误形态） | 统一出口 |
| 终局 | `ToolDefinition.finalizeContent` | 否（仅内容不变式） | 强制同步约束 |
| 观测 | `tools/result` 同步通知 | 否 | 结果已冻结 |
| 落盘 | `session event: tool/result` | 否 | 单条模型可见结果 |
| 上下文 | `additionalContexts` FIFO | 否 | 在已记录结果之后注入 |

## 实例演练

场景：模型发出一次 `bash` 调用，且某个钩子要求先审批。

第一步，记录与呈现。执行器拿到原始批次，`tool/call` 在执行前写入会话日志；同时 UI 立刻出 pending 卡（`presentCall(args)`）——注意此时还没有任何执行结果，卡片靠参数渲染。

第二步，前置。`tools/pre-execute` 依次跑钩子、权限与沙箱判断，某个钩子返回 `ask`，于是进入 `ctx.approval` 的一次性提示。假设用户在浏览器里点了允许，返回 `allowed-once`，控制权回到守卫；如果他点了拒绝，或这条会话根本没有回答方（`unavailable`），就直接进入拒绝路径。

第三步，守卫。已注册的单调守卫逐个表态，允许或弃权。这里不能出现「反向放行」：如果某条所有者策略要求拒绝，前一步的审批允许也救不回来——顺序正是「先问人、再过闸」。

第四步，环绕与工具体。`tools/execute` 以环绕分发的方式包住工具体（超时、重试、指标都在这一层），工具体真正 spawn 进程。执行期间它发出自己的事件：`hook/invoked`、`hook/result` 等落在 `tool/call` 与 `tool/result` 之间。这条路径不是 `tool-fs` 的变更，所以 `fs/write-intent` 不触发。

第五步，投影与后置。工具体返回后，`projectContent` 把执行产物变成准备好的文本与图片；`tools/post-execute` 在此之上做策略判断——它可以接受、阻断、替换内容，或追加一段上下文。第 2 章的 seam 表里，`ctx.spillStore` 的消费方 `spill-policy` 就是这一层的消费者：过大的工具文本在这一步被换成面向模型的定位信息与取回提示。

第六步，终局。`finalizeContent` 在已随快照固定的定义上执行最后一个仅内容不变式；`tools/result` 观察冻结后的结果；会话日志写下唯一的 `tool/result`；UI 出 completed 卡（`presentResult(args, result)`）。

第七步，批次收口。等这一批的 `tool/result` 全部齐全，批次视为结算完成；活跃批次的 `additionalContexts` 按 FIFO 作为 `user/message` 注入，位置固定在已记录的工具结果之后——模型因此先看到结果，再看到补充上下文。

如果第三步走的是拒绝路径，流程并不提前结束：跳过工具体后仍然经过 `projectContent`、`post-execute`、`finalizeContent`，最后照样写出单条 `tool/result`，只是 `isError` 为真。这就是「拒绝也是一次正常结果」的实际含义。

## 关键要点

1. 顺序是契约：`pre-execute` → 单调守卫 → `execute` → 工具体 → `projectContent` → `post-execute` → `finalizeContent` → `tools/result`。
2. 询问永远在守卫之前；审批只能放行一次，且「没有回答方」等于拒绝。
3. 守卫只能收紧不能放宽，身份受保护；需要放宽就改策略本身，而不是在结果层补救。
4. 三个瀑布都能转换调用，但职责不同：前置管策略、环绕管横切、后置管内容。
5. 所有异常汇入同一个规范化节点，折算为 `isError`，保证终局路径唯一。
6. 拒绝路径与成功路径共用后半程，因此模型侧与 UI 侧只有一条结果通路。
7. `additionalContexts` 只在批次结算后注入，且永远排在已记录的 `tool/result` 之后。

## 关联

- **第 2 章**：`ctx.sandbox`、`ctx.approval`、`ctx.spillStore` 等 seam 在这条流水线上被消费；配套插件正是靠 `tools/*` 事件介入。
- **第 3 章**：`tool/call`、`tool/result` 在轮次与步骤中的位置，以及工具批次如何决定再领一个步骤。
- **第 6 章**：`tools/pre-execute`、`tools/execute`、`tools/post-execute`、`tools/result` 的生产者／消费者矩阵。
- **第 30 章**：工具、审批与权限预设的组合用法（`workspace-write`／`danger-full-access` 如何同时改流水线的两个输入）。
- **外部概念**：中间件链与 AOP 环绕通知——`pre`/`post` 是中间件，`tools/execute` 是环绕通知，`finalizeContent` 是不可绕过的终结器。
