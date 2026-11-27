# 第 27 章：Service API

## 核心思想

`Service` 是"把一件能力做成 `ctx.<name>`"的基类，它的全部行为可以压成两句话：子类在构造函数里 `super(ctx, name)`，服务**立即注册**，并**随所属 fiber 自动移除**。剩下的 API 面是一组 `Symbol` 键——用途是让子类不覆写框架逻辑也能改写五件事：初始化时机、可用性判定、可调用性、实例派生、拦截与追踪元数据。本章讲契约，第 17 章讲用法。

## 框架与方法

- **定义服务：构造函数里注册，注册即生效**
  - 何时用：某能力要以 `ctx.<name>` 暴露给其他插件。
  - 怎么做：`class Foo extends Service`，构造函数 `super(ctx, name)`。注册发生在这一行，不发生在 `apply`、不发生在某个 `init` 回调里。卸载不需要你写代码：服务随所属 fiber 一起被移除。
  - 判据：`Service` 子类本身就是插件，因此它会以插件身份被装载；"以插件形式加载的子类会将自身注册为 `ctx.<name>`"——装载方式是注册的前提。

- **`Service.init`：把"构造之后"的初始化放进生命周期，而不是构造函数**
  - 何时用：初始化逻辑依赖构造完成后的实例（字段已就位），但仍属于本插件的一次装载。
  - 怎么做：声明一个以 `[Service.init]` 为键的实例方法。框架在构造完成后调用它。这对类插件形态尤其关键——类插件没有 `apply`，构造之后没有别的注入点。

- **`Service.check`：声明实例何时"可用"**
  - 何时用：服务实例存在，但可能暂时不可用（未连接、未就绪）。
  - 怎么做：提供一个可用性谓词，以 `[Service.check]` 为键；该谓词会作为可用性判定传给 `ctx.provide()`。它回答的是「这个实例此刻可用吗」，而注册本身回答的是「它存在吗」。

- **`Service.invoke`：让服务本身可被调用**
  - 何时用：希望消费方写 `ctx.logger('name')` 而不是 `ctx.logger.get('name')`。
  - 怎么做：实现以 `[Service.invoke]` 为键的调用体。签名里明确点名了这个例子：`ctx.logger()` 就是可调用服务。

- **`Service.extend`：派生一个"同族但不同配置"的服务实例**
  - 何时用：需要在既有服务之上派生出扩展实例（例如带默认参数或额外能力的变体）。
  - 怎么做：使用以 `[Service.extend]` 为键的辅助方法，它负责从当前实例派生扩展实例。

- **`ctx.effect(execute, label?)`：一切注册的统一清理入口**
  - 何时用：任何"装上就要能卸掉"的副作用——事件监听、定时器、服务注册、外部连接。
  - 怎么做：`execute` **立即运行**，它产出的 disposer 被收集；调用返回的 disposer 或卸载 fiber，二者先到者触发清理，disposer **按相反顺序**运行。重复调用返回的 disposer 是 no-op。
  - 判据：`execute` 返回的结构不合法抛 `TypeError`；fiber 已 dispose 时抛 `CordisError('INACTIVE_EFFECT')`。`label` 会出现在 `getEffects()` 的诊断树里。

- **`Effect` 的三种形态，越晚 yield 越早清理**
  - 何时用：一次作用要注册多个资源时。
  - 怎么做：返回单个 disposer、返回兑现为 disposer 的 promise、或返回（可能异步的）可迭代对象 yield 多个 disposer。生成器作用**每 yield 一个就注册一个**，因此清理顺序恰好是资源申请顺序的镜像。

- **`Service` 的符号协议按"你改哪一层"选**
  - 何时用：想介入框架对服务的处理，而不是覆写服务方法。
  - 怎么做：`init` 改初始化时机，`check` 改可用性，`invoke` 改可调用性，`extend` 改派生，`metadata` / `mergeIntercept` / `resolveIntercept` 改拦截元数据（虚设类型参数、合并钩子、解析辅助），`tracker` 改上下文追踪元数据。

## 关键概念

