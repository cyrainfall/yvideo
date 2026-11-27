# 第 20 章：组合与 HMR

## 核心思想

`cordis.yml` 不是一份启动脚本，而是**应用本身**：它选择插件树，因此改变组合就是改产品形态。因为卸载会释放 effect（第 16 章）、加载会遵循依赖（第 17 章），「先卸载再加载」天然构成一次安全的替换——这就是热模块替换（HMR，hot module replacement）的全部原理。代价是：如果一个插件的依赖没人提供，它会安静地停在 PENDING，什么也不说。

## 框架与方法

- **给条目一个 `id`：让 loader 认出「同一个条目」。**
  - 何时用：任何会被反复编辑的 `cordis.yml`。
  - 怎么做：写 `id: greeter` 之类的稳定标识。loader 按 `id` 比较 Cordis 配置项，从而区分「修改现有条目」与「先删除再添加」，只挂载、卸载或重新配置发生变化的部分。
  - 不写的代价：不带 `id` 的条目在每次读取时都会获得一个新生成的 id，所以只要配置文件发生任何编辑，即使自身文本未变，它也会被视为先删除再添加并重新挂载。
- **用 `disabled` 停用而不删除。**
  - 何时用：临时关掉某个插件、排查问题时。
  - 怎么做：`disabled: true` 会卸载插件而不删除其 Cordis 配置项；改回原值后，插件以及**所有因依赖其服务而处于 PENDING 的插件**都会再次加载。
- **用组与 `isolate` 组织作用域。**
  - 组：可以嵌套一份 Cordis 配置项子列表，并将其作为一个单元加载和卸载。
  - `isolate`：为一个组提供某项服务名称的**独立实例**，于是两个组可以各自看到配置不同的 `shell` 提供方，互不影响。
- **HMR：监视文件，保存即替换。**
  - 何时用：开发期反复修改插件代码。
  - 怎么做：在组合里加入 `@deepseek-ai/dsh-hmr`，用 `config.root` 指定监视目录，并在 tsx 下运行 Cordis。替换流程是「旧实例先卸载（其所有 effect 都会回卷）→ 新代码加载 → `apply` 再次运行」。
  - 两个必需伙伴：HMR 通过 Cordis logger 服务记录日志，**没有控制台导出器就看不到它的消息**；它还 `inject` `timer` 服务来实现去抖，**没有 `@deepseek-ai/cordis-plugin-timer` 就会永远停在 PENDING，而且不发出任何提示**。
- **诊断 PENDING：直接枚举插件注册表。**
  - 何时用：插件「既不执行任何操作，也不报告任何内容」。
  - 怎么做：从 `@deepseek-ai/cordis` 取 `FiberState`，遍历 `ctx.registry.values()`，再遍历每个 runtime 的 `fibers`，筛出 `fiber.state === FiberState.PENDING` 并打印名字。
  - 判据：PENDING 不是错误，而是合法状态——提供方可能稍后才挂载，所以不要试图靠改配置「修好」它，先确认依赖是否有人提供。

## 关键概念

- **Cordis 配置项**：`cordis.yml` 列表里的一项，可携带 `id`、`name`、`config`、`disabled` 等元数据。
- **`id`**：条目的稳定标识，是「修改」与「删除再添加」的分界线。
- **`disabled`**：卸载插件但保留条目，可逆。
- **组（group）**：嵌套一份子条目列表，作为单元加载与卸载。
- **`isolate`**：为组提供某服务名称的独立实例，实现服务隔离。
- **HMR**：保存文件即卸载旧实例、加载新代码的替换机制，依赖 effect 撤销与依赖驱动加载。
- **PENDING 诊断**：通过 `ctx.registry` 与 `FiberState.PENDING` 找出等待依赖的 fiber。
- **`Loader` 与 `Include`**：loader 自身的插件，在枚举注册表时同样以 ACTIVE 出现——因为配置文件本身也是通过插件挂载的。

## 心智模型

