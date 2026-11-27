# 第 22 章：Context API

## 核心思想

`ctx` 不是普通对象，而是一个代理：普通属性读取走服务解析器，因此"读一个属性"可能等价于"向依赖容器要一个服务"。所有作用域变化都由三个派生方法完成——`extend()`、`isolate()`、`intercept()` 各自返回一个子上下文，**父上下文永不被修改**。把握住"作用域是派生的、所有权是 fiber 的"这两句话，整个 Context API 就只剩查表。

## 框架与方法

- **三种派生：`extend` / `isolate` / `intercept`**
  - 何时用：需要"在某个子树里换一套语义"，而不是改全局时。
  - 怎么做：
    - `extend(meta = {})` 附加元数据。子上下文通过**原型继承**获得当前上下文的全部属性，`meta` 的**自有属性**遮蔽继承来的同名属性（包括以 symbol 为键的自有属性）；父上下文不受影响。
    - `isolate(name, label?)` 为单个服务名开一个独立作用域。在返回的上下文之下，对该服务的**读写**都按新标签解析，因此可以提供一个不同实现而不影响父作用域。
    - `intercept(name, config)` 为下方启动的插件合并服务专属的拦截元数据。解析顺序是**注入的元数据在前、祖先上下文的拦截在后**（见 `Service[symbols.resolveIntercept]`）；父上下文不受影响。

- **隔离作用域的两个反直觉点**
  - 何时用：写隔离逻辑或排查"服务读到旧实现"时。
  - 怎么做：第一，**同 label 即同作用域**——把同一个 `label` 传给两次 `isolate()` 调用，两者加入同一作用域，这是跨插件共享一份隔离实现的唯一手段；不传 `label` 则每次新建一个唯一 symbol。第二，**不回退**——返回的上下文及在其下启动的插件都不会回退到外层插件注入的 `name`，即使 `label` 与父上下文的标签相同也一样；在新作用域里有提供者之前，读它会**抛错**而不是返回 `undefined`。

- **服务存储五件套：`get` / `set` / `provide` / `accessor` / `mixin`**
  - 何时用：需要绕过或补足常规注入机制时（正常情况下你应该只用 `inject`）。
  - 怎么做：按"权限门槛"选，不要按"哪个能跑通"选。
    - `get(name, strict?)`：从存储读服务，**不需要注入声明**。`strict` 为 `true`（默认）时只返回提供方 fiber 当前处于活动状态的实现；未提供返回 `undefined`。
    - `set(name, value)`：覆盖**已提供**服务的值，只有提供该服务的 fiber 才能设置；设置未提供的名字会抛错。
    - `provide(name, value)`：注册一个归当前 fiber 所有的实现，返回注销用的 disposer；fiber 激活后对同一隔离作用域内的依赖方可见，disposer 运行或 fiber 卸载时注销并**唤醒依赖方**；名字已在此作用域提供、或已声明为访问器，都抛错。
    - `accessor(name, options)`：定义一个由 `get` / 可选 `set` 钩子支持的**计算型**上下文属性；当前 fiber 卸载时移除；名字已声明则抛错。
    - `mixin(name, mixins)`：把某个服务上的指定成员直接暴露到 `ctx`，每个混入键变成一个**转发访问器**并把方法绑定到该服务——`ctx.on` 就是这样转发到 `ctx.events.on` 的；当前 fiber 卸载时移除。

- **品牌判定用 `Context.is()`**
  - 何时用：任何"这是不是一个上下文"的判断。
  - 怎么做：`Context.is(value)` 对 Cordis 上下文代理和上下文原型都返回 `true`，并收窄类型。它能跨 realm、跨多份 cordis 副本工作，因为品牌以**全局 symbol** 为键，而不是靠 `instanceof`。

- **环境句柄与静态 symbol 键：只读的内部入口**
  - 何时用：需要拿到总线、注册表、反射层本体，或需要读隔离/拦截映射时。
  - 怎么做：`ctx.events` / `ctx.registry` / `ctx.reflect` / `ctx.logger` 是四个服务句柄（前两个的方法已混入 `ctx`）；`ctx.baseUrl` 是运行时可选设置的基础 URL，用于解析相对插件／模块说明符。五个静态键 `Context.root` / `effect` / `filter` / `isolate` / `intercept` 让你读到根上下文、effect 诊断树、监听器过滤器、隔离映射、拦截映射。读得到不等于该改——写入应走对应方法。

