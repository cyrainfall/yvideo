# S2E01（EP07）「接缝」· 上屏事实表

> 核对对象：`/Users/cyx/repo/deepseek-harness`，HEAD `d98f5d6851`
> 核对时间：2026-11-26 22:4x +0800（本机）
> 规则：本表每一行的名字、字段、数字、引文都能在仓库里按 `文件:行` 查到；表内路径全部是**仓库相对路径**（相对 header 那个 checkout）。
> 索引声明：`projects/dsh-anatomy/SERIES-S2-PLAN.md` §5、`dsh-internals/ch02-capability-seams.md`、`ch11-glossary.md`、`glossary.md`、`patterns.md` 只当索引读过，结论一律回仓库核对。**未修改** `SERIES-S2-PLAN.md`。
> 工作树状态（上屏时必须知道）：HEAD 之上有 11 项未提交改动，其中 4 项落在认证/连接区（`packages/client/connection/src/rpc.ts`、`src/rpc-host.ts`、`packages/host/authentication-token/src/browser-auth.ts` 及其测试）。`packages/client/connection/src/authentication.ts` **本身干净**，但认证链相关行号以当前工作树为准，那批改动落盘后需重核。原始 grep 收据见 `projects/dsh-anatomy/demo/receipts-s2/E01-facts/`。

---

## 表 A · 上屏断言

