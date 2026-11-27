# 第 30 章：工具、审批与调度

## 核心思想

一个工具能不能被调用，要连续穿过三道**彼此正交**的门：它存在吗（注册与作用域）、它被允许吗（审批与策略）、它什么时候跑（调度与编排）。三者各有自己的 `ctx.*` 键与拦截点；把任意两道混为一谈，就会写出「注册了就该能跑」或「审批过了就该立刻跑」这类错误假设。

## 框架与方法

- **注册即能力，作用域即可见性（scoped registration）**：`ctx.tools.register` 注册到全局或调用方 agent 的作用域；同层重名与保留名 `run_code` 失败。作用域注册**遮蔽**全局同名工具，而作用域只能用 `ToolRestriction` 收缩它**继承来的**工具（全局加每个祖先），自己的注册不受约束——子 agent 因此保留回报所依赖的工具。
  - 何时用：给子 agent 装独占工具，或裁剪继承面。
  - 怎么做：新能力用注册，裁剪用 `ctx.tools.restrict({ allow?, deny? })`；多道限制**取交集**。`deny` 只挡列出的，`allow` 排除未列出的；空过滤器、未知名、作用域本地名被拒绝。
- **定义契约（`defineTool` / `output`）**：`defineTool` 把参数推断绑定到 `parameterSchemaSpecToJsonSchema()` 与 `validateArgs()`，把返回类型绑定到 `InferValue<OutputSchema>`；`output` 强制存在，`execute` 只返回它能表达的无损 JSON。
  - 何时用：所有第一方工具。
  - 怎么做：`execute` 只产出值，模型可读文本交给 `render`；参数不匹配抛 `ToolArgsError`（`INVALID_ARGS`），返回体不匹配抛 `ToolOutputError`。
- **宿主元数据不进模型请求（allowlisted projection）**：`schemas()` 用显式允许列表构造 `ToolSchema[]`，只放 `name`/`description`/`parameters`；`output`、`execute`、`projectContent`、`finalizeContent`、`timeoutMs`、`isConcurrencySafe`、`presentCall`、`presentResult` 绝不泄漏。
  - 何时用：决定新字段放模型侧还是宿主侧。
  - 怎么做：只问「模型需要用它决策吗」，不需要就留在宿主侧。
- **两个承诺（`timeoutMs` / `isConcurrencySafe`）**：`timeoutMs` 由 `@deepseek-ai/dsh-tool-call-timeout-policy`（一个 `tools/execute` 包装器）执行，声明它等于承诺把 `exec.signal` 转发给能到达静止（quiescence）的实现；做不到就不要声明。执行模式只有 `{ kind: 'parallel' }` 与 `{ kind: 'exclusive' }`（独占且构成顺序屏障）；分类器纯同步，只有返回 `true` 才加入并行组，其余一律按独占。
  - 何时用：工具体有可中断等待，或想与兄弟同批并行。
  - 怎么做：并行前提是**不修改父级拥有的状态**。执行器无法硬杀同进程代码——没观察 `exec.signal` 的 `timeoutMs` 只是让调用方先拿到结果。
- **步骤准入（`ResolvedToolSet`）**：注册可带 `when`。AgentLoop 每个步骤以捕获的模型选择调一次 `ctx.tools.resolve()`，返回集合决定该步骤声明、执行器分区与批次每次调用（含 PTC 子调用）；`executable()` 执行时再应用一次，无集合时条件注册不可用。同名替换或新限制会拦住尚未开始的调用，批次结束即释放。
  - 何时用：工具只在某些模型或模式下才出现。
  - 怎么做：`when` 是**步骤级**判断，不得改注册或启动工具工作；越界即失效。
