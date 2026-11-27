# 第 23 章：Events API

## 核心思想

五个分发方法不是同一次调用的五种写法，而是五种**编排策略**：谁等待、返回值归谁、什么时候终止。选错方法不会报错——它只会静默丢失异步结果，或者让一个无关的返回值提前短路整条链。每个上下文中都混入了这套分发 API；harness 的事件声明与分发模式会生成到各自所属的子系统页面上。

## 框架与方法

- **五种分发模式（`DispatchMode`）**
  - 何时用：按"要不要等结果"和"要不要用返回值"两个问题选。
  - 怎么做：
    - `emit(name, ...args)`：同步分发，**忽略监听器返回值**，不等待它们。返回 `void`。它是通知，不是询问。
    - `parallel(name, ...args)`：**并发**运行所有监听器，返回一个在所有监听器都 settle 后兑现的 `Promise<void>`。返回值不被使用，但异常与耗时会被等到。
    - `serial(name, ...args)`：**依次 await** 各监听器，直到其中一个提前终止分发；返回第一个提前终止值（`Promisify<ReturnType<...>>`，即异步情形下包一层 promise）。
    - `bail(name, ...args)`：**依次调用**各监听器，遇到第一个**同步**提前终止值就停；直接返回该值，不 await。
    - `waterfall(name, ...args)`：最后一个参数是 `next` 续接回调。每个监听器包裹调用链的其余部分：调用 `next()` 执行下一个监听器，最终执行内置行为；不调用则**否决**后续执行。返回最外层监听器的返回值。

- **提前终止值（bail value）的判定**
  - 何时用：写 `serial` / `bail` 的监听器时。
  - 怎么做：判定条件是**非 `null`、非 `false`、非 `undefined`**。也就是说 `0` 和 `''` 都算提前终止值——一个"顺手 `return count`"的监听器，在 `count === 0` 时也会把整条链截断。要表达"没意见"，返回 `undefined`（或不返回）。

- **`serial` 与 `bail` 的唯一差别是等不等**
  - 何时用：监听器可能返回 promise 时。
  - 怎么做：需要异步监听器也能参与"谁先给答案"的竞争，用 `serial`；只听同步返回值、要求立即得到结论，用 `bail`。用 `bail` 处理返回 promise 的监听器，拿到的是 promise 对象本身——它非 null 非 false 非 undefined，会被当作提前终止值。

- **`on` / `once`：监听器所有权与可撤销性**
  - 何时用：任何订阅。
  - 怎么做：`on(name, listener, options?)` 注册一个**归当前 fiber 所有**的监听器，返回 disposer `() => boolean`——调用它移除监听器，若移除时监听器仍处于注册状态则返回 `true`。`once` 行为相同，但监听器在首次调用后自行注销。`options` 传布尔值等价于设置 `prepend`。

- **监听器选项 `EventOptions`**
  - 何时用：需要控制顺序或绕过过滤时。
  - 怎么做：`prepend: true` 把监听器插到同事件已有监听器**之前**；`global: true` 让监听器**无视上下文过滤器检查**接收事件（过滤器即 `Context.filter` 上的那个判断）。两个选项互不相干，不要指望 `global` 改变顺序。

- **`thisArg` 重载**
  - 何时用：需要给监听器显式绑定 `this` 时。
  - 怎么做：五个分发方法和 `on` / `once` 都有两个重载——第二重的第一个参数是 `thisArg: NoInfer<ThisType<Events[K]>>`，其后才是事件名与参数。不传时 `this` 走默认绑定。

## 关键概念

