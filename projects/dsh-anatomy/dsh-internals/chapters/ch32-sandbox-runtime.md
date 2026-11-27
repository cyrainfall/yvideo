# 第 32 章：沙箱与执行环境

## 核心思想

执行不是「跑一条命令」，而是一个分层世界：沙箱只把 argv 包装成受约束的形状，子进程 seam 管真进程，shell seam 管请求/规格与归因，文件系统提供方定义文件在哪，工作目录定义解析基址与写边界。每层都是可替换的 Service Provider，所以**换一个提供方就换掉整个执行世界**。剩下的纪律只有一条：把「命令跑了吗」和「为什么没成」分开归因。

## 框架与方法

- **沙箱是 argv 包装器，不是进程管理**：`ctx.sandbox.confine(argv, policy, signal)` 返回 `ConfinedArgv`（新 `argv` + `enforcement` + 两种 stderr 分类器），自己不建进程。
  - 何时用：`read-only` / `workspace-write`。`danger-full-access` 不在 `ConfinedSandboxMode` 里，消费方根本不调它，直接 spawn 原始 argv。
  - 判据：`SandboxMode` 只管辖文件效果（`read-only` 连 `/dev/null` 接收器都要显式授予），网络与进程可见性不在词汇内；`enforcement: 'partial'` 是后端报告的**事实**（旧内核 ABI、Windows ACL 的硬链接/读不受限/AppContainer 缺口），要绝对边界的调用方必须拒绝它。
- **`ctx.sandboxPolicy.resolve()` 是唯一优先级权威**：经批准的显式 `mode` > 会话最后一条 `sandbox/mode` 事件 > 部署默认。
  - 怎么做：**会话 cwd 就是 `workspace-write` 边界**，Host 搬 Session 就搬边界；强制方在文件实际存在的位置规范化根，含 `symlink/..` 的 cwd 因此指向子进程真正跑的那目录。
  - 危险：`registerWritableRoot()` 的授予**运行时专属**，resume / fork 后必须重新注册；Windows 子进程忽略额外授权，只有 Harness 文件工具遵守。
- **fail-closed 与归因三步**：受限策略下静默的无隔离透传永远不合法（`SANDBOX_UNAVAILABLE` / `SANDBOX_PREPARATION_FAILED` / `SANDBOX_INVALID_ROOT`）。
  - 怎么做：先 `runnerFailureRules`（过 `allowedExitCodes` 门控，按**整行精确**剥掉 `informationalLines`，再在余下行内不区分大小写匹配 `fatalSignatures`）→ 再 `denialSignatures` → 最后才是进程失败。runner failure 表示命令**从未运行**，denial 表示约束**生效并阻止**了它；仅凭退出码永不足以证明 runner 失败。
  - 判据：`denialSignatures` 是**这个后端的方言**（bwrap 的 EROFS 文本、Landlock 的 EACCES、Seatbelt 的 EPERM），不是跨后端并集。
- **`ctx.subprocess.spawn(spec)` 完全显式、零默认值**：`argv` 绝不经过 shell；`resolveExecutable()` 拒绝**含分隔符的相对路径**（解析基址未定义，宁可 fail loud 也不猜）。
  - 怎么做：stdin 是 `'ignore' | 'pipe' | { data }`，stdout/stderr 是 `'pipe' | 'inherit' | SubprocessCollect`；**省略 `spill` 只留内存尾部**（诊断尾部形状），包含 `spill` 才让完整流可恢复。
  - 怎么做：`DSH_*` 归 Harness 所有——先**丢弃**环境里已有的 `DSH_*`，再合并调用方显式 `env`；显式 `undefined` 是 tombstone。
- **受管范围与「只报退出事实」**：`terminate()` 是唯一终止动词（幂等，abort signal 也触发）；`waitForExit()` 等的是**同一范围为空**，不只是被 spawn 的命令报出结果，所以存活的工作仍可观察。
  - 判据：`SubprocessOutcome` 只有 `exitCode` 与 `signal`，**故意不带**超时/取消分类、也不带输出——分类归调用方，输出留在 `handle.collected`；读取器吃全流字节偏移且从不消费，偏移滑出窗口时读作 `lossy`。
