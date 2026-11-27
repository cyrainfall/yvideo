# 第 15 章：Cordis 入门与第一个插件

## 核心思想

Cordis 是 DSH 底层以 vendor 方式引入的插件框架，它是一个小型运行时：工具、LLM 适配器、文件访问乃至 agent loop 本身，都是挂载到共享上下文中的插件。因此写插件不是「扩展框架」，而是「描述自己的贡献」——贡献在 `apply(ctx)` 里注册，组合交给 `cordis.yml`，启动顺序交给 `inject`，撤销交给 Cordis。

## 框架与方法

- **五个核心概念**：这套词汇决定了插件作者的全部动作边界。
  - 何时用：第一次读某个插件的源码，或决定「这段逻辑该放哪」时。
  - 怎么做：插件是实现 Service 的对象——可以是带可选 `inject` 与 `apply(ctx)` 的函数，也可以是 `Service` 子类，生命周期由 Cordis 挂载到当前上下文；上下文是服务的容器，一个服务占据一个稳定的 `ctx.<key>`（`ctx.tools`、`ctx.llm`、`ctx.sessions`），其他插件按 key 查找服务而不是导入具体实现；通过 `inject` 声明所需服务，插件会等这些服务就绪才启动，加载顺序因此由服务依赖表达，而不是手工编排启动序列；类型化事件用于通信，服务通过 TypeScript 声明合并注册事件名，再按分发模式分发；注册是可逆副作用，提示词片段、工具 schema、适配器、提供方和监听器通过 `ctx.effect()` 或 `ctx.on()` 安装，reload 与 teardown 时会按预期撤销。

- **分发模式选择（dispatch modes）**：每个事件只有一种分发模式，且只能通过对应方法分发。
  - 何时用：声明新事件，或选择「观察」「包装」「扇出」时。
  - 怎么做：要观察用 `emit`；要包装或改写链条用 `waterfall`；要并行扇出又必须等全部完成用 `parallel`；要按注册顺序串行且收集返回值用 `serial`；要停在首个非空结果用 `bail`。分发模式是事件公开约定的一部分，新事件通过 `@mode` 标签记录，好让生成的目录把声明与分发调用点做交叉校验。

- **waterfall 是环绕中间件**：监听器接收 `(...args, next)`。
  - 何时用：需要让多个监听器依次处理同一个请求或决策对象时。
  - 怎么做：调用 `next()` 会执行下游监听器，下游返回值经由 `next()` 回到当前包装层，可由该层包装后继续向外返回；不调用 `next()` 直接返回就是短路。协作式监听器通常修改一个共享的请求或决策对象再委托；也可以完全替换结果，此时下游只看到替换后的结果。仅当监听器必须在普通注册之前运行时才用 `prepend: true`。对单决策事件，短路是设计意图：拥有决策权的策略监听器可以直接返回，只做标注或观察的监听器必须委托。

- **三种插件形态**：函数、对象、类。
  - 何时用：决定这个插件要不要对外公开服务时。
  - 怎么做：需要公开服务之前，一直用函数形态（导出 `apply`，可带 `name` 作为诊断用的显示元数据）；对象形态适合需要携带其他字段的场景；类形态是 `Service` 子类，等你要公开服务时再用。

- **组合在 YAML，顺序在依赖**：`cordis.yml` 是一组 Cordis 配置项的列表，`name` 是模块指定符（相对路径或 NPM 包名），loader 会挂载每个配置项。
  - 何时用：新增插件、拆分组合、排查「谁先加载」时。
  - 怎么做：把每个插件当成并发启动的独立项——它们在列表中的位置不保证加载先后，顺序由服务依赖（`inject`）决定，而非文件中的位置。插件文件里不写框架启动代码：插件描述自己的贡献，YAML 组合应用。`dsh` base 的 `cordis.patch.yml` 就是一份更长的组合，由部署 overlay 对它进行修补。