- **两道执行入口（`ToolExecutor`）**：`ctx.tools.execute()` 把完整原始批次交给最近作用域的执行器。`describe()` 产出 schema 与校验顺序的 `knownNames`；`execute()` 按输入顺序返回结果，中止的调用也有结果，且绝不在已启动工作仍在运行时结算。`maxParallelToolCalls` 只约束并发安全的**根调用**。
  - 何时用：要替换调度、重试或日志策略。
  - 怎么做：实现这两个方法即可；`agent` 与 `log` 都可选，有 `agent` 无 `log` 时仍受作用域约束但不记根事件（初始化钩子即此形态）。
- **程序化工具调用（PTC / `run_code`）**：PTC 把保留的 `run_code` 注册进同一张表，模型写程序而非逐条发调用，程序经绑定命名空间（PTC 传 `tools`）调用原生工具。子分派带 `parent` token，只有**带父级**的调用才能执行原生工具名；模型直接发起的调用在策略流水线前被判 `UNKNOWN_TOOL`。
  - 何时用：一次发几十个同质调用，或需在程序里分支、聚合、重试。
  - 怎么做：它是「工具能力的第二种传输」，不是第二套权限——子调用照样穿 `pre-execute` 与守卫，`tools/ptc-dispatch-log` 只可改写**持久日志副本**。执行由 `ctx.ptcRuntime` 负责：`resolve()` 补全目录、截止与授权，`run()` 返回结果；`timeout`/`abort`/`worker-exit` 等八种 `kind` 是**正交结果**，不是异常。
- **人类命令（`ctx.commands`）**：斜杠命令由注册表提供给交互式适配器，**针对确切 agent 直接执行**，不创建模型消息。作用域规则与工具同构：agent 子上下文注册的定义遮蔽全局同名定义。
  - 何时用：给人类「不走模型」的确定性动作。
  - 怎么做：`command/run` 与 `command/done` 都是只写日志、不被轮次包裹的追加；语法或名字未命中不写任何东西。附件准入在服务端强制，未声明 `input.attachments`、附件库缺失、超图片上限都在 handler 前结算为错误。
- **一次性审批（`ctx.approval` one-shot）**：审批 seam 只回答「这个具体操作是否可以继续」。结果闭合为 `allowed-once`/`rejected`/`cancelled`/`unavailable`，**唯一许可是 `allowed-once`**。
  - 何时用：`pre-execute` 的 `ask` 分支，或任何需人类放行的同进程操作。
  - 怎么做：不要自造询问通道；缺应答方、抛异常、返回不合规值都归 `unavailable`——失败方向是关闭。请求以 `callId` 关联已流式的调用，**不复制参数**；`reason` 是审计文本，`displayReason` 是本地化提示。
- **按会话审批策略（`ApprovalPolicy`）**：`ask` 委托组合的应答者链（无应答时落到 `unavailable`）；`never` 确定性返回 `rejected`，不分发任何应答者。生效值是会话日志中最后一条 `approval/policy`，回退到服务配置；`setApprovalPolicy` 是唯一写路径。
  - 何时用：CI 与无人值守用 `never`，交互会话用 `ask`。
  - 怎么做：写在**会话**层，因为它必须能被回放重建；`never` 在服务内部、waterfall 分发前强制执行，`prepend` 注册的应答者也绕不过。审计事件只写日志、不进 transcript。
- **权限预设捆两个旋钮（`ctx.permissionPresets`）**：预设把 `sandbox/mode` 与 `approval/policy` 两个独立 knob 映射成具名 key，供客户端当作单个 Permissions 选择器。默认表含 `workspace-write`（`workspace-write` + `ask`）与 `danger-full-access`（`danger-full-access` + `never`）；`custom` 与 `auto` 是保留名。
  - 何时用：给人类一个「安全级别」下拉。
  - 怎么做：把它当**视图加写入路径，不是策略拥有者**。`set` 先追加仅记日志的 `permission/preset`，再经各 knob 的 setter 写入，仅在生效值变化时写；选择事件先于旋钮事件。`current()` 优先取仍匹配的已记录选择，其次首个匹配的配置条目，否则返回 `custom`——派生值，绝不是切换目标。
