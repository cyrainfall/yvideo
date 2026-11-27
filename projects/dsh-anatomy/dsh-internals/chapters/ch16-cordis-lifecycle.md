# 第 16 章：生命周期与副作用

## 核心思想

插件不是一直活着的东西：修改配置、热重载、显式释放资源、所需服务消失，任何一条都会让它卸载。凡是经 Cordis API 建立的注册都属于 effect，卸载时自动撤销；只有 API 之外自行管理的资源（定时器、连接、watcher）必须用 `ctx.effect()` 包起来并交出 disposer。写插件的第一个判断不是「怎么写」，而是「这份资源归谁管」。

## 框架与方法

- **effect（副作用单元）**：把 Cordis 管不到的资源的获取与释放写成一对。
  - 何时用：资源不由 Cordis 建立，例如 `setInterval`、网络连接、文件 watcher、订阅回调。
  - 怎么做：在 `ctx.effect(fn)` 里获取资源，`fn` 返回一个 disposer；effect 主体在**加载期间**运行，disposer 在**卸载期间**运行。对于生命周期与插件一致的资源，你永远不需要自己调用 disposer。
- **登记已属于 effect 的内置注册**：先盘点，再决定要不要手写。
  - 何时用：每次想在 `apply` 里挂东西之前。
  - 怎么做：`ctx.on(event, listener)` 的监听器在卸载时移除；`ctx.plugin(child)` 的子插件随父插件一同 dispose；服务注册本身属于 effect；harness 注册表（如 `ctx.tools.register(...)`）返回的 disposer 会附着到调用插件上。这些都不需要额外包装。
- **fiber 句柄与其递归释放**：`ctx.plugin(x)` 返回 fiber，即「一个已加载插件实例的运行时句柄」。
  - 何时用：需要提前结束某个插件、或在多插件之间编排加载与卸载时。
  - 怎么做：调用 `fiber.dispose()`。它会等该插件的所有清理工作（包括异步 disposer）完成后才结束，并递归卸载它挂载的所有子插件。
- **异步 disposer 的顺序纪律**：disposer 按注册顺序的**逆序**启动，但多个**异步** disposer 会**并发**运行。
  - 何时用：拆除步骤之间有先后依赖（先断流再断连、先停消费者再停生产者）。
  - 怎么做：把这几步放进**同一个** disposer，在其中依次 `await` 每一步；不要指望多个异步 disposer 之间自然有序。
- **函数插件与对象插件的形态区分**：`ctx.plugin(heartbeat)` 把**来自代码**的函数挂载为插件，这与 YAML loader 为每个配置项做的事相同。
  - 何时用：函数插件不需要 `apply`，Cordis 直接调用该函数，其 `name` 只用于诊断；只有对象形态（如 `ctx.plugin({ apply(ctx) { /* ... */ } })`）才要求 `apply` 方法；`Service` 子类则是类形态，同样作为插件挂载。
- **把释放逻辑写进 effect，而不是写进 `apply` 的收尾**：disposer 不仅在显式卸载时运行，热重载时也不例外。
  - 何时用：任何「插件活多久、资源就该活多久」的资源。
  - 怎么做：不要在 `apply` 末尾安排清理代码，也不要假设存在一个「插件退出」的回调；唯一被保证的清理时机就是 disposer。

## 关键概念

- **effect**：插件加载期间建立的、可被撤销的注册；撤销动作由 effect 返回的 disposer 描述。
- **disposer（资源释放函数）**：effect 主体返回的函数，在卸载期间被调用一次。
- **fiber**：一个已加载插件实例的运行时句柄，`ctx.plugin()` 的返回值，承载该实例的状态与清理。
- **函数插件**：以函数而非 `{ apply }` 对象形式挂载的插件，函数被直接调用，无 `apply` 方法。
- **PENDING**：插件已声明，但所需服务尚不可用，`apply` 还没开始。
- **FAILED**：`apply` 或配置校验抛出异常后进入的状态。
- **DISPOSED**：所有 disposer 均已运行，一切均已拆除的终态。
- **回卷（unwind）**：卸载时按注册顺序的逆序撤销 effect 的整体过程。

## 心智模型

- **当资源寿命可能长于插件时，用 `ctx.effect()`；当两者同寿时，什么都不写。** 反过来记更容易：只有「插件死了这东西还活着」才是 bug 来源。
- **把 `ctx.effect(fn)` 看成领资源时同时签一张归还单。** `fn` 是领取动作，返回的函数是归还动作；签了单就有权不管，没签单就得自己盯着。
- **把 fiber 看成实例的租约，而不是实例本身。** 你持有的是句柄，`dispose()` 是提前退租；退租时会把它名下所有东西（含子插件）一并清掉。
- **把卸载看成栈的回卷，但只有「启动顺序」是栈。** 逆序适用于注册顺序；异步 disposer 的**完成**顺序不受保证，所以别把顺序依赖藏进多个 disposer 之间。

## 反模式