- **启动器的三步与 Loader 的表达式边界**：单文件启动器创建根 `Context`、挂载 Loader 插件，再让它从当前目录加载 `./cordis.yml`。
  - 何时用：第一次跑通示例，或解释「为什么我只写了一个 `apply`」时。
  - 怎么做：Loader 读取 `cordis.yml`、解析 `./hello.ts`，把它作为子插件挂载，然后 Cordis 调用 `apply(ctx)`。配置里的 `!!js` 由 `cordis-plugin-include` 解析为表达式节点：Loader 在声明的注入激活后基于插件上下文（`ctx.serviceName`）插值条目的 `config`，并在每次挂载决策时基于 loader 上下文插值 `disabled`；Include 会保留嵌套行表达式直到目标行激活，其余条目元数据保持字面值。由环境选择插件时用 overlay。

- **实践规则：把行为封装成插件，把注册变成可撤销的**：工具流水线事件属于 `ctx.tools`，模型流式输出属于 `ctx.llm`，实时 agent 协调属于 `ctx.agents`。
  - 何时用：决定「用事件还是用服务方法」时。
  - 怎么做：拦截和策略优先用事件，直接能力调用优先用服务方法。每个注册都应有对应的 disposer——要么从 `ctx.effect()` 返回一个，要么用 Cordis 提供的辅助方法自动处理；如果 teardown 顺序有要求，把相关工作放进同一个 effect，确保资源按预期顺序释放。

## 关键概念

- **插件（plugin）**：实现 Service 的对象，形态为函数、对象或 `Service` 子类，生命周期由 Cordis 挂载到当前上下文。
- **上下文（Context / `ctx`）**：服务的容器；Cordis 加载模块时用上下文调用 `apply`，插件通过它注册全部贡献。
- **`ctx.<key>`**：服务的稳定占位，其他插件按 key 查找服务而非导入实现。
- **`inject`**：插件声明的服务依赖；声明后插件等待这些服务就绪才启动。
- **分发模式（dispatch mode）**：事件的公开约定之一，决定是否 await、分发顺序与是否有返回值。
- **`waterfall`**：环绕中间件式分发，监听器通过 `next()` 委托下游并可包装其返回值。
- **Loader**：读取 `cordis.yml`、解析模块指定符并挂载子插件的插件。
- **disposer**：撤销一次注册的资源释放函数，注册与撤销成对出现。

## 心智模型

- 当你想在插件里安排启动顺序时，停下来，把它改写成 `inject` 依赖。
- 把 `ctx` 看成一个按 key 索引的服务台：你登记自己的 `ctx.<key>`，别人按 key 找你，没有人 import 你的类。
- 把每次注册看成一笔要还的账：没有 disposer 的注册就是泄漏，reload 时会加倍偿还。
- 把 `cordis.yml` 看成组合清单而不是启动脚本：它声明有哪些插件、各自怎么配，不规定谁先跑。

## 反模式

- **在插件文件里写框架启动代码**：启动器已经创建根 `Context` 并挂载 Loader；重复启动会得到两套互不相识的运行时。
- **用配置项顺序控制加载顺序**：各项并发启动，位置不保证先后，真正的顺序只来自 `inject`。
- **用服务方法做拦截策略**：拦截与策略优先用事件；服务方法留给直接能力调用。
- **注册不返回 disposer**：teardown 与 reload 时资源不会按预期释放。
- **把 `waterfall` 当 `emit` 用**：既委托不了下游，也没有表达短路意图，链条会在第一层断掉。
- **把插件加载失败当成「跳过该项」**：`apply` 抛异常会让进程终止；只有模块无法解析才是 logger 报告。

## 代码/配置示例

最小插件：一个命名导出 `apply`，`name` 只是诊断用的显示元数据。

```ts
import type { Context } from '@deepseek-ai/cordis'

export const name = 'hello'

export function apply(ctx: Context) {
  console.log('hello from my first plugin')
}
```

组合应用：一份 Cordis 配置项列表，`name` 是模块指定符。

```yaml
- name: './hello.ts'
```

运行与预期输出：

```sh
node --import tsx ../../vendor/cordis/bin.js
# hello from my first plugin
```

三种形态并列：