- **`ctx.shell.resolve()` 把请求与规格分开**：`ShellExecRequest` 的 `workdir` / `timeoutMs` / `stdoutMaxBytes` 可选，`ShellExecSpec` 同名字段必填；默认与封顶只在这里补。
  - 判据：**前台是调用方 await 什么，不是 spawn 的属性**——await `result` 是前台，留句柄是后台，`onExpiry: 'none'` 让调用方自己限定等待。`stdin` / `env` / `stdoutMaxBytes` 是受信任插件输入，`dsh-tool-bash` 不暴露成参数。
  - 判据：`exitCode` / `signal` / `timedOut` / `aborted` 各自独立——进程可以同时超时并以 0 退出（自己捕了信号）；`timedOut` 与 `aborted` 互斥且 first-cause。`ShellSandboxInfo` 的事实独立于退出状态：前台遇 `runnerFailed` 抛错，后台只能读事实；更宽松的重试是**新调用**，需 `ctx.approval` 事前批准。
- **`ShellProcess` 无 id、无 owner**：`readOutput()` 是**消费式**增量，`observed` 是**非消费**偏移读取器；`done` 绝不 reject，提供方 rejection 结算成 `killed`。
  - 怎么做：`dsh-tool-bash` 把它适配成 `ctx.jobs.start()` 钩子，任务标识归通用运行时；**只有 `ctx.subprocess` 的 disposal 会终止并等待后台进程**，只重载执行器则进程照跑。
- **终端是两层**：`spawnTerminal()` 是非管道原语（控制终端、前台进程组、须等待的 TERM→KILL），`ctx.terminals` 在其上做持久会话。
  - 怎么做：`ctx.terminals` 按**确切 `Agent`** 授权（不是名称也不是猜的 id），`hasOwnerActivity()` 在 spawn-to-close 全程为 true，一个会话同时只接受**一个**活动发送；提示符检测、scrollback 与持久所有权仍在 PTY 后端；`terminalEnvironment()` 的 platform 与 `defaultShell` 也来自提供方，不是浏览器。
  - 判据：`TerminalWaitReason`（`stdin_read` / `inferred_idle` / `timeout` / `session_exit`）与 `TerminalSessionStatus` 是两件事——发送可因超时返回而顶层 shell 仍存活；清理失败用 `TerminalBackendCleanupError` 拒绝，不拿它替换调用方的取消原因。
- **`ctx.fs` 用不透明目标隔开路径与身份**：`targetKey` / `FsVersion` 禁止解析，也不能假设是本地路径；跨能力坐标问 `processPath()` / `fileUrl()` / `contains()`。
  - 怎么做：`stat()` 只给元数据（`type` 读前拒目录，`size` 选 `readText` 还是 `streamText`）；要检查信任边界先 `lstat()`——**路径级、不跟随最后一段链接**，因为 `resolve()` 会**有意**跟随 symlink 产生稳定标识。
- **`fs/*` 守卫是事件门禁，不是服务方法**：`dsh-fs-observation-policy` 不注册服务，只裁决 `fs/write-intent` / `fs/edit-intent` / `fs/delete-intent` 三个**单槽决策 waterfall**，并用 `fs/observed` 记录观测。
  - 怎么做：工具带默认 thunk 分发（返回 `undefined` 即裸提供方），监听方**完全决策而不调 `next()`**，slot **先到先得**；**移除插件不破坏工具**（工具调 `ctx.fs` 并分发事件），无插件时 `write` 无条件覆盖。
  - 危险：`fs/observed` 监听方必须**同步且只产生副作用**，工具不捕获它的异常。
  - 判据：`absent` 只授权**创建**，**永不授权编辑**（所以没有 `FS_PARTIAL_OBSERVATION`）；「无守卫」靠**省略 `expected`** 表达；`createIfAbsent` 对探测之后才出现的文件也必须拒绝。
- **变更是一个临界区，移动是两个效果**：`editText` / `patchText` 带守卫时先验版本再字面匹配（陈旧报 `FS_STALE_VERSION` 而非匹配失败），匹配、行尾与原子替换同区完成，不要在外部拼 `read` + `write`；移动可能已发布目标而源删除失败（`sourceDeleted: false`）。
  - 判据：**文件 IO 不设超时**。bash/web 消费 `@deepseek-ai/dsh-timeout`、`glob`/`grep` 由工具调用超时策略强制——那些**是进程支撑的**；本地系统调用超时迫使不了 `fsync`/`rename`，这里的 `timeoutMs` 会是一个 seam 无法强制执行的截止时间。