- **`DispatchMode`**：`'emit' | 'parallel' | 'serial' | 'bail' | 'waterfall'`，事件分发策略的类型。
- **提前终止值（bail value）**：非 `null`、非 `false`、非 `undefined` 的返回值，用于中止 `serial` / `bail` 的链。
- **`next` 续接**：`waterfall` 传给每个监听器的最后一个参数，代表"链的其余部分，直到内置行为"。
- **`prepend`**：把监听器排到同事件已有监听器之前。
- **`global`**：跳过上下文过滤器检查，无论过滤结果都接收事件。
- **监听器 disposer**：`on` / `once` 返回的 `() => boolean`，兼作"是否仍在注册"的探针。
- **`Events` 声明合并**：事件名与参数类型由声明合并提供；harness 侧的事件在其所属子系统页面生成。
- **settle**：监听器完成（兑现或拒绝）的统称；`parallel` 等的是 settle，不是成功。

## 心智模型

- 把五个方法放在一张二维表上选：**是否等待**（`emit` 不等 / `parallel` 等全部 / `serial`、`bail` 逐个 / `waterfall` 由监听器决定） × **返回值归谁**（丢弃 / 聚合 / 第一个提前终止值 / 最外层返回值）。选之前先回答这两个问题。
- 把 `emit` 看成广播通知，把 `serial` 看成依次征询，把 `waterfall` 看成**接力**——接力棒是 `next`，掉棒就等于否决。
- 把 `on` 返回的 disposer 看成归还凭据：它同时告诉你"当时还在不在"。
- 当需要"某监听器能否决内置行为"时用 `waterfall`；`bail` 只能中止链，不能包裹内置行为。

## 反模式

- **用 `emit` 分发预期会异步完成的事件**：监听器的 promise 没人等，失败也没人看，问题只在负载下偶发。
- **在 `serial` / `bail` 监听器里顺手 `return` 一个有用值**：它会变成提前终止值，后面的监听器整段不执行。
- **在 `waterfall` 监听器里忘记调用 `next()`**：不报错，静默否决后续监听器与内置行为——最典型的"功能悄悄不生效"。
- **把 `options` 传 `true` 当作"只触发一次"**：布尔值是 `prepend` 的简写，只触发一次要用 `once`。
- **用 `bail` 处理异步监听器**：promise 对象本身会成为提前终止值。
- **注册监听器后不管 disposer**：短期脚本无所谓，长期插件会累积重复回调；正确做法是让 fiber 所有权负责撤销，或在明确时点调用 disposer。

## 代码/配置示例

分发方法（含 `thisArg` 重载）：

```ts
parallel<K extends keyof Events>(name: K, ...args: Parameters<Events[K]>): Promise<void>
parallel<K extends keyof Events>(thisArg: NoInfer<ThisType<Events[K]>>, name: K, ...args: Parameters<Events[K]>): Promise<void>

emit<K extends keyof Events>(name: K, ...args: Parameters<Events[K]>): void
serial<K extends keyof Events>(name: K, ...args: Parameters<Events[K]>): Promisify<ReturnType<Events[K]>>
bail<K extends keyof Events>(name: K, ...args: Parameters<Events[K]>): ReturnType<Events[K]>
waterfall<K extends keyof Events>(name: K, ...args: Parameters<Events[K]>): ReturnType<Events[K]>
```

订阅与选项：

```ts
on<K extends keyof Events>(name: K, listener: Events[K], options?: boolean | EventOptions): () => boolean
once<K extends keyof Events>(name: K, listener: Events[K], options?: boolean | EventOptions): () => boolean

interface EventOptions {
  /** Add the listener before existing listeners for the same event. */
  prepend?: boolean
  /** Receive the event regardless of context filter checks. */
  global?: boolean
}

type DispatchMode = 'emit' | 'parallel' | 'serial' | 'bail' | 'waterfall'
```

## 参考表

五种分发模式：

| 方法 | 是否等待监听器 | 是否使用返回值 | 终止条件 | 返回 |
| --- | --- | --- | --- | --- |
| `emit` | 否，同步调用后即返回 | 忽略 | 无 | `void` |
| `parallel` | 是，等全部 settle | 不使用 | 无 | `Promise<void>` |
| `serial` | 是，依次 await | 第一个提前终止值 | 某监听器返回非 `null`/非 `false`/非 `undefined` | 该值的 promise 形态 |
| `bail` | 否，只看同步值 | 第一个提前终止值 | 同上，且只认同步值 | 该值本身 |
| `waterfall` | 由监听器决定（调用 `next()` 才继续） | 最外层监听器的返回值 | 某监听器不调用 `next()` | 最外层返回值 |