```ts
import { Service, type Context } from '@deepseek-ai/cordis'

// 1. Function plugin（最常见）
export function apply(ctx: Context) {}

// 2. Object plugin：带 apply 方法的对象
export const objectPlugin = {
  name: 'object-plugin',
  apply(ctx: Context) {},
}

// 3. Class plugin：Service 子类（公开服务时才需要）
export class MyService extends Service {
  constructor(ctx: Context) {
    super(ctx, 'myTutorialService')
  }
}
```

## 参考表

分发模式：是否 await、分发顺序、是否有返回值共同决定用哪个方法。

| 模式 | 是否 await | 分发顺序 | 是否有返回值 |
|---|---|---|---|
| `emit` | 否 | 监听器按注册顺序观察 | 否 |
| `waterfall` | 否 | 监听器按注册顺序观察（环绕包装，可短路） | 是 |
| `parallel` | 是 | 所有监听器并行观察事件 | 否 |
| `serial` | 是 | 监听器按注册顺序观察 | 是 |
| `bail` | 否 | 监听器按注册顺序观察，直到某个返回 bail 值 | 是 |

## 实例演练

从零到一次运行，全程只有两个文件。

准备：在仓库内建 `tmp/cordis-tutorial` 目录——`tmp/` 已被 git 忽略，写进去的东西不会进入版本控制。本教程不需要 API 密钥，所有示例都能在无密钥环境运行。每一章都从该目录运行同一条命令：`node --import tsx ../../vendor/cordis/bin.js`；`--import tsx` 让 Node 无需构建步骤即可运行配置指向的 TypeScript 文件。

写插件：创建 `hello.ts`，导出 `apply`，在函数体里打印一行。请注意文件里没有任何框架启动代码——没有 new Context、没有 listen、没有 import loader。

写组合：创建 `cordis.yml`，内容是一行 `- name: './hello.ts'`。这就是全部配置：它没有说明加载顺序，因为顺序不归它管。

运行：启动器创建根 `Context` 并挂载 Loader；Loader 读取 `cordis.yml`、解析 `./hello.ts`，把它作为子插件挂载；Cordis 调用你的 `apply(ctx)`。看到 `hello from my first plugin` 后，进程在没有内容继续运行时自行退出——这本身就是「插件描述贡献、组合由 YAML 负责」的证据。

制造第一个错误：让 `apply` 抛出异常。再次运行时进程会因该错误终止，插件加载失败是明确报错，不会仅仅跳过该配置项。所以「我的插件没生效」的第一个分支应该是「它是不是抛了」。

制造第二个错误：把 `cordis.yml` 里的路径拼错。这一次 Cordis 不会崩溃，而是通过 logger 服务报告错误——模块无法被解析时的处理路径与运行时异常不同。启动阶段这条报告可能在 console 导出器开始观察之前丢失，于是现象变成「新增配置项似乎没有任何效果」。诊断顺序因此固定：先检查拼写，再怀疑生命周期。

## 关键要点

1. 插件只描述贡献；组合在 `cordis.yml`，顺序在 `inject`，撤销在 Cordis。
2. 配置项的列表位置不代表加载先后，各项并发启动。
3. 需要公开服务之前一直用函数形态；类形态留给 Service。
4. 分发模式是事件契约的一部分，新事件用 `@mode` 记录以便生成目录交叉校验。
5. `waterfall` 里只有调用 `next()` 才委托下游；不委托就要明确这是短路意图。
6. 每个注册都要有 disposer，teardown 有顺序要求时放进同一个 effect。
7. `apply` 抛异常终止进程，模块解析失败只记日志——两者诊断路径不同。

## 关联

- **第 16 章 生命周期与副作用**：`ctx.effect()` 与 disposer 的完整语义，以及插件卸载时发生什么。
- **第 17 章 服务**：`inject`、`Service` 子类与 `ctx.<key>` 的公开方式。
- **第 18 章 事件**：类型化事件、声明合并与 waterfall 短路的具体写法。
- **第 2 章 能力接缝**：seam 的 Service Definition 必须是 Cordis `Service`，本章的函数/类形态是它的落地形态。
- **第 11 章 术语表与词汇纪律**：`seam` 只留给已定义的能力，插件与服务不要混称。
- **外部概念**：依赖注入容器与中间件式（onion）事件模型，分别对应 `inject` 与 `waterfall`。
