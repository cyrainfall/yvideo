# 第 6 章：事件生产者与消费者矩阵

## 核心思想
DSH 的 harness 自有事件没有单一注册表，也没有可读的调用图，而是由一张生成式矩阵钉住：每个事件一行，同时记录它的派发模式（Mode）、声明位置（Declared in）、派发方（Dispatchers）和监听方（Listeners）。读这一行，等于同时回答两个问题——「这个事件的契约归谁所有」和「我改这里会触发谁」。事件之间是多对多关系，密集的关系数据用表格承载，而不是画一张大型关系图。

## 框架与方法

- **事件矩阵（event producer-consumer matrix）**：五行结构 `Event | Mode | Declared in | Dispatchers | Listeners`。
  - 何时用：要新增事件、要改某个事件的值、要把 `emit` 升级成可改写的模式，或者排查「这个包为什么被调起来了」。
  - 怎么做：先看 `Declared in` 确认契约出处（`packages/<area>/<pkg>/src/...:行号`），再看 `Mode` 决定你有多少权限，最后按 `Listeners` 逐个核对影响面。三列的顺序不能颠倒——先确认自己有权改，再谈改什么。

- **派发模式（dispatch mode）**：矩阵里实际出现五种值：`emit`、`serial`、`waterfall`、`parallel`、`bail`。模式由 Cordis 事件系统定义（见第 18 章），本矩阵只负责记录「这个事件用的是哪一种」。模式是权限声明：它告诉你这个事件是纯观测点，还是允许监听者介入并改变后续行为的接缝。
  - 何时用：任何一次「我想在这里插一手」的改动。
  - 怎么做：`emit` 类事件（如 `session/event`、`tools/result`、`session/created`）按观测对待，不要指望通过它改变已经发生的值；`waterfall` 类事件（如 `tools/pre-execute`、`tools/execute`、`agent/pre-step`、`llm/stream`、`system-prompt/assemble`）才是可以改写链路的接缝；`serial` 类事件（如 `agent/created`、`agent/turn-stopping`）用于有顺序要求的多方响应；`parallel` 类事件（如 `session/flush`、`workspace/session-stop`、`plugin-manager/operation`）用于可以并行扇出的通知。

- **`bail` 的稀缺性作为判据**：整张表里 `bail` 只出现一次——`webserver/authorize`，由 `remote-connection` 和 `webserver` 派发、`connection` 监听。当你要决定某个新事件该用什么模式时，默认不要选 `bail`：它意味着一方可以短路整条授权路径，只有 `/api` 这类信任围栏才配得上。

- **声明位置（Declared in）**：事件名的类型声明所在文件与行号，通常挂在 `src/types.ts` 或 `src/index.ts`，少数集中在 `src/events.ts`（如 `packages/core/tools/src/events.ts`、`packages/storage/storage-domain/src/events.ts`）。
  - 何时用：改名、改载荷、判断一个事件是不是正式契约。
  - 怎么做：`Declared in` 有值的才是一等事件；只出现在「未声明事件串」表里的，属于包内部约定或技术债。

- **派发形态（dispatch form）**：`Dispatchers` 列在包名后带一对括号，记录代码里的派发方式：`emit`、`waterfall`、`serial`、`parallel`、`bail`，以及 `events.dispatch`。`events.dispatch` 是服务层统一的派发助手，和直接 `ctx.emit` 是两种写法。少数事件同时存在两种形态，例如 `agent/error` 由 `agent-loop` 用 `emit` 派发、由 `cua` 用 `emitAgentEvent` 派发。

- **内含派发位置（inline dispatch site）**：矩阵有意收录「绕过 `ctx.emit` 的派发位置」，典型是 subagent 生命周期封装——那里事件不是从插件上下文发出的，而是从封装层里发出来的。`emitAgentEvent` 这类包装函数就是此类。
  - 何时用：搜索 `ctx.emit` 找不到派发方时。
  - 怎么做：不要因为 grep 不到就断定事件没人发；先查矩阵的 `Dispatchers` 列，再回到对应包读封装层。