- **`Service`**：上下文服务基类。子类以插件形式加载时把自身注册为 `ctx.<name>`。
- **`Service.init`**：构造完成后运行的实例方法的符号键（类插件）。
- **`Service.check`**：可用性谓词的符号键，该谓词传给 `ctx.provide()`。
- **`Service.invoke`**：调用体的符号键，使服务可被调用（如 `ctx.logger()`）。
- **`Service.extend`**：派生扩展服务实例的辅助方法的符号键。
- **`Service.metadata` / `mergeIntercept` / `resolveIntercept` / `tracker`**：拦截与追踪元数据的四个符号键——虚设类型参数、合并钩子、解析辅助、跟踪器元数据。
- **`Effect`**：作用主体结果，单个 disposer / 其 promise / 可迭代的多个 disposer。
- **`Disposable`**：作用返回的清理函数；可异步，卸载会等待它完成。
- **`EffectMeta`**：`{ label, children }` 的树节点，用于把嵌套作用标签暴露给诊断。
- **`INACTIVE_EFFECT`**：在已 dispose 的上下文上创建作用时的稳定错误码。

## 心智模型

- **把 `super(ctx, name)` 看成一次 `ctx.provide(name, this)`**：注册时刻由构造函数决定，注销时刻由 fiber 决定，二者都不由你调度。
- **把 `ctx.effect()` 看成"逆序栈"而不是"回调集合"**：先申请的资源后释放，所以"构造时注册的服务"会比"服务内部启动的连接"更晚被注销——这正是你想要的顺序。
- **把 `Service.*` 符号看成可覆写的框架钩子，而不是 API 表面**：不实现它们时一切正常，实现哪一个就等于声明"我在这一层有特殊语义"。
- **把 `check` 和"实例是否存在"分开看**：注册由构造函数回答，可用性由谓词回答，两者不是同一个问题。

## 反模式

- **在构造函数之外注册服务**：注册时机脱离装载时机，服务在 fiber 未激活时就可见或干脆不可见，依赖方的唤醒时机随之错乱。
- **把 `Service` 子类当普通类 `new` 出来**：服务注册与 fiber 所有权绑在一起，不走插件装载就没有所属 fiber，也就没有随卸载自动移除的保证。
- **在构造函数里做重活**：构造函数只该注册与赋值，构造后的初始化属于 `[Service.init]`。
- **用 `ctx.effect()` 包裹"卸载后仍需存在"的全局副作用**：fiber 重载会把它撤掉，功能静默消失。
- **忽略 disposer 可以是异步的**：卸载会等待它；在里面放长任务会让整个卸载链变慢。
- **依赖 disposer 抛错来发现重复清理**：重复调用是 no-op，不是错误；已废弃上下文上的**创建**才会抛 `INACTIVE_EFFECT`。
- **省略 `label`**：`getEffects()` 只返回带标签的活动作用树，没标签的作用在诊断里难以定位。
- **把 `check` 实现成"永远是 true"**：等于放弃了可用性语义，所有读这个判定的消费方都只会看到「可用」。

## 代码/配置示例

服务基类的关键约定（签名取自原文）：

```ts
/** Symbol key of an instance method run after construction (class plugins). */
static readonly init: unique symbol

/** Symbol key of the availability predicate passed to `ctx.provide()`. */
static readonly check: unique symbol

/** Symbol key of the call body making a service callable (e.g. `ctx.logger()`). */
static readonly invoke: unique symbol

/** Symbol key of the phantom intercept-metadata type parameter. */
static readonly metadata: unique symbol

/** Symbol key of the helper deriving an extended service instance. */
static readonly extend: unique symbol

/** Symbol key of the tracker metadata used for context tracing. */
static readonly tracker: unique symbol
```

`ctx.effect()` 的两条重载：

```ts
effect(execute: () => SyncEffect, label?: string): Disposable<Promise<void>>
effect(execute: () => Effect, label?: string): AsyncDisposable<Promise<void>>
```

`Effect` 与 `Disposable`：

```ts
type Effect<T = any> = SyncEffect<T> | AsyncEffect<T>

/**
 * Function returned by an effect to release resources during disposal.
 * Disposers run in reverse registration order when the owning fiber unloads;
 * they may be async, in which case unloading awaits them.
 */
type Disposable<T = any> = () => T
```

一个类形态服务的最小骨架：

```ts
class Greeter extends Service {
  constructor(ctx: Context) {
    super(ctx, 'greeter')       // 注册：立即生效，随 fiber 移除
  }

  [Service.init]() {
    // 构造完成后运行；适合依赖实例字段的初始化
  }

  [Service.check]() {
    return this.ready           // 可用性谓词，交给 ctx.provide()
  }

  [Service.invoke](name: string) {
    return this.get(name)       // 使 ctx.greeter('x') 合法
  }
}
```

## 参考表

`Service` 的符号协议：

