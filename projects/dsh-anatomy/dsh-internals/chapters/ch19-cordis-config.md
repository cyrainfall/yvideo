# 第 19 章：配置

## 核心思想

`cordis.yml` 里每个 Cordis 配置项都可以携带 `config` 块，插件则导出一个 schema 在运行 `apply` 之前验证它。结论只有一句：**插件绝不会在配置不完整时启动**——错误配置让加载失败并给出准确错误。真正需要单独理解的是第二种配置：`volatile` 字段，它允许值变化而不重新挂载插件。

## 框架与方法

- **可配置插件：一份 `Config` 两种身份。**
  - 何时用：任何需要从 `cordis.yml` 取参数的插件。
  - 怎么做：写 `export interface Config { ... }` 给 TypeScript，同时写 `export const Config: Schema<Config> = Schema.object({...})` 给 Cordis 做验证；`apply(ctx: Context, config: Config)` 的第二个参数就是验证后的结果。
  - 判据：导出的 `Config` 既是类型也是同名的运行时 schema。本仓库用 Schemastery 定义 schema，而 Cordis 本身接受任意 Standard Schema 验证器；因此把**普通对象**导出为 `Config` 无法工作。
- **默认值补齐**：用 `Schema.string().default('Hello')`、`Schema.array(String).default(['world'])` 声明缺省值。
  - 怎么做：把缺省值写进 schema，而不是写进 `apply` 里的 `??` 兜底。
  - 附带结论：`apply` 始终会收到完整且经过验证的配置，未提供的字段由 schema 默认值补齐。
- **明确报错**：验证失败时 fiber 进入 FAILED。
  - 怎么做：不要 try/catch 吞掉；让错误冒出来。错误文本会指名到字段路径（如 `$.targets` 与 `(at targets)`），启动器打印后以状态码 1 退出。
  - 延伸义务：若配置通过了 schema 验证，但其中指定的资源或提供方不可用，插件也应当在**能解析该引用时立即拒绝**，而不是带着空引用继续跑。
- **volatile 字段：值变而不重挂载。**
  - 何时用：插件在**每次操作**中都会读取的字段（例如问候语、采样开关），希望改动立即生效且不打断运行。
  - 怎么做：在 schema 上链 `.volatile()`，在 `apply` 里把 `config` 的类型写成 `ReturnType<typeof Config>`，读取时用 `config.greeting.get()`；字段变化会更新稳定引用，无需重新挂载插件。
  - 通知方式：监听 `loader/volatile-update`，其参数是**以键数组表示的变化路径**。
- **volatile 的读取纪律**（最容易踩的部分）。
  - 可以：保存引用本身；或保存一次读取值并在**单次操作**内使用，包括跨越 `await`。
  - 不可以：把这次读到的值用于**后续操作**——它不会随引用一起更新。
  - 值形态：对象和数组值是脱离输入、递归冻结的普通数据快照；函数、类实例和循环引用会被拒绝。
  - 声明位置：在**固定对象路径**上声明 volatile 字段，或把整个对象/数组标记为 volatile；数组、字典、union 或 intersect 分支、lazy、transform 或另一个 volatile 值内部的独立引用都会被拒绝。
- **计算得到的配置值：`!!js` 标签。**
  - 何时用：必须在加载时求值的配置，例如读环境变量。
  - 怎么做：`greeting: !!js process.env.DEMO_GREETING ?? 'Hello'`。`!!js` 仅在 `config` 与条目 `disabled` 字段内有效。
  - 特例：`disabled: !!js ...` 在**每次挂载决策**时基于 loader 上下文求值（本仓库的扩展），可按平台或环境门控一行；其余元数据（`name`、`id`、`inject` 等）保持静态，其中的表达式只是普通真值数据。

## 关键概念

