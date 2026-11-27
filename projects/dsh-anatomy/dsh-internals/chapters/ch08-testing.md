# 第 8 章：测试体系

## 核心思想
测试分七层，每层回答一个不同的问题，任何一层都不能代替另一层。三条判断压过一切：行覆盖率是必要条件但永远不是充分条件；断言必须验证外部世界而不是 agent 的自我报告；测试必须打在真实入口路径上，即构建后由普通 `node` 执行的产物。此外这里有一条明确立场——推理很便宜，不要吝惜真实 API 测试。

## 框架与方法

- **七层测试（testing layers）**：每层的命令、覆盖对象与判据都不同，按「你要证明什么」选层，而不是按「哪层跑得快」选层。
  - 何时用：每次要新增断言之前。
  - 怎么做：单元测试证明局部行为与清理；覆盖率门禁证明没有未被执行的行；真实 API e2e 证明 agent 能对接真实模型；所属位置的预期输出证明组装后的 CLI/进程行为；性能基准证明耗时、堆与缩放预算；快照证明组装后的 transcript；Web 浏览器快照证明渲染与 ARIA 输出。

- **优先真实实现而非 mock**：只 mock 开销高或不确定的边界——LLM 适配器、网络、时钟；下游一切保持真实。
  - 何时用：想给某个桥接层写替身时。
  - 怎么做：手写替身只能证明桥接层在搬运字节，不能证明交付的工具行为符合断言。范例是桥接工具调用测试：`makeBridgeHarness()`（`packages/acp/acp/tests/harness.ts`）挂载 agent loop、会话存储、工具注册表与 JSONL 持久化，唯一 mock 是脚本化 `MockAdapter`——真实的工具注册表与执行管线留在 mock 模型的下游。

- **验证外部世界，而非自我报告**：e2e 断言应重新运行命令或从外部重新读取文件；对 agent 自身输出做关键词探测会让作弊的 agent 通过。断言未修改的文件逐字节一致。
  - 何时用：写任何涉及文件系统或命令副作用的断言。
  - 怎么做：先想「如果 agent 撒谎，这条断言还会绿吗」。会绿就重写。

- **测试真实入口路径（real entry path）**：《真实入口路径》指的是已发布的产物：包的 `bin` 所运行的是构建后的 `lib/bin.js`，并由普通 `node` 执行，从而暴露 tsx 会掩盖的失败——结算竞态、模块解析、被吞掉的加载失败。
  - 何时用：新插件、新 CLI 入口、新 bundle。
  - 怎么做：产品可见的插件必须有一个非单元的真实组合测试。手动构造的 `ctx.plugin(...)` 套件不够：要通过 Loader 和 app/process 启动仅用于测试的 `cordis.yml`，只 mock 外部服务或非确定性输入，断言模型可见的请求/日志、持久状态或用户可见输出，不要把 opt-in 选项混进交付默认值。规则同样适用于非 index 运行时入口（Node 程序 bootstrap `lib/process.js`）与多 bundle 共享的单例模块（`packages/sdk/server/tests/built-scope-carrier.e2e.ts`）。

- **守卫必须被证明有效**：一个守卫只有在回归能让它失败时才有效。
  - 何时用：新增任何守卫断言。
  - 怎么做：引入回归、观察变红、回退。反例很具体：对于没有 `inject` 的插件（bundle/组合插件），Loader 冒烟测试在默认导出替换必需具名导出时仍然绿着——需要补 `expect('default' in mod).toBe(false)` 加 `unwrapExports` 往返断言。

- **仅限源码的解析（source-only resolution）**：每个 vitest 配置都把 vite-tsconfig-paths 指向 `tsconfig.base.json`；工作区包的裸导入解析到 `src`，绝不经由包的 `exports` 解析到构建后的 `lib/`，因为其中的陈旧产物会加载第二份模块单例。
  - 何时用：判断某条测试该用 `src` 还是 `lib`。
  - 怎么做：构建产物只在显式指定时使用——以 `lib` 模式运行的子进程，以及构建产物冒烟测试。只有测试对象本身是源码路径解析时才可以选 `src`，且必须在测试里写明这一约定。