| 符号 | 语义 | 改变的是 |
| --- | --- | --- |
| `Service.init` | 构造完成后运行的实例方法 | 初始化时机 |
| `Service.check` | 传给 `ctx.provide()` 的可用性谓词 | 可用性判定 |
| `Service.invoke` | 调用体，使服务可被调用（如 `ctx.logger()`） | 调用形态 |
| `Service.metadata` | 虚设拦截元数据类型参数 | 拦截元数据类型 |
| `Service.extend` | 派生扩展服务实例的辅助方法 | 实例派生 |
| `Service.tracker` | 上下文追踪的跟踪器元数据 | 追踪 |
| `Service.mergeIntercept` | 拦截元数据合并钩子 | 元数据合并 |
| `Service.resolveIntercept` | 拦截元数据解析辅助 | 元数据解析 |

`ctx.effect()` 的错误与边界：

| 情形 | 结果 |
| --- | --- |
| `execute` 返回不合法结构 | `TypeError` |
| fiber 已 dispose | `CordisError('INACTIVE_EFFECT')` |
| 重复调用返回的 disposer | no-op（不抛错） |
| disposer 或 fiber 卸载 | 逆序运行，先发生者触发 |
| disposer 为异步 | 卸载过程等待其完成 |

## 实例演练

一个带后台刷新的 `metrics` 服务，从注册到注销的完整顺序：

1. 定义 `class Metrics extends Service`，构造函数 `super(ctx, 'metrics')`。这一行把实例注册进当前隔离作用域，归属当前 fiber。
2. 用 `ctx.plugin(Metrics)` 装载。类插件没有 `apply`，构造完成后框架调用 `[Metrics.init]()`；在这里启动刷新循环，并用 `ctx.effect(() => { start(); return () => stop() }, 'metrics:flush')` 把启动与清理绑成一对。
3. 依赖方声明 `inject` 含 `metrics`，在它可用后才运行；若 `[Metrics.check]()` 返回 false，`ctx.provide()` 拿到的可用性判定就是「不可用」，而服务本身仍然处于已注册状态。
4. 消费方写 `ctx.metrics('requests')`——这是 `[Service.invoke]` 提供的可调用形态。
5. 卸载开始：fiber 进入 dispose。作用表按**逆序**执行——刷新循环的 disposer 先跑（stop），服务注册的注销后跑。于是任何还在调用 `metrics` 的代码不会看到"服务已注销但后台仍在跑"的中间态。
6. 服务注销会唤醒依赖方：它们随之卸载，各自的作用再按自己的逆序清理。整条链上没有任何一处需要手写 `if (disposed) return`——清理是结构性的。
7. 若在卸载后仍有代码尝试 `ctx.effect(...)`，会拿到 `CordisError('INACTIVE_EFFECT')`，而不是悄悄注册一个永不会运行的作用。

## 关键要点

1. 注册发生在 `super(ctx, name)`，注销发生在 fiber 卸载；中间不需要任何卸载代码。
2. 构造后初始化放 `[Service.init]`，不要塞进构造函数。
3. `[Service.check]` 决定"可用"，与"存在"是两个问题，不要混用一个布尔。
4. `[Service.invoke]` 是 `ctx.logger()` 这类可调用服务的实现方式，不是语法糖。
5. 所有注册都走 `ctx.effect()`：立即执行、逆序清理、幂等、异步可等待。
6. 清理顺序的镜像性质保证了"先注册的外层资源最后释放"，服务注销天然排在它自己的内部资源之后。
7. `Effect` 的生成器形态逐个 yield 逐个注册，适合资源数量不定的场景。
8. 给每个 effect 写 `label`，否则它在 `getEffects()` 诊断树里不可见。

## 关联

- **第 17 章**：服务的使用路径——`super(ctx, name)`、`declare module` 声明合并、`inject` 硬依赖、`ctx.get` 可选依赖。本章是同一批 API 的契约细节。
- **第 24 章**：`Fiber` 类定义了 `ctx.effect()` 的宿主，以及 `getEffects()`、`assertActive()`、`restart()` 与作用表的关系。
- **第 22 章**：`ctx.provide()` / `ctx.set()` / `ctx.accessor()` / `ctx.mixin()` 是服务注册的底层原语，`Service` 是它们的类封装。
- **第 16 章**：装载 / 卸载的状态转换解释了 dispose 何时开始、作用何时被排空。
- **第 26 章**：`Service` 子类以插件身份装载，走的就是 Registry 的 `ctx.plugin()`；`provide` 也被 `Plugin.Base.provide` 声明。
- **资源获取即初始化（RAII）**：`ctx.effect()` 是它在 Cordis 里的形态——用作用域代替显式 `close()`。