- **「目录」是三层不同的东西**：`ctx.workingDirectory` 是执行边界，`ctx.worktrees` 是改它的手段，`ctx.workspaceRegistry` 只是记录。
  - 判据：`set()` 的调用方**只有 Host 操作**（建工作树、forge 面板、SDK 请求），模型没有移动目录的工具——否则一条模型给的路径就把写边界一起搬走；变更只影响一个 Session，**已有终端与持久 shell 保留自己的目录**，`get()` 是唯一读接口。
  - 怎么做：worktree 用**调用方当前目录**定源仓库，先固定提交（省略取 `HEAD`），只 fetch 那一个远程分支且不带 tags；**现有沙箱策略必须允许目标目录与共享 Git 管理目录**；检出禁用 clean/smudge/process 过滤器且不复制未提交文件；`exit()` 取**包含当前目录的最长**那条，嵌套每层退一次。
  - 判据：workspace 是「稳定 id + 标题 + 有序会话账本」，**不增加任何模型可见内容**；`WorkspaceId` 是 uuid **永不用路径**（路径规范化会重写路径而锚点须稳定）；`delete()` 只删注册，目录与日志不动。
- **SSH 只换提供方，执行世界整体搬家**：远端家族用部署方持有的 OpenSSH 实现**既有**文件系统/子进程/沙箱 API，**不引入 SSH 专用工具**，Harness 与 Session 存储留在主机。
  - 判据：文件系统身份、可执行文件查找、进程 cwd、沙箱根、LSP 文件 URL **全指向 SSH 主机**；`processPathFromHostPath()` **仍不可用**（装了远端产物≠主机路径可移植）。
  - 判据：**SSH 只是传输方式**，文件效果限制由远端沙箱提供方执行；管理 RPC 走 helper 的 exec 流，普通 stdio 与终端输出走**分别认证的转发 Unix 套接字**，各有独立通道窗口但共享带宽与传输失败。
  - 危险：SSH 丢失使待处理操作失效，客户端**如实报告未确认结果，绝不重连重放可能已执行的操作**；管理截止只约束**单次 RPC**，不替代执行截止。

## 关键概念

- **`ConfinedArgv`**：`confine()` 的结果——替换后的 `argv`、`enforcement`、`denialSignatures`、`runnerFailureRules`。
- **`SandboxExecutionPolicy`**：一次调用解析出的完整策略（`mode` / `workspaceRoot` / `additionalWritableRoots?` / `sessionId?`）；`SandboxPolicy` 是它的收窄版。
- **方言（dialect）**：某后端对被拒文件效果产生的 stderr 特征文本。
- **受管范围（managed range）**：提供方实际能观察并终止的进程集合，`terminate()` 与 `waitForExit()` 都作用其上。
- **`CollectedOutput`**：一条被收集的流——截断时是尾部文本、`truncated` 标志、可选的完整流 `spillPath`。
- **first-cause 分类**：一条融合截止同时驱动超时与取消，只报最先到达的原因。
- **`FsTarget` / `FsVersion`**：不透明目标身份与不透明新鲜度 token，可显示、绝不解析。
- **`FsObservation`**：`present(version)` 或 `absent`；后者只授权创建，永不授权编辑。
- **`WorkspaceId`**：工作区记录的生成 uuid，与路径标识刻意分离。

## 心智模型

- **把 `confine()` 看成纯函数式的 argv 变换器。** 它给你一段新 argv 和一份「这个后端怎么说话」的说明书；进程、输出、退出码都是别人的事。
- **选提供方就是选一整个世界。** 换子进程提供方，`PATH` 解析、cwd 规范化与受管范围边界一起换；换文件系统提供方，路径语义一起换。「本地能跑」从来不是「远端能跑」的证据。
- **先问「命令跑了吗」，再问「为什么没成」。** 三步顺序：runner failure（从未运行）→ denial（跑过但被挡）→ 进程自身非零退出。
- **把 cwd 看成沙箱边界，而不是字符串偏好。** 谁有权改 cwd，谁就有权改可写范围。

