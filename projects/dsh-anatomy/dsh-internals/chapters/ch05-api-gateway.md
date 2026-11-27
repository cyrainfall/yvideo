# 第 5 章：API 网关

## 核心思想

Host 上的业务服务用 `@Remote` 或 `@RemoteScope` 选择对 Client 开放的方法；构建期从唯一的 Host `ts.Program` 严格分析出**调用描述符**与 codec；运行期调用复用 Connection 的 RPC 与 `/api` 路由，逐次解析描述符、校验参数、解析对象、调用实时 Cordis 服务。边界同样重要：Remote 只承担单请求单结果的一元方法与 Host→Client 流，会话事件流、分页、增量 reduce 与投影不应伪装成 Remote 方法。

## 框架与方法

- **两个装饰器（`@Remote` / `@RemoteScope`）**：`@Remote` 调用根 Host Context 中注册的 Cordis 服务；`@RemoteScope(key)` 先通过 `ctx.typert.contexts` 把 identity 解析为作用域 Context，再从该 Context 取得服务并调用——适用于方法依赖作用域组合、而不需要显式接收 `Agent` 等对象的情形。
  - 何时用：要让一个业务方法对 Client 可见时。未标记的方法不会进入生成的 Client 类型或运行时贡献，也不能通过 `ctx.remote` 调用。
  - 怎么做：`@Remote` 接受导出名或 `{ name?, mode?, resources? }`；`@RemoteScope(key, option?)` 的第二个参数接受导出名（如 `@RemoteScope('agent', 'current')`）或 `{ name?, resources? }`。`resources` 按资源种类给出读取函数，返回一次调用所访问资源的身份，类型从被装饰方法推断；多数方法不声明它，而由声明了 `resource` 的 lookup 参数、作用域 Context 或 `typert.resources` 的默认字段与 resolver 提供。
- **wire identity 与 lookup（`TypertLookupMap` / `ctx.typert.lookups`）**：复杂 Host 对象不能直接跨 wire 传输；业务包必须通过 `TypertLookupMap` 声明它与 wire identity 的关联，并在运行时向 `ctx.typert.lookups` 注册默认解析提供方。
  - 何时用：签名里有 `Agent`、`Session`、workspace 这类对象参数时。
  - 怎么做：Host 签名中的 `Agent` 参数名为 `agent`，生成的 wire 字段为 `agentId`，Gateway 在调用业务方法前把 id 解析回对象。Host 组合可用 `ctx.typert.lookups.configure()` 覆盖某个 key 的解析策略，而不改变业务包拥有的参数名、wire 字段或规范类型 symbol。
  - 两段式生命周期：`register()` 同时提供稳定声明与默认 resolver；`configure()` 提供由 Host 组合拥有、可异步、受 effect 生命周期约束的 resolver。配置可先于提供方挂载——此时调用仍以 `gateway/lookup-unavailable` 失败；配置卸载后恢复提供方默认策略。
- **严格生成流水线（`scripts/generate-typert.ts`）**：根构建先跑仅源码的 Host 分析，再编译打包 Host 与 Client face，最后构建 Web。生成器以 Host aggregate 为唯一 `ts.Program` 种子，在包编译前写出 Remote 声明；Host 的 tsdown 阶段只转换装饰器、不重复生成元数据；Client 阶段消费这些声明与运行时贡献。各包本地配置根据 `DSH_BUILD_FACE` 返回当前阶段入口；`api/remotes`、`api/gateway`、`api/session-controller`、`api/workspace-controller`（外加 `client/connection`）都拆 TypeScript face，消费方必须分别引用各自的 `tsconfig.host.json` 或 `tsconfig.client.json`。
  - 何时用：新增或修改任何 Remote 约定时。
  - 怎么做：产物写进贡献业务包自己的 `lib/`（不是源码目录）；业务包用 `./typert` 暴露 Host Loader 入口、用 `./remote` 暴露 Host-for-Client 入口，生成器校验这两个 export 与发布文件清单。`api-remotes` 的 `clientBundle(..., { hostPhase: true })` 让 Host 入口在 Host tsdown 生成，Client tsdown 只生成 browser 入口。
