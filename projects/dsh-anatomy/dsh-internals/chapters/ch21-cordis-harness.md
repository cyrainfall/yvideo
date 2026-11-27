# 第 21 章：进入 Harness

## 核心思想

第 15–20 章讲过的机制在这一章一次性兑付：向 harness 的 `tools` 服务注册一个模型可调用的工具，让它走真实的工具执行流水线跑一遍，再让另一个完全不知情的插件通过 `tools/result` 事件观察结果。整个示例不需要密钥，也不调用模型——被替代的只有"模型发起调用"这一个环节。

## 框架与方法

- **`inject: ['tools']` + `ctx.tools.register(...)`：一次注册，两处所有权**
  - 何时用：任何要给模型新增能力的插件。
  - 怎么做：`inject` 让插件等待工具注册表就绪才启动；`ctx.tools.register()` 返回的注册 disposer 被附着到插件上，因此插件卸载时工具自动注销。这两点都不是新知识——`inject` 是第 17 章的服务机制，disposer 归属是第 16 章的 effect 语义。

- **`defineTool` 的四段契约**
  - 何时用：定义工具时，不要手写 JSON Schema，也不要自己校验参数。
  - 怎么做：`parameters` 写"规约"（字段名 → `type` / `required` / `description`），`defineTool` 负责三件事——把它转换成展示给模型的 JSON Schema、推导 `args` 的 TypeScript 类型、在 `execute` 运行前校验模型提供的参数。`execute` 返回的是由 `output.schema` 声明的**规范值**（canonical value），不是最终展示文本；`output.render` 作为 Native renderer（原生渲染器）另行生成可持久化的结果内容。

- **`ctx.tools.execute()`：把模型该做的事自己写出来**
  - 何时用：无密钥冒烟测试、回归验证、脱离模型调试工具。
  - 怎么做：构造 `calls` 数组，每项是 `{ type: 'tool-call', id, name, arguments }`，`arguments` 是 JSON 字符串；再传一个 `signal`（`AbortController` 的 signal，用于取消）。返回值的形状是 `result.results[0]?.result.content`。注意 `id` 不是随手写的字符串：`brandString<ToolCallId>('demo-1')` 给相关 id 打上品牌，模拟一个真实 provider 会签发的那种 id。

- **观察者插件与包级声明合并**
  - 何时用：想在不改动被观察插件的前提下旁路记录行为。
  - 怎么做：单独建一个插件，`ctx.on('tools/result', (exec, result) => ...)`。`'tools/result'` 及其 payload 能有类型，靠的是 `import type {} from '@deepseek-ai/dsh-tools'` 这行空导入——它引入该包的声明合并。这与教程里导入 `stats.ts` 以扩展事件类型的做法相同，只是扩展到了包级别。

- **为什么驱动器要写成 `void (async () => ...)()`**
  - 何时用：在 `apply` 里做一次性异步动作时。
  - 怎么做：`apply` 本身不是 async 函数，一次性调用必须自己包一层并显式丢弃 promise（`void`）。它立即执行，与注册动作处于同一同步段，因此"注册完成 → 立刻调用"这件事是确定顺序的。代价是其中的异常不再冒泡到插件加载流程，只留在控制台。

- **组合层的隐藏依赖**
  - 何时用：写 `cordis.yml` 时。
  - 怎么做：`@deepseek-ai/dsh-tools` 会注入 `systemPrompt` 服务，因为工具需要向系统提示词贡献 schema，所以组合中必须同时列出该服务的提供方 `@deepseek-ai/dsh-system-prompt`。缺了提供方，工具插件会像第 20 章所述那样停在 PENDING，而不是报错——这是最容易误判为"代码写错了"的故障。

## 关键概念

- **`tools` 服务**：harness 的工具注册表，工具插件的注入目标。
- **`defineTool`**：工具定义函数，把参数规约、输出 schema、渲染器和执行体打包成一个可注册对象。
- **Native renderer（原生渲染器）**：`output.render`，把规范值转成可持久化结果内容的函数。
- **`ToolCallId`**：工具调用的相关 id 品牌类型；真实链路由 provider 签发，示例用 `brandString` 伪造。
- **`tools/result`**：结果物化阶段发出的事件，携带执行记录与结果。
- **PENDING**：插件已加载但依赖未满足时的挂起状态。
- **声明合并（declaration merging）**：通过空类型导入让外部包的事件名与 payload 获得类型。
- **patch overlay**：叠加在 profile 层之上的小型配置补丁，用于把教程插件挂进真实 agent。