## 关键概念

- **上下文代理（context proxy）**：`ctx` 的实现形态，属性读取经服务解析器解析。
- **派生上下文**：由 `extend` / `isolate` / `intercept` 产生的子上下文，原型继承父级。
- **隔离作用域（isolation scope）**：某个服务名在某个 label 下的独立解析域。
- **label**：隔离作用域的标识 symbol；同 label 即同作用域。
- **拦截元数据（intercept metadata）**：合并进服务解析结果的配置，注入优先、祖先其次。
- **服务存储（service store）**：`get` / `set` / `provide` 操作的底层容器。
- **访问器（accessor）**：由 get/set 钩子支撑的计算型上下文属性。
- **混入（mixin）**：把服务成员以转发访问器形式提到 `ctx` 上。
- **品牌（brand）**：以全局 symbol 为键的跨副本类型标识，`Context.is` 的判据。
- **反射层（reflect）**：为代理提供支持的 `ReflectService`。

## 心智模型

- 把 `ctx` 看成两层叠加：**作用域视图**（读到哪个实现）＋**fiber 所有权**（谁提供、谁撤销）。`get` 只看第一层，`provide` / `set` / `accessor` / `mixin` 都受第二层约束。
- 当需要两份不同实现共存时，用 `isolate` 派生一个分支，而不是改父作用域——父作用域是给别人用的，改动会外溢。
- 把 `provide` 返回的 disposer 看成"归还所有权"的凭据：它不只是取消注册，还会唤醒等待该服务的依赖方。
- 把 `ctx.get` 看成逃生舱：它能读到东西，但失去了注入带来的顺序保证与类型约束，只在诊断或框架层使用。

## 反模式

- **用 `ctx.get` 取代 `inject` 做依赖声明**：注入是启动顺序的契约；绕过它，插件可能在提供方尚未激活时就跑起来，行为随加载顺序漂移。
- **用 `ctx.set` 去"提供"一个还没人提供的服务**：`set` 只改已提供服务的值，未提供的名字直接抛错。
- **`isolate` 之后立刻读被隔离的服务**：新作用域里还没有提供者，读到的是抛错，不是 `undefined`，也不是父级的实现。
- **用 `instanceof Context` 判断**：跨 realm 或多份 cordis 副本时失效，必须用 `Context.is`。
- **把 `extend` 的 `meta` 当深合并**：它是自有属性遮蔽，嵌套对象不会递归合并。
- **把 `accessor` / `mixin` 当永久全局注册**：两者都随当前 fiber 卸载而移除，长期存在的东西应该由长期存活的 fiber 提供。

## 代码/配置示例

派生方法的契约签名：

```ts
extend(meta = {}): this
isolate(name: string, label?: symbol)
intercept<K extends InjectKey>(name: K, config: Context[K] extends { [symbols.metadata]: infer T } ? T : never): this
intercept(name: string, config: any): this
```

服务存储的契约签名：

```ts
get<K extends string & keyof this>(name: K, strict?: boolean): undefined | this[K]
set<K extends string & keyof this>(name: K, value: undefined | this[K]): void
provide<K extends string & keyof this>(name: K, value: undefined | this[K]): () => void
provide(name: string, value?: any): () => void
accessor(name: string, options: Omit<Property.Accessor, 'type'>): void
mixin<K extends string & keyof this>(name: K, mixins: (keyof this & keyof this[K])[] | Dict<string>): void
mixin<T extends {}>(source: T, mixins: (keyof this & keyof T)[] | Dict<string>): void
```

服务句柄与静态成员：

```ts
baseUrl?: string | undefined
events: EventsService
logger: LoggerService
reflect: ReflectService
registry: RegistryService

static readonly root: unique symbol
static readonly effect: unique symbol
static readonly filter: unique symbol
static readonly isolate: unique symbol
static readonly intercept: unique symbol
static is(value: any): value is Context
```

## 参考表

三种派生方法：

| 方法 | 参数 | 子上下文获得什么 | 父上下文 | 所有权/撤销 |
| --- | --- | --- | --- | --- |
| `extend` | `meta = {}` | 原型继承全部属性，`meta` 自有属性遮蔽同名项（含 symbol 键） | 不被修改 | 无独立撤销动作 |
| `isolate` | `name`、可选 `label` | 该服务名的独立解析作用域 | 不被修改 | 同 label 即同作用域；无提供者时读取抛错 |
| `intercept` | `name`、`config` | 合并后的服务拦截元数据 | 不被修改 | 注入元数据在前，祖先拦截在后 |