- **未声明事件串清单（undeclared event strings）**：矩阵的第二张表，列出「非 harness 或未声明」的事件字符串及其派发方/监听方。
  - 何时用：怀疑自己撞上了半正式契约。
  - 怎么做：把它当升级候选清单。里面有 `agent/request`（由 `agent-loop` 以 `waterfall` 派发，被 `compaction-basic` 和 `timeline` 监听）、`loader/volatile-update`、以及 `internal/*` 一族（`internal/config`、`internal/dispatch`、`internal/plugin`、`internal/service`、`internal/status`）；还有 UI 侧的 `theme/change`、`locale/change`、`slots/changed`、`connection/reset`。要长期依赖其中任何一个，先把它提升成声明事件。

- **应用级监听者边界（app-level listener boundary）**：矩阵只覆盖包级生产/消费关系，应用级监听者不在范围内。Desktop Host 就是这样一个越界者：它通过 `installOperationDiagnostics` 订阅 `plugin-manager/operation`，并向壳转发有界记录——所以在矩阵里 `plugin-manager/operation` 的 Listeners 是空的，但这不代表没人听。
  - 何时用：核对「这个 emit 事件到底有没有消费者」。
  - 怎么做：空 Listeners 优先解释为「包外有监听者」或「预留钩子」，而不是死代码。矩阵里 Listeners 为空的事件有一批：`agent-loop/config-start-failed`、`authorization/settled`、`connection/request`、`hmr/change`、`hmr/reload`、`session-telemetry/record`、`skills/change`、`system-prompt/change`、`workflow/start`、`workflow/end`、`worktree/cleanup`。

- **生成式维护（generated maintenance）**：两段表格都由代码生成，维护模式写明「Cordis 事件声明与生产者/监听者边由仓库 TypeScript Program 解析得出」。
  - 何时用：发现表格与实际不符。
  - 怎么做：不要手改表格，改源码再重新生成；表里的 `BEGIN/END GENERATED` 注释标出了可重写区间。

- **命名约定（`domain/verb`）**：事件名统一为「域/动词」的小写连字符形式，如 `agent/pre-step`、`tools/post-execute`、`fs/write-intent`、`workspace/session-archived`。域前缀直接对应包族：`agent-`、`api-session/`、`cordis/`、`credentials/`、`deepseek-account/`、`fs/`、`goal/`、`llm/`、`mcp-manager/`、`plugin-manager/`、`plugin-market/`、`schedule/`、`session/`、`session-telemetry/`、`skills/`、`subagent/`、`system-prompt/`、`timeline/`、`tools/`、`user-questions/`、`web/`、`webserver/`、`workflow/`、`working-directory/`、`workspace/`、`worktree/`。

## 关键概念
- **harness 自有事件**：由 harness 包（而非 Cordis 内核）声明并派发的事件，矩阵只收这一类。
- **Mode**：事件的派发模式，取值 `emit` / `serial` / `waterfall` / `parallel` / `bail`。
- **`Declared in`**：事件类型声明的源文件与行号，是契约的唯一定位符。
- **Dispatcher**：在代码里实际触发该事件的包，可能多个。
- **Listener**：订阅该事件的包，可能几十个。
- **`events.dispatch`**：服务层统一派发助手，与直接 `ctx.emit` 并列为两种派发形态。
- **内含派发**：从封装层而非插件上下文触发事件的做法，如 subagent 生命周期封装。
- **未声明事件串**：源码里出现但未进类型声明的事件名，属半正式契约。
- **应用级监听者**：包矩阵之外的订阅方，如 Desktop Host 的 `installOperationDiagnostics`。