| 上屏断言 | 文件:行 | 原文摘录 | 备注 |
|---|---|---|---|
| 定义是**类**不是 TS interface：`ShellExecutor extends Service` | `packages/shell/shell/src/index.ts:64-66` | `export abstract class ShellExecutor extends Service {` / `super(ctx, 'shell')` | 「拥有 `ctx.<key>`」由构造里的 `super(ctx,'shell')` 完成 |
| 定义把 `shell` 挂进 `Context`（类型面） | `packages/shell/shell/src/index.ts:30-32` | `declare module '@deepseek-ai/cordis' {` / `interface Context {` / `shell: ShellExecutor` | 运行时注册 + 编译期声明合并，缺一即「能跑没类型」 |
| 每上下文一个实现，第二个抛错（**包自己的注释**） | `packages/shell/shell/src/index.ts:38-39` | `* implementation per context; loading a second throws, which is cordis'` / `* standard duplicate-service behavior).` | 注释把归因交给 cordis，见「出入」#4 |
| 提供方 1：`dsh-bash-local` 实现抽象类 | `packages/shell/bash-local/src/index.ts:97`（`super(ctx)` 在 `:110`，`export default` 在 `:404`） | `export class LocalBashExecutor extends ShellExecutor {` | 包名 `@deepseek-ai/dsh-bash-local`（`packages/shell/bash-local/package.json:2`）；只注入 `subprocess`（`:98`） |
| 提供方 2：`dsh-bash-sandbox`，注册成 `ctx.shell` 顶替本地执行器 | `packages/shell/bash-sandbox/src/index.ts:45`（doc `:38-44`） | `export class SandboxBashExecutor extends LocalBashExecutor {` / ``Registers as `ctx.shell` in place of the local executor and requires a`` | 包名 `@deepseek-ai/dsh-bash-sandbox`（`package.json:2`）；它**继承 bash-local 的类**，不是直接实现抽象类（见「出入」#1） |
| 提供方 2 多要两个 seam | `packages/shell/bash-sandbox/src/index.ts:46` | `static override inject = ['subprocess', 'sandbox', 'sandboxPolicy']` | 换 provider 连带换依赖面，消费方不用改 |
| 消费方只认 `ctx.shell` | `packages/shell/tool-bash/src/index.ts:251`、`:320` | `const defaultMode = ctx.shell.sandboxMode` / `proc = await ctx.shell.execute({ ...spec, signal })` | 工具层不出现任何执行器类名 |
| 消费方自述是 Consumer | `packages/shell/tool-bash/src/index.ts:2` | ``* Model-facing Consumer of the `ctx.shell` capability seam. While a job`` | 同一句接着讲 `ctx.jobs` 可选、无注册表则「foreground-only」 |
| 消费方把 `shell` 当**硬依赖** | `packages/shell/tool-bash/src/index.ts:36` | `export const inject = ['tools', 'shell', 'systemPrompt', 'shellEnv', 'workingDirectory']` | 缺席语义是 PENDING，不是 unavailable（见「出入」#2） |
| 第二个消费方，同一 seam | `packages/shell/tool-pwsh/src/index.ts:2-5` | ``* Model-facing PowerShell Consumer of the `ctx.shell` capability seam. Intended for`` / `* Windows compositions where a PowerShell executor (e.g.` | 换执行器不必改工具契约 |
| 消费方不依赖提供方（manifest 层） | `packages/shell/tool-bash/package.json:36`、`:49-51`、`:60` | `"@deepseek-ai/dsh-shell": "workspace:*"`（peerDependencies）/ `"dependencies": { "@deepseek-ai/schemastery": "workspace:~" }` / `"@deepseek-ai/dsh-bash-local": "workspace:*"`（devDependencies） | 定义包只作 peer；**两个提供方都不在运行期依赖里**，bash-local 只出现在 devDependencies（测试） |
| 三角色齐全的能力，仓库自己有一张生成表 | `docs/capability-seams.md:801` | `` \| `ctx.shell` \| `seam` \| … \| `bash-local`, `bash-sandbox`, `pwsh-local` \| `tool-bash`, `tool-pwsh`, `hooks-claude-code`, `hooks-codex` \|`` | 生成文件（`scripts/gen-doc-graphs.ts` 产出，表头 `:707`）；实现列是 3 个，不是 2 个 |
| 「可替换能力是少数派」这组数字 | `docs/capability-seams.md:709-829` | 表格 121 行，`core` 64 / `seam` 36 / `service` 20 / `bundle` 1 | 逐行统计所得，与 `ch02` 的 121/64/36/20/1 完全吻合 |
| `unavailable` 是词表里的合法值 | `packages/interaction/user-approval/src/types.ts:32`（doc `:29-31`） | `export type ApprovalOutcome = 'allowed-once' \| 'rejected' \| 'cancelled' \| 'unavailable'` / ``* request, or unavailable answerer. Callers fail closed on `unavailable`.`` | 消费方按闭合联合穷举，不是异常 |
| 没有回答方时**默认**就是 unavailable | `packages/interaction/user-approval/src/index.ts:310` | `() => Promise.resolve<ApprovalOutcome>('unavailable'),` | 这是 waterfall 的兜底返回值；同文件 `:315`、`:318` 把越界返回与抛错也归一成 `'unavailable'` |
| 真实消费路径 1：升级审批缺席 → `SANDBOX_ESCALATION_UNAVAILABLE` | `packages/sandbox/sandbox/src/escalation.ts:256-260`（词表 `:141`） | `case 'unavailable':` / `throw new SandboxEscalationError(` / `` `sandbox escalation to "${mode}" requires approval, but no approval channel is available`, `` | 结构复制词表，`EscalationOutcome` 刻意不 import approval 包（`:137-139` 注释） |
| 真实消费路径 2：job 注册表缺席 → `ToolContextUnavailableError` | `packages/shell/tool-bash/src/index.ts:592`、`:546`；错误类 `packages/core/tools/src/contracts.ts:316`，码 `packages/core/tools/src/error-codes.ts:24` | `let foregroundOnly = ctx.get('jobs') === undefined ? ctx.tools.register(bashTool(undefined)) : undefined` / `throw new ToolContextUnavailableError('background jobs unavailable: load @deepseek-ai/dsh-jobs and @deepseek-ai/dsh-tool-jobs')` | 可选 seam 缺席 → 工具**照样注册**，只有需要它的分支报 unavailable（与 `:592` 的 `ctx.inject(['jobs'])` 成对） |
| 重复加载抛错的**精确出处** | `vendor/cordis/src/reflect.ts:326` | ``throw new Error(`service "${name}" has been registered at <${this.store[key].ctx.fiber.name}>`)`` | cordis `provide()` 的标准占位检查；shell 侧只有一个断言测试（见下行） |
| 该行为有测试钉住 | `packages/shell/shell/tests/service.spec.ts:83-87` | `it('loading a second implementation throws (one bash service per context — cordis standard)', async () => {` / `await expect(ctx.plugin(SecondExecutor)).rejects.toThrow(/service "shell" has been registered/)` | 上屏若要「当场抛错」，跑这条用例即可（或装载两次） |

