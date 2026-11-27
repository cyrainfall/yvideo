# 第 26 章：Registry API

## 核心思想

Registry 只有两个动词：`ctx.plugin()` 装载、`ctx.inject()` 依赖驱动地装载。所有插件形态、依赖声明与运行时记录，都是围绕这两条签名展开的类型层。原文较薄——一页生成式签名加上三个类型（`Plugin`、`Inject`、`Runtime`），不含叙事与时序——所以本章的重点是把签名背后的**身份关系**讲清楚：一次 `ctx.plugin()` 调用产生一个 `Fiber`，同一个插件回调的所有 fiber 共享一条 `Runtime` 记录。

## 框架与方法

- **`ctx.plugin(plugin, ...args)`：唯一的装载原语**
  - 何时用：任何"在当前上下文里启动一个插件"的场合，包括框架自己装载内置插件。
  - 怎么做：传三种形态之一（函数 / 类 / `{ apply }` 对象），其余参数是插件配置，会按插件的 `Config` schema 校验。
  - 返回值：`Fiber & PromiseLike<Fiber>`。它既是同步拿到的 fiber，又是 thenable——对该值 `await` 会在加载完成后结算，配置错误或启动错误则 reject。

- **`ctx.inject(deps, callback)`：把装载时机交给依赖图**
  - 何时用：插件存在的前提是某几个服务可用，且希望服务被替换时自动重载。
  - 怎么做：它就是 `ctx.plugin({ inject, apply: callback })` 的简写。`deps` 可以是服务名数组，也可以是「名称 → 配置」的映射；`callback` 以 `(ctx, config)` 被调用。
  - 判据：**每当某个必需服务发生变化，回调会被卸载并重新运行**。这不是"等一次"的守卫，而是一段持续成立的关系。

- **同一回调 = 同一 Runtime，每次调用 = 一个新的 Fiber**
  - 何时用：需要在插件体内放状态时。
  - 怎么做：把状态存在 `ctx.fiber` 或插件实例上，不要放在模块级变量里。`Runtime.fibers` 是该插件所有活 fiber 的 `DisposableList<Fiber>`，`Runtime.callback` 是注册表的身份键——所有 `ctx.plugin()` 调用共享同一个 callback 时，它们只是同一条记录下的多个 fiber。
  - 附带结论：`Runtime.name` 是从**第一个**注册的插件形态复制过来的，`Runtime.Config` 是给每个 fiber 的配置施加的同一个校验器。也就是说运行时记录描述的是"这一类插件"，不是"这一次装载"——需要 per-fiber 的信息，读 fiber 而不是读 Runtime。

- **插件元数据写在 `Plugin.Base` 上，不靠约定**
  - 何时用：要让注册表与工具链理解你的插件。
  - 怎么做：可选填五个字段——`name`（诊断与 logger 名）、`Config`（standard-schema 校验器）、`inject`（所需服务）、`provide`（声明提供的服务名，供 `Service` 与 loader 读取）、`intercept`（声明消费哪些服务的 intercept 配置）。

- **`Inject` 的两种形态语义不同，不是简写关系**
  - 何时用：写依赖声明时。
  - 怎么做：数组形式请求服务且**不带** intercept 配置；对象形式把每个服务名映射到可选的 intercept 配置，该配置会进入插件上下文。需要规范化时用 `Inject.resolve()`，它把数组 / 对象 / 类继承来的 `inject` 元数据压平成「服务名 → intercept 配置或 `null`」的普通映射。

- **配置变换用 `Transform`，而不是在 apply 里手写**
  - 何时用：用户配置形状与运行时配置形状不同。
  - 怎么做：给对象标 `schema: true`，并提供 `Config: (config: S) => T`——它把面向用户的配置转成运行时配置。

## 关键概念