- **把 `cordis.yml` 看成可热编辑的装配图。** 你不是在「运行一个脚本」，而是在声明一个由插件节点组成的产品；改图就是改产品。
- **把 HMR 看成一次原子的「卸载 → 加载」。** 它没有任何魔法：能替换，是因为旧实例的 effect 会全部回卷、新实例按依赖重新加载。
- **把 PENDING 看成「在等」而不是「坏了」。** 它是最常见的假故障：进程不崩溃、不报错、甚至静默退出 0。
- **把 `id` 看成表格里的主键。** 没有主键，任何一次编辑都只能按「删一行、加一行」处理，于是整条重挂载、状态全丢。

## 反模式

- **条目不带 `id`**：任何编辑（哪怕是改别的行）都可能把它当作新条目重挂载，运行态丢失且难以理解原因。
- **用删除条目的方式停用插件**：`disabled: true` 才是保留可恢复性的做法；删掉条目就丢了 `id` 与配置上下文。
- **把 PENDING 当 bug 反复改配置**：它只说明某个 `inject` 的服务没有提供方；去补提供方，而不是改消费方。
- **HMR 组合里省掉 logger 或 timer**：前者让你看不到任何 HMR 日志，后者让 HMR 永久 PENDING——两种「没反应」都没提示。
- **期待 HMR 保留插件内部状态**：旧实例先卸载，`apply` 会重跑，内存里的状态不会跨替换存活。
- **不在 tsx 下跑 HMR**：HMR 通过 Loader 的原生辅助工具读取 Node 的 loader 内部结构，运行方式必须配套。
- **以为编辑 `cordis.yml` 会整体重启**：loader 按 `id` 只处理变化的部分。

## 代码/配置示例

带元数据的条目：

```yaml
- id: greeter          # stable identity for this entry
  name: './greeter.ts'
- id: consumer
  name: './consumer.ts'
  disabled: true       # keep the entry, skip mounting it
```

HMR 组合：

```yaml
- id: logger
  name: '@deepseek-ai/cordis-plugin-logger-console'
- id: timer
  name: '@deepseek-ai/cordis-plugin-timer'
- id: hmr
  name: '@deepseek-ai/dsh-hmr'
  config:
    root: ['.']
- id: hello
  name: './hello.ts'
```

运行（必须在 tsx 下）：

```sh
node --import tsx ../../vendor/cordis/bin.js
```

编辑 `hello.ts` 保存后的输出：

```
hello from my first plugin
2026-07-22 15:44:36 [I] hmr watching [ '.' ]
2026-07-22 15:44:39 [I] hmr reload plugin at hello.ts
hello from my EDITED plugin
```

PENDING 诊断 `diagnose.ts`：

```ts
import { FiberState, type Context } from '@deepseek-ai/cordis'

export const name = 'diagnose'

export function apply(ctx: Context) {
  setTimeout(() => {
    for (const runtime of ctx.registry.values()) {
      for (const fiber of runtime.fibers) {
        if (fiber.state === FiberState.PENDING) {
          console.log(`${fiber.name} is PENDING — a required service is missing`)
        }
      }
    }
  }, 500)
}
```

依赖无法满足的插件 `needs-timer.ts`：

```ts
import type { Context } from '@deepseek-ai/cordis'

export const name = 'needs-timer'
export const inject = ['timer']

export function apply(ctx: Context) {
  console.log('needs-timer loaded')
}
```

## 参考表

| 元数据 | 作用 | 典型用法 |
|---|---|---|
| `id` | 条目的稳定标识，决定「修改」还是「删除再添加」 | 每个会被编辑的条目都写 |
| `name` | 模块路径或包名，指向插件实现 | `'./hello.ts'`、`'@deepseek-ai/dsh-hmr'` |
| `config` | 传给插件的配置块，由插件 schema 验证 | `root: ['.']` |
| `disabled` | 卸载插件但保留条目，可逆 | 临时关停、排查 |
| 组 | 嵌套子条目列表，作为单元加载和卸载 | 成组启停 |
| `isolate` | 为组提供某服务名称的独立实例 | 两个组各用配置不同的 `shell` |