---

## 表 B · 注册形态五例

| 注册形态 | 真实范例（package） | 文件:行 | 判定形态的理由 |
|---|---|---|---|
| 1 · 命名注册表 | `ctx.llm`（`@deepseek-ai/dsh-llm`）+ 提供方 `@deepseek-ai/dsh-llm-deepseek-api-key` | `packages/llm/llm/src/index.ts:336-337`（`private adapters = new Map<string, AdapterRegistration>()`）、`:383`（`registerAdapter(providers: string[], adapter: LlmAdapter)`）、`:425`；提供方 `packages/llm/llm-deepseek-api-key/src/index.ts:20`（`const PROVIDER = 'deepseek-official'`）、`:92`；实际落库 `packages/llm/llm-deepseek/src/host.ts:83` | 多提供方**并列共存**，各占一个名字；**只有重名**才抛 `DUPLICATE_ADAPTER`（`an adapter for provider "${provider}" is already registered`），异名可无限加 |
| 2 · 单槽 | `ctx.browserUse`（`@deepseek-ai/dsh-browser-use`）+ 提供方 `experimental-browser-use-runtime` 等 | `packages/browser-use/browser-use/src/index.ts:16`、`:35-38`（`:30-31` 注释）；提供方 `packages/experimental/browser-use-runtime/src/mcp.ts:130` | 服务只存**一个** `registration: BrowserUseProviderName`；第二次注册**无条件**抛错，注释写明「A second registration fails even when it repeats the current name」；共享服务本身不提供浏览器操作 API（`docs/capability-seams.md:731`） |
| 3 · 有序尝试 | 认证链 `ctx.connection.authentication`（`@deepseek-ai/dsh-client-connection`）+ 提供方 `host-authentication-token`、`host-authentication-desktop` | `packages/client/connection/src/authentication.ts:7`、`:27`（`register(provider: AuthenticationProvider)`，doc `:23`「Add a credential verifier **after the existing registrations**」）、`:44-54`（遍历 + 首个存活 return）、`:55`；提供方 `packages/host/authentication-token/src/index.ts:35`、`packages/host/authentication-desktop/src/index.ts:26` | 注册**只追加**、顺序即优先级；`authenticate()` 顺序尝试，首个返回非 undefined 且未 aborted 的 Peer 即 `return { peer }`；全不过 → 401，有 provider 抛错 → 503。注意它是 **Host 传输层**的 seam，不是模型侧 seam |
| 4 · 每上下文一实例 | `ctx.shell`（`@deepseek-ai/dsh-shell`） | `packages/shell/shell/src/index.ts:36-39`（doc）、`:64-66`（abstract class + `super(ctx,'shell')`）；行为出处 `vendor/cordis/src/reflect.ts:326`；断言 `packages/shell/shell/tests/service.spec.ts:83-87` | **没有具名注册表**：能力是一个抽象类，一个上下文只容许一个实现占位；第二个实现装载时由 cordis 抛 `service "shell" has been registered at <…>` |
| 5 · 注册即绑定 | `ctx.credentials`（`@deepseek-ai/dsh-credentials`）+ 提供方 `credentials-local`，消费者 `llm-pi-ai` | `packages/credentials/credentials/src/index.ts:205-207`、`:211-214`（「Resolution is per call: consumers re-resolve at each operation and must not cache across operations」）、`:66`（scope 就是「the owning plugin's registered name, such as `llm-pi-ai`」）；绑定点 `packages/llm/llm-pi-ai/src/auth.ts:24-29`（`export const RECORD_SCOPE = 'llm-pi-ai'`）、`:37`（`credentialKey(RECORD_SCOPE, providerId)`）；提供方 `packages/credentials/credentials-local/src/index.ts:531`；按操作解析 `packages/llm/llm-pi-ai/src/index.ts:218-224` | 注册时**只带引用/名字**，值归提供方；插件名即凭据作用域的键前缀，所以「注册」同时完成「绑定」；解析按操作发生 → 轮换后的凭据下一次请求就生效 |
| 附例 · 缺席也是合法状态（支撑表 A 的 `unavailable`，非第六种形态） | `ctx.approval`（`@deepseek-ai/dsh-user-approval`）无回答方 | `packages/interaction/user-approval/src/index.ts:310`（waterfall 兜底）、`:315`、`:318`；`packages/interaction/user-approval/src/types.ts:29-32`；消费方 `packages/sandbox/sandbox/src/escalation.ts:256-260` | 回答方不是一个注册表，而是 `approval/request` waterfall 的监听器；**一个都没有**时不是崩溃也不是挂起，而是 `'unavailable'`，消费方 fail closed |

