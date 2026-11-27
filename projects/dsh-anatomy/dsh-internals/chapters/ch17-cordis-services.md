# 第 17 章：服务

## 核心思想

**服务（service）** 是插件提供、其他插件通过 `ctx` 消费的具名能力。消费方只写下 `'tools'` 这样的能力名，不导入提供方，于是「谁来提供」变成配置问题而不是编译问题。配合 `inject`，加载顺序从「文件顺序」变成「依赖关系」——这是 Cordis 里最重要的一次解耦。

## 框架与方法

- **提供服务：运行时注册 + 编译时声明，两件事必须同时做。**
  - 何时用：某能力要被多个插件共用，且希望可替换实现。
  - 怎么做：写一个 `Service` 子类，构造函数里 `super(ctx, 'greeter')` 以名称注册实例；再用 `declare module '@deepseek-ai/cordis'` 块做 TypeScript 声明合并，把 `greeter` 加进 `Context` 接口。
  - 判据：运行时那条决定「能不能访问」，编译时那条决定「访问有没有类型」。声明合并**不生成代码**；缺了它服务在运行时照样工作，只是消费方失去类型安全。
- **类形态即插件**：`Service` 子类本身就是插件，因此 `ctx.plugin(GreeterService)` 会和挂载其他插件一模一样地挂载它。
- **消费服务：用 `inject` 声明硬依赖。**
  - 何时用：没有该服务插件就无法工作。
  - 怎么做：`export const inject = ['greeter']`。Cordis 会让插件保持 PENDING，直到列出的**每一项**服务都存在，因此在 `apply` 内可以保证 `ctx.greeter` 已经就绪。
  - 附带结论：`cordis.yml` 里的加载顺序无关紧要。交换两行、甚至把消费方写在提供方之前，输出完全相同。
- **可选依赖：跳过 `inject`，在使用处探测。**
  - 何时用：某项功能缺失时插件仍可运行。
  - 怎么做：用 `ctx.get('greeter')` 取服务，没有提供方时得到 `undefined`，用可选链与空值兜底处理。
- **依赖不是一次性检查**：`inject` 描述的是持续成立的关系。
  - 何时用：设计任何持有服务引用的消费方。
  - 怎么做：不做额外处理，交给运行时。若运行期间所需服务消失（提供方被卸载或热替换），每个依赖插件也会随之卸载，并在服务恢复后再次加载。结合 effect（第 16 章），消费方自己的注册会一并撤销，因此不会留着指向不可用服务的引用。
- **命名与可发现性**：每个应用中的服务名称共用一个扁平命名空间。
  - 何时用：注册任何自有服务之前。
  - 怎么做：为自有服务加可辨识的前缀或命名空间——harness 已占用 `tools` 和 `llm` 等普通名称；子系统页面上生成的 `cordis-surface` 区块列出 harness 注册的每个名称，是查重与取名的第一站。

## 关键概念

- **服务**：插件提供的具名能力，通过 `ctx.<name>` 访问，注册属于 effect。
- **`Service`**：服务基类，子类在构造函数中 `super(ctx, name)` 完成注册，本身也是插件。
- **声明合并**：用 `declare module` 扩充 `Context` 接口，为 `ctx.<name>` 提供类型，不产生运行时代码。
- **`inject`**：插件导出的服务名数组，声明硬依赖，未满足时插件停在 PENDING。
- **PENDING**：已声明但依赖未满足的状态；`apply` 未运行，也不让 Node 事件循环保持活跃。
- **`ctx.get(name)`**：按名取服务的探测式访问，缺失时返回 `undefined`，用于可选依赖。
- **扁平命名空间**：一个应用内所有服务名共用一个无层级的名字空间，因此需要前缀避免撞名。

## 心智模型

- **把服务看成一个「由当前加载决定的插槽」，而不是一个 import。** 消费方声明插槽形状，提供方插进去；换提供方等于换配置项，不用改消费方一行代码。
- **把 `inject` 看成启动前置条件，而不是启动检查。** 它决定插件**何时**开始，也决定服务消失时插件**何时**退出。
- **把 `cordis.yml` 的顺序看成无关噪音。** 决定启动时机的是依赖图，文件里的先后只是书写便利。
- **把服务名看成一个全局扁平的键空间。** `tools`、`llm` 这类普通词已经被 harness 占用，自建服务应带可辨识前缀。

## 反模式

- **消费方直接 `import` 提供方模块**：能力名被焊死成模块依赖，配置再也无法替换提供方——这正好毁掉服务存在的理由。
- **只写 `super(ctx, 'greeter')`，忘了 `declare module`**：运行时正常，类型检查全线失守；反过来只写声明不注册，则是编译通过、运行时 `ctx.greeter` 为空。
- **用 `inject` 表达可选依赖**：插件会永久停在 PENDING，不输出任何内容，既不崩溃也不报错，最难排查。
- **用 `tools`、`llm` 这类通用名注册自有服务**：扁平命名空间里直接与 harness 撞名。
- **相信「先加载的提供方优先」**：加载顺序由依赖决定，`cordis.yml` 的行序不构成任何保证。
- **把 PENDING 当成异常去 try/catch**：它是合法状态，提供方可能稍后才挂载。

