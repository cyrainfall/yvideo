# 第 29 章：Agent 编排

## 核心思想

编排不是五个并列功能，而是一条栈：**委派**（delegation）决定谁执行，**团队**（agent-team）决定多个执行者如何共享任务，**计划**（plan）约束当前轮次，**目标**（goal）约束跨轮次；**待办**（todo）不构成第五层，它只是贯穿全栈的一本最小账。五者形状一致——日志事件是唯一真相，投影是读模型，工具准入发生在**步骤边界**而不是调用边界。

## 框架与方法

- **委派：一个 activation API，两种后端**
  - 何时用：需要另一个 agent 干活，无论它在同进程还是另一个产品里。
  - 怎么做：所有后端都走 `startActivation`，先由能力标记校验请求选项。带 `prepareContinuable` 的提供方执行**本地可继续**子代理，只有 `start` 的执行**一次性外部**子代理——方法是否存在就是路由开关。
  - 判据：`prepareContinuable` 是提供方在可继续创建中的唯一参与点，只贡献"子会话是否带父历史"。身份预留、组装、Agent 创建、提示投递、冷恢复、释放全归管理器，提供方看不到子 Agent、句柄或轮次。

- **委派的三条所有权边界**
  - 怎么做：身份——本地子级可由 `childId` 预留，外部后端自己分配 id；容量——`capacityOf()` 只观测不预留（`running` 含启动中、常驻、停止中，不含根；限额调低后 `running` 可超 `limit`）；释放——`dispose()` 只释放这一次 activation，`drainDescendants()` 才等整棵树。
  - 附带结论：`delivery: 'parent'` 通知模型、本地子级必进父目录；`'caller'` 只回结果，成员关系与结果收集由调用方自负。

- **委派的结果是 `stopReason`，不是异常**
  - 怎么做：`output` 取最后一条非空 assistant 消息（跳过空内容与仅用量消息，退回累积文本流，再无则 `[]`）；`structured` 只在 `outputSchema` 被满足时存在；`diagnostic` 已脱敏、限 4096 字节；`stopReason` 取 `completed` / `aborted` / `error` / `max-tokens` / `refusal`。
  - 判据：`run.result` **不因子级失败而 reject**——那会以 `stopReason: 'error'` 结算，交工具层映射成 `isError`；只有 seam 无法表达成 stopReason 的基础设施故障才 reject。

- **团队：共享任务 DAG 用比较并设置（compare-and-set），不用锁**
  - 怎么做：每条 task event 都存完整快照，`revision` 是 CAS 值、每次 +1；`blockedBy` 必须指向未删除任务并维持无环；`writeScopes` 是规范化的**提示性**路径前缀，不是锁；`ready` 与 `writeScopeWarnings` 只在视图上派生，不回写快照。
  - 判据：`pending` 是未开始**或已释放**，`in_progress` 携带负责人，`completed` 满足依赖，`deleted` 是保留墓碑；`ownerName` 是分配时捕获的不可变 agent 路径。

- **团队模式：根会话的单一开关，读在步骤边界**
  - 怎么做：`agentTeam.enabled` 由根保存，新会话默认 false，`team/mode` 记录显式选择，仅根可 `setEnabled`，后代共享。工具在步骤准备时定可用性，提示词提供方在求值时读选择；任务修改在排队操作开始时检查模式，已获准的继续完成。
  - 附带结论：写入先立即生效再等刷盘；刷盘失败时已追加的选择仍生效，重试只再刷盘、不重复追加事件。

- **计划：软性指引与硬性闸门分离**
  - 怎么做：`plan:policy` 是软性指引（激活期间以 order 50 渲染，未激活不贡献文本）；强制限制在沙箱与审批，两者都不读写计划状态。状态本身是仅记日志的 `plan/mode`（整值替换，永不进 transcript）。
  - 判据：`section` 缺失、空白、非字符串或含未知键，在**插件加载**阶段失败，不被忽略。

- **计划的追加点只有轮内 pre-step**
  - 怎么做：用户选择保持待生效，直到下一个被接受的轮内 pre-step 在派生请求前追加。`set()` 的四种结局就是全部可能：`committed`、`queued`、`cancelled`、`noop`。轮间调用立即追加，因为没有轮内 pre-step 会跑。
  - 附带结论：某轮最后一个被接受 pre-step 之后做出的选择只存在于进程内，进程退出即丢失。