## 实例演练

从零把上面的 HMR 组合跑通，并在最后一步制造一次 PENDING。

**第一步：装组合。** `cordis.yml` 写四个条目：`logger`（控制台日志导出器）、`timer`（定时器服务）、`hmr`（监视 `root: ['.']`）、`hello`（自己的插件）。每条都带显式 `id`。此时两个辅助插件不是可选项：没有 logger，后面的 HMR 日志一行都看不到；没有 timer，HMR 会因为 `inject` 的 `timer` 缺失而**永远停在 PENDING，且不发出任何提示**。

**第二步：跑起来。** `node --import tsx ../../vendor/cordis/bin.js`。要 `tsx`，是因为 HMR 通过 Loader 的原生辅助工具读取 Node 的 loader 内部结构。首屏打印 `hello from my first plugin`，随后 HMR 打印 `hmr watching [ '.' ]`。

**第三步：改代码。** 编辑 `hello.ts` 的日志文本并保存。输出显示 `hmr reload plugin at hello.ts`，然后新的 `hello from my EDITED plugin`。中间发生了什么：旧实例卸载，它的所有 effect 回卷（第 16 章），新代码加载，`apply` 再次运行（第 17 章的依赖驱动加载保证顺序）。没有任何残留的定时器或监听器，否则重载几次就会看到重复输出。

**第四步：改组合。** 编辑 `cordis.yml` 增删某条也会触发更新，但 loader 按 `id` 比较，只处理发生变化的部分。如果给某条去掉 `id`，它就变成「每次读取都是新条目」：任何一次文件编辑——即使那一行没动——都会把它删掉再挂上。

**第五步：制造一次 PENDING。** 写 `needs-timer.ts`，`inject: ['timer']`；再写 `diagnose.ts`，把两者放进一个没有 `timer` 提供方的组合。运行后 `needs-timer` 的 `apply` 永远不会执行，因此它自己一声不响、进程也不报错；500ms 后 `diagnose` 遍历 `ctx.registry`，筛出 `FiberState.PENDING`，打印 `needs-timer is PENDING — a required service is missing`。往组合里加上 `- name: '@deepseek-ai/cordis-plugin-timer'`，插件立刻加载并打印 `needs-timer loaded`。

顺带一个观察：如果不加 PENDING 过滤条件遍历，会看到 loader 自身的插件（`Loader`、`Include`）处于 ACTIVE——因为配置文件本身也是通过插件挂载的。这条细节提醒你：注册表里不只有你写的插件。

## 关键要点

1. `cordis.yml` 是应用定义，改组合就是改产品；条目元数据比 `name` 多。
2. 给条目写 `id`，否则任何编辑都可能把整条视为删除再添加并重挂载。
3. `disabled: true` 可逆地停用插件，并连带恢复依赖它的 PENDING 插件。
4. 组负责成组启停，`isolate` 负责服务隔离（如两个组各自的 `shell` 提供方）。
5. HMR = 卸载（effect 全回卷）+ 加载（依赖驱动），因此不会残留。
6. HMR 需要 logger（否则无日志）与 timer（否则永久 PENDING），并且必须在 tsx 下运行。
7. 插件「毫无反应」先查 fiber 状态：`ctx.registry` + `FiberState.PENDING` 能直接指出缺失的依赖。

## 关联

- **第 16 章**：HMR 能安全替换的前提是 effect 会在卸载时全部撤销，不留残留。
- **第 17 章**：依赖驱动加载决定了替换后重新加载的顺序；`inject` 缺失即 PENDING。
- **第 19 章**：`config` 块的验证、`disabled` 字段与 `!!js` 门控都作用在条目元数据上。
- **第 21 章**：把同一套组合与 HMR 手法用于真实 harness 服务。
- **第 24 章 Fiber API**：`ctx.registry`、`runtime.fibers` 与 `FiberState` 的完整接口面。