## 心智模型

- 当想给模型加一项能力时，用 `defineTool` 定义、用 `ctx.tools.register` 挂载、用 `inject: ['tools']` 排顺序——三件事各管一段，不要混在一个函数里做完。
- 把 `ctx.tools.register()` 的返回值看成一张"归还凭据"：谁注册谁负责注销，插件卸载即归还，所以永远不需要写卸载钩子。
- 把 `tools/result` 看成**结果物化阶段的广播**，而不是 `execute` 的返回值：它发生在 `execute` 向调用方返回的 promise 兑现**之前**，因此观察者总是先于调用方看到结果。
- 把工具插件和日志插件看成两个互不引用的进程内模块，它们之间的唯一连线是 `tools` 注册表（注册）与事件总线（观察）。

## 反模式

- **让注册者自己 `console.log` 充当观察者**：能跑，但把"提供能力"和"可观测性"焊死在一个插件里，无法单独开关、单独替换，也验证不了事件契约真的成立。
- **在 `execute` 里返回渲染后的 content**：`execute` 应返回 `output.schema` 声明的规范值；把渲染结果当返回值会让持久化内容与规范值耦合，`output.render` 形同虚设。
- **手写 JSON Schema 或手工校验 `args`**：`defineTool` 已经从 `parameters` 规约派生 schema、推导类型并前置校验，重复实现只会引入两套不一致的规则。
- **漏列 `dsh-system-prompt` 提供方**：表现是插件静默 PENDING 而非抛错，排查成本极高。
- **在示例里直接调 `execute` 回调而不走 `ctx.tools.execute`**：绕过了流水线，等于没验证"模型调用"这条路径。
- **把 `void` 丢弃的 promise 当成有错误处理**：一次性驱动器的异常不会冒泡到插件加载，失败在控制台之外是静默的。

## 代码/配置示例

工具插件（关键结构）：

```ts
import type { Context } from '@deepseek-ai/cordis'
import { brandString } from '@deepseek-ai/dsh-brand'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { ToolCallId } from '@deepseek-ai/dsh-llm'

export const name = 'greet-tool'
export const inject = ['tools']

export function apply(ctx: Context) {
  ctx.tools.register(defineTool({
    name: 'greet',
    description: 'Greet the named person.',
    parameters: {
      name: { type: 'string', required: true, description: 'Who to greet' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      return `Hello, ${args.name}!`
    },
  }))

  void (async () => {
    const result = await ctx.tools.execute({
      calls: [{
        type: 'tool-call', id: brandString<ToolCallId>('demo-1'),
        name: 'greet', arguments: JSON.stringify({ name: 'Cordis' }),
      }],
      signal: new AbortController().signal,
    })
    console.log('tool replied:', JSON.stringify(result.results[0]?.result.content))
  })()
}
```

观察者插件：

```ts
import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-tools'

export const name = 'tool-logger'
export const inject = ['tools']

export function apply(ctx: Context) {
  ctx.on('tools/result', (exec, result) => {
    const text = result.content
      .map(block => (block.type === 'text' ? block.text : ''))
      .join('')
    console.log(`[tool-logger] ${exec.name} -> ${text}`)
  })
}
```

组合：

```yaml
- name: '@deepseek-ai/dsh-system-prompt'
- name: '@deepseek-ai/dsh-tools'
- name: './tool-logger.ts'
- name: './greet-tool.ts'
```

运行与输出：

```sh
node --import tsx ../../vendor/cordis/bin.js
```

```
[tool-logger] greet -> Hello, Cordis!
tool replied: [{"type":"text","text":"Hello, Cordis!"}]
```

## 参考表

`defineTool` 各项的规约对象与在流水线中的位置：

| 字段 | 形态 | 规约了什么 | 在流水线中的作用 |
| --- | --- | --- | --- |
| `name` | 字符串 | 工具标识 | 模型发起调用时引用的名字 |
| `description` | 字符串 | 用途说明 | 展示给模型 |
| `parameters` | 字段名 → `{ type, required, description }` | 参数规约 | 派生成 JSON Schema、推导 `args` 类型、`execute` 前校验 |
| `output.schema` | schema 对象 | 规范值形状 | 声明 `execute` 返回值 |
| `output.render` | `(_args, value) => block[]` | 可持久化内容 | 作为 Native renderer 生成结果内容 |
| `execute` | `async (args) => value` | 执行体 | 流水线内实际执行 |