## 心智模型
- 当你要往某处插一手时，先读那一行的 `Mode`：`emit` 是旁听席，`waterfall` 才是手术台。
- 把 `Declared in` 看成「这个事件的不动产权证」，`Dispatchers` 和 `Listeners` 只是当下的租户名册。
- 把空的 `Listeners` 看成「包外还有人听」或「预埋钩子」，不要看成可以随手删的死代码。
- 把 `session/event` 看成全系统的总线主干：三十余个监听方挂在上面，任何在这条事件上做昂贵工作的改动都会乘上这个基数。

## 反模式
- **在 `emit` 事件的监听者里指望改变结果**：`emit` 是观测模式，返回值不构成改写通道；要改写必须换事件或换模式，而换模式意味着重审全部监听者。
- **在 `waterfall` 链上做重活**：`tools/pre-execute`、`agent/pre-step`、`llm/stream` 都在关键路径上逐跳串行，一个慢监听者会拖住整条链，且它的延迟会出现在每一次工具调用上。
- **把 `bail` 当普通拦截用**：`bail` 能短路授权路径，滥用等于给某个包一票否决权；矩阵里它只出现一次是有意的。
- **手改生成表**：`BEGIN/END GENERATED` 区间的唯一来源是 TypeScript Program，手改会在下次生成时静默丢失。
- **以 `grep ctx.emit` 判定事件无人派发**：内含派发位置（subagent 生命周期封装、`emitAgentEvent`）不会出现在搜索结果里。
- **在自己包里用裸字符串派发新事件**：那就落进「未声明事件串」表，别人无法从类型层面发现你，也无法从矩阵里查到影响面。
- **在 `session/event` 上做每事件重计算**：这是最热的一条事件，监听方数量级在数十，成本按监听者数量相乘。

## 代码/配置示例

矩阵的单行契约形状（`Mode` 与括号内的派发形态是两处独立信息）：

```text
Event                  | Mode      | Declared in                                     | Dispatchers                | Listeners
tools/pre-execute      | waterfall | packages/core/tools/src/events.ts:18            | tools (waterfall)          | auto-review, hooks-claude-code, hooks-codex, liveshare, tool-jobs, workspace-changes
tools/result           | emit      | packages/core/tools/src/events.ts:49            | tools (events.dispatch)    | agent-instructions, claude-code-mods, cua, forge-session, liveshare, subagent, timeline, tool-office, tool-present, ui-trajectory
webserver/authorize    | bail      | packages/host/webserver/src/index.ts:60         | remote-connection (bail),  | connection
                       |           |                                                 | webserver (bail)           |
```

生成区间用注释标出，只有区间内可被重写：

```markdown
<!-- BEGIN GENERATED event-producer-consumer:events -->
| Event | Mode | Declared in | Dispatchers | Listeners |
...
<!-- END GENERATED event-producer-consumer:events -->
```

## 参考表

高频事件速查（`Declared in` 省略公共前缀 `packages/`）：