- **计划闸门：`exit_plan_mode` 的渐进式披露**
  - 怎么做：自"已选计划状态首次为激活"的步骤起准入并保持到会话结束；首次进入前调用是 `UNKNOWN_TOOL`，计划模式未提交时以 `PLAN_NOT_ACTIVE` 失败。要求以 `#` 标题开头的完整 markdown 计划，否则 `ToolArgsError` 拒绝，并经用户交互 seam 呈交。
  - 判据：批准返回 `{ approved: true }` 并记录**静默**待生效退出——当前这批工具调用仍在计划指引下；"继续规划"以 `PLAN_REVISION_REQUESTED` 失败并携带反馈；放弃返回 `{ approved: false }` 并结束当前轮次，计划模式保持激活直到用户下一条消息。

- **目标：持久阶段与进程本地 activation 分离**
  - 怎么做：`GoalPhase`（`active` / `paused` / `blocked` / `complete`）持久；`activation` 是进程本地的续跑资格，**永不持久**，经 `goal/activation-changed` 实时推给客户端。只想停自动续跑而不动持久阶段，用 `disarm()`。
  - 判据：`blocked` 是唯一表示"因问题而停止"的持久状态，带 lower-kebab-case 的 `code` 与一段 `message`，且 `blockedReason` 恰好只在 `blocked` 时存在。

- **Goal Round：只有获准的用户轮次推进 `roundsStarted`**
  - 怎么做：为每个获准轮次标上正数且连续的 `round` 与当前 `revision`（`GoalMessageSource`），只有这些获准的 `user/message` 推进 `roundsStarted`，`maxGoalRounds` 是总上限。回放拒绝非正数、编号缺口、陈旧修订、已停止阶段与超限。
  - 附带结论：每次变更是一条 `goal/change`，载荷是完整快照或清除墓碑；严格折叠只从这些事件派生生命周期，inbox 变更不影响 goal 状态。

- **目标变更全程比较并设置**
  - 怎么做：所有修改都传 `GoalRef { id, revision }`，每次获准的持久变更 +1。`create` 只在 `complete` 阶段可替换，其他阶段须先 `clear` 或 `resume`；`edit` 是局部替换且至少给一个字段；`clear` 返回的墓碑 ref 是"被清快照 + 1"。

- **待办：刻意最小，因为整表替换**
  - 怎么做：`TodoItem` 只有 `content` 与三态 `status`；没有 id、优先级、`activeForm`——每次写入整体替换列表（last-write-wins），条目不需要稳定身份。事件是仅记日志的 `todo/write`。

## 关键概念

- **子代理树（subagent tree）**：由创建关系构成的执行拓扑；根名为 `lead`，普通 Session fork 会开启一棵独立的新树。
- **activation**：一次受管的子执行；`dispose()` 只针对这一次，绝不针对之后的恢复。
- **`SubagentProvider`**：已注册的执行传输；受信的同进程实现，调用方把其返回值当作借用的不可变数据。
- **`prepareContinuable`**：提供方对可继续创建的唯一参与点，只贡献"子会话是否带父历史"。
- **共享任务 DAG**：团队任务图，`blockedBy` 必须无环且指向未删除任务。
- **计划模式（plan mode）**：记录到日志的逐 agent 协作状态，软性指引，不是强制限制。
- **pre-step**：轮内、派生请求之前的步骤，计划选择的唯一合法追加点。
- **`GoalPhase` vs `activation`**：前者持久可回放，后者进程本地、永不持久。
- **Goal Round**：一个获准用户消息轮次的连续编号，自动续跑的计量单位。
- **`TodoItem`**：`content` + 三态 `status` 的列表项，整表替换取代逐条更新。

## 心智模型

- **把五者看成同一台机器的刻度**：日志事件（真相）→ 投影（读模型）→ 步骤边界（准入）。任何"为什么没生效"先问它落在哪一格。
- **把委派看成所有权转移**：`start()` 兑现前提供方拥有安装过程并清理半成品，兑现后所有权易主，之后的失败经 `result` 结算。
- **把计划模式看成提示词上的开关，不是权限闸门**：它只改 `plan:policy` 段落，强制限制在沙箱与审批。
- **把目标看成"两套状态叠一个修订号"**：持久阶段回答发生了什么，activation 回答能否再跑一轮，`revision` 防并发写坏。

## 反模式

- **用 `delivery: 'caller'` 却期待子级出现在父目录里**：父级通知与成员关系都被抑制，得调用方自己收集。
- **把 `list_agents` 的 `running` / `inactive` 当任务完成度**：它们不描述完成情况，也不保证 `send_message` 会成功。
- **靠团队任务变更唤醒 agent**：任务变更不结束收件箱等待、不添加消息、不启动空闲 agent；要处理就发明确消息。
- **把 `writeScopes` 当互斥锁**：它只是提示性前缀，冲突仅以 `writeScopeWarnings` 呈现。
- **在计划模式里期待"批准即生效"**：批准记录的是待生效退出，由下一个被接受的轮内 pre-step 追加。
- **把 `plan/mode` 当强制限制或写进 transcript**：它仅记日志；限制在沙箱与审批。
- **用过期的 `GoalRef` 提交或在 `blocked` 上无视预算 `resume`**：CAS 与回放都会拒绝，`resume` 只在轮次预算仍有容量时成功。
- **给待办条目做增量更新或引用**：整表替换、无 id，按条目身份的操作为伪。
- **假设移除提供方会终止已返回的运行**：它只阻断新启动，已交给持有者的 run 不受影响。