## 代码/配置示例

提供方 `greeter.ts`：

```ts
import { Service, type Context } from '@deepseek-ai/cordis'

declare module '@deepseek-ai/cordis' {
  interface Context {
    greeter: GreeterService
  }
}

export class GreeterService extends Service {
  constructor(ctx: Context) {
    super(ctx, 'greeter')
  }

  greet(who: string) {
    return `Hello, ${who}!`
  }
}

export const name = 'greeter'

export function apply(ctx: Context) {
  ctx.plugin(GreeterService)
}
```

消费方 `consumer.ts`：

```ts
import type { Context } from '@deepseek-ai/cordis'

export const name = 'consumer'
export const inject = ['greeter']

export function apply(ctx: Context) {
  console.log(ctx.greeter.greet('world'))
}
```

组合：

```yaml
- name: './greeter.ts'
- name: './consumer.ts'
```

可选依赖的写法：

```ts ignore-check
export function apply(ctx: Context) {
  // undefined when no provider is loaded; the plugin still runs.
  const greeter = ctx.get('greeter')
  console.log(greeter?.greet('maybe') ?? 'no greeter available')
}
```

## 参考表

| 消费方式 | 声明 | 服务缺失时的行为 | 适用场景 |
|---|---|---|---|
| 硬依赖 | `export const inject = ['greeter']` | 插件停在 PENDING，`apply` 不运行，不输出任何内容 | 没有该能力插件就没有意义 |
| 可选依赖 | 无 `inject`，用 `ctx.get('greeter')` 探测 | 得到 `undefined`，插件照常运行，由使用处决定降级 | 能力是增强项，缺失也能工作 |

## 实例演练

三段实验都来自同一个组合，改的只有 `cordis.yml`。

**第一段：正常组合。** 加载 `./greeter.ts` 时 `apply` 执行 `ctx.plugin(GreeterService)`，构造函数 `super(ctx, 'greeter')` 完成注册；随后加载 `./consumer.ts`，它的 `inject` 已满足，`apply` 直接运行，打印 `Hello, world!`。

**第二段：交换顺序。** 把 `./consumer.ts` 放到前面。消费方先被声明，但 `greeter` 尚不存在，fiber 停在 PENDING；`./greeter.ts` 加载并注册服务后，消费方从 PENDING 转入加载。输出仍然是 `Hello, world!`——这是「依赖驱动启动」的直接证据。

**第三段：彻底移除 `./greeter.ts`。** 消费方保持 PENDING，什么也不打印：既不崩溃，也不会只运行一半。更微妙的是，PENDING 的 fiber 不会让 Node 的事件循环保持活跃，因此如果组合中没有其他运行项，进程会**静默地以状态码 0 退出**。这个现象是第 20 章诊断手法的动机：看起来「什么都没发生」，实际是插件在等一个永远不会来的服务。

最后把 `inject` 换成 `ctx.get('greeter')`，同样移除提供方，消费方会正常运行并打印 `no greeter available`。同一份插件、同一个缺失场景，两种声明给出两种正确行为——选择哪一个，取决于这个能力是「必需」还是「增强」。

这套机制在真实 harness 里的形态就是服务替换：卸载 Cordis 配置项 `dsh-bash-local`，挂载另一个 `shell` 提供方，所有注入 `'shell'` 的插件都会重新启动并使用新实现，而它们的代码一行都不用改。这也解释了为什么消费方绝不能 `import` 提供方——一旦 import，替换就退化成改代码。

## 关键要点

1. 服务 = 运行时注册（`super(ctx, name)`）+ 编译时声明（`declare module`），缺一即残。
2. `Service` 子类是插件，用 `ctx.plugin()` 挂载，不要手动 `new` 出来直接用。
3. `inject` 表达硬依赖，Cordis 保证 `apply` 运行时 `ctx.<name>` 已就绪。
4. 加载顺序由依赖决定，`cordis.yml` 行序不构成保证。
5. 依赖是持续的：提供方消失，消费方连带卸载；恢复后重新加载。
6. 可选依赖用 `ctx.get()` 探测，不要用 `inject` 表达「最好有」。
7. 自建服务加前缀，避开 harness 已占用的 `tools`、`llm` 等扁平名字。

## 关联

- **第 16 章**：服务注册属于 effect；依赖消失时消费方连带卸载，靠的正是 effect 撤销机制。
- **第 18 章**：不适合共享状态的场景用事件通信，插件无需知道谁在监听。
- **第 20 章**：服务可替换是配置能力的基础（卸载 `dsh-bash-local`、挂载另一个 `shell` 提供方），`isolate` 则给组独立的服务实例。
- **第 22 章 Context API**：`ctx.<service>` 访问器与 `ctx.get()` 的完整接口。
- **第 27 章 Service API**：`Service` 基类的完整契约。