- **宿主级调度（`ctx.schedule`）**：任务独立于 Session 状态存于宿主；同一管理 API 按 id 操作，同一求值器处理 `after`/`at`/`every`/`daily`/`weekly`/`cron`/`rrule` 七种权威时间类型。目标三选一：`session`、`new_once`（省略时默认）、`new`。
  - 何时用：要「到点让某个 agent 做某事」。
  - 怎么做：**读写都不激活 Session**，只有投递会创建或唤醒它；已存 `scheduledAt` 是规范 RFC 3339 UTC 时刻，解码不按当前时区重算。停机后只追赶最新一次到期，规则耗尽以 `ended` 保留。时间用带判别字段的 `timing`（如 `{ kind: 'cron', cron: { expression, time_zone } }`）；Cron 从不转成 RRULE。单任务最小间隔 60 秒。
- **工作流编排（`ctx.workflowEngine`）**：工作流让模型写一段会启动 subagent 的脚本；与 subagent、PTC 一样是**可选能力**，不在 agent loop 里，每个上下文只允许一个引擎实现。`start()` 返回持有者拥有的 `WorkflowRun`：`result` **绝不拒绝**（失败 `stopReason: 'error'`、取消 `'cancelled'`），`cancel` 与幂等 `dispose` 由持有者负责。
  - 何时用：要一次扇出几十个子 agent，并需脚本级分支与聚合。
  - 怎么做：`meta` 与 `args` 是普通 JSON，引擎用 schema 校验 `meta`、**绝不对脚本文本求值**取它们；`parent` 必填。钩子误用、未知或延迟的 `agent()` 选项、超 schema、超上限、取消都抛 `fatal: true` 的 `WorkflowError`，`parallel()`/`pipeline()` 对 fatal 直接重抛而**不**映射为 `null`；逐项 `null` 只留给子运行失败。`workflow/*` 纯供观察。

## 关键概念

- **`ToolDefinition`**：已注册工具，含模型 schema、强制的 `output`、`execute`、宿主侧调度元数据与可选展示回调。
- **`ToolOutputDefinition`**：工具自有的输出契约，含 `schema`、纯 `render` 与可选 `presentationMeta`。
- **`ToolRestriction`**：作用域对**继承工具**的实时过滤器，多道取交集，不影响自身注册。
- **`ResolvedToolSet`**：一个步骤的准入集合，可 `view(scope)` 读取，批次结束即 `dispose()`。
- **`ToolExecutionMode`**：`parallel` 或 `exclusive`，后者构成顺序屏障。
- **`PtcBindingNamespace`**：宿主函数作为程序可见的全局对象，成员名按自有属性处理（可含 `__proto__`）。
- **`ApprovalOutcome`**：闭合四值审批结果，唯一许可是 `allowed-once`。
- **`PresetSpec`**：预设的 `sandbox` + `approval` 组合；`custom` 是派生态。
- **`ScheduleTiming`**：七种时间类型的带判别载荷，是调度的权威时间来源。
- **fatal `WorkflowError`**：脚本层误用的致命错误，组合器直接重抛而不吞成 `null`。

## 心智模型

- 判断「这个工具为什么不可见」时，按 **注册 → 作用域遮蔽 → 限制交集 → 步骤准入 → 执行器** 逐层排查，先别看模型。
- 把 `ToolRestriction` 看成只能减不能加的面具：它盖在继承能力上，永远不给你新能力。
- 把权限预设看成遥控器面板：它按的是两个真实旋钮，自己不是电路。

## 反模式