## 反模式

- **在受限策略下静默透传**：没有可用后端就退化成本地裸跑，等于把「沙箱」变成口号。
- **把 `danger-full-access` 塞给 `ctx.sandbox`**：它不在 `ConfinedSandboxMode` 里，该模式由消费方直接 spawn 原始 argv。
- **用跨后端并集匹配拒绝文本**：会把正常错误误判成策略拦截。
- **只用退出码判断 runner 失败**：必须先剥掉 `informationalLines` 再匹配致命签名。
- **把 `registerWritableRoot()` 当持久权限**：它是运行时专属，resume / fork 后必须重新注册。
- **把 `readOutput()` 当观察器**：它是消费式游标，会真的把字节取走；旁观者用 `observed`。
- **为「看起来一致」给文件 IO 加 `timeoutMs`**：那会是 seam 无法强制执行的截止时间。
- **让模型发起的路径移动 cwd**：模型能移动目录就等于能移动写边界。

## 代码/配置示例

```ts
interface ConfinedArgv {
  argv: string[]                  // runner, profile, separator, then caller's argv
  enforcement: SandboxEnforcement // 'full' | 'partial'
  denialSignatures: readonly string[]        // THIS backend's dialect
  runnerFailureRules: readonly RunnerFailureRule[]
}

interface RunnerFailureRule {
  allowedExitCodes?: readonly number[]   // omitted permits any nonzero exit
  fatalSignatures: readonly string[]
  informationalLines?: readonly string[] // excluded by exact full-line equality
}
```

逐调用策略：同一提供方、同一时刻、不同边界。

```ts
const policy = ctx.sandboxPolicy.resolve({ session })   // mode + 绝对 workspaceRoot
const confined = await ctx.sandbox.confine(['bash', '-c', command], {
  ...policy,
  mode: 'read-only',        // 收窄模式，roots 不变
}, signal)
// 然后 spawn confined.argv，而不是自己的 argv
```

零默认值的 spawn spec：

```ts
const handle = ctx.subprocess.spawn({
  argv, cwd,                                  // argv[0] 是程序，永不经 shell 解释
  stdio: {
    stdin: { data: input },                   // 或 'ignore' / 'pipe'
    stdout: { maxBytes: 1 << 20, spill: { maxBytes: 32 << 20 } },  // 完整流可恢复
    stderr: { maxBytes: 64 << 10 },           // 无 spill = 只留诊断尾部
  },
  graceMs,
  signal,
  env: { PATH: '/usr/bin' },                  // 合并到已清理的父环境之上
})
```

请求 → 规格：

```ts
const spec = ctx.shell.resolve({ command, timeoutMs: 30_000 })
// workdir / timeoutMs / onExpiry / stdoutMaxBytes 全部已填并已封顶
const execution = await ctx.shell.execute(spec)
```

## 参考表

| seam | `ctx.*` 键 | Service Definition | 拥有的东西 |
| --- | --- | --- | --- |
| 沙箱 | `ctx.sandbox` | `dsh-sandbox`（`SandboxProvider`） | argv 包装、`enforcement`、拒绝方言 |
| 沙箱策略 | `ctx.sandboxPolicy` | `dsh-sandbox-policy` | 默认模式、root 回退、会话目录授权 |
| 子进程 | `ctx.subprocess` | `dsh-subprocess`（`SubprocessRuntime`） | `DSH_*` 命名空间、凭据清除、受管范围 |
| shell | `ctx.shell` | `dsh-shell`（`ShellExecutor`） | 请求/规格拆分、结果归因、`[exit code: N]` |
| shell 环境 | `ctx.shellEnv` | `dsh-shell-env`（`ShellEnvRegistry`） | 内建 `DSH_*` 事实与插件贡献 |
| 终端 | `ctx.terminals` | `TerminalSessionService` | PTY 后端注册、确切 Agent 归属、scrollback |
| 文件系统 | `ctx.fs` | `dsh-fs`（`FileSystem`） | 不透明目标、原子发布、带守卫变更 |
| 工作目录 | `ctx.workingDirectory` | `dsh-working-directory` | `workspace-root/change`、`working-directory/access` |
| 工作树 | `ctx.worktrees` | `dsh-experimental-worktree` | 检出池、进出、归档回收 |
| 工作区 | `ctx.workspaceRegistry` | `dsh-workspace` | 稳定 id + 会话账本（不改执行语义） |
| SSH | `ctx.ssh` | `dsh-ssh`（`SshConnection`） | 远端 helper 验证与流转发 |

