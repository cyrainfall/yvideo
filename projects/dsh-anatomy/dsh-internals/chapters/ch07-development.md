# 第 7 章：开发工作流

## 核心思想
这个仓库的类型检查不是「一个 tsconfig 跑到底」，而是两个互不相见的 aggregate（Host 与 Client）各自构成一张 Project Reference 图，再叠一层门禁调度器。因此开发工作流的核心判据只有一条：按改动表面选择能达到该表面的最小命令集——选多了是浪费，选少了会在 CI 才暴露。

## 框架与方法

- **双聚合（Host / Client aggregate）**：`tsconfig.host.json` 收 Host 包、示例、测试、脚本和 website，外加 `api/remotes` 的 Host 特例 project；`tsconfig.client.json` 收 `packages/client/*` 及其测试、`apps/web`，外加 `api/remotes` 的 Client 特例 project。
  - 何时用：新增包、判断一个改动该在哪一侧验证。
  - 怎么做：普通包只登记进其中一个 aggregate。`host/webserver`、`compaction/compaction`、`typert/registry` 三个包被两侧同时引用，作为共享 leaf，让两边对同一份源码做类型检查。拆分的理由是硬的：两侧在相同键下以不同服务对 cordis `Context` 接口做声明合并，单一 program 同时看到两份合并就会报冲突。

- **solution 根与 paths 门面**：`tsconfig.json` 是 solution 根，`extends` base、`files: []`、引用两个 aggregate，它不是 program；`tsconfig.base.json` 只放共享 `compilerOptions` 与源码 `paths`，也没有 `include`，因此它的 `paths` 对任何 importer 都生效。
  - 何时用：想让某段代码在整仓可解析，或在写构造全仓 program 的脚本。
  - 怎么做：三条纪律——base 永不加 `include`/`files`（会泄漏进每个 extends 它的包项目并收窄门面的全匹配范围）；构造全仓 `ts.Program` 的脚本必须以 `tsconfig.host.json` 或 `tsconfig.client.json` 为种子，根 solution 永不作为种子；新包只登记进一个 aggregate。

- **拆分 compiler face（split compiler face）**：一个包同时有 Node 入口和 browser 入口并不构成拆分理由——普通 Client 插件的两份运行时产物都在 Client 构建阶段生成。真正拆分的只有七个：`api/remotes`、`api/gateway`、`api/session-controller`、`api/workspace-controller`、`client/connection`、`session-query/session-log-export`、`experimental/liveshare-protocol`。
  - 何时用：怀疑某个包需要两侧各一份类型环境。
  - 怎么做：看它的根 `tsconfig.json` 是否只作 solution、并带 `tsconfig.host.json` 与 `tsconfig.client.json` 两个 leaf。workspace `constraints` 门禁遍历可达的 Project Reference 图，按各引用 project 自身的 compiler face 检查：单一配置的目标可由任一 face 引用，拆分配置的目标必须引用匹配的 leaf，不得引用 solution 根或另一侧 leaf。该门禁按「两个 leaf 配置同时存在」自动发现拆分包。

- **产物步骤顺序（build:artifacts pipeline）**：`build:artifacts` 只检查并编译各 compiler face 的包 reference，Client 编译必须等待 Host 和 Desktop 的 bundle 完成，因为拆分 compiler face 会重写这些 bundle 步骤读取的共享 `lib/types` 文件。
  - 何时用：需要可运行的产物、要跑 `dev:web` / `dev:desktop`、要继续做基于产物的检查。
  - 怎么做：顺序是固定的——`build:native-system` → `tsx scripts/generate-typert.ts` → Host 的 `tsc -b` → Host 的 `tsdown` → desktop bundle → Client 的 `tsc -b` → Client 的 `tsdown` → `build:web`。

- **三条构建命令的分工**：
  - 何时用：决定「我现在该跑哪一条」。
  - 怎么做：`build:check` 只并发跑两个 `tsc -p`，project mode 依据磁盘上已有的包声明检查仓库级测试与脚本 program，从不编译 reference，也不检测/重建缺失或过期的产物——产物缺失时表现为编译器错误。`build` 把两组步骤作为一张依赖图运行，每个 aggregate 检查在本 face 包编译完成后立即开始并与其余产物步骤重叠。`typecheck` 生成元数据、按 reference 顺序编译两侧包、再以 `tsc -b` 检查，跳过 native addon、bundle、Web 和 client build record。

- **门禁调度（run-gates）**：`DSH_GATE_CONCURRENCY` 限制并发步骤数（`1` 按依赖顺序执行），`DSH_GATE_FAIL_FAST=1` 在第一个失败时停止，否则失败只跳过其依赖方，因此会一次报出所有相互独立的错误。失败步骤打印自身输出，任一失败都以非零状态退出且不写 client build record。