- **Registry**：插件注册表。作为 `ctx.registry` 存在，其方法混入 `ctx`（`ctx.plugin`、`ctx.inject`）。
- **`Plugin`**：插件入口点联合类型，`Plugin.Function | Plugin.Constructor | Plugin.Object`。
- **`Plugin.Base`**：三种形态共享的元数据接口，含 `name` / `Config` / `inject` / `provide` / `intercept`。
- **`Plugin.Transform`**：以 `schema: true` 标记的配置变换对象，`Config` 是「用户配置 → 运行时配置」的函数。
- **`Plugin.Runtime`**：一个插件回调的注册表记录，含 `name`、`fibers: DisposableList<Fiber>`、`callback`、`Config`。
- **`Inject`**：依赖声明类型，数组形式（无 intercept 配置）或对象形式（服务名 → intercept 配置）。
- **`Inject.resolve()`**：把三种来源的 inject 元数据规范化成普通映射的工具。
- **`Fiber & PromiseLike<Fiber>`**：`plugin()` / `inject()` 的双重返回值——可当 fiber 用，也可 await。
- **standard-schema 校验器**：`Config` 字段接受的校验器类型（`StandardSchemaV1`），框架在插件启动前施加。

## 心智模型

- **把 `ctx.inject()` 看成一条订阅，而不是一次请求**：它订阅的是"这些服务可用"这个条件，条件反复成立，回调就反复运行。
- **把 `ctx.plugin()` 的返回值看成"已经存在、可能还没加载完"**：identity 是同步的，就绪是异步的。要确保装好，就 await 或 `fiber.await()`。
- **把 `Runtime` 看成一个插件类的"类记录"，`Fiber` 看成它的实例**：`Runtime.callback` 是类身份，`Runtime.fibers` 是实例表。
- **把 `Inject` 的对象形式看成"依赖 + 该依赖的拦截配置"**：值不是备注，是要交给服务解析的元数据。

## 反模式

- **在 `ctx.inject()` 回调里放不可重建的状态**：服务一变回调就卸载重跑，状态随旧 fiber 一起消失；状态应挂在实例上或每次重建。
- **把 `ctx.inject()` 当"只执行一次"的初始化守卫**：它与 `ctx.plugin` 生命周期同构，不是 `once`。
- **拿到 `ctx.plugin()` 返回值就假设服务已注册**：返回的是 thenable；不 await 意味着加载可能仍在进行中，错误也不会在此处浮出。
- **用模块级变量记录"当前插件实例"**：同一回调可以有多个 fiber，模块级单例会互相覆盖。
- **在 apply 里重新校验配置**：`Config` schema 已在启动前跑过，重复校验只会产生两套错误语义（`ValidationError` 与自定义错误）。
- **把数组形式的 `inject` 和对象形式互换当等价物**：对象形式的值会被当作 intercept 配置消费。
- **手动维护 fiber 列表**：`Runtime.fibers` 已是 `DisposableList`，由注册表负责增删。

## 代码/配置示例

两条入口签名（注释为原文 JSDoc）：

```ts
/**
 * Run a callback once the requested services are available.
 *
 * Shorthand for `ctx.plugin({ inject, apply: callback })`: the callback
 * is unloaded and re-run whenever a required service changes.
 */
inject(deps: Inject, callback: Plugin.Function<void>): Fiber & PromiseLike<Fiber>

/**
 * Load a plugin in the current context.
 *
 * @returns the fiber; awaiting it settles once loading finished
 * (rejecting on config or startup errors).
 */
plugin<P extends Plugin>(plugin: P, ...args: Spread<GetPluginConfig<P>>): Fiber & PromiseLike<Fiber>
```

插件元数据与运行时记录的结构：

```ts
type Plugin<T = any> =
  | Plugin.Function<T>
  | Plugin.Constructor<T>
  | Plugin.Object<T>

namespace Plugin {
  export interface Base<T = any> {
    name?: string
    Config?: StandardSchemaV1<any, T>
    inject?: Inject
    provide?: string | string[]
    intercept?: Dict<boolean>
  }

  export interface Runtime {
    name?: string
    fibers: DisposableList<Fiber>
    callback: globalThis.Function
    Config?: StandardSchemaV1
  }
}
```

依赖声明的两种写法：

```ts
// 数组形式：请求服务，不带 intercept 配置
const inject = ['tools', 'llm']

// 对象形式：每个服务名映射到可选的 intercept 配置
const inject = { tools: { /* intercept config */ } }
```

## 参考表

