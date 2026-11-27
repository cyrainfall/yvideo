# 第 24 章：Fiber API

## 核心思想

fiber 是**一次插件应用的运行时实例**：它同时装着生命周期状态、经过校验的配置、以及已注册的作用（effect）。`ctx.fiber` 指向当前 fiber，`ctx.effect()` 只是把调用委托给它。把 fiber 理解成"插件实例的账本"，就能解释本章所有 API 的分工——一半在记账（`rawConfig` / `effectiveConfig` / `provisions` / `committed`），一半在追账（`resolveConfig` / `update` / `restart` / `await` / `dispose`）。

## 框架与方法

- **`ctx.effect(execute, label?)`：唯一的副作用原语**
  - 何时用：任何需要"注册时生效、卸载时还原"的动作。
  - 怎么做：`execute` **立即运行**；它产生的 disposer 被收集，在两种时机之一按**相反顺序**运行——调用返回的 disposer，或 fiber 卸载，**以先发生者为准**。重复调用返回的 disposer 是空操作。fiber 已经 dispose 时抛 `CordisError('INACTIVE_EFFECT')`；`execute` 返回不受支持的结构时抛 `TypeError`。`label` 会出现在 `getEffects()` 的诊断树中。
  - 返回值的两种形态对应两种作用体：同步作用体返回 `Disposable<Promise<void>>`，含异步的作用体返回 `AsyncDisposable<Promise<void>>`——两者都保证"清理完成后才结算"。

- **作用体的三种可接受结构**
  - 何时用：需要在一次 effect 里注册多个资源时。
  - 怎么做：单个清理函数；兑现为清理函数的 promise；或产出多个清理函数的（可能为异步的）可迭代对象。**生成器作用**会在每个清理函数产生时立即注册，因此"边产出边登记"，而不是等迭代完再统一登记。

- **配置三态：`rawConfig` / `effectiveConfig` / `resolveConfig`**
  - 何时用：读取、试算、或怀疑"配置没生效"时。
  - 怎么做：
    - `rawConfig`：为下次激活保留的**原始输入**，不求值表达式、不校验。
    - `effectiveConfig`：传给插件激活过程、或最近一次成功保留实例的更新的**那个对象**。候选配置求值不发布它；volatile 更新保留其中的引用。**激活前为 `undefined`，卸载后仍可读**——所以需要"运行中实例"的调用方必须另外检查 `state`。
    - `resolveConfig(config)`：用此 fiber 的 `internal/config` 钩子和运行时 schema 对**候选值**求值并校验。它**不发布结果、不替换原始输入、不提交运行中的 volatile 引用**——纯粹是试算。返回候选的解析结果并保留 schema 返回对象的身份；schema 拒绝时抛 `ValidationError`，钩子自身抛的错原样传播。钩子用到的注入服务必须已经可用。

- **`update(config, noSave = false)`：把候选变成现状**
  - 何时用：程序化改配置。
  - 怎么做：求值候选 → 保留原始输入 → 通过更新 waterfall（`internal/update`）应用。pending 状态的 fiber 会把求值**推迟到激活时**；`noSave` 为 `true` 时抑制持久化通知（对应 `internal/commit`），同步监听器处理掉更新时返回 `undefined`，活动 fiber 的候选非法时抛 `ValidationError`。

- **`await()` / `restart()` / `dispose()`：三种收束方式**
  - 何时用：等待稳定、重载、彻底卸载。
  - 怎么做：`await()` 等当前生命周期工作完成，并**重新抛出**配置校验或插件启动错误，成功后返回 fiber 本身；`restart()` 用当前配置 dispose 再立即重新加载，已在 dispose 状态时抛 `CordisError('INACTIVE_EFFECT')`；`dispose` 是只读属性（`() => Promise<void>`），卸载插件并在清理完成后结算。

- **诊断入口：`assertActive()` 与 `getEffects()`**
  - 何时用：在可能已失效的上下文里继续操作前；排查"谁没清理"。
  - 怎么做：`assertActive()` 在 fiber 已 dispose 时抛 `CordisError`（`INACTIVE_EFFECT`，其 `uid` 已被清空），仍活动时无返回；`getEffects()` 为每个**带标签的**活动作用返回一棵 `EffectMeta` 树（`label` + 嵌套 `children`）。

## 关键概念

- **fiber**：单次插件应用的运行时实例，跟踪依赖状态、原始配置与有效配置、生命周期作用与清理操作。
- **`ctx.fiber`**：拥有当前上下文的 fiber；`ctx.effect` 委托给它。
- **`uid`**：注册表内唯一 id；根 fiber 为 `0`，dispose 后为 `null`。
- **`provisions`**：fiber 拥有的服务实现集合，含隔离域中的实现。
- **`committed`**：在依赖方清理完成前保留的必需服务实现。
- **`inertia`**：当前正在进行的加载或卸载转换；无转换时为 `undefined`。
- **`EffectMeta`**：诊断树节点，`label` 加嵌套 `children`，只为带标签的作用生成。
- **`CordisError`**：带稳定机器可读错误码的框架错误，目前公开的码是 `INACTIVE_EFFECT`。
- **`ValidationError`**：standard-schema 校验失败时抛出的错误，继承 `TypeError`。
- **`Disposable<T>`**：作用返回的清理函数；卸载时按注册相反顺序运行，可为异步。