- **本地 worker 预算**：在 CI 之外，门禁调度器、`build`、`typecheck`、Oxlint、publint 默认 12 个 worker，Vitest fork 与本地覆盖率 48 个；`doc-sync`、`test:docs`、`hygiene`、`check:all` 最多同时 8 个门禁。
  - 何时用：共享主机上出现莫名其妙的超时。
  - 怎么做：用 `DSH_GATE_CONCURRENCY`、`DSH_OXLINT_THREADS`、`DSH_COVERAGE_MAX_WORKERS` 或 Vitest 的 `--maxWorkers` 覆盖。理由是 `os.availableParallelism()` 报的是宿主 CPU 数而不是容器配额，不设上限会在共享主机上超额订阅；CI 仍用 runner 的 CPU 数。

- **Typert 生成（Typert）**：通过 `tsconfig.host.json` 分析 Host 类型，在包编译之前生成 Host 反射和 Host-for-Client Remote 声明。
  - 何时用：业务服务要在 Client 侧被调用。
  - 怎么做：Host 侧用 `@Remote` 或 `@RemoteScope` 声明可调用方法；Host 构建生成类型与运行时贡献，Client 的 `api-remotes` 组合加载这些贡献并挂到 `ctx.remote` 与作用域 `agentCtx.remote` namespace。仅源码的 `generate-typert.ts` 阶段拒绝依赖构建产物的工作区导入。

- **Lefthook 快速检查点（lefthook）**：`pre-commit` 校验暂存配对记录、用不加载项目的 `.oxlintrc.staged.json` 验证暂存文件、有界重试应用 Oxlint 修复、检查空白错误、校验 pi-ai 元数据、跑 vendor manifest 守卫；`pre-merge-commit` 在 Git 创建自动合并提交前执行同样的以索引为准的配对检查；`pre-push` 运行 `pnpm run typecheck`。
  - 何时用：理解「为什么提交被拒」。
  - 怎么做：这些钩子有意不跑测试、快照、文档检查、构建或 `hygiene`——全量覆盖率、产物冒烟和 Node 版本矩阵由 CI 负责。

- **TODO 标记三级**：`FIXME` 是应阻塞发布的问题（未经评审者明确同意不应进入发布版本）；`TODO` 是应尽快修复、资源到位即可处理；`XXX` 是也许某天会修、不作承诺。
  - 何时用：留下已知问题。
  - 怎么做：按紧急程度选标签，让读代码的人一眼分清「发布阻塞」和「有空再说」。

- **`ts type-equiv` 逐字类型门禁**：子系统页面要粘贴与源码等价的声明及其原始 JSDoc，为避免漂移，围栏标成 ` ```ts type-equiv ` 并在 `scripts/type-equiv.manifest.json` 登记镜像的源文件与符号。`pnpm run verify-type-equiv` 通过 TypeScript 解析器提取该符号声明与附带 JSDoc，断言代码块同时匹配两者。隐藏实现体用 ` ```ts public-api ` 配 `"projection": "public-api"`，保留公共字段、构造函数、访问器、方法及原始 JSDoc，省略实现体和私有/受保护成员。

## 关键概念
- **aggregate**：一张独立可检查的 Project Reference 图，本仓库有 Host 与 Client 两张。
- **solution 根**：只 `extends` base、`files: []`、引用两个 aggregate 的 `tsconfig.json`，是 tsserver 发现入口，不是 program。
- **compiler face**：一个包在某一侧的类型环境；拆分包有两个 face。
- **共享 leaf**：同时被两个 aggregate 引用的包，因两侧需检查同一份源码而存在。
- **paths 门面**：`tsconfig.base.json` 的 `paths` 映射，因无 `include` 而对任何 importer 生效。
- **产物树（artifacts tree）**：`build:artifacts` 产出的 `lib/` 与 `lib/types`，是所有产物消费门禁的前提。
- **client build record**：每次 `build` 或 `build:artifacts` 成功后写入的 gitignore 记录，把精确公开值与 Vite 输出及动态 client bundle 绑定。
- **dirty 标记**：Git 报告本地变化时内联进构建的标记；`build:official` 省略它。
- **门禁（gate）**：`run-gates` 依赖图里的一个可并行步骤。
- **worktree 本地钩子**：由 `scripts/install-lefthook.mjs` 配置的 per-worktree Lefthook 钩子。

## 心智模型
- 当你不确定跑什么检查时，从「改动表面」反推：文档改动只要 `doc-sync`，包源码改动要 `build:artifacts`，声明 TypeScript 工作完成要 `build:check` 或 `build`。
- 把 `tsconfig.json` 看成 solution 而不是 program——它引用两张图，自己不含任何文件。
- 把 `build:check` 看成「读磁盘上已有的声明做检查」，它不生产声明，所以产物过期时它会以编译器错误的形式报警。
- 把 `hygiene` 的 `publint` / `verify-node-next-types` 看成产物消费者：新 worktree 在 `build` 之前跑它们，只会得到「文件不存在」。