- **`Config`（双重身份）**：同名导出的 TypeScript 接口与运行时 schema，前者给编译器，后者给加载器。
- **schema 验证**：在 `apply` 运行前执行的校验，失败即 FAILED，插件不启动。
- **`ValidationError`**：配置不合法时的错误形态，指出字段路径与期望类型。
- **volatile 字段**：`.volatile()` 标记的字段，变化时更新稳定引用而不重新挂载插件。
- **稳定引用**：volatile 字段的容器对象，通过 `.get()` 读取当前值。
- **`loader/volatile-update`**：only-volatile 变化后发给所属实例的通知事件，携带变化路径。
- **`internal/config` 钩子**：volatile 变化解析与校验所经过的插件钩子。
- **`internal/update`**：普通字段变化走的更新流程，volatile 变化**不进入**它。
- **`simplify()`**：序列化时解包 volatile 引用的工具。
- **`!!js`**：loader 支持的配置标签，在加载时求值表达式。

## 心智模型

- **把 schema 看成一堵墙，而不是一份文档。** 墙内的 `apply` 永远拿到完整、已验证、带默认值的配置；墙外可以是任意脏输入。
- **把 volatile 看成「可换的电池」，而不是「新配置」。** 换电池不停机；但你在某次操作里量到的电压不能当成以后一直有效。
- **把普通字段变化与 volatile 变化看成两条不同的更新车道。** 前者重走激活与 `internal/update`，后者只提交引用并发一次通知；两条车道的语义差异是本章全部复杂度的来源。
- **把 `!!js` 看成加载期的宏展开，而不是运行时求值。** 它只在 `config` 与 `disabled` 两处生效，写进 `name` 或 `inject` 就只是普通字符串真值。

## 反模式

- **把普通对象导出为 `Config`**：没有验证器，Cordis 无法验证，配置形同虚设。
- **在 `apply` 里缓存 volatile 的读取值供后续操作用**：那个值不会随引用更新，插件会一直用旧值，且看不出任何异常。
- **用 volatile 表达结构性配置**：需要重建资源的变化本应触发重新挂载；标成 volatile 只是让引用换了值，资源并不会按新结构重建。
- **在数组元素、union 分支、transform 内部声明独立 volatile 引用**：会被直接拒绝，声明位置必须在固定对象路径上。
- **把 `!!js` 写进 `name` / `id` / `inject`**：这些元数据保持静态，表达式在这里只是普通真值数据，不会被求值。
- **以为无效的 volatile 候选会立即生效**：它只会被记录日志，运行中的引用保持不变，**直到下次激活**。
- **把验证错误 try/catch 掉继续启动**：插件会在配置不完整的状态下运行，比直接失败更难查。

## 代码/配置示例

`config-demo.ts`：

```ts
import type { Context } from '@deepseek-ai/cordis'
import Schema from '@deepseek-ai/schemastery'

export const name = 'config-demo'

export interface Config {
  greeting: string
  targets: string[]
}

export const Config: Schema<Config> = Schema.object({
  greeting: Schema.string().default('Hello'),
  targets: Schema.array(String).default(['world']),
})

export function apply(ctx: Context, config: Config) {
  for (const target of config.targets) {
    console.log(`${config.greeting}, ${target}!`)
  }
}
```

`cordis.yml`：

```yaml
- name: './config-demo.ts'
  config:
    targets: ['alpha', 'beta']
```

输出：

```
Hello, alpha!
Hello, beta!
```

无效配置：

```yaml
- name: './config-demo.ts'
  config:
    targets: 'not-an-array'
```

```
ValidationError: invalid config:
  - $.targets expected array but got not-an-array (at targets)
```

volatile 字段：

```ts
import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/cordis-plugin-loader'
import Schema from '@deepseek-ai/schemastery'

export const Config = Schema.object({
  greeting: Schema.string().default('Hello').volatile(),
})

export function apply(ctx: Context, config: ReturnType<typeof Config>) {
  ctx.on('loader/volatile-update', () => {
    console.log(config.greeting.get())
  })
}
```

计算配置值：