## 心智模型

- 把 fiber 看成一插件实例的账本：`rawConfig` 是"输入原文"，`effectiveConfig` 是"已入账的那一版"，`resolveConfig` 是"试算不落账"，`update` 才是"落账"。
- 当在读 `effectiveConfig` 做判断时，同时读 `state`——因为卸载后它依然可读，单看它会把已死的实例当成活的。
- 把 effect 的 disposer 看成一次性票据：重复调用无害，但也不代表能"再恢复一次"。
- 把 `uid` 为 `null` 看成"这具身体已经注销"：此后任何 effect 都会 `INACTIVE_EFFECT`。

## 反模式

- **在已卸载的上下文里继续注册副作用**：拿到 `CordisError('INACTIVE_EFFECT')`。正确做法是操作前 `assertActive()`，或把逻辑放进仍在活动的 fiber。
- **把 `effectiveConfig` 当成"当前一定在跑的配置"**：它激活前是 `undefined`，卸载后仍可读；判断活性必须看 `state`。
- **用 `resolveConfig` 去应用配置**：它明确不发布结果、不替换原始输入、不提交 volatile 引用——试算完什么都没变。
- **在 `update` 上假设"一定重挂载"**：同步监听器可以处理掉更新，此时返回 `undefined` 且实例未重建；pending fiber 还会把求值推迟到激活时。
- **依赖 effect 的注册顺序去做清理**：disposer 按注册的**相反顺序**运行，注册顺序与清理顺序是反的。
- **把 `getEffects()` 当成完整审计**：它只为**带标签的**活动作用返回元数据；没给 `label` 的作用不出现在诊断树里。
- **手工比对 `ValidationError` 的类型**：跨 cordis 副本时用 `ValidationError.is(error)`，它认的是全局品牌标识。

## 代码/配置示例

`ctx.effect` 与 `fiber.effect` 的契约：

```ts
effect(execute: () => SyncEffect, label?: string): Disposable<Promise<void>>
effect(execute: () => Effect, label?: string): AsyncDisposable<Promise<void>>
```

fiber 的字段与访问器：

```ts
public uid: number | null
public readonly ctx: Context
public config: any
public state
public readonly dispose: () => Promise<void>
public committed: Readonly<Dict<Impl>> | undefined
public readonly provisions: Set<Impl>
public inertia: Promise<void> | undefined
get name()
get rawConfig(): unknown
get effectiveConfig(): unknown
```

方法与错误类型：

```ts
assertActive()
getEffects()
resolveConfig(config: unknown): unknown
async await()
async restart()
update(config: any, noSave = false): Awaitable<void>

type Effect<T = any> = SyncEffect<T> | AsyncEffect<T>
type Disposable<T = any> = () => T
interface EffectMeta { label: string; children: EffectMeta[] }

class CordisError extends Error {
  constructor(public code: CordisError.Code, message?: string)
}
namespace CordisError {
  export const Code = {
    INACTIVE_EFFECT: 'cannot create effect on inactive context',
  } as const
}

class ValidationError extends TypeError {
  name = 'ValidationError'
  constructor(public issues: readonly StandardSchemaV1.Issue[])
  static is(error: unknown): error is ValidationError
  static normalizePath(path?: StandardSchemaV1.Issue['path'])
  static formatPath(path: StandardSchemaV1.Issue['path'])
}
```

## 参考表

字段与访问器：

| 成员 | 类型 | 语义 | 是否可变 |
| --- | --- | --- | --- |
| `uid` | `number \| null` | 注册表内唯一 id；根为 `0`，dispose 后 `null` | 可变 |
| `ctx` | `Context` | 插件运行所在的上下文（扩展自父上下文） | 只读 |
| `config` | `any` | 为下次激活保留的原始插件输入 | 可变 |
| `state` | 生命周期状态 | 当前状态；转换会发出 `internal/status` | 可变 |
| `dispose` | `() => Promise<void>` | 卸载插件，清理完成后结算 | 只读 |
| `committed` | `Readonly<Dict<Impl>> \| undefined` | 依赖方清理完成前保留的所需实现 | 可变 |
| `provisions` | `Set<Impl>` | 拥有的服务实现（含隔离实现） | 只读集合 |
| `inertia` | `Promise<void> \| undefined` | 进行中的加载/卸载转换 | 可变 |
| `name` | `string`（getter） | 继承自最近具名祖先，否则 `'root'` | 只读 |
| `rawConfig` | `unknown`（getter） | 原始输入，不求值不校验 | 只读 |
| `effectiveConfig` | `unknown`（getter） | 激活时或最近一次成功更新所用的对象 | 只读 |