- **裸用 `setInterval` / 连接 / watcher，不包 `ctx.effect()`**：插件卸载后回调仍在跑，热重载一轮就多一份，直到进程被拖死。
- **手动调用 disposer 或手动 `removeListener`**：Cordis 已负责撤销，人工再撤一次会双重释放，或在热重载时撤销掉新实例的注册。
- **依赖「多个异步 disposer 会按逆序完成」**：它们只按逆序**启动**，随后并发；拆除有依赖时必须合并进同一个 disposer 顺序 `await`。
- **在模块顶层或 `apply` 之外获取资源**：这绕过了 fiber 的记账，卸载时无人知道该释放什么。
- **认为 `fiber.dispose()` 是「发个信号」**：它等待所有清理（含异步）完成才返回，因此可以安全地在它后面 `process.exit(0)`。
- **把「卸载后还会被触发的回调」当无关紧要**：本教程里的演示定时器本身就是用 `ctx.effect()` 包住的，目的正是防止它在已死的 app 上开火。

## 代码/配置示例

`lifecycle.ts`（放在 `tmp/cordis-tutorial`）：

```ts
import type { Context } from '@deepseek-ai/cordis'

export const name = 'lifecycle-demo'

function heartbeat(ctx: Context) {
  console.log('heartbeat plugin loading')
  ctx.effect(() => {
    const timer = setInterval(() => console.log('tick'), 200)
    return () => {
      clearInterval(timer)
      console.log('heartbeat cleaned up')
    }
  })
}

export function apply(ctx: Context) {
  // Mount a child plugin and keep its fiber to dispose it later.
  const fiber = ctx.plugin(heartbeat)
  // The demo timer is itself an effect: if THIS plugin is unloaded first,
  // the pending callback is cancelled instead of firing on a dead app.
  ctx.effect(() => {
    const timer = setTimeout(async () => {
      await fiber.dispose()
      console.log('disposed')
      process.exit(0)
    }, 700)
    return () => clearTimeout(timer)
  })
}
```

`cordis.yml`：

```yaml
- name: './lifecycle.ts'
```

运行：`node --import tsx ../../vendor/cordis/bin.js`，输出：

```
heartbeat plugin loading
tick
tick
tick
heartbeat cleaned up
disposed
```

## 参考表

每个已加载插件实例都拥有一个 fiber，状态转换为 `PENDING → LOADING → ACTIVE → UNLOADING → DISPOSED`，并存在 `FAILED` 分支：

| 状态 | 含义 |
|---|---|
| PENDING | 已经声明，但所需服务（第 17 章）尚不可用 |
| LOADING | `apply` 正在运行 |
| ACTIVE | `apply` 已完成 |
| FAILED | `apply` 或配置校验抛出异常 |
| UNLOADING | disposer 正在运行 |
| DISPOSED | 一切均已拆除 |

## 实例演练

按上例走一遍完整时间线，重点看三件事如何咬合。

**加载期**：根插件 `apply` 先执行 `ctx.plugin(heartbeat)`，heartbeat 的 `name` 只用于诊断，函数体被直接调用，打印 `heartbeat plugin loading`；它内部 `ctx.effect()` 建立 200ms 的 `setInterval`，effect 主体立即运行，disposer 被记为待用。`ctx.plugin()` 返回 fiber 并被 `apply` 保存下来——这是后面能提前卸载子插件的唯一凭据。

**运行期**：每 200ms 打印一次 `tick`。700ms 处的 `setTimeout` 也是 effect 建立的，它在加载期就被排上，因此即使根插件先被卸载，这个待触发的回调也会被取消，而不会在已经死掉的 app 上执行。

**拆除期**：约 700ms 时回调触发，`await fiber.dispose()`。fiber 进入 UNLOADING，heartbeat 的 disposer 运行：`clearInterval` 并打印 `heartbeat cleaned up`；`dispose()` 等待全部清理完成才返回，于是 `disposed` 在清理之后才打印，最后 `process.exit(0)` 用一个确定的状态码结束进程。

输出顺序即证据：`heartbeat cleaned up` 一定先于 `disposed`。如果把 `await fiber.dispose()` 写成不 `await`，`disposed` 就可能抢先，进程也可能在清理中途被杀——这正是 `dispose()` 定义为「等待完成」的意义。

## 关键要点

1. 先分类资源：Cordis 建立的注册不用管，Cordis 之外的资源一律进 `ctx.effect()`。
2. effect 主体在加载期运行、disposer 在卸载期运行，两者是**同一次登记**的两端。
3. 插件不需要自己调用 disposer；只有需要提前结束时才用 `fiber.dispose()`。
4. `fiber.dispose()` 会等待异步清理并递归卸载子插件，是「可安全退出」的同步点。
5. disposer 逆序**启动**但异步**并发**，顺序依赖必须收进同一个 disposer。
6. 看到 `PENDING` 不要当成 bug：它表示依赖未满足，答案在第 17、20 章。

## 关联

- **第 15 章**：第一个插件的三种形态（函数、对象、类），本章的 `heartbeat` 就是函数插件。
- **第 17 章**：PENDING 的成因是 `inject` 列出的服务缺失；服务一旦提供方消失，依赖插件会连带卸载。
- **第 20 章**：HMR 之所以能替换运行中的代码，正是因为「卸载释放 effect + 加载遵循依赖」这两件事已经成立；PENDING 的诊断也在那里展开。
- **第 24 章 Fiber API**：本章用到的 `fiber`、`FiberState`、`dispose()` 的完整接口面。
- **第 23 章 Events API**：`ctx.on` 属于 effect 这一结论的完整语义。