`SandboxMode` 与后端行为：

| mode | POSIX runner | Windows ACL runner | 额外目录授权 |
| --- | --- | --- | --- |
| `read-only` | 拒绝写入，仅授予 `/dev/null` 接收器 | 不授予任何显式可写根，因环境 ACL 缺口报 `partial` | 无效 |
| `workspace-write` | 工作区根 + 受支持额外目录 + 后端临时区域 | 同上，且子进程**忽略**额外授权 | 仅 Harness 文件工具遵守 |
| `danger-full-access` | 绕过隔离（不进 `ctx.sandbox`） | 同左 | 不适用 |

## 实例演练

一次受限的前台 bash 调用，端到端：

1. **解析策略。** 拿活跃会话调 `ctx.sandboxPolicy.resolve({ session })`：不可变 cwd 成为 `workspaceRoot`，日志最后一条 `sandbox/mode` 若是 `workspace-write` 就取它，否则取部署默认；此前 `registerWritableRoot()` 的登记与配置额外根一起被快照。
2. **收窄并包装。** 这次只要读，覆盖 `mode: 'read-only'`（roots 不变），调 `ctx.sandbox.confine(['bash','-c',command], policy, signal)`，拿到新 argv、`enforcement`、本方方言与 runner 失败规则。
3. **spawn。** 执行器用 `ctx.subprocess.spawn()` 跑那段 argv：`argv` 不经 shell，`stdin` 是 `'ignore'`，stdout 收集带 spill，stderr 只留尾部。
4. **归因。** 非零退出后**先**按 `runnerFailureRules` 判：退出码在门控内、剥掉 `informationalLines` 后仍命中 `fatalSignatures` → 沙箱基础设施故障，前台抛 `SANDBOX_UNAVAILABLE`。**再**按 `denialSignatures` 判：stderr 出现 bwrap 的 EROFS 文本 → `denied: true`。都不命中，才是命令自己失败。
5. **产出结果。** `ShellRunResult` 把四个退出字段分开写，`sandbox` 带 `mode` / `denied` / `enforcement` / 必要时 `runnerFailed`。模型只在拒绝标记指出生效模式时才知道模式，并可请求一次性更宽松的重试——那是**新调用**，`ctx.approval` 必须事前批准。

同一条链放到远端形状不变：`dsh-sandbox-ssh` 用与 SSH 文件系统、SSH 子进程提供方配套的远端后端执行**同一套策略**。把 Session 移进工作树是 `ctx.worktrees.enter()` 经工作目录服务改 cwd，写边界随之移动；把项目登记成 workspace 则什么执行语义都不改。

## 关键要点

1. 沙箱只改 argv、从不建进程；`danger-full-access` 根本不进 `ctx.sandbox`。
2. `SandboxMode` 只管辖文件效果，网络与进程可见性需要另立词汇。
3. 策略按每次调用携带，优先级只有 `ctx.sandboxPolicy.resolve()` 一个权威。
4. 归因顺序固定：runner failure → denial → 进程失败，三者证据彼此正交。
5. `partial` 是事实不是警告，要绝对边界的调用方必须拒绝它。
6. 子进程 seam 不给默认值；每条流的处置与每个上限由调用方显式决定。
7. 目录有三层：cwd 是执行边界（只有 Host 能改），worktree 是改它的手段，workspace 是纯记录。

## 关联

- **第 16 章（生命周期与副作用）**：`registerWritableRoot()` 返回的正是 Cordis effect disposer，授予随调用方 fiber 释放。
- **第 6 章（事件总线）**：`sandbox/mode` 是 `resolve()` 的输入；`fs/*` 的 waterfall 与 emit 是同一套分发语义，只是槽位与副作用约束更严。
- **`capability seam`**：本章各层都是同一模式的实例——Service Definition 定语义，Service Provider 定平台，Consumer 只管 await。