- **在 `execute` 里自己拼模型可读文本**：绕过 `output.schema` 校验、渲染器投影与后置策略，UI 与模型会看到两套事实。
- **把 `timeoutMs` 当保险丝**：同进程代码无法被硬杀，未观察 `exec.signal` 的工具体超时后继续跑，副作用照旧发生。
- **在并行工具里写父级状态**：违反并行组契约，bug 以竞态形式出现，极难复现。
- **把 `never` 读成「全部批准」**：两者都是「不问」但方向相反——`never` 确定性 `rejected`，无人值守因此是关闭而非放行。
- **用审批补作用域的洞**：审批答「这一次能不能做」，作用域答「有没有这个能力」；拿审批补洞会给每次调用加人工闸，忘记批准时行为随环境漂移。
- **把工作流的 fatal 吞成 `null`**：那正是为了让写错的选项炸出来；包一层 try/catch 降级等于把配置错误伪装成子 agent 故障。
- **指望读任务会唤醒它的 Session**：读与管理写从不激活 Session，只有投递会。

## 代码/配置示例

```ts
// 一个带强制输出声明与并行许可的工具
defineTool({
  name: 'glob',
  description: '按路径模式查找文件',
  parameters: {
    pattern: { type: 'string' },                 // 隐式开放对象根；必填靠 required: true
    path: { type: 'string', required: true },
  },
  output: {
    schema: { type: 'array', items: { type: 'string' } },
    render: (_args, value) => [{ type: 'text', text: value.join('\n') }],
  },
  isConcurrencySafe: () => true,                 // 只读、不写父级状态
  async execute(args, exec) {
    return findPaths(args.pattern, args.path, exec.signal)  // 必须观察 signal，返回无损 JSON
  },
  presentResult: (_args, _result) => ({ card: 'search', shape: 'paths', truncated: false, total: 0 }),
})
```

```ts
// 作用域裁剪：只作用于继承来的全局工具，且取交集
const lift = ctx.tools.restrict({ deny: ['bash', 'write'] })
// 该 agent 后续步骤里 bash/write 不可见；它自己 register 的工具仍然可见。

// 调度：带判别字段的时间，持久化前拒绝无效组合
await ctx.schedule.create({
  title: '每工作日晨报',
  prompt: '汇总昨天的 CI 与告警',
  timing: { kind: 'cron', cron: { expression: '0 9 * * 1-5', time_zone: 'Asia/Shanghai' } },
  target: { kind: 'new_once' },                  // 省略 target 时的默认
})                                               // 读与写都不激活 Session

// 工作流：脚本 + 数据化 meta + 必填 parent
const run = ctx.workflowEngine.start({
  script,
  meta: { name: 'audit-fanout', description: '按文件扇出审计', phases: [{ title: '扫描' }] },
  args: { files },
  parent: agent,
})
const result = await run.result                   // 绝不拒绝
if (result.stopReason !== 'completed') { /* 映射为 isError 工具结果 */ }
await run.dispose()                               // 每条路径都必须调用
```

## 参考表

| 执行模式 | 语义 | 何时出现 |
| --- | --- | --- |
| `{ kind: 'parallel' }` | 可与兄弟调用重叠 | `isConcurrencySafe(args) === true` |
| `{ kind: 'exclusive' }` | 独占运行，构成顺序屏障 | 省略、抛异常、返回非 `true`、非法定义参数 |

| 层 | `ctx.*` 键 | 拦截点 | 决定什么 |
| --- | --- | --- | --- |
| 注册／作用域 | `ctx.tools` | `schemas()` 允许列表、`resolve` 步骤准入、`executable` | 是否存在、是否可见、本步骤是否可用 |
| 审批／策略 | `ctx.approval`、`ctx.permissionPresets` | `pre-execute` 的 `ask`、`approval/request` waterfall、`never` 前置 | 本次调用是否放行 |
| 调度／编排 | `ctx.schedule`、`ctx.workflowEngine`、`ctx.commands` | 宿主定时器、`start()`、斜杠命令解析 | 何时、以什么顺序、由谁发起 |