- **子进程启动模式（双模式启动器）**：CI 与已有构建产物的测试通道通过共享双模式启动器，从构建后的 `lib/` 运行每个 profile 或 Cordis 配置子进程。
  - 何时用：测试要拉起子进程。
  - 怎么做：不要手写 `--import tsx`。不加载 Cordis 的协议与操作系统 fixture 直接通过 Node 运行使用可擦除语法的 `.ts` 文件，不经过 tsx 或根路径映射。

- **何时需要快照测试**：每项非平凡的模型可见、协议可见或人类可见变更，都在同一 PR 中添加或更新无密钥录制会话场景；包级、e2e、仅 mock 和 PR 理由证据都不能取代组装后的 transcript。
  - 何时用：改动触及模型输入输出、协议报文或渲染结果。
  - 怎么做：四类录制各归其位——Headless 在 `snapshots/session/`、SDK 在 `snapshots/sdk/`、ACP 在 `snapshots/acp/`、Web 在 `snapshots/web/`。不由录制会话驱动的预期输出留在所属应用、包或脚本的 `tests/expected/` 下，且不使用 `*.snapshot.ts` 后缀。Agent loop、会话生命周期与 `SessionEventMap` 变更要同时更新两个 SDK 投影：`snapshots/sdk/` 拥有 TypeScript，Python 运行时 CI 拥有 `scripts/snapshots/python-sdk-single-exe/`。

- **资源责任到 teardown**：fork 出的 worker 并行跑多个 spec 文件，coverage gate 拆成并发 partition 与同一 job 内其它 gate 并排跑，自托管 runner 共用同一台宿主机和同一个卷。被隔离的只有进程：端口、可预测路径、外部命名空间和继承而来的子进程都不隔离。
  - 何时用：测试用到端口、临时路径、全局状态。
  - 怎么做：为每个占用的资源负责到 teardown。只在单独运行时通过的 spec 存在测试缺陷，而非 runner 不稳定。

- **HMR 安全测试（HMR-safe test）**：每个注册表都有一个，对向该注册表贡献内容的 fiber 执行 dispose，并断言清理完成。
  - 何时用：新增或修改任何注册表。
  - 怎么做：照既有模式补一个，清理不完就是泄漏。

## 关键概念
- **覆盖率分区（coverage partition）**：把覆盖率门禁拆成并发片段，复用按平台和运行器池隔离的文件耗时来均衡工作量。
- **契约回归测试**：为约定回归永久保留的测试，如 `packages/core/agent-loop/tests/contract-regressions.spec.ts`。
- **parent / child generation**：快照 session 文件名 `session[.vN].jsonl` 与 `session.<ordinal>[.vN].jsonl`，v0 省略 `.v0`，正版本必须小写 `.vN`，且每个文件名必须与其 header 一致。
- **`snapshot.yml`**：声明 profile、组合与请求头类别、录制策略、例外回放或输入元数据以及 workspace 事实。
- **`DSH_SNAPSHOT=replay`**：CI 强制的只读回放模式；record/refresh 留在本地。
- **`makeBridgeHarness()`**：挂载 agent loop、会话存储、工具注册表与 JSONL 持久化的桥接测试 harness。
- **`unwrapExports`**：Loader 冒烟测试里用于证明默认导出未替换具名导出的往返断言工具。
- **所属位置的预期输出**：无录制会话往返的无密钥组装 CLI/进程预期，驱动为 `*.expected.e2e.ts`，与 `tests/expected/` 同属一处。
- **冒烟测试**：启动已交付的 `dsh` profile、发一条提示词、检查外部世界。

## 心智模型
- 把覆盖率看成「这条行代码被走到过」的证据，不是「功能按交付预期工作」的证据。
- 把 mock 的位置定在系统边界上：边界以内保持真实，边界以外才替身。
- 把「只在单独运行时通过」直接读成测试缺陷的诊断，而不是 CI 的偶发性。
- 把快照当成唯一能代表「组装后」的证据：任何包级断言都到不了那个粒度。