方法：

| 方法 | 返回 | 是否发布/改变配置 | 主要失败 |
| --- | --- | --- | --- |
| `effect(execute, label?)` | `Disposable` / `AsyncDisposable` | 否（注册作用） | `INACTIVE_EFFECT`、`TypeError` |
| `assertActive()` | 无 | 否 | `INACTIVE_EFFECT`（uid 已清空） |
| `getEffects()` | `EffectMeta` 树/活动作用 | 否 | — |
| `resolveConfig(cfg)` | 候选解析结果 | **不发布、不替换、不提交** | `ValidationError`；钩子错误原样传播 |
| `await()` | this fiber | 否（等稳定） | 重抛配置校验/启动错误 |
| `restart()` | promise | 重挂载并应用当前配置 | `INACTIVE_EFFECT` |
| `update(cfg, noSave?)` | 可等待结果或 `undefined` | **是**（经 `internal/update`，除非 `noSave`） | 活动 fiber 候选非法 → `ValidationError` |

配置三态一句话对照：

| 视角 | 谁写的 | 何时可见 | 典型误用 |
| --- | --- | --- | --- |
| `rawConfig` | 加载器/调用方原始输入 | 保留到下次激活 | 以为它已经过校验 |
| `effectiveConfig` | 激活或成功保留实例的更新 | 激活后；卸载后仍可读 | 当成活性判据 |
| `resolveConfig()` | 你自己试算 | 立即返回，不落账 | 以为应用了配置 |

## 实例演练

一次程序化配置更新，从候选到落账：

1. 调用方执行 `fiber.update({ retries: 3 }, false)`。
2. fiber 是否为 pending？若是，**求值被推迟到激活时**，本次只保留原始输入。
3. 活动 fiber 走 `resolveConfig` 路径：`internal/config` 钩子先跑，随后运行时 schema 校验。钩子用到的注入服务必须已经可用，否则钩子自己会抛。
4. 校验失败 → `ValidationError`，其 `issues` 每条一行消息，路径可用 `formatPath` 拼成点号字符串、或 `normalizePath` 拆成纯属性键。此时**什么都没改**。
5. 校验通过 → 保留原始输入（进 `rawConfig`），然后通过更新 waterfall `internal/update` 应用。这里是关键分叉：某个同步监听器处理掉了更新，`update` 返回 `undefined`，实例**不被重建**，而 volatile 更新会保留 `effectiveConfig` 中的引用；没有监听器接管则走向重挂载。
6. 除非 `noSave` 为 `true`，否则 `internal/commit` 会把原始配置持久化。
7. 状态每次转换都发出 `internal/status`——想观测整个过程，就订阅它。
8. 需要确保稳定后再继续的调用方 `await fiber.await()`；它会等当前生命周期工作完成，并把启动期错误重新抛出，而不是把它们咽掉。

对照另一条路径：调用 `restart()` 时，fiber 用**当前配置** dispose 再立即重载，等价于"先按逆序跑完所有 disposer，再从头激活"。因此 restart 期间会持续发出 `internal/status`，`inertia` 表示"转换正在进行"；处于 dispose 状态的 fiber 其 `uid` 为 `null`。若在 dispose 之后才想起要注册 effect，得到的不是静默失败而是 `CordisError('INACTIVE_EFFECT')`——这是好的失败方式。

## 关键要点

1. effect 的 disposer 在"你调用它"或"fiber 卸载"两者**先发生者**时运行，顺序与注册相反，重复调用无害。
2. 生成器作用边产出边注册，每个清理函数产生时即登记。
3. `rawConfig` 是输入原文，`effectiveConfig` 是已入账版本，`resolveConfig` 只试算。
4. `effectiveConfig` 卸载后仍可读——判断活性必须看 `state`。
5. `update` 不一定重挂载：同步监听器可接管，pending fiber 会延后求值。
6. `await()` 会重抛启动错误，是"别把失败咽掉"的官方姿态。
7. 跨副本判校验错误用 `ValidationError.is`，路径格式化用 `formatPath` / `normalizePath`。

## 关联

- **第 16 章**：生命周期与副作用的教程视角；本章是同一套语义的完整契约。
- **第 19 章**：配置校验与 schema，`resolveConfig` / `ValidationError` 的上游。
- **第 22 章**：`ctx.fiber`、`ctx[Context.effect]` 与"fiber 所有"的作用域语义。
- **第 23 章**：`internal/config`、`internal/update`、`internal/commit` 的 waterfall 分发语义。
- **第 25 章**：这些 `internal/*` 事件的一行职责速查。
