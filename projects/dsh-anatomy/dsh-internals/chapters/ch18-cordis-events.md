# 第 18 章：事件

## 核心思想

服务是「直接调用」，事件是「广播通知」：发出方无需知道有哪些插件在监听。Cordis 的事件不是单一语义，而是一组**分发模式（dispatch mode）**——emit、parallel、serial、bail、waterfall——模式本身是事件契约的一部分，决定了监听器能否返回值、能否并发、能否彼此短路。写错模式的监听器不会报错，只会静默改变行为。

## 框架与方法

- **声明事件：`interface Events` 声明合并。**
  - 何时用：任何自定义事件，先声明再发。
  - 怎么做：在 `declare module '@deepseek-ai/cordis'` 块里写 `interface Events { 'stats/report'(name: string, count: number): void }`。它声明事件名与监听器签名，使 `ctx.emit` 与 `ctx.on` 都获得完整类型。
  - 配套：消费方用 `import type {} from './stats.ts'` 让 TypeScript 看到这份合并声明——这一行不产生运行时代码，只负责把类型接进来。
- **命名约定**：用 `namespace/action` 形式（如 `stats/report`、`agent/pre-step`），让扁平的事件命名空间保持易读。
- **选择分发模式**：按「你要不要结果、要不要并发、能不能被拦截」三问决定。
  - `emit`：同步广播，不等也不收集返回的 promise 与值——只通知，不取结果。
  - `parallel`：所有监听器并发运行并一同等待——取全部结果、无顺序依赖。
  - `serial`：按顺序运行并等待，第一个非 `null`/`false`/`undefined` 的返回值胜出并停止后续监听器——「谁先给出定论就听谁的」。
  - `bail`：`serial` 的同步版本。
  - `waterfall`：环绕中间件，见下条。
  - 判据：每个 harness 事件都会在其所属子系统页面自动生成的参考文档里记录其模式，用之前先查，不要猜。
  - 附带结论：模式不同，监听器签名也不同——waterfall 的监听器要多接一个 `next()`，而 `emit` 的监听器即使写了 `return` 也没人接。
- **waterfall：转换或短路。**
  - 何时用：需要让协作插件**包装**或**回答**某个决策。
  - 怎么做：监听器签名带 `next()` continuation（`ctx.waterfall(name, ...args, next)`）。监听器可以 `await next()` 并转换其返回值，也可以**不调用 `next()` 就直接返回**，从而短路链条其余部分。Cordis 文档把后一种行为称为**否决（veto）**。
- **观察型监听器的纪律**：只负责观察或标注的 waterfall 监听器**必须调用 `next()`**。
  - 为什么：不调用就直接返回代表有意短路。一个忘记调 `next()` 的日志监听器，会悄无声息地吞掉所有下游的默认行为。这是本仓库的常设规则。
- **在服务与事件之间选型**：先问「我要能力，还是要通知」。
  - 何时用：设计任何跨插件交互的入口。
  - 怎么做：需要返回值、需要明确提供方、需要可替换实现 → 用服务；需要多个未知订阅者、或让通知与处理彻底解耦 → 用事件。harness 用事件处理工具结果、模型请求和审批决定等交互，正是后者的典型形态。

## 关键概念

- **事件**：插件向未知监听者发出的通知，发出方与监听方互不依赖。
- **`interface Events`**：声明合并块，定义事件名与监听器签名的类型。
- **分发模式**：事件的调用语义（emit / parallel / serial / bail / waterfall），是事件契约的一部分。
- **短路（short-circuit）**：某个监听器返回后不再调用后续监听器，链条提前结束。
- **否决（veto）**：waterfall 监听器不调用 `next()` 直接返回，使最内层默认逻辑不执行。
- **`next()`**：waterfall 中把控制权交给下游的 continuation，也是「我不接管」的显式表态。
- **`namespace/action`**：事件命名约定，如 `stats/report`。

## 心智模型

- **把 `emit` 看成公告板，把 `serial` 看成接力赛。** 公告板只管贴出去；接力赛里第一个给出非空结论的人终止比赛。
- **把 waterfall 看成洋葱。** 请求从外向内穿过每层监听器，响应再从内向外穿回来；`next()` 是继续钻下一层的动作。
- **把「不调用 `next()`」看成一次签字。** 你不是「忘了往下传」，而是宣布「由我裁决，下游不必运行」——所以观察者不该签这个字。
- **把分发模式当成 API 的一部分而非风格偏好。** 同一个事件用错模式，类型照样通过，行为已经变了。

## 反模式

- **观察型 waterfall 监听器忘记 `next()`**：不是少打一行日志，而是把整条下游默认行为吞掉，且没有任何报错。
- **用 `emit` 却指望拿到返回值**：`emit` 不等待、不收集 promise 与值，调用方永远拿不到结果。
- **用 `serial` 表达广播**：第一个非空返回值会截断其余监听器，本该都被通知的插件收不到。
- **用 `parallel` 表达有顺序的决策**：所有监听器并发，谁先返回不确定，不能用来做「先问 A 再问 B」。
- **事件名不带 `namespace/action`**：扁平命名空间迅速失去可读性，也无法从名字看出归属子系统。
- **忘了 `interface Events` 声明或忘了 `import type {}`**：`emit` / `on` 失去类型，拼错事件名也不会被编译器抓住。
- **手动维护 `removeListener`**：`ctx.on()` 属于 effect，监听器随插件一同消失，人工再摘一次是多余且危险的。

## 代码/配置示例

声明并发出事件的服务 `stats.ts`：