```yaml
- name: './config-demo.ts'
  config:
    greeting: !!js process.env.DEMO_GREETING ?? 'Hello'
```

## 参考表

| 维度 | 普通字段 | volatile 字段 |
|---|---|---|
| 读取方式 | 直接取属性 | `.get()` |
| 变化后是否重新挂载 | 是（走激活与 `internal/update`） | 否，只更新稳定引用 |
| 走哪个钩子 | 原更新流程 | 目标插件的 `internal/config` |
| 是否发通知 | 旧引用不更新也不接收通知 | 发一次 `loader/volatile-update`，参数为变化路径 |
| 等值更新 | — | 不通知 |
| 无效候选 | 加载失败 | 记录日志，运行中的引用不变，直到下次激活 |
| 声明位置限制 | 无特殊限制 | 只能在固定对象路径，或整个对象/数组 |

## 实例演练

同一个 `config-demo.ts` 走三段，观察三种结局。

**第一段：缺字段。** `cordis.yml` 只给 `targets: ['alpha', 'beta']`，没给 `greeting`。schema 的 `.default('Hello')` 在验证阶段把 `greeting` 补齐，`apply` 拿到的是一份完整配置，循环打印 `Hello, alpha!` 与 `Hello, beta!`。注意这里没有任何兜底代码——补齐发生在墙外，`apply` 内不需要防御。

**第二段：类型错。** 把 `targets` 改成字符串 `'not-an-array'`。验证在 `apply` 之前失败，抛 `ValidationError`，消息精确到 `$.targets expected array but got not-an-array (at targets)`；fiber 进入 FAILED，启动器打印错误后以状态码 1 退出。插件从未进入 LOADING，也就谈不上「部分运行」——这正是「绝不会在配置不完整时启动」的含义。

**第三段：volatile 换值。** 把 `greeting` 标成 `.volatile()`，`apply` 监听 `loader/volatile-update` 并在回调里 `config.greeting.get()`。只改 `greeting` 时：Loader 比较原始配置时会忽略这个 volatile 字段，仅-volatile 的变化经 `internal/config` 解析校验，在所有普通字段有效值仍一致的前提下，把新值提交到运行中的引用，并发一次 `loader/volatile-update`——参数是键数组形式的变化路径。插件没有重新挂载，`apply` 没有重跑，但下一次 `.get()` 已经是新值。

反过来的情形同样重要：如果同时改了普通字段（例如 `targets`），就回到原更新流程，旧引用不会更新，也收不到通知——你必须重新挂载才能看到新值。这也是为什么 volatile 只该用于「每次操作都读一遍」的字段。

## 关键要点

1. `Config` 必须同时是类型和运行时 schema；普通对象当 `Config` 不工作。
2. 默认值写进 schema，`apply` 永远收到完整配置，不需要内部兜底。
3. 验证失败 → FAILED + 精确字段路径 + 非零退出；不要吞异常。
4. 配置合法但引用的资源不可用，也应在能解析时立即拒绝。
5. volatile 用于「每次操作都读」的字段，变化更新引用而不重新挂载。
6. volatile 读取值只能用于单次操作（可跨 `await`），不能留到后续操作。
7. 普通字段变化与 volatile 变化走两条车道，混改时按普通字段处理。
8. `!!js` 只在 `config` 与 `disabled` 内有效，其余元数据保持静态。

## 关联

- **第 16 章**：配置校验失败让 fiber 进入 FAILED；生命周期的状态机是本章错误路径的落点。
- **第 18 章**：`loader/volatile-update` 用普通 `emit` 通知，不等待资源重新配置完成。
- **第 20 章**：`disabled` 字段控制条目是否挂载，`!!js` 可按环境门控一行；loader 按 `id` 比较条目以决定重挂载范围。
- **第 33 章**：`settings` 与持久化；现有 settings 消费者继续使用原有 settings 接口，序列化 schema 保留 volatile 标记供表单使用。