## 反模式
- **给 `tsconfig.base.json` 加 `include` 或 `files`**：会泄漏进每个 extends 它的包项目，并收窄门面的全匹配范围。
- **构造全仓 `ts.Program` 时以根 solution 为种子**：两个 aggregate 被展平，撞上 `Context` 声明合并冲突。
- **在新 worktree 上直接跑 `hygiene` 或依赖 `lib/*.js` 的检查**：`build` 之前没有打包的 JS 与声明文件，失败原因与代码无关。
- **改了包源码后只跑 `build:check`**：它不重建产物，检查的是磁盘上的旧声明。
- **手改 vendor 代码而不更新 manifest**：vendor manifest 守卫会拒提交，`vendor/*/src` 的改动必须连同 `vendor/README.md` manifest 更新一起暂存。
- **在共享主机上依赖默认 worker 数**：`os.availableParallelism()` 是宿主 CPU 数而非容器配额。
- **把 `check:all` 当成对 agent 的指令**：它只是给贡献者的可选全面门禁集，独立于 Git 钩子。
- **移动检出目录后不重跑钩子安装脚本**：Lefthook 包装脚本会报陈旧锁或拒绝现有 Git 配置，此时应读它的诊断而不是猜着改 worktree 元数据。

## 代码/配置示例

前置条件与首次搭建：

```sh
node --version   # 需 24.9+
corepack enable  # pnpm 固定 pnpm@11.28.5
pnpm install     # 同时经 scripts/install-lefthook.mjs 配置 worktree 本地钩子
pnpm run typecheck   # 成功退出即表示搭建完成
```

钩子缺失时（缓存恢复或 `postinstall` 被跳过）：

```sh
node scripts/install-lefthook.mjs
```

凭证（仓库根目录被 gitignore 的 `.env`）：

```sh
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://... # optional
```

`type-equiv` 清单条目：

```json
{ "doc": "docs/subsystems/session.md", "symbol": "SessionEvent", "source": "packages/core/session/src/types.ts" }
```

## 参考表

tsconfig 文件职责（原文表）：

| 文件 | 角色 | 是否构成 program？ |
|---|---|---|
| `tsconfig.json` | solution 根：`extends` base、`files: []`、引用两个 aggregate；tsserver 发现入口，也是显式执行整张 Project Reference 图的入口；经继承的 `paths` 充当 tsx 运行 `scripts/` 时的解析配置 | 否 |
| `tsconfig.host.json` | Host aggregate：Host 包、示例、测试、脚本与 website，以及 `api/remotes` 的 Host 特例 project | 是 |
| `tsconfig.client.json` | Client aggregate：`packages/client/*` 及测试、`apps/web`，以及 `api/remotes` 的 Client 特例 project | 是 |
| `tsconfig.base.json` | 共享 `compilerOptions` 与源码 `paths`；同时是各 vitest 配置让 vite-tsconfig-paths 指向的解析门面 | 否 |
| `tsconfig.base.client.json` | 浏览器编译设置（`jsx`、DOM lib、`types: []`），由 Client aggregate 与每个 `packages/client/*` 包 extends | 否 |

按改动选命令（原文表）：

| 场景 | 命令 |
|---|---|
| 迭代包源码并需要可运行产物 | `pnpm run build:artifacts`（`dev:web` / `dev:desktop` 启动前会先执行） |
| 检查测试、脚本、benchmarks 或 website 代码的类型 | 最近一次 `build:artifacts` 之后运行 `pnpm run build:check`；包源码有改动先重跑 `build:artifacts` |
| 声明 TypeScript 工作完成之前 | 最近一次 `build:artifacts` 之后 `build:check`，或直接 `build` |
| 完整验证（与 CI 必需构建 lane 相同） | `pnpm run build` |
| 只做类型检查、不需要 Web 与 Desktop 产物 | `pnpm run typecheck` |
| lint 或文档代码块检查 | `pnpm run lint` 或 `pnpm run doc-typecheck`（各自先准备 `host-contracts`） |

Web 与 Desktop 共用的应用命令（原文表）：

| 命令 | 作用 |
|---|---|
| `pnpm run start:web` | 用源码启动器服务已构建的 Web 产物（与 `pnpm dsh web` 同一启动） |
| `pnpm run dev:web` | 构建、服务，并在源码修改时持续重建 Web client bundle |
| `pnpm run start:desktop` | 启动已构建的 Desktop 产物 |
| `pnpm run dev:desktop` | 先构建，再启动 Desktop |