## 代码/配置示例

委派的统一入口与两种后端（签名取自原文）：

```ts
interface SubagentProvider {
  readonly name: string
  readonly capabilities: SubagentCapabilities
  /** 子级是否看到父已完成的轮次前缀；描述性，不是服务校验的启动能力。 */
  readonly inheritsParentContext: boolean
  readonly agentRouteDefaults?: Readonly<{ provider: string; model: string }>
  /** 建立一次外部执行并返回其句柄。 */
  start?(request: ResolvedSubagentStartRequest): Promise<SubagentRun>
  /** 可选：可继续创建能力；方法存在即选择本地 activation 执行。 */
  prepareContinuable?(request: ContinuableCreateRequest): Promise<ContinuableCreateSpec>
}
```

activation 的生命周期形状：

```ts
interface SubagentActivation {
  readonly childId: SessionId
  /** 模型可见名：自根起每级都有名称时为斜杠路径，否则为子 Session id。 */
  readonly name: string
  readonly messageId?: MessageId
  /** 资源释放与通知发出之后结算；采集失败会 reject。 */
  readonly result: Promise<SubagentResult>
  /** 只停止并释放这一次 activation；teardown 失败时 reject。 */
  dispose(): Promise<void>
}
```

计划模式的四种结算：

```ts
set(agent: Agent, active: boolean): 'committed' | 'queued' | 'cancelled' | 'noop'
```

目标快照与视图的分层：

```ts
interface GoalSnapshot extends GoalRef {
  readonly objective: string
  readonly phase: GoalPhase           // 'active' | 'paused' | 'blocked' | 'complete'
  readonly blockedReason?: GoalBlockReason   // 恰好只在 blocked 时存在
  readonly maxGoalRounds: number
}

interface GoalView extends GoalSnapshot {
  readonly roundsStarted: number
  readonly createdAt: number
  readonly updatedAt: number
  readonly activation: GoalActivation  // 进程本地，永不持久
}
```

待办项：

```ts
interface TodoItem {
  content: string   // 短祈使句，UI 展示
  status: 'pending' | 'in_progress' | 'completed'
}
```

## 参考表

编排栈的对照（四层 + 贯穿的待办账本）：

| 层 | 持久真相 | 读模型 | 模型入口 | 冲突策略 |
| --- | --- | --- | --- | --- |
| 委派 | 父会话日志里的目录记录（创建时写入成员关系，不记执行状态） | 父级拥有的 `subagentCatalog` 投影 | 委派工具 + `list_agents` | 容量与身份预留；`dispose` 精确到 activation |
| 团队 | 每任务一条完整快照事件 | 根会话的 `agentTeam` 投影 | 任务工具 + 任务面板 | `revision` compare-and-set；DAG 无环 |
| 计划 | `plan/mode`（仅日志、整值替换） | `plan` 单元折叠 | `/plan` 命令 + `exit_plan_mode` | 待生效选择由轮内 pre-step 追加 |
| 目标 | `goal/change`（快照或墓碑） | `goal` 投影 + `GoalView` | `ctx.goals`（`get`/`create`/`edit`/…） | `GoalRef` compare-and-set |
| 待办 | `todo/write`（完整替换列表） | 回放投影 | `todo` 工具 | last-write-wins，无条目身份 |

目标阶段：

| 阶段 | 含义 | 可否 `create` 覆盖 | 自动续跑 |
| --- | --- | --- | --- |
| `active` | 进行中 | 否（先 `clear`） | 可，受 `maxGoalRounds` 约束 |
| `paused` | 暂停 | 否 | 否（已 disarm） |
| `blocked` | 因问题停止（唯一此类持久状态） | 否 | 否（已 disarm） |
| `complete` | 已完成 | 是，可直接替换 | 否 |

子代理停止原因：

| `stopReason` | 含义 | 结果可用性 |
| --- | --- | --- |
| `completed` | 子级正常完成本轮 | 完整 |
| `aborted` | 经请求信号或释放取消 | 可能部分 |
| `error` | 模型或传输失败 | 可能部分 |
| `max-tokens` | 触发 token 上限 | 可能部分 |
| `refusal` | 子级拒绝任务 | 可能部分 |