| Event | Mode | Declared in | Dispatchers | 监听面（代表性） |
| --- | --- | --- | --- | --- |
| `session/event` | `emit` | `core/session/src/index.ts:85` | `session` (`events.dispatch`) | 三十余个：持久化、投影、遥测、telemetry-otel、title、subagent、timeline、token-meter、tool-jobs、workspace-changes 等 |
| `session/created` | `emit` | `core/session/src/index.ts:62` | `session` (`events.dispatch`) | `server`、`session-controller`、`session-projection`、`session-projection-cache`、`session-telemetry` |
| `session/disposed` | `emit` | `core/session/src/index.ts:71` | `session` (`events.dispatch`) | `agent-loop`、`session-persistence-jsonl`、`session-persistence-sqlite`、`session-title`、`workspace-changes` 等 |
| `session/flush` | `parallel` | `core/session/src/index.ts:93` | `session` (`events.dispatch`) | 两个持久化实现 + `session-telemetry` |
| `agent/pre-step` | `waterfall` | `core/agent/src/runtime-types.ts:351` | `agent-loop` (`waterfall`) | 二十余个：`compaction-basic`、`plan-mode`、`subagent`、`agent-instructions`、`time-context`、`tmux-context`、`session-reference`、`tool-skill` 等 |
| `agent/created` | `serial` | `core/agent/src/runtime-types.ts:291` | `agent` (`serial`) | `agent-team`、`goal`、`goal-round-driver`、`permission-presets`、`timeline`、`cua`、两个 hooks 包等 |
| `agent/disposed` | `emit` | `core/agent/src/runtime-types.ts:300` | `agent` (`events.dispatch`) | `agent-loop`、`mcp-client`、`subagent`、`timeline`、`tool-office`、`tool-subagent-control` 等 |
| `agent/status` | `emit` | `core/agent/src/runtime-types.ts:310` | `agent-loop` (`emit`) | `acp`、`compaction-basic`、`goal-round-driver`、`server`、`session-controller`、`timeline` |
| `agent/error` | `emit` | `core/agent/src/runtime-types.ts:430` | `agent-loop` (`emit`)、`cua` (`emitAgentEvent`) | `acp`、`headless`、`server`、`session-telemetry`、`subagent` 等 |
| `agent/request-error` | `waterfall` | `core/agent/src/runtime-types.ts:390` | `agent-loop` (`waterfall`) | `compaction-basic`、`compaction-image-offload`、`llm-retry` |
| `tools/pre-execute` | `waterfall` | `core/tools/src/events.ts:18` | `tools` (`waterfall`) | `auto-review`、`liveshare`、`tool-jobs`、`workspace-changes`、两个 hooks 包 |
| `tools/execute` | `waterfall` | `core/tools/src/events.ts:29` | `tools` (`waterfall`) | `cua`、两个浏览器运行时、`session-checkpoint-policy`、`timeout-policy` |
| `tools/post-execute` | `waterfall` | `core/tools/src/events.ts:41` | `tools` (`waterfall`) | `spill-policy`、`repeat-tool-reminder`、`tool-fs-search`、两个 hooks 包 |
| `tools/result` | `emit` | `core/tools/src/events.ts:49` | `tools` (`events.dispatch`) | `subagent`、`timeline`、`tool-present`、`tool-office`、`ui-trajectory` 等 |
| `tools/change` | `emit` | `core/tools/src/events.ts:56` | `tools`、`agent-preset-registry` | `browser-use-runtime`、`timeline` |
| `llm/stream` | `waterfall` | `llm/llm/src/index.ts:78` | `llm` (`waterfall`) | `llm-replay`、`session-title`、`session-checkpoint-policy`、`timeline` |
| `system-prompt/assemble` | `waterfall` | `core/system-prompt/src/index.ts:41` | `system-prompt` (`waterfall`) | `browser-use-runtime`、`working-directory` |
| `webserver/authorize` | `bail` | `host/webserver/src/index.ts:60` | `remote-connection`、`webserver` | `connection` |
| `webserver/request` | `waterfall` | `host/webserver/src/index.ts:68` | `webserver` (`waterfall`) | `authentication-token`、`deepseek-account`、`mcp-client`、`remote-connection` |
| `workspace/session-stop` | `parallel` | `workspace/workspace/src/index.ts:148` | `workspace` (`parallel`) | `agent`、`jobs`、`schedule`、`subagent` |
| `plugin-manager/operation` | `parallel` | `boot/plugin-manager/src/types.ts:447` | `plugin-manager` (`parallel`) | 表内为空；Desktop Host 经 `installOperationDiagnostics` 包外订阅 |

## 实例演练

场景：一次普通的 shell 工具调用，穿过 `tools` 事件族的四个接缝。