- **严格分析约束（acceptance rules）**：Remote 必须是公开、非静态、有具体实现的实例方法；不能是泛型；参数必须是具名且必填的简单标识符，不能使用解构、默认值、rest 或可选参数。
  - 何时用：写新 Remote 方法，或解释一次莫名的构建失败。
  - 怎么做：可 JSON 表示的普通类型由 Typert 生成严格 schema；工作区 class 等复杂对象必须有唯一的 `TypertLookupMap` 声明。lookup 与 Context 包同时负责静态声明合并与运行时提供方注册，缺任一侧都会在构建时或首次调用时失败。需要协作式取消时，Host 签名的最后一个参数必须是全局类型的 `signal: AbortSignal`——它记录进描述符而不进入 `args`，Client 生成的方法接受最后一个可选的 `AbortSignal`。
- **运行时调用序列（trust / peer / access / codec / lookup）**：Client 调用形状是 `connection.rpc.call('/api', '<namespace>/<method>', { args }, signal)`；HTTP carrier 对应 `POST /api/<namespace>/<method>`，payload 只含一个具名 `args` 对象。
  - 何时用：调试一次调用为什么被拒。
  - 怎么做：Connection 在 HTTP bridge 之前做 `/api` 的统一信任检查，再在共享 FetchHandler 内分发；Gateway 只认领存在严格描述符或活跃 SRC marker 的两段式 endpoint，每次调用都从当前注册表解析描述符与实时服务（不缓存业务对象），确定其代表的 Peer（已 dispose 的以 `gateway/peer-disposed` 被拒），并要求 `args` 字段集合与描述符完全一致。对非 owner 的 Peer，它解析调用访问的资源并询问 `ctx.remoteAccess.decide()`——被拒时不解析 lookup、不激活 Agent。之后 codec 校验 wire 值、lookup 或 Context 提供方解析对象，最后调用 binding 指向的服务方法。
  - 失败面：缺少提供方、identity 未命中、binding 不一致、参数缺失或多余、schema 失败、方法不存在，都在进入业务代码前或离开业务代码后失败。含 `Uint8Array` 的一元结果（含嵌套字段与数组条目）走二进制 Remote 传输：Gateway 把二进制字段投影为 JSON 兼容元数据及相对结果的字节附件，由 Connection 封装为 multipart；需要 RPC 信封之外响应的功能注册精确的 Connection Fetch 路由，其他请求返回 404。
  - 错误映射：`api-session-controller` 负责 Agent／Session 身份策略与对应 lookup——复用 live Agent、自动恢复普通冷会话、对并发恢复去重、拒绝由 subagent routing 拥有的 identity。恢复失败与 ownership fence 抛出带自有码的 `RemoteError`（`session/not-found` 或 `session/agent-busy`），Gateway 原样编码上 wire；只有未归类的 throw 才折成 `gateway/internal`。
- **流方法（`mode: 'stream'`）**：标记返回 `Iterable`、`AsyncIterable` 或 `RemoteStream<Out, In>` 的方法；Gateway 把每个产出项经多路复用的 `/api/remote.mux` WebSocket 或进程内载体投递，Client 生成的方法返回 `RemoteStreamHandle<Out, In>`。
  - 何时用：方法返回一串项而不是单值。
  - 怎么做：Client 侧迭代下行项，并为同一条逻辑流的上行提供 `send`、`end` 与 `dispose`；`RemoteStream<Out, In>` 的第二个类型参数声明上行项类型，Gateway 在 Host 方法通过 `this.ctx.invocation.uplink<In>()` 读取之前，用生成的 `In` codec 校验 Client 发送的每一项（它们来自浏览器）。上行既不进入 `args` 也不进入参数列表；帧、半关闭、取消与 inbox 上限归 Gateway README 约定。
- **Client 装配与依赖纪律（`ctx.remote` / `agentCtx.remote`）**：Client 使用普通对象上的具体函数，不使用 JavaScript Proxy；直接调用与作用域调用分别在 `ctx.remote.<namespace>` 与 `agentCtx.remote.<namespace>`。
  - 何时用：新增业务包，或新增一个 Remote namespace。
  - 怎么做：每个 namespace 都是注册为 `remote.<namespace>` 的可追踪 Cordis 子服务；assembly 通过 `ctx.remote.$mount()` 挂载贡献，最后一个方法撤回后该 namespace 卸载。依赖声明归实际调用方：只有读取该 namespace 的业务包才在 `inject` 中同时声明 `remote` 与 `remote.<namespace>`，只负责挂载的 assembly 与不调用它的上层运行时不代业务包声明。Client 应用只装配 `@deepseek-ai/dsh-api-remotes`（导入被选业务包的 `/remote` 子路径并重导出声明合并），增加一个 Host Remote 包是 Client 组合所有者的显式选择；该装配不依赖 React。当 `@Remote` 方法恰好有一个 lookup 参数、且同名 `TypertContextMap` 使用相同 wire identity 时，生成的作用域签名会省略该参数；`@RemoteScope` 只生成作用域调用接口。