## 反模式
- **对 agent 自身输出做关键词探测**：作弊的 agent 会通过；必须重新运行命令或从外部重读文件。
- **把共享 fixture 放进另一个 `*.e2e.ts`**：导入一个 spec 会重新注册它的 `describe`，导致真实 API 调用重复执行；共享 fixture 应放在普通的 `tests/harness.ts`。
- **手写 `--import tsx` 子进程**：会掩盖结算竞态、模块解析与被吞掉的加载失败；用共享双模式启动器从 `lib/` 跑。
- **看到未覆盖行就去补测试**：100% 门禁标出的未覆盖行往往是死代码，正确处置是删除。
- **让 mock 覆盖掉真实工具注册表**：那就只能证明字节搬运，无法证明交付行为。
- **用 `src` 解析做产物冒烟**：`lib/` 与 `src` 的两份模块单例会同时存在，冒烟结论失效。
- **在 `afterEach` 之外依赖 GC 回收资源**：失败/重试/超时路径都会漏；dispose 必须在 `afterEach` 里。
- **把例外回放写进 `snapshot.yml` 却不评审 diff**：record 与 refresh 的每处差异都必须评审，变更 workspace 的场景还要独立比较完整的 `workspace.expected/` 目录，record 与 refresh 绝不改写该目录。

## 代码/配置示例

快照文件名约定与角色：

```text
session[.vN].jsonl              # parent generation
session.<ordinal>[.vN].jsonl    # child 角色
# v0 省略 .v0；正版本必须小写 .vN；每个文件名必须与其 header 一致
```

守卫有效性证明的三步（引入回归 → 观察变红 → 回退）：

```ts
// 对没有 inject 的插件，默认导出替换具名导出时 Loader 冒烟测试仍会绿
expect('default' in mod).toBe(false)
unwrapExports(mod)  // 往返断言
```

桥接 harness 的唯一 mock 位置：

```text
agent loop ─ 会话存储 ─ 工具注册表 ─ JSONL 持久化   ← 全部真实
                     ↑ 下游
MockAdapter（脚本化模型）                            ← 唯一 mock
```

## 参考表

七层测试（命令 / 覆盖对象 / 判据）：

| 层 | 命令 | 覆盖对象 | 判据要点 |
| --- | --- | --- | --- |
| 单元测试 | `pnpm run test` | 各包与示例的 `tests/**`，以及 `scripts/**/*.spec.ts` | 测试文件与所覆盖代码放在一起；优先覆盖边界、错误路径、事件顺序、并发竞态与契约回归 |
| 覆盖率门禁 | `pnpm run test:coverage` | `packages/*/*/src` 按文件 100% | 行覆盖是必要非充分；`packages/shell/pwsh-local/src` 需真实 `pwsh`，缺它时套件自动跳过并由 `vitest.config.ts` 豁免 |
| 真实 API e2e | `pnpm run test:e2e` | 真实提供方 API（含 DeepSeek 模型与各提供方冒烟） | 各自密钥控制，缺密钥自动跳过 |
| 所属位置的预期输出 | `pnpm run test:expected` | 无密钥组装的 CLI/进程预期 | 驱动为 `*.expected.e2e.ts`，与 `tests/expected/` 同处；CI 对构建产物运行；包/脚本用 `test`，浏览器用 `test:web` |
| 性能基准 | `pnpm run test:bench` | `benchmarks/` 按用户路径组织的门禁 | 先构建 library 与 worker，被计时代码在纯 Node 下运行、不用 TSX；合成输入执行耗时/堆/缩放预算；包内 `.perf.ts` 仅作诊断 |
| 快照 | `pnpm run test:snapshot` | 顶层场景的已录制 parent generation | parent 提供用户输入与模型回放，同时作为持久化结果的预期值 |
| Web 浏览器快照 | `pnpm run test:web` | `snapshots/web/` 全部会话驱动输出 + `apps/web/tests/expected/` 全部纯 UI 输出 | 先构建插件 CSS 再用 Chromium 比较；模型与推理强度选择场景还在 WebKit 跑；CI 强制 `DSH_SNAPSHOT=replay` |