1. 契约入口在 `packages/core/tools/src/events.ts`。`tools/pre-execute` 声明在第 18 行，模式 `waterfall`，派发方是 `tools` 包。这意味着六个监听方按链式顺序经过同一次调用：`auto-review` 可以在这里拦下高风险命令，`liveshare` 把意图广播给协作者，`tool-jobs` 可以把它转成后台任务，`workspace-changes` 提前登记这次调用可能带来的文件变更，两个 hooks 包（`hooks-claude-code`、`hooks-codex`）把外部钩子接进来。
2. 若未被短路，进入 `tools/execute`（第 29 行，同为 `waterfall`）。这里的监听方换成了执行面本身：`cua`、两个浏览器运行时、`session-checkpoint-policy`（决定是否落检查点）、`timeout-policy`（注入超时预算）。注意 `tools/pre-execute` 和 `tools/execute` 的监听方集合几乎不重叠——接缝按阶段切分，而不是按功能切分。
3. 执行结束走 `tools/post-execute`（第 41 行，`waterfall`）：`spill-policy` 决定大输出是否溢出到外部存储，`repeat-tool-reminder` 检测重复调用，`tool-fs-search` 补搜索语义，hooks 再次介入。这一层仍可改写结果。
4. 最后是 `tools/result`（第 49 行，`emit`，派发形态是 `events.dispatch`）。十个监听方在这里纯观测：`timeline` 记录、`tool-present` 决定交付、`ui-trajectory` 渲染轨迹、`subagent` 把结果回传给父 agent、`tool-office` 与 `forge-session` 各取所需。写到这里的值已经定了。

对照实验：把同样的四段看成「三扇可改写的门 + 一个旁听席」。如果你的需求是「改变工具行为」，答案只能在第 1–3 步；如果需求是「知道工具做了什么」，答案在第 4 步。这个判据不需要读任何实现，只看 `Mode` 一列。

再叠加一层：`agent/pre-step` 也是 `waterfall`，监听方二十余个，其中 `compaction-basic` 同时出现在 `agent/pre-step`、`agent/request-error`、`agent/status` 三条事件上。当一个包跨多条事件出现时，它通常在维护一个跨阶段的状态机——这类包是改动风险最高的邻居，动手前应把它在所有相关行里的位置列全。

## 关键要点
1. 一行五个字段的读法固定：先 `Declared in` 确认契约，再 `Mode` 确认权限，再 `Listeners` 确认影响面。
2. `emit` 是观测，`waterfall` 是接缝，`serial` 是有序响应，`parallel` 是并行扇出，`bail` 是授权短路——`bail` 全表唯一，不要新增。
3. 事件名遵循 `domain/verb`，域前缀就是包族，可按前缀批量评估影响面。
4. 空 `Listeners` 不等于无消费者：应用级监听者（Desktop Host 的 `installOperationDiagnostics`）在矩阵之外。
5. 找不到派发方时先想内含派发：subagent 生命周期封装和 `emitAgentEvent` 绕过了 `ctx.emit`。
6. 「未声明事件串」表是升级候选清单，长期依赖前先提升为声明事件。
7. 表格由 TypeScript Program 生成，唯一正确的修法是改源码后重新生成。

## 关联
- **第 4 章 工具执行流水线**：`tools/pre-execute` → `tools/execute` → `tools/post-execute` → `tools/result` 四段就是那条流水线的可插拔面。
- **第 18 章 事件**：`emit` / `serial` / `waterfall` / `parallel` / `bail` 的语义由 Cordis 事件系统定义，本章只记录谁用了哪种。
- **第 28 章 会话与对话**：`session/event` 是全系统最热的一条事件，持久化、投影、遥测、标题全部挂在它上面。
- **第 29 章 Agent 与子代理编排**：`agent/created` 的 `serial` 语义和 subagent 的内含派发位置都在这一章展开。
- **第 36 章 Web 客户端**：`webserver/authorize`、`webserver/request`、`webserver/upgrade` 构成 `/api` 的信任围栏。
- **发布-订阅（pub/sub）与观察者模式**：本章的矩阵是这两种模式在大型 TypeScript 单仓里的落地形态——用生成物替代人工维护的注册表。