---

## 分级

### 一、已核对（可以直接上屏）

1. 三角色：定义 `packages/shell/shell/src/index.ts:30-32,64-66`；提供方 `packages/shell/bash-local/src/index.ts:97`、`packages/shell/bash-sandbox/src/index.ts:45`；消费方 `packages/shell/tool-bash/src/index.ts:2,36,251,320`，第二个消费方 `packages/shell/tool-pwsh/src/index.ts:2-5`。
2. 「消费方不 import 提供方」：`packages/shell/tool-bash/package.json:36`（peer 只有定义包）+ `:49-51`（运行期依赖只有 schemastery）+ `:60`（bash-local 仅在 devDependencies）。
3. 五形态各一例，见表格 B（每例都有真实包 + file:line + 形态判据）。
4. `unavailable` 词表与至少两条真实消费路径（审批升级、job 注册表缺席）。
5. 重复加载抛错的精确字节：`vendor/cordis/src/reflect.ts:326`，并有 `packages/shell/shell/tests/service.spec.ts:87` 的正则断言。
6. 规模数字 121 / 64 core / 36 seam / 20 service / 1 bundle，与生成表 `docs/capability-seams.md:709-829` 逐项吻合（可直接当屏上数字，注明「生成文件」）。

### 二、需要用演示收据补（源码在，但「演示」这一环还没收据）

| 要演的事 | 现状 | 需要什么收据 |
|---|---|---|
| 「换一个提供方就换一种产品」 | 源码只有并列事实：两者 `inject` 不同（`bash-local:98` vs `bash-sandbox:46`），且 `bash-sandbox` 的 doc（`:38-44`）自述「in place of the local executor … the tool layer is unchanged」 | 一次真实装载切换：`Config.listConfigs` 里两个插件行 + `ctx.shell.sandboxMode`（`tool-bash:251` 读的就是它）在切换前后的值变化 |
| 「一屏指认三角色」 | 已有预跑显示 `cordis_inspect` 的服务目录**不给** provider/consumer 归属，且本机 `tool-bash` 为 inactive（见 `demo/receipts-s2/E01-inspect/receipts.md`） | 三段串联收据：服务合约 + Config 插件行 + 源码行（即本表 A/B），不能赌一个面板 |
| 「第二个实现当场抛错」 | 有测试；没有运行期失败装载日志 | 一次重复装载的失败输出（或直接放 `service.spec.ts:87` 用例的跑动收据） |
| 五形态「形态在运行时可见」 | 全部是源码事实 | 若要屏上展示注册表内容，需 `ctx.llm` 适配器列表 / `ctx.browserUse.providerName` 的活体读数 |

### 三、**与计划措辞有出入**（最重要的部分：请按「改成」这一列改口播/字幕）