| 预设 | 沙箱模式 | 审批策略 |
| --- | --- | --- |
| `workspace-write` | `workspace-write` | `ask` |
| `danger-full-access` | `danger-full-access` | `never` |
| `auto`（Auto review 注册，会话级） | `danger-full-access` | `ask` |
| `custom`（派生，不可选） | 当前生效值 | 当前生效值 |

| 投递目标 | 行为 |
| --- | --- |
| `session` | 投递到已有 Session；启用时查存在、未归档、非委托子 agent，投递时再查归档 |
| `new_once` | 首次投递前预留 id，必要时创建后保存为 `session` 复用；重试与重启保留预留 |
| `new` | 每次投递新建；创建前持久化 `pendingDelivery.targetSessionId`，失败尝试复用同一 Session |

## 实例演练

一个子 agent 要读文件、绝不允许写，且希望与兄弟调用并行：

1. 父作用域照常注册 `bash`、`read`、`write`。子 agent 在自己上下文里调 `ctx.tools.restrict({ deny: ['write'] })`：限制只盖继承层，取交集后 `write` 消失；它自注册的只读工具仍可见。
2. 步骤开始时 AgentLoop 调 `ctx.tools.resolve()`；某条件注册的 `when` 为假，则既不出现在声明里，也不会被派发。
3. 模型发出两个 `glob`：`isConcurrencySafe` 返回 `true`，两者进同一 `parallel` 组；同批若有一个未声明并发的工具，它作为 `exclusive` 屏障把它们分开。执行器在有界滚动池里跑：先记 `tool/call` 出 pending 卡片，结束记 `tool/result`；批次结算后 `additionalContexts` 才以 `user/message` 注入。
4. 若某个调用被 `pre` 判为 `ask`，它进入 `ctx.approval.request`：`callId` 指向已流式的调用。会话策略为 `never` 时，服务在分发应答者**之前**返回 `rejected`；为 `ask` 而无人应答则落到 `unavailable`——两者都不是放行。只有 `allowed-once` 让调用回到守卫与工具体。
5. 另一条链走完「时机」层：人类切到 `workspace-write` ⇒ `set` 先追加 `permission/preset`，再把两个 knob 写成 `workspace-write`、`ask`（仅改变化了的那个）。此前建的 `{ kind: 'cron', … }` 任务只躺在宿主存储里；某个工作日 09:00 定时器到期，Schedule 经 `schedule/resolve-agent` 解析目标、遵守 60 秒最小间隔投递。任务用的仍是它自己那套作用域与审批策略——调度只改变**何时**发起。

## 关键要点

1. 三道门正交：注册与作用域管**能力**，审批与策略管**许可**，调度管**时机**；排错按门定位。
2. `output` 不是可选项——它是 `execute` 返回值、`render` 投影与模型内容的唯一契约。
3. `schemas()` 的白名单是安全边界：宿主侧元数据不该进模型请求。
4. 声明 `timeoutMs` 或 `isConcurrencySafe` 都是**承诺**，不是配置项。
5. 审批只有 `allowed-once` 一种许可；无人值守要显式选 `never`，不能指望「没人问就通过」。
6. 权限预设是遥控器不是电路；Schedule 的读写不激活 Session，Cron 不会被转成 RRULE。
7. 工作流把脚本误用当致命错误、把子运行失败当逐项 `null`；`result` 永不拒绝，但 `dispose` 必须每条路径都调用。

## 关联

- **第 4 章**：工具执行流水线，解释 `pre-execute`/守卫/`execute`/`post-execute` 的次序与规范化。
- **第 2 章**：能力 seam 的通用形态；本章各 `ctx.*` 都是它在不同问题域的实例。
- **第 28 章**：Session 日志，`tool/call`、`tool/result`、`command/run`、`approval/asked` 的持久化与回放。
- **第 32 章**：沙箱与执行环境，`sandbox/mode` 是被预设捆进面板的旋钮之一。
- **Subagent 与 MCP**：工作流的子 agent 归属必填 `parent`；MCP 工具走同一套注册与 schema 子集。