- **SRC 回退与开发模式**：Host 通过 `node --import tsx/esm` 从源码启动时不执行 Typert 编译插件；标准 decorator 初始化器仍把方法名与调用模式记录到 Service 原型上的带版本描述符中，`TypertRemoteService` 或 `bindTypertRemote()` 提供显式 binding，Gateway 因而能在不启动 `ts.Program` 的情况下构造一个较弱的临时描述符。
  - 何时用：本地 `dev:web` 调试 Host 源码时。
  - 怎么做：SRC 从运行中函数解析简单参数名；参数名与某已注册 lookup 的 `parameter` 相同（如 `agent`、`session`）就用其 `agentId`／`sessionId` wire 字段并在 Host 解析对象，其他参数只检查是否为无循环、无特殊 prototype 的 JSON-safe 数据。它不读类型、不生成 Zod、不推断可选参数，也不支持解构、默认值、rest 或重复名；Client 不会从运行中的 Host 发现 decorator，并拒绝挂载缺少严格 codec 的 SRC 描述符。
  - 构建分工：`pnpm run dev:web` 先构建 Host、Client 与 Web 产物，再启动源码 Host 并持续重建 Client bundle。只改方法实现体不需重生成；改装饰器、导出名、namespace、参数、返回值、lookup、Context 或取消签名时，重跑 `pnpm run build:lib`（先 Host 后 Client）。watcher 不分析 Host decorator、不生成 Remote Client DTS；`pnpm run typecheck` 先用不打包的 Typert 生成刷新 Host 约定，再跑 Client tsc。

## 关键概念

- **Remote 方法描述符**：构建期生成的严格调用契约，含参数、返回值、取消签名与 schema；运行期不读 TypeScript。
- **Remote namespace**：注册为 `remote.<namespace>` 的可追踪 Cordis 子服务，也是 Client 调用的命名空间。
- **wire identity**：复杂 Host 对象在 wire 上的稳定标识（如 `agentId`），由 `TypertLookupMap` 声明。
- **lookup resolver**：把 wire identity 解析回 Host 对象的函数，分提供方默认与 Host 组合配置两层。
- **Host face / Client face**：同一份源码的两种构建产物；两侧不进入同一个 `ts.Program`，Host 入口不导入 Client 的 Context 合并，反之亦然。
- **`TypertRemoteService`**：让 Cordis 服务 key 与默认 Remote namespace 在构造器中显式绑定的基类；已有其他基类时可改声明 `readonly typertRemote = bindTypertRemote(this, serviceKey)`。
- **SRC 回退（source runtime）**：从源码启动时由原型描述符构造的较弱临时描述符，只服务 Host 进程。
- **`RemoteStreamHandle<Out, In>`**：Client 侧流句柄，迭代下行项并提供 `send`、`end`、`dispose` 三条上行操作。

## 心智模型

- 把描述符看成构建期快照：运行期只信描述符与 codec，不信源码里的类型。
- 把 lookup 看成「wire id → Host 对象」的解析器，策略可被组合替换，契约不能。
- 把 `/api` 看成一条共享走廊：Connection 管传输、RPC id、响应 envelope 与取消，Gateway 管数据协议与业务分发。
- 把 SRC 看成开发期的梯子：Host 能用，Client 永远不要用。

## 反模式

- **给 Remote 方法加可选、解构、默认值或 rest 参数**：严格分析直接拒绝，构建失败而不是运行时才发现。
- **用 Remote 传会话事件流或分页**：它们是独立数据协议，即使复用 Connection 也不应伪装成 Remote 方法或塞进调用描述符。
- **在业务方法里猜测对象是否来自恢复**：lookup 策略按 key 配置，所有 `agent`／`session` 参数共享冷恢复行为；只接受 live 对象需要逐参数或逐 endpoint 策略，而这种策略并不存在。
- **让 assembly 代业务包声明 namespace 依赖**：依赖声明归实际调用方，否则任何上层装配都会悄悄拉入不需要的 namespace。