Web 命令后面的参数会传给 `dsh web`，例如 `pnpm run dev:web --no-open --port 3081`；`dev:web` 另接受 `--skip-build`（复用现有产物树）与 `--no-serve`（只跑重建 watcher，配合别处启动的服务器）。两个 Web 命令使用正常的 Harness home，Desktop 命令使用隔离的开发 home。根目录 `Makefile` 以 `make web`、`make dev-web`、`make desktop`、`make dev-desktop`、`make build` 命名同一套命令，`ARGS='--no-open'` 转发参数。

## 实例演练

一位新贡献者从零到「搭建完成」。

第一步是查版本。Node 必须 24.9+；CI 覆盖 24.9、最新的 24 和 26。TypeScript 类型剥离必须启用——构建脚本用 tsdown 的 native 配置加载器加载 `tsdown.config.ts`，所以 `NODE_OPTIONS` 里出现 `--no-experimental-strip-types`、或 Node 构建缺少 TypeScript 支持，都会失败；好在 `pnpm run build` 会先检查这一条件并指出原因。pnpm 必须经 Corepack 解析到 `pnpm@11.28.5`，Git 需 2.26+。

第二步 `pnpm install`。pnpm 使用严格符号链接布局，未声明的依赖直接失败而不是被提升；依赖的构建脚本必须明确列入 `pnpm-workspace.yaml` 的允许列表。安装过程顺带用 `scripts/install-lefthook.mjs` 配置 worktree 本地钩子。DevTools 前端由固定版本的 npm 源码包加 Vite 在本地编译，装完依赖后构建不需要网络或安装浏览器——workspace 与发布包的安装都不运行 DevTools 资源下载 hook。若依赖从缓存恢复导致钩子缺失，手动跑一次那个脚本。

第三步 `pnpm run typecheck`。它生成 Typert 元数据、按 reference 顺序编译两侧包、再对每个 aggregate 做 `tsc -b` 检查，跳过 native addon、bundle、Web 和 client build record。成功退出就是搭建完成的判据。此刻 `hygiene` 还不能跑：新 worktree 没有打包的 JS 和声明文件，`publint` 与 `verify-node-next-types` 都在等 `lib/`。

第四步开始干活。假设改的是 `packages/client/*` 下一个插件的源码并要跑起来看：执行 `pnpm run build:artifacts`，等 Host 编译、Host bundle、desktop bundle、Client 编译、Client bundle、Web 构建依次完成；然后 `pnpm run dev:web`——它会先再跑一次 `build:artifacts`，读取一次当前版本与 Git 状态，并在本次会话所有 watcher stage 之间共享该环境（它不校验完整构建记录，因为 watcher stage 会重写记录覆盖的产物）。

第五步提交。`pre-commit` 做的是快检查：配对记录、暂存文件的 Oxlint、空白错误、pi-ai 元数据、vendor manifest 守卫——都不跑测试和构建。`pre-push` 跑 `pnpm run typecheck`。如果这次改动碰到某个非平凡的模型可见、协议可见或人类可见行为，测试的补齐要求见第 8 章，钩子不会替你兜住。

## 关键要点
1. 先确定改动落在哪个 aggregate，再决定命令；跨两侧的只有共享 leaf 与七个拆分包。
2. `tsconfig.json` 是 solution 不是 program；base 永不加 `include`/`files`。
3. `build:check` 不生产声明，必须在最近一次 `build:artifacts` 之后跑；`build` 才是与 CI 等价的完整验证。
4. 产物消费门禁（`hygiene`、publint、NodeNext 声明校验）以 `build` 为前提，新 worktree 上不成立。
5. worker 默认值按宿主 CPU 给，共享主机上必须用 `DSH_GATE_CONCURRENCY` 等变量压低。
6. 提交钩子是快速检查点，不全量；CI 负责覆盖率、产物冒烟与 Node 24.9/24/26 矩阵。
7. `FIXME` / `TODO` / `XXX` 三级标签按紧急程度选，不要让发布阻塞项混进 `XXX`。

## 关联
- **第 8 章 测试体系**：钩子不跑测试，补测责任在贡献者；测试的解析路径直接依赖本章的 `paths` 门面。
- **第 5 章 API 网关**：本章的 Typert 生成（`@Remote` / `@RemoteScope` → `ctx.remote`）是网关两侧产物的来源。
- **第 9 章 CLI 与命令面**：`dev:web` 的参数会转发给 `dsh web`，本章的应用命令是 CLI 命令面的开发期封装。
- **第 12 章 文档规范**：`verify-type-equiv` 与双语配对记录属于文档侧门禁，与本章同属 `doc-sync`。
- **TypeScript Project References**：两个 aggregate 就是一个 Project Reference 图被切成两张，用来隔离声明合并冲突。
- **内容寻址式构建记录**：client build record 把公开值与 Vite 输出绑定，思路等价于构建清单（build manifest）。