| # | 计划 §5 S2E01 的措辞 | 仓库实际 | 改成 |
|---|---|---|---|
| 1 | 「`dsh-bash-local` / `dsh-bash-sandbox`（**两个**提供方）」，「**各自**实现抽象类」 | 生成表 `docs/capability-seams.md:801` 给 `ctx.shell` 列了 **3** 个实现：`bash-local`、`bash-sandbox`、`pwsh-local`；源码里还有 `packages/shell/pwsh-sandbox/src/index.ts:52`（表未列）。且 `bash-sandbox` 是 `extends LocalBashExecutor`（`bash-sandbox:45`），不是直接 `extends ShellExecutor` | 「ctx.shell 有多个提供方；这台机器上装的是 **Bash 的两个**：本地执行器和沙箱执行器。沙箱那个不是从抽象类重新写一遍，而是**继承**本地那个再改执行世界」 |
| 2 | 「提供方缺席是合法状态，走 `unavailable`」 | 缺席分两种：**硬 `inject`** 缺席 → 插件停 PENDING（`tool-bash:36` 把 `shell` 硬注入，`ctx.shell` 根本不会被调用）；**可选 `ctx.get`** 缺席才变 `unavailable`/降级（`tool-bash:592` jobs、`:253` sandboxPolicy、`:281` approval，落到 `escalation.ts:256-260` 或 `ToolContextUnavailableError`） | 「缺席有两种：硬依赖缺席是**停摆（PENDING）**，可选依赖缺席才是 **`unavailable`**。判断标准就一条：消费方写的是 `inject` 还是 `ctx.get`」 |
| 3 | 「消费方按 key 查找、**不 import 提供方**」 | 成立，但精确表述更强也更好讲：定义包只作 **peerDependency**，两个提供方**都不在运行期依赖里**（`tool-bash/package.json:36,49-51,60`）。另外 tool-bash 从 `dsh-shell` 真 import 了一个**运行期值** `DSH_ENV_PREFIX`（`tool-bash:29`），所以「只 import 类型」这句话会被人抓 | 「消费方依赖的是**定义包**，而且只是 peer；两个提供方都不在它的运行期依赖里——不 import 实现，连实现的名字都不需要知道」 |
| 4 | 「每上下文一实例」若描述成包自己的守卫 | 抛错来自 cordis：`vendor/cordis/src/reflect.ts:326`；shell 包里只有注释（`:38-39`）和一条测试（`service.spec.ts:83-87`） | 「这不是 shell 的守卫，是 cordis 的标准行为：一个服务名在一个上下文里只能有一个占位，第二次装载直接抛 `service "shell" has been registered at <…>`」 |
| 5 | 「有序尝试（认证链）」暗示在模型侧能力图里 | `ctx.connection.authentication` 属于 **Host 传输层**（`packages/client/connection/`），消费者是 Connection 自己；且首轮语义比「first success wins」细：跳过已撤销项、单个 provider 抛错被吞并继续、全不过 401 / 有抛错 503（`authentication.ts:44-55`） | 「认证链是传输层的 seam，不是模型侧：按注册顺序问过去，第一个给出存活 Peer 的就赢；没人认领 401，有人炸了 503」 |
| 6 | 「形态随发布固化，选错 = 重写消费方」 | 仓库里没有对应事实句，属于判断（`patterns.md` 的观点） | 保留为**评论句**，不要说成「仓库事实」；事实句只说到「形态决定多提供方怎么共存：命名注册表只拒绝重名，单槽拒绝第二个人」 |
| 7 | 计划只写「每上下文一实例」，没给 `ctx` 键；索引文档 `ch02` 举的是 `ctx.workflowEngine`（本集改用 `ctx.shell`） | 两种说法描述同一件事：**没有具名注册表**，只有「一个实现占一个名额」。仓库侧证据只有 `ctx.shell` 这一处（`shell:36-39` + cordis `:326`），`ctx.workflowEngine` 需另行取证才能上屏 | 「第四种形态最容易讲错：它不是注册表，而是一个名额——`ctx.shell` 连注册函数都没有，第二个实现装载直接抛错」 |

> 一句话总结出入：**计划的「两个提供方」「缺席即 unavailable」「重复加载是包自己的守卫」三处会与仓库对不上**；三角色、五形态、`unavailable` 词表本身都成立。
