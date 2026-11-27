# 第 38 章：新增工具、包与插件

## 核心思想

新增能力的第一答案不是「加一套机制」，而是在文档化扩展点上挂一个监听器或注册：功能到机制的映射表里没有任何一行修改循环本身。真正的成本不在写实现，而在满足契约——工具的六条 `execute()` 约定、包的清单不变式、README 的固定结尾。本章按「步骤清单 + 检查项 + 常见坑」组织，照着做即可落地。

## 框架与方法

- **`defineTool` 的六条执行约定**：工具契约的真源。
  - 何时用：任何面向模型的工具。
  - 怎么做：①参数已为你校验——`defineTool` 按统一 `ParameterSchemaSpec` 校验模型 `arguments`，但 schema 表达不了的约束（非空字符串、正数、跨字段）仍要自己判并以 `ToolArgsError` 拒绝；②注册借用你的只读定义，注册后不要改 schema 或换回调，热替换只能 dispose 后重新注册；③执行身份受保护——`arguments` 被物化为分离的无损 JSON 并冻结，`exec.token`、`callId`、`agent`、必填 `signal` 全程不可变，只有 around-dispatch 包装器能替换并恢复 `exec.signal`；④只返回一个规范 JSON 值，由 `output.render(args, value)` 负责模型可见内容，工具主体不要返回内容块；⑤抛出异常或返回无效值即 `isError`，每种预期失败抛带稳定 `code` 的 `HarnessError` 子类；⑥遵守 `exec.signal`，让 signal 的 reason 或 `AbortError` 直接传播，不要换成普通 `Error`。

- **前台信号与后台信号**：两套取消生命周期不能混用。
  - 何时用：工具支持 `run_in_background`。
  - 怎么做：`ctx.jobs.start()` 发布 id 之后，用任务自有的取消信号；此后取消外层调用只停止等待本次调用，不终止已发布的工作——该生命周期归 `job_kill`、owner dispose 与服务 teardown。前台工作仍与 `exec.signal` 耦合。预先中止的调用属于失败，因为没有任务、其 id 无法满足成功输出 schema。

- **展示三层分离**：模型可见内容、持久卡片数据、可回放 UI 状态各归其位。
  - 何时用：工具在 UI 里有专用卡片。
  - 怎么做：`output.render` 出模型可见自然语言；`output.presentationMeta(args, value)` 从同一规范值派生可回放 JSON，核心把它持久化在 `tool/result` 上并传给 `presentResult`；`presentCall`／`presentResult` 返回带 `card` 标签的渲染意图。两者都必须是 `args`（加 result）的纯函数——不做 I/O、不读会话状态、不用时钟或随机数，因为它们在实时流式与日志回放时都会运行。

- **扩展点阶梯（pre-execute → guard → execute → post-execute → result）**：选对拦截层。
  - 何时用：要加策略、超时、重试、指标、展示变换或审计。
  - 怎么做：可扩展的允许／拒绝／询问策略用 `tools/pre-execute`（waterfall，返回 `{ kind: 'deny', reason }` 这类类型化决策）；需要单调的最终拒绝用 `ctx.tools.guard()`，后续监听器无法撤销；需要包裹分发生命周期（截止时间／重试／指标）用 `tools/execute`；要替换展示内容或返回值、阻止结果、附加模型可见上下文用 `tools/post-execute`；只观察不可变最终结果用 `tools/result`。

- **PTC 自动触达**：不需要额外集成。
  - 何时用：希望工具在 PTC mode 里可被 `await tools.<name>(args)` 调用。
  - 怎么做：什么都不做——每个可见的已注册工具都自动可调。生成的 `ToolArgsMap`／`ToolOutputMap` 从同一组 schema 派生精确参数与规范返回类型，调用重新进入正常流水线。因此要把 `output.schema` 当实用程序化 API 设计：直接返回句柄与字段，人类解释留给 `output.render`。

- **新增 workspace 包的清单**：逐文件，不是逐感觉。
  - 何时用：要新建 `@deepseek-ai/dsh-<name>`。
  - 怎么做：建 `package.json`／`tsconfig.json`／`src/index.ts`／`locale/{en,zh}.json`／`README.md`；在 `tsconfig.host.json` 或 `tsconfig.client.json` 的 `references` 里加一条（普通包恰好属于一个 aggregate，绝不两个都加）；`client/*` 包改 extends `tsconfig.base.client.json`，并额外声明 `dsh.client`、导出 `./client`、调用共享 tsdown preset。