## 代码/配置示例

一个同时提供直接调用与作用域调用的业务服务：

```ts
import type { Agent } from '@deepseek-ai/dsh-agent'
import { TypertRemoteService, Remote, RemoteScope } from '@deepseek-ai/dsh-typert-protocol'
import type { Context } from '@deepseek-ai/cordis'

export interface CreateGoalRequest { objective: string }
export interface CreateGoalResult { accepted: boolean }

export class GoalService extends TypertRemoteService {
  constructor(ctx: Context) {
    super(ctx, 'goals')
  }

  @Remote('create')
  createForClient(
    agent: Agent,
    request: CreateGoalRequest,
    signal: AbortSignal,
  ): CreateGoalResult {
    signal.throwIfAborted()
    return this.create(agent, request)
  }

  @RemoteScope('agent', 'current')
  currentForClient(): CreateGoalResult {
    return { accepted: true }
  }

  private create(_agent: Agent, request: CreateGoalRequest): CreateGoalResult {
    return { accepted: request.objective.length > 0 }
  }
}
```

Client 侧调用与依赖声明：

```ts
import type { SessionId } from '@deepseek-ai/dsh-session/types'
import type { AgentContext } from '@deepseek-ai/dsh-api-session-controller/client'
import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-api-remotes/client'

export const inject = ['remote', 'remote.goals']

declare const ctx: Context
declare const agentCtx: AgentContext
declare const agentId: SessionId

await ctx.remote.goals.create(agentId, { objective: 'ship it' })
await agentCtx.remote.goals.create({ objective: 'ship it' })
```

## 参考表

组件职责：

| 位置 | 包或入口 | 职责 |
|---|---|---|
| 共享 | `@deepseek-ai/dsh-typert-protocol` | 声明 decorator、Gateway binding、可合并协议映射、调用描述符及提供方类型；不启动 TypeScript 分析，也不注册 Cordis 服务 |
| 构建 | `@deepseek-ai/dsh-typert-generator` | 从 Host `ts.Program` 严格分析 Remote 签名、类型图、lookup、Context 与源码位置，生成 Host 与 Host-for-Client 产物 |
| Host | `@deepseek-ai/dsh-typert-registry` 与 Loader | 把生成的 Host 描述符、schema 及业务包注册项放入 `ctx.typert`，并持有 lookup 与 Context 提供方 |
| Host | `@deepseek-ai/dsh-api-session-controller` | 负责应用的 Agent／Session 身份策略，并配置对应的 Typert lookup |
| Host | `@deepseek-ai/dsh-api-gateway` | 提供 `ctx.typertGateway`，认领 Remote endpoint，校验请求值，解析对象或 Context，并调用实时 Cordis 服务 |
| Host | `@deepseek-ai/dsh-api-remote-access` | 按 role 的 policy 判定非 owner Peer 可调用哪些方法，过滤列表结果并推送访问快照 |
| Client | `@deepseek-ai/dsh-api-gateway/client` | 提供 `ctx.remote` 与 `remote.<namespace>`，把描述符挂成具体方法，经 Connection 发起与取消调用 |
| Client | `@deepseek-ai/dsh-api-remotes/client` | 显式选择并挂载本应用允许使用的 `/remote` 贡献，向业务代码带入声明合并 |
| 双侧 | `@deepseek-ai/dsh-client-connection` | RPC carrier、请求关联、信任边界、取消、响应 envelope 与 `/api` HTTP bridge |

生成文件与消费者：

| 文件 | 消费方 | 内容 |
|---|---|---|
| `typert.host.js` | Host Loader | Host face 的运行时反射、严格调用描述符和 schema 注册值 |
| `typert.host.d.ts` | Host 类型系统 | Host face 的生成声明 |
| `typert.remote-client.js` | `api-remotes` | 可挂载的 `TypertRemoteContribution`，含严格描述符与运行时 codec |
| `typert.remote-client.d.ts` | Client 类型系统 | `TypertRemoteNamespaceMap` 与 `TypertRemoteScopeMap` 的声明合并及 Client-safe 类型引用 |
| `typert.remote-client.d.ts.map` | 编辑器 | 把生成的方法属性映射回 Host 包中的 Remote 方法声明 |