团队任务状态：

| 状态 | 语义 |
| --- | --- |
| `pending` | 未开始，或已释放 |
| `in_progress` | 携带负责人（`ownerId`，可能带 `ownerName`） |
| `completed` | 满足依赖，可解锁后继 |
| `deleted` | 保留的墓碑记录，不可作为 `blockedBy` 目标 |

## 实例演练

一次"继续"引发的整栈联动（据各页已声明行为推演）：

1. **目标重新武装。** 人类说"继续"。所有者调用 `resume(agent, ref)`；若驱动曾被卸载，`disarm()` 已摘掉 activation 却没动 `phase` 与 `revision`。`resume` 只在预算仍有容量时成功——由 `roundsStarted` 与 `maxGoalRounds` 决定。成功后 `phase` 仍是 `active`，activation 重新具备资格，`goal/activation-changed` 让客户端实时看到。
2. **Round 被分配。** 这一轮是获准的 `user/message`，续跑消费方给它标上正数连续的 `round` 与当前 `revision`，`roundsStarted` 随之推进；编号缺口或陈旧修订号会被回放拒绝，而不是静默接受。
3. **计划仍只是指引。** 此步若在计划模式中，请求里多了 order 50 的 `plan:policy` 段落；行为受影响，权限不受影响。若该选择发生在某轮最后一个被接受的 pre-step 之后，它此刻仍是 `pending`，要等下一轮追加。
4. **团队开工。** 根会话的模式决定任务工具是否可用（步骤准备时判定）。某成员 `createTask` 建出 `revision: 1` 的无主 `pending` 任务，另一成员以 CAS 领取，状态转 `in_progress` 并带上 `ownerId`/`ownerName`。写范围只在视图上产生警告，不阻止动手。
5. **委派。** 本地走带 `prepareContinuable` 的提供方，外部走只有 `start` 的提供方——比如把整轮交给另一个产品。请求的每项启动能力都要在该提供方 `capabilities` 里被支持，否则启动前即被拒；`delivery` 决定结果回到模型还是只回调用方。
6. **结果按 `stopReason` 分流。** `completed` 读 `output`（有 `outputSchema` 再读 `structured`）；`error` / `max-tokens` / `aborted` / `refusal` 不抛异常，由工具层映射成 `isError`，`diagnostic` 单独呈现。
7. **收口与唤醒。** 执行者以 CAS 推到 `completed`，后继因此就绪。此刻**不会**有人被自动唤醒——任务变更不添加收件箱消息、不启动空闲 agent；要让人处理就发明确消息。全程任何一步都可以重写 `todo/write` 整张列表，界面永远看到最后一份一致快照。
8. **卡住了怎么办。** 用 `block(agent, ref, reason)` 记 `blocked`：`code` 稳定可路由、`message` 给人看；它同时 disarm 自动续跑。要再试，先确认预算，再 `resume`。

## 关键要点

1. 编排是一条栈：委派 → 团队 → 计划 → 目标，待办是贯穿账本；别按包名理解它们。
2. 每层都是"日志事件为真相、投影为读模型、准入在步骤边界"这一形状。
3. 委派只有 `startActivation` 一个入口；`prepareContinuable` 是否存在决定本地可继续还是外部一次性执行。
4. 子级失败是 `stopReason`，不是 rejected promise；只有基础设施故障才 reject。
5. 团队的并发靠 `revision` CAS 与无环 DAG，不靠锁；`writeScopes` 只是提示。
6. 计划模式是软性指引，追加点只有轮内 pre-step，四种结算即全部结局。
7. 目标把持久阶段与进程本地 activation 分开；`blocked` 是唯一"因问题停止"，带 `code` + `message`。
8. 待办刻意无 id：整表替换、last-write-wins。

## 关联

- **第 28 章**：Session 是这层的日志底座——`plan/mode`、`goal/change`、`todo/write`、team task 事件都写在会话日志里，投影与回放由此而来。
- **第 3 章**：agent 生命周期（步骤、轮次、turn boundary）解释了 pre-step 为什么是唯一追加点。
- **第 17 章**：`ctx.subagents`、`ctx.agentTeams`、`ctx.planMode`、`ctx.goals` 都是服务形态，契约见服务页。
- **第 26 章**：提供方注册声明为 effect 作用域、HMR 安全，走的就是 Registry 的装载与清理机制。
- **第 38 章**：给 harness 加工具包时，编排工具的准入集合与步骤准备必须对齐。
- **多智能体系统（multi-agent system）**：本页是它在 DSH 里的具体形态——子代理树、共享任务 DAG、按轮次计量的续跑预算。