- **包角色命名（role vocabulary）**：名字必须描述当前稳定职责。
  - 何时用：给新包、新服务或新类取名。
  - 怎么做：接口包用能力名，实现包加机制／协议／环境／厂商限定词；单数 `ctx` key 用于 engine／runtime／policy／controller／resolver／store，复数 key 用于 registry 或拥有多个具名成员的服务。不要用首个实现或可能的未来扩展命名。

- **vendored 包**：上游 Cordis 包按固定版本源码 vendor 到 `vendor/`，而不是加 NPM 依赖。
  - 何时用：需要 `@cordisjs/plugin-http` 这类上游包。
  - 怎么做：复制上游 `src/` 原样；`tsconfig.json` 放宽上游代码所需的严格项并给每个被引用的 vendored 包加 `references`；`package.json` 改写 name 的 scope、保留上游 `exports`／`type`、不设 `private: true`、必须设 `publishConfig.access: public`；传递性依赖也要 vendor 或已存在——vendor 一个包往往意味着 vendor 整条依赖树。

- **插件配图（feature preview）**：一张固定尺寸 SVG，不是图库。
  - 何时用：官方组合包的详细介绍文档需要插图。
  - 怎么做：`width="640" height="300" viewBox="0 0 640 300"`，32:15；中英各一份（同一张图的替代版本）；自包含——不用字体、远程资源、脚本、事件处理器、动画、样式表、`text` 或 `foreignObject`；文字转路径；同时对比浅色与深色主题；存为 `docs/preview.svg` 与 `docs/preview.zh.svg`，与 `DETAIL.md`／`DETAIL.zh.md` 并列。

## 关键概念

- **`ParameterSchemaSpec`**：`defineTool` 的 schema DSL；显式对象节点必须声明 `additionalProperties: true | false`，隐式参数根对象保持开放。
- **`output.schema`**：`ValueSchemaSpec`，根可为对象、数组、标量或 null；注册表把它快照为无损 JSON、校验并冻结后再交给渲染器。
- **渲染意图联合（card union）**：`generic`／`terminal`／`diff`／`read`／`search`／`web` 六种 `card` 标签，工具绝不导入 UI 或传输类型。
- **`ToolArgsError`**：schema 无法表达的约束被违反时的拒绝类型。
- **`tools/execute`**：包裹核心分发的扩展点，仅 `exec.signal` 可替换。
- **`dsh.client`**：包清单里声明浏览器插件身份的字段，需 `platform: 'web'` 与 `exports["./client"]`。
- **`meta.detail`**：组合包详细介绍文档的相对路径（如 `docs/DETAIL.md`），无包字段回退。
- **`NO_MODEL_EXPERIENCE_SECTION`**：与模型无关的通用包在 README 里可用的受审计语句。
- **`check-vendor-manifest.sh`**：pre-commit 钩子，`vendor/*/src` 有暂存改动而 `vendor/README.md` 未一起暂存时失败。

## 心智模型

- 当想加一个新机制时，先在功能→机制映射表里找一行：绝大多数需求已经落在某个文档化扩展点上。
- 把一个工具看成三份产物：模型的 schema 与规范值、UI 的可回放卡片、以及策略层看到的不可变执行身份。
- 把包清单看成一个「不变式集合」——它不是风格偏好，`pnpm run constraints` 会逐条检查。
- 把 vendored 包看成「我们有源码的上游依赖」，而不是「一个奇怪的 workspace 包」：可发布、不 private、有 manifest 记录。

## 反模式

- **在 `presentCall` 里取文件旧内容或工作目录**：展示器必须是纯函数；这些属于持久结果元数据或 UI 适配器。
- **只为 UI 把格式塞进规范值**：围栏 ` ```console ` 块、diff、相对化路径都不应进入规范值或 Native 内容。
- **用文本解析后台任务 id**：`{ kind: 'background', jobId }` 是类型化规范句柄；PTC mode 绝不能从 `started background job bash-1` 这类自然语言里取 id。
- **在工具主体里内建部署策略**：策略应放 `tools/pre-execute`；内建后无法按部署替换。
- **把 client 包同时加进两个 aggregate**：普通包恰好属于一个 `references` 聚合；`api/remotes` 的拆分是仓库专属例外，新包不得仿照。
- **给 `vendor/` 目录加独立 `tsdown.config.ts` 作默认**：只有构建配置真与根默认不同时才需要；否则多一份维护面。
- **省略 README 的 Model Experience 三字段**：验证器强制要求有序 H4 结构，`None, as ` 与 `Indirectly, through ` 是受审计的固定句式。

## 代码/配置示例

最小工具形态，注意 `output` 与 `execute` 的分工：

```ts
import { readFile } from 'node:fs/promises'
import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'my-tool'
export const inject = ['tools']