## 实例演练

场景：Client 调用 `ctx.remote.goals.create(agentId, { objective: 'ship it' })`。

构建期，生成器在唯一的 Host aggregate `ts.Program` 中读到 `@Remote('create')`，发现首个参数 `agent: Agent` 在 `TypertLookupMap` 有声明，于是把参数名 `agent` 映射为 wire 字段 `agentId`，并生成 schema、Host 描述符与 Client codec；`signal: AbortSignal` 记进描述符而不进入 `args`。五个文件写进 `lib/`，两个入口已校验。

Client 侧，`api-remotes` 以运行时值导入该业务包的 `/remote` 子路径，通过 `ctx.remote.$mount()` 安装贡献，于是 `ctx.remote.goals` 这个 `remote.goals` 子服务出现，业务包里 `inject = ['remote', 'remote.goals']` 的声明才成立。

传输时，方法调用变成 `connection.rpc.call('/api', 'goals/create', { args }, signal)`，HTTP carrier 上是 `POST /api/goals/create`，body 只含一个 `args` 对象。Connection 先在 HTTP bridge 之前做统一信任检查，再在共享 FetchHandler 内分发。

到网关，Gateway 只认领两段式 endpoint 且必须存在严格描述符或活跃 SRC marker；它从当前注册表解析描述符与实时服务（不缓存业务对象），确定这次调用代表的 Peer（已 dispose 的直接 `gateway/peer-disposed`），检查 `args` 字段集合与描述符完全一致。若该 Peer 不是 owner，它随后解析调用访问的资源并询问 `ctx.remoteAccess.decide()`；被拒时不解析任何 lookup、也不激活 Agent——这条短路顺序同时省成本与保安全。

解析与调用阶段，codec 校验 wire 值，lookup 提供方把 `agentId` 解析成 live `Agent`（必要时自动恢复普通冷会话、并发去重、拒绝由 subagent routing 拥有的 identity），最后调用 `GoalService.createForClient`。恢复失败或 ownership fence 会抛带自有码的 `RemoteError`（`session/not-found` 或 `session/agent-busy`），Gateway 原样编码上 wire；未归类异常才折成 `gateway/internal`。普通 JSON 结果走原处理；含 `Uint8Array` 的结果走二进制传输，由 Client Gateway 用生成 codec 校验。

改代码时：只改 `createForClient` 实现体不必重生成，`dev:web` 的 watcher 重建 Client bundle 即生效；若把 `@Remote` 改成 `@RemoteScope`，或把 `request` 改成可选参数，就必须重跑有序 lib 构建，先 Host 后 Client。

## 关键要点

1. 开放与否只由装饰器决定；未标记的方法既不在 Client 类型里，也不在运行时贡献里。
2. 复杂对象不能跨 wire，必须用 `TypertLookupMap` 声明 wire identity，并用 `register()` 提供默认 resolver。
3. 严格分析排除泛型、可选、解构、默认值与 rest，让生成器不必猜类型。
4. 调用顺序固定：信任检查 → Peer 判定 → args 集合校验 → 访问控制 → codec 校验 → lookup 解析 → 业务调用。
5. 自有错误码（`session/not-found`、`session/agent-busy`）原样上 wire，未归类异常才折成 `gateway/internal`。
6. Remote 只做一元调用与 Host→Client 流；事件流、分页、投影各有独立协议。
7. 改实现体不用重生成，改约定必须 `build:lib` 且先 Host 后 Client。

## 关联

- **第 2 章**：`ctx.remoteAccess`、`ctx.connection`、`ctx.connection.authentication` 等 seam 与本章调用链直接相连。
- **第 3 章**：会话事件流为什么不走 Remote，答案在持久事件与派生历史的纪律里。
- **第 36 章**：Web 客户端如何装配 `api-remotes` 并渲染 Remote 结果。
- **第 39 章**：新增远程 API 的分步手册。
- **外部概念**：gRPC／tRPC 式的「schema 先行 + 代码生成」——描述符是 IDL，生成器是编译器，Gateway 是服务端桩，`ctx.remote` 是客户端桩。