服务存储操作：

| 方法 | 权限门槛 | 生效范围 | 撤销方式 | 失败条件 |
| --- | --- | --- | --- | --- |
| `get` | 无（不需注入） | 只读 | — | 未提供返回 `undefined` |
| `set` | 仅提供该服务的 fiber | 覆盖已有值 | — | 名字未被提供 → 抛错 |
| `provide` | 当前 fiber 所有 | 同隔离作用域，fiber 激活后可见 | 返回的 disposer 或 fiber 卸载（唤醒依赖方） | 本作用域已提供、或已声明为访问器 → 抛错 |
| `accessor` | 当前 fiber 所有 | 计算型上下文属性 | fiber 卸载移除 | 名字已声明 → 抛错 |
| `mixin` | 当前 fiber 所有 | 服务成员转发到 `ctx`（方法绑定到服务） | fiber 卸载移除 | 见签名约束 |

静态 symbol 键读什么：

| 键 | 读到什么 |
| --- | --- |
| `Context.root` | 应用根上下文，所有子上下文共享 |
| `Context.effect` | disposer 上挂 `EffectMeta` 诊断树的键 |
| `Context.filter` | 上下文监听器过滤器，每次分派事件都查询 |
| `Context.isolate` | 服务名 → 作用域标签的映射 |
| `Context.intercept` | 服务名 → 拦截元数据的映射 |

## 实例演练

目标：在某个插件子树里把 `db` 换成一个测试实现，且不影响父作用域。

1. 在测试插件里 `const child = ctx.isolate('db')`。不传 `label`，所以每次都得到一个新的唯一 symbol 作用域。
2. 在 `child` 下读取 `db` 立即抛错——新作用域没有提供者，而且**不会回退**到外层插件注入的 `db`，即使 label 恰好与父级相同。
3. 在 `child` 上调用 `provide('db', fakeDb)`。返回一个 disposer；此时服务仍不可见，要等提供方 fiber 激活。
4. 激活后，`child` 之下的依赖方读到 `fakeDb`，父作用域仍读到真 `db`。同一段代码在两条分支上解析到不同实现，而父上下文一行未改。
5. 如果另一处测试也想共享这份 `fakeDb`，把同一个 `label` 传给它的 `isolate('db', label)`——两次调用加入同一作用域，于是彼此可见。
6. 想微调某个消费方的解析行为但不换实现，改用 `child.intercept('db', config)`：`config` 会被合并进下方插件看到的拦截元数据，注入在前、祖先在后。
7. 测试结束调用那个 disposer：服务注销，**依赖方被唤醒**（而不是继续持有失效引用）。即使忘了调用，fiber 卸载也会做同样的事。

同一套推演用 `extend` 走另一条路：`ctx.extend({ traceId })` 只加元数据，不碰服务解析；`traceId` 是自有属性，遮蔽任何继承来的同名项，父上下文依旧干净。

## 关键要点

1. 三个派生方法都不修改父级；需要"另一套语义"时派生，不要改全局。
2. `isolate` 的意义是**不换代码换实现**；同 `label` 才共享，不传则每次全新。
3. 隔离后读不到父级实现，且是抛错而非 `undefined`——这是有意的失败方式。
4. `get` / `set` 是低层逃生舱，常规依赖只用 `inject`。
5. `provide` / `accessor` / `mixin` 的生命周期都绑定在当前 fiber 上，卸载即撤销。
6. 判上下文用 `Context.is`，永远不要 `instanceof`。
7. `intercept` 的合并顺序是注入在前、祖先在后，排查覆盖问题时按这个顺序读。

## 关联

- **第 17 章**：服务提供与注入的教程视角，本章是它的完整契约。
- **第 23 章**：`ctx.events`、`Context.filter` 与监听器选项的配合。
- **第 24 章**：`ctx.fiber`、`ctx.effect` 的所有权语义是本章"fiber 所有"的根据。
- **第 26 章**：`ctx.registry` / `ctx.plugin` / `ctx.inject` 的详细参考。
- **第 27 章**：`Service[symbols.resolveIntercept]` 所述的拦截解析细节。