export function apply(ctx: Context) {
  ctx.tools.register(defineTool({
    name: 'read_file',
    description: 'Read a file from disk.',
    parameters: {
      path: { type: 'string', required: true, description: 'Absolute path' },
      limit: { type: 'number' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args, exec) {
      return readFile(args.path, { encoding: 'utf8', signal: exec.signal })
    },
  }))
}
```

钩子插件（以权限门禁为例），返回类型化决策而不是布尔：

```ts
export function apply(ctx: Context) {
  ctx.on('tools/pre-execute', async (exec, next): Promise<PreToolDecision> => {
    if (!(await isAllowed(exec))) {
      return { kind: 'deny', reason: 'Denied by policy.' }
    }
    return next()
  })
}
```

包 README 的规范结尾是一段固定层级序列，顺序不可换：

```text
H2  Model Experience
  H3  每个模型上下文条目一个（direct / conditional / capped / lifecycle …）
        H4  Request context and condition
        H4  What the model sees      ← 稳定系统提示词用 H5 + markdown 围栏原样给出
        H4  Token effect             ← fixed / conditional / retained / replaced / capped / zero-direct
        H4  KV Cache effect          ← append-only / prefix-stable / replacing / independent
H2  Known Limitations and Deferred Work
      - **Consumer-visible gap** — 缺失的操作或情形、后果、以及维护者约束
```

没有上下文效果、或只有消费方拥有路径的包，改用 `SENTENCE_MODEL_EXPERIENCE` 中受审计的 `None, as `／`Indirectly, through ` 语句，随后仍必须给出非空的 `KV Cache effect` 正文；与模型无关的通用包可改用 `NO_MODEL_EXPERIENCE_SECTION`。

## 参考表

工具提交前检查清单：

| # | 检查项 | 失败后果 |
|---|---|---|
| 1 | schema 表达不了的约束已在 `execute` 内判并以 `ToolArgsError` 拒绝 | 非法输入进入业务逻辑 |
| 2 | 显式对象节点声明了 `additionalProperties` | 静默接受多余字段 |
| 3 | 注册后未再改 schema 或换回调 | 热替换语义崩溃 |
| 4 | 把 `args` 当只读，只有 around-dispatch 改 `signal` | 冻结失效、身份被改 |
| 5 | 返回一个规范 JSON 值，不带内容块 | 渲染器拿到异物 |
| 6 | 预期失败抛 `HarnessError` 子类并带稳定 `code` | 丢失 `error.code`，只剩 message |
| 7 | 遵守 `exec.signal`，不把中止换成普通 `Error` | 记录成错误而非 `TOOL_ABORTED` |
| 8 | 展示方法为纯函数、对坏输入返回 `undefined` 而非抛错 | 回放崩溃 |
| 9 | 后台化后用任务自有取消信号 | 取消外层调用误杀已发布工作 |
| 10 | 已按测试策略补组装覆盖 | 交付不可验证 |

新增 workspace 包清单：

| 文件 | 必须包含 |
|---|---|
| `package.json` | `private: true`；`version` 与根一致；`type: module`；`main: lib/index.js`；`types: lib/types/index.d.ts`；`exports["."]` 的 `types`／`default`；`@deepseek-ai/cordis` 同时在 peer 与 dev（同范围）；每个 dsh 对等依赖在 dev 中镜像；`@deepseek-ai/schemastery` 在 `dependencies`；`files` 精确列出产物与 `src` |
| `tsconfig.json` | extends `../../../tsconfig.base.json`；`rootDir: src`；`outDir: lib/types`；每个被引用包一条 `references` |
| `src/index.ts` | 服务默认导出，或插件（`name`／`inject`／`apply`／`Config`） |
| `locale/en.json`、`locale/zh.json` | `meta.title`、`meta.description`，可选 `meta.detail`；字段可选但填了必须是非空字符串 |
| `README.md` | 服务 API、事件、扩展点、设计说明；结尾的 Model Experience 与 Known Limitations |
| 根配置 | `tsconfig.host.json` 或 `tsconfig.client.json` 的 `references` 恰好一处 |

vendored 包与 workspace 包的差异：

| 项 | workspace 包 | vendored 包 |
|---|---|---|
| `private` | `true` | 不得为 `true` |
| 发布 | 私有 | `publishConfig.access: public` |
| `src` 来源 | 自写 | 上游 verbatim |
| 相对导入 | 显式 `.ts` 后缀 | 同，但这是仓库与上游的差异 |
| `paths` 映射 | 通配符按分组 | 每个包一条 `"<npm-name>": ["./vendor/<dir>/src"]` |
| `references` 位置 | `packages/*` | `vendor/*`，置于 `packages/*` 条目之前 |
| 额外登记 | — | `vendor/README.md` 一行 manifest + 本地修改说明 |
| `publint-all.ts` | 自动覆盖 | 仅当该包本身从此仓库发布时才需要 |

## 实例演练

从零加一个「把命令跑在后台并把输出喂给模型」的工具，按章序走一遍。

先写 `defineTool`：`parameters` 里声明 `command: { type: 'string', required: true }`，`output.schema` 设计成一个可程序化消费的句柄联合——前台分支给 `{ kind: 'foreground', output, exitCode }`，后台分支给 `{ kind: 'background', jobId }`；`output.render` 负责把前者渲染成人读文本，后者渲染成 `started background job bash-1`。

再补展示：`presentCall` 返回 `{ card: 'terminal', title: command }`，因此 pending 卡片直接是终端；`presentResult` 返回 `{ card: 'terminal', output }`。注意这里不能顺手把 `exec.cwd` 传进去——展示器不读会话状态，`cwd` 属于 owner props 或持久元数据。

然后接后台：走 `run_in_background` 分支时调 `ctx.jobs.start({ kind: 'bash', label: command, owner: exec.agent, output: [{ read: fromByte => shell.readFrom(fromByte) }], run })`。`readFrom` 家族正好符合 `JobOutputSource` 的形状；注册表自己按 `pumpPollMs` 泵，结算前再排干一次，因此 `done` 里不需要折进任何输出。

接着处理失败：命令不存在属于预期失败，抛带稳定 `code` 的 `HarnessError` 子类，而不是返回 `{ kind: 'foreground', output: 'command not found' }`。但进程以非零状态退出是**成功的领域结果**，写进规范值，由 Native 渲染器解释。

最后过检查清单：`additionalProperties` 声明了没有？后台化后用的是不是任务自有取消信号？`exec.signal` 中止时有没有让 `AbortError` 直接传播？展示方法对旧版日志里的畸形参数是否返回 `undefined`？十项全过再提交。

常见坑集中在两处：一是把 `exec.signal` 继续用于后台任务，导致外层调用一取消就把已发布的工作杀掉；二是把 UI 需要的格式化结果塞进规范值，结果 PTC mode 与 `presentResult` 都拿到带装饰的字符串。

## 关键要点

1. 先查功能→机制映射表；能挂监听器就不要造机制。
2. 工具的正确性主要取决于契约遵守，而不是实现技巧——按十条清单逐项过。
3. 前台与后台是两套取消生命周期，`ctx.jobs.start()` 之后切到任务自有信号。
4. 模型内容、卡片数据、UI 状态三层分离；展示器必须纯、必须对坏输入软失败。
5. 策略放 `tools/pre-execute`，单调最终拒绝放 `ctx.tools.guard()`，包裹分发放 `tools/execute`，观察放 `tools/result`。
6. 新包的 `references` 只能落在一个 aggregate；client 包还要 `dsh.client` + `./client` 导出 + 共享 tsdown preset。
7. vendored 包是可发布的 release member：不 private、`publishConfig.access: public`、manifest 与源码同 commit 暂存。
8. 验证是一条固定命令链：`pnpm install` → `doc-sync` → `constraints`/`typecheck`/`lint` → `build`/`hygiene`。

## 关联

- **第 4 章**：工具执行流水线——本章的扩展点阶梯就是那条流水线的拦截层。
- **第 30 章**：工具、审批与调度——`pre-execute` 的 `ask` 决策与审批 seam 对接。
- **第 33 章**：存储、设置与凭据——工具的 `Config` 与即时字段遵循同一套 schema 约定。
- **第 36 章**：Web 客户端——`tool.call.toolview` keyed slot 是工具在 Web 里获得专用卡片的路径。
- **第 39 章**：远程 API、格式与适配器——`@Remote`、配置表单与系统消息是同一「按清单交付」的写法。