`Plugin.Base` 字段：

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| `name` | `string` | fiber 诊断与 logger 使用的显示名 |
| `Config` | `StandardSchemaV1<any, T>` | 插件启动前施加于配置的校验器 |
| `inject` | `Inject` | 所需服务；全部可用时才加载 |
| `provide` | `string \| string[]` | 声明提供的服务名，被 `Service` 与 loader 读取 |
| `intercept` | `Dict<boolean>` | 声明消费哪些服务的 intercept 配置 |

三种插件形态与调用方式：

| 形态 | 类型 | 调用方式 |
| --- | --- | --- |
| 函数插件 | `Plugin.Function<T>` | `(ctx, config)` |
| 类插件 | `Plugin.Constructor<T>` | `new (ctx, config)` |
| 对象插件 | `Plugin.Object<T>` | `apply(ctx, config)` |

`Inject` 两形态：

| 形态 | 类型 | 语义 |
| --- | --- | --- |
| 数组 | `(keyof M)[]` | 请求服务，不带 intercept 配置 |
| 对象 | `{ [K in keyof M]?: M[K] }` | 服务名 → 该服务的可选 intercept 配置 |

## 实例演练

一个消费 `tools` 服务的插件，从装载到被服务变动重载：

1. 写插件体，声明依赖：`inject: ['tools']`，并在体内用 `ctx.effect()` 注册一个清理感知的副作用（也可直接返回 disposer，插件启动接受同样的作用主体结果）。
2. 用 `ctx.inject(['tools'], callback)` 装载。它等价于 `ctx.plugin({ inject: ['tools'], apply: callback })`，fiber 立刻被创建，但回调要等 `tools` 可用才执行。
3. 提供方稍后挂载 `tools`，回调被调用，`ctx.tools` 可用；此刻 `callback` 产生的 disposer 被收进该 fiber 的作用表。
4. 提供方被卸载或热替换 → 该服务发生变化 → 回调被**卸载**：disposer 按注册逆序运行，插件体内的注册全部撤销，不留指向失效服务的引用。
5. 新提供方就绪 → 回调**重新运行**，在新上下文里重新取 `ctx.tools`。整个过程 fiber 身份不变，`Runtime.fibers` 也不需要手工维护。
6. 若第 2 步之后立刻需要确认装载结果，`await` 那个返回值（或 `fiber.await()`）：加载完成即结算，配置校验失败或启动抛错则在此处 reject。

## 关键要点

1. 全章只有两条入口：`ctx.plugin()` 装载，`ctx.inject()` 依赖驱动装载，后者是前者的语法糖。
2. `ctx.inject()` 的语义是「服务变则重载」，不是「服务到位后跑一次」。
3. `Fiber & PromiseLike<Fiber>` 意味着 identity 同步、就绪异步；要确认就 await。
4. 插件形态三选一，元数据统一放在 `Plugin.Base` 的五个可选字段里。
5. 同一 callback 共享一条 `Runtime`，每次 `ctx.plugin()` 产生独立 fiber——状态放实例，不放模块。
6. `Inject` 对象形式的值是 intercept 配置，不是注释；不确定就交给 `Inject.resolve()` 规范化。
7. 配置校验属于 `Config` 字段（standard-schema），不要在 `apply` 里重复一遍。

## 关联

- **第 17 章**：服务页把 `Service` 子类、`declare module` 声明合并与 `inject` 的使用路径讲透；本章是它在注册表层面的类型底座。
- **第 24 章**：`Fiber` 类给出了 `plugin()` 返回值背后的实例语义——`uid`、`state`、`dispose`、`await()`、`restart()`。
- **第 22 章**：`ctx` 是注册表方法的宿主，`ctx.registry` 即本页的 `RegistryService`。
- **第 16 章**：装载 / 卸载的状态转换与 `internal/status` 事件，解释了"回调被卸载重跑"在生命周期上的位置。
- **第 23 章**：`internal/*` 事件链是依赖变化驱动重载的观测面。
- **依赖注入（dependency injection）**：本章的 `Inject` 是 DI 容器里"声明式依赖"的极简形态，与 Spring/Angular 的注入令牌同构。