`EventOptions` 两个开关：

| 选项 | 作用 | 影响面 |
| --- | --- | --- |
| `prepend` | 插到同事件已有监听器之前 | 只影响顺序 |
| `global` | 无视上下文过滤器检查接收事件 | 只影响是否收到，不改顺序 |

`serial` 与 `bail` 的差别集中在一点：

| 关注点 | `serial` | `bail` |
| --- | --- | --- |
| 监听器返回 promise | await 它，取兑现值判断 | 不 await，promise 本身即为提前终止值 |
| 返回类型 | `Promisify<ReturnType<...>>` | `ReturnType<...>` |
| 适合的监听器 | 可能异步 | 纯同步 |

## 实例演练

场景一：一个可选择否决的流水线钩子，用 `waterfall`。

```ts
ctx.on('some/hook', (input, next) => {
  if (!input.enabled) return           // 不调用 next()：否决后续与内置行为
  return next()                        // 调用 next()：继续到下一个监听器，最终内置行为
})
```

推演：分发时最外层监听器先跑。它调用 `next()`，于是第二个监听器跑；第二个也调用 `next()`，最终执行内置行为。返回值沿链回传，`waterfall()` 得到的是**最外层监听器**的返回值——所以内层对返回值的加工，只有在外层把它透传出来时才可见。若最外层直接 `return` 而不调 `next()`，整条链连同内置行为一起不发生，且没有任何报错。

场景二：收集一个有唯一答案的决策，用 `serial`。

```ts
const answer = await ctx.serial('some/question', payload)
```

推演：监听器按序被 await。第一个返回 `undefined`——不算提前终止值，继续。第二个异步算出 `0` 并返回——`0` 非 `null`、非 `false`、非 `undefined`，**算提前终止值**，`serial` 立即以 `0` 兑现，第三个监听器再也不跑。这正是"顺手 return 数值"最危险的地方。

场景三：同一个事件改用 `emit` 分发。

监听器全部被同步调用，其中两个返回 promise。`emit` 不等它们，调用方立刻拿到 `void`；两个 promise 各自 settle，异常落在无人 await 的地方。功能看起来"有时生效"，因为它依赖监听器内部是否有同步副作用。

场景四：订阅顺序。给同一个事件先注册 A 再注册 B，B 用 `prepend: true`。实际顺序是 B、A。若 B 还带 `global: true`，它连"上下文过滤器判定不通过"的事件也能收到——但顺序仍由 `prepend` 决定，两个选项各管一件事。

## 关键要点

1. 先回答"要不要等"和"要不要用返回值"，再选五个分发方法之一。
2. `emit` 是通知，`parallel` 是等待全部，`serial` 是依次征询，`bail` 是同步抢答，`waterfall` 是接力。
3. 提前终止值的判定是"非 `null`、非 `false`、非 `undefined`"——`0` 与 `''` 都会截断链。
4. `bail` 不 await，异步监听器返回的 promise 会被当成提前终止值。
5. `waterfall` 里不调 `next()` 等于静默否决，连内置行为一起跳过。
6. `prepend` 管顺序，`global` 管是否收到，二者互不影响。
7. `on` / `once` 的 disposer 返回布尔值，可用来确认"移除时是否仍在注册"。

## 关联

- **第 18 章**：事件教程视角；本章是同一套机制的分发策略参考。
- **第 22 章**：`ctx.events` 句柄与 `Context.filter`——`global` 选项绕过的正是那个过滤器。
- **第 24 章**：`on` / `once` 注册的监听器归当前 fiber 所有，撤销走 fiber 卸载。
- **第 25 章**：`internal/update`、`internal/config` 等框架事件正是 `waterfall` 模式的使用者，省略 `next()` 会保留当前实例。
- **第 6 章**：harness 事件的生产者与消费者全景。