```ts
import { Service, type Context } from '@deepseek-ai/cordis'

declare module '@deepseek-ai/cordis' {
  interface Context {
    stats: StatsService
  }
  interface Events {
    'stats/report'(name: string, count: number): void
  }
}

export class StatsService extends Service {
  private counts = new Map<string, number>()

  constructor(ctx: Context) {
    super(ctx, 'stats')
  }

  bump(name: string) {
    const next = (this.counts.get(name) ?? 0) + 1
    this.counts.set(name, next)
    this.ctx.emit('stats/report', name, next)
  }
}

export const name = 'stats'

export function apply(ctx: Context) {
  ctx.plugin(StatsService)
}
```

监听方 `reporter.ts`：

```ts ignore-check
import type { Context } from '@deepseek-ai/cordis'
import type {} from './stats.ts'

export const name = 'reporter'
export const inject = ['stats']

export function apply(ctx: Context) {
  ctx.on('stats/report', (name, count) => {
    console.log(`[stats] ${name} -> ${count}`)
  })
  ctx.stats.bump('tool_call')
  ctx.stats.bump('tool_call')
  ctx.stats.bump('prompt')
}
```

组合与输出：

```yaml
- name: './stats.ts'
- name: './reporter.ts'
```

```
[stats] tool_call -> 1
[stats] tool_call -> 2
[stats] prompt -> 1
```

waterfall 示例 `waterfall-demo.ts`：

```ts
import type { Context } from '@deepseek-ai/cordis'

declare module '@deepseek-ai/cordis' {
  interface Events {
    'demo/transform'(input: string, next: () => Promise<string>): Promise<string>
  }
}

export const name = 'waterfall-demo'

export function apply(ctx: Context) {
  // Listener 1: wrap the downstream result.
  ctx.on('demo/transform', async (input, next) => {
    const downstream = await next()
    return downstream.toUpperCase()
  })

  // Listener 2: short-circuit when it owns the decision.
  ctx.on('demo/transform', async (input, next) => {
    if (input.includes('blocked')) return '** blocked **'
    return next()
  })

  void (async () => {
    console.log(await ctx.waterfall('demo/transform', 'hello', async () => 'hello'))
    console.log(await ctx.waterfall('demo/transform', 'blocked words', async () => 'blocked words'))
  })()
}
```

## 参考表

| 模式 | 调用 | 语义 |
|---|---|---|
| emit | `ctx.emit(name, ...args)` | 同步广播；不会等待或收集返回的 promise 与值。 |
| parallel | `await ctx.parallel(name, ...args)` | 所有监听器并发运行，并一同等待。 |
| serial | `await ctx.serial(name, ...args)` | 监听器按顺序运行并等待；第一个非 `null`/`false`/`undefined` 返回值胜出，并停止后续监听器。 |
| bail | `ctx.bail(name, ...args)` | serial 的同步版本。 |
| waterfall | `ctx.waterfall(name, ...args, next)` | 环绕中间件，可转换下游结果或不调 `next()` 直接否决。 |

## 实例演练

`waterfall-demo.ts` 两次调用，输出 `HELLO` 与 `** BLOCKED **`。按顺序推演第二行怎么产生：

1. `ctx.waterfall('demo/transform', 'blocked words', async () => 'blocked words')` 进入链条，**监听器 1** 先运行（示例中它是第一个注册的监听器）。
2. 监听器 1 调 `await next()`，把控制权交给**监听器 2**。
3. 监听器 2 看到 `input.includes('blocked')` 为真，**直接 `return '** blocked **'`，不调用 `next()`**。
4. 因此最内层默认逻辑（传给 `ctx.waterfall` 的那个函数）从未运行——这就是否决。
5. 返回途中，监听器 1 拿到替换结果 `'** blocked **'`，把它 `toUpperCase()`，得到 `** BLOCKED **`，打印。

第一行 `'hello'` 走的是另一条路径：监听器 2 不满足短路条件，改为 `return next()`，默认逻辑运行并返回 `'hello'`，监听器 1 再转成大写 `HELLO`。同一对监听器，一次包装、一次否决，结果就是 waterfall 的两种全部用法。

真实 harness 用 waterfall 处理「协作插件可以包装或回答」的决策：`agent/pre-step` 允许插件拒绝拟议步骤或替换其输入；`approval/request` 允许策略代替用户作答。这两个都是「下游有默认答案，但上游有权改写或直接给结论」的形状——正是 waterfall 的适用条件。反过来，如果哪天给 `agent/pre-step` 加一个纯日志监听器却忘了 `return next()`，它会变成一次静默否决，把拟议步骤全部吃掉。

## 关键要点

1. 事件 = 广播式通信；需要返回值与顺序保证时，先确认模式是否支持。
2. 五种模式中只有 serial / bail / waterfall 会因返回值而短路；`emit` 什么都不收集。
3. 事件的模式属于契约，用之前查子系统页面自动生成的参考文档。
4. waterfall 监听器的两条合法出口：`await next()` 后转换结果，或不调 `next()` 直接否决。
5. 观察型监听器必须调用 `next()`——这条是本仓库的常设规则，不是风格建议。
6. `ctx.on()` 是 effect，监听器随插件卸载自动移除，不要手动清理。
7. 事件名用 `namespace/action`，并用 `interface Events` + `import type {}` 保证类型贯通。

## 关联

- **第 16 章**：`ctx.on()` 属于 effect，这是监听器不需要手动移除的原因。
- **第 17 章**：服务是直接调用、强类型、有明确提供方；事件是匿名广播，两者互补。示例中 `reporter` 同时用了 `inject: ['stats']` 与 `ctx.on`，正好是两种机制的合流。
- **第 20 章**：`loader/volatile-update` 是一个用普通 `emit` 通知的事件，不等待资源重新配置完成。
- **第 23 章 Events API**：五种模式的完整签名与实现细节。
- **第 6 章**：harness 里事件生产者与消费者的实际布局。