两个插件的对称性：

| 关注点 | `greet-tool`（注册者） | `tool-logger`（观察者） |
| --- | --- | --- |
| 注入 | `['tools']` | `['tools']` |
| 用到的机制 | `ctx.tools.register` + disposer 归属 | `ctx.on('tools/result')` |
| 类型来源 | `defineTool` 推导 | 包级声明合并 |
| 彼此是否引用 | 否 | 否 |
| 连接方式 | 注册表服务 + 事件 | 注册表服务 + 事件 |

## 实例演练

从启动到两行输出的完整推演：

1. 加载器读到四个条目。`dsh-system-prompt` 先就绪，`systemPrompt` 服务进入可用状态；`dsh-tools` 注入 `systemPrompt`，因此能激活并向系统提示词贡献工具 schema；两个本地 `.ts` 插件注入 `tools`，等注册表就绪后激活。
2. `greet-tool` 激活时立即调用 `ctx.tools.register(...)`，工具 `greet` 进入注册表，注册 disposer 记在该插件的 fiber 名下。
3. 同一插件体内，立即执行的 async IIFE 以"假模型"身份调用 `ctx.tools.execute`，传入一个 `tool-call` 与一个 `AbortController` 的 signal。
4. 流水线校验 `arguments`（`{"name":"Cordis"}` 满足 `name` 必填），运行 `execute` 得到规范值 `Hello, Cordis!`。
5. 结果物化：按 `output.schema` 确认规范值，调用 `output.render` 生成 `[{type:'text', text:'Hello, Cordis!'}]`，该内容可持久化。
6. 物化过程中发出 `tools/result`，`tool-logger` 的监听器同步打印 `[tool-logger] greet -> Hello, Cordis!`。**这一行先出现。**
7. `ctx.tools.execute` 的 promise 随后对调用方兑现，打印 `tool replied: [{"type":"text","text":"Hello, Cordis!"}]`。

第 6 步与第 7 步的先后顺序是最值得记住的观察结果：它证明 `tools/result` 属于**物化阶段**而不是**返回阶段**，也证明两个互不引用的插件确实被事件连上了。

把这段推演改成"真实 agent"是纯配置动作：在 profile 层之上加一个小型 `--patch` overlay，指向 `./greet-tool.ts`。真实 agent 的其余部分就是同一套组合再加插件——LLM 适配器、agent loop、持久化、应用入口。读 base profile 层与 headless 层的 `cordis.patch.yml` 时，你已经能逐条读懂每一行在注入什么、监听什么。

## 关键要点

1. 给模型加能力的最小闭环是三个动作：`defineTool` 定义、`ctx.tools.register` 挂载、`inject: ['tools']` 排依赖。
2. 工具的参数校验、JSON Schema 生成、`args` 类型推导全部由 `defineTool` 从 `parameters` 规约完成，不要重写。
3. `execute` 返回规范值，`output.render` 负责可持久化内容，两者不要混。
4. `ctx.tools.execute` 能在不调用模型的前提下走完真实流水线，是工具开发的主要调试通道。
5. 组合里必须成对出现 `dsh-tools` 与 `dsh-system-prompt`，否则表现为静默 PENDING。
6. `tools/result` 早于 `execute` 的 promise 兑现——看到这个顺序，说明流水线走对了。
7. 观察者插件只需要 `inject: ['tools']` 和一行包级声明合并导入，不需要引用被观察插件。

## 关联

- **第 16 章**：`ctx.tools.register` 的 disposer 归属就是本章反复用到的 effect 语义。
- **第 17 章**：`inject: ['tools']`、`dsh-tools` 注入 `systemPrompt`，都是服务依赖的实例。
- **第 18 章**：`tools/result` 是 harness 事件的典型样本，其分发语义见第 23 章。
- **第 20 章**：缺提供方时停在 PENDING、用 `--patch` overlay 挂载，都是组合与 HMR 的内容。
- **第 22–25 章**：本章用到的 `ctx.on`、`ctx.effect`、`ctx.fiber` 等 API 的完整签名在那里。
- **第 1 章（架构总览）**：本章末尾提到的 base profile 层、headless 层在系统地图中的位置。