## 实例演练

一个守卫为什么「绿着但无效」，以及如何把它变成有效守卫。

起点是一个 bundle/组合插件——它没有 `inject`。它为 Loader 冒烟测试写的断言本来是想保护「默认导出不能替换必需的具名导出」这个约定。测试跑起来是绿的：Loader 成功装载，插件起来了，行为看起来正常。问题在于这个断言从未真正约束默认导出：当有人把必需具名导出删掉、改用一个 `default` 导出承载同样的东西时，Loader 依然能装载成功，冒烟测试依然是绿的。守卫存在，但它对目标回归免疫。

修法分两步。第一步补上显式断言 `expect('default' in mod).toBe(false)`，再加一次 `unwrapExports` 往返，把「模块对象里不该有 default」和「unwrap 之后仍然拿到同样的东西」两件事都钉住。第二步也是真正的一步：证明守卫有效——引入回归（把具名导出换成 default）、运行、观察它变红、然后回退。不做第二步，就只是换了一条同样可能无效的断言。

这个例子可推广成一条通用工序：任何新守卫都配一次「引入回归 → 变红 → 回退」，否则无法区分「守卫生效」和「这条路径根本走不到」。它也解释了为什么本仓库把「测试真实入口路径」写成硬要求：只有经过 Loader 与 app/process 的真实启动路径，才存在让默认导出替换具名导出这类回归发生的机会；手写的 `ctx.plugin(...)` 套件把这条路径整个绕过去了，守卫再怎么写也碰不到它。

配套的收尾纪律来自资源模型：这个冒烟测试会拉起子进程，而 worker 之间只隔离进程——端口、可预测路径、外部命名空间、继承的子进程都不隔离。因此它必须在 `afterEach` 里 dispose，即使失败、重试或超时也要释放；共享 fixture 要放在普通的 `tests/harness.ts`，绝不放另一个 `*.e2e.ts`，否则一次 import 就会重新注册 `describe`，让真实启动与真实 API 调用重复执行。

## 关键要点
1. 按「要证明什么」选层，七层各有不可替代的证据类型。
2. 覆盖率 100% 是必要非充分；未覆盖行优先按死代码处理。
3. mock 只放在高开销或不确定的边界上：LLM 适配器、网络、时钟。
4. e2e 断言必须能从外部验证：重跑命令、重读文件、逐字节比对未修改文件。
5. 打真实入口路径——构建后的 `lib/bin.js`、普通 `node`、经 Loader 启动的测试用 `cordis.yml`；但测试解析本身只用源码，`lib` 仅在 `lib` 模式子进程与产物冒烟中显式使用。
6. 每个守卫都用「引入回归 → 变红 → 回退」证明一次。
7. 非平凡的模型/协议/人类可见变更，必须在同一 PR 里带无密钥录制场景。

## 关联
- **第 7 章 开发工作流**：测试的 `paths` 解析门面、`build:artifacts` 前提与钩子「不跑测试」的分工都在那一章。
- **第 3 章 Agent 生命周期与会话格式**：快照文件名与 header 的对应关系由会话写入格式决定。
- **第 28 章 会话与对话**：`SessionEventMap` 变更要同时更新 TypeScript 与 Python 两个 SDK 投影。
- **第 39 章 远程 API、格式与适配器**：新增会话格式版本时的快照后继代际规则。
- **测试金字塔 / 测试替身（test double）**：七层结构是测试金字塔在单仓 + 协议 + UI 三类表面上的展开；本章的 mock 纪律等价于「只在边界处用替身」。
- **黄金文件测试（golden file / snapshot testing）**：本章把黄金文件提升为「组装后 transcript」的唯一权威证据。
