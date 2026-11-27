# 第 2 章：能力接缝

## 核心思想

一项能力在 dsh 里不是一个函数、也不是一个接口文件，而是一份三方契约：**Service Definition**（服务定义）声明接口，**Service Provider**（服务提供方）实现它，**Consumer**（消费方，通常是面向模型的工具）使用它。seam（接缝）正是「替换一个提供方就改变整个产品」的那个位置——所以判断某个东西是不是 seam，看的不是它长不像接口，而是这三种角色是否都有人承担。

## 框架与方法

- **三角色契约（Definition / Provider / Consumer）**：一个包可以合并承担多个角色，但单一角色本身不是 seam；添加一项能力意味着把三者一并设计。
  - 何时用：要给 dsh 加一项「可被替换」的能力，或评审别人提交的能力时。
  - 怎么做：先在定义包里写清接口与注册面，再写至少一个提供方，最后写消费方；如果消费方直接 `import` 了某个具体提供方，这次设计就已经漏了。
  - 反例校准：`ctx.workingDirectory` 的定义包与提供方同为 `working-directory`，看起来像「一个包什么都干」，但它的消费方有十三个（`tool-fs`、`tool-bash`、`tool-pwsh`、`subagent`、`sdk-jsonrpc-server`、`sandbox-policy`、`api-workspace-files`、`api-terminal-controller`、`workspace-changes`、`file-reference-local`、`tool-skill`、`agent-instructions`、`tool-lsp`），三角依然完整——角色由「谁声明、谁实现、谁消费」决定，不由仓库目录决定。
- **四类服务角色（core / service / seam / bundle）**：能力图给每个 `ctx` 键标注了角色，这是全库最省时间的一张分类表。
  - 何时用：想知道「这个东西能不能换」的时候。
  - 怎么做：读角色列。`seam` 表示实现列里有可替换的提供方；`core` 表示主干服务，实现列通常为空、由所属包自己拥有；`service` 是独立服务（有的只有类型声明，如 `ctx.config`「只有类型的声明」）；`bundle` 是组合包／组合点，例如 `ctx.agentLoop` 是「唯一的具体循环插件，扩展包依赖 `dsh-agent` 的事件和服务，而不依赖此包」。
  - 规模感：当前表里 121 个条目，其中 64 个 `core`、36 个 `seam`、20 个 `service`、1 个 `bundle`。也就是说，可替换能力是少数派——这恰好是它能保持锋利的原因。
- **注册形态（registry shapes）**：seam 的注册面不是一种，而是五种，决定了「多提供方如何共存」。
  - 何时用：写新提供方之前，先确定它属于哪一种。
  - 怎么做：
    - **命名注册表**（多提供方并列，各占一个名字）：`ctx.llm` 注册适配器；`ctx.storage` 的 `storage-json` 与 `storage-sqlite`「以不同名称并列注册」；`ctx.skills` 合并各提供方的 skill 目录。
    - **单槽提供方**（一个实例只注册一个名字，服务本身不提供操作 API）：`ctx.browserUse`、`ctx.computerUse` 都是「每个服务实例注册一个提供方拥有的名称」，且「共享服务不提供浏览器操作 API」；`ctx.sessionTitle` 只允许「唯一的可选异步提供方注册」。
    - **有序尝试**（按注册顺序短路）：`ctx.connection.authentication`「按注册顺序尝试作用域拥有的凭据验证器，返回首个存活 Peer」。
    - **每上下文一实例**（没有具名注册表）：`ctx.workflowEngine`「每个上下文使用一个引擎，与 bash 相同，且没有具名提供方注册表」。
    - **注册即绑定**（提供方按操作解析）：`ctx.credentials` 里配置只携带对机密信息的引用，提供方拥有实际值，消费方按操作解析，因此轮换后的凭据会在紧接着的下一次请求中生效。
- **消费方式（consumption）**：消费方只认定义，不认提供方；这是 seam 唯一的硬约束。
  - 何时用：给已有 seam 写新消费方，或怀疑某处耦合过紧时。
  - 怎么做：通过 `ctx.<name>` 调用与提供方无关的接口。范本是 `ctx.subprocess`：Bash 执行器、PTY shell 后端、LSP Host，以及进程外的 ACP、Codex、Claude Code subagent 后端全都通过它 spawn 进程；它负责进程坐标、进程树／会话生命周期、stdio 处置、终端机制和 kill 升级，而消费方完全不知道进程最终跑在本地还是远端。
  - 检查法：如果一个消费方需要知道「当前是哪个提供方」，那么要么该信息应该变成提供方的返回值，要么它根本不该是 seam。
- **配套插件（companion plugin）**：有些行为不属于 seam 本身，而是挂在 seam 旁边的一等插件，表里单列一列。
  - 何时用：要加的是「策略」而不是「实现」时。
  - 怎么做：写成监听该 seam 事件的配套插件，而不是塞进定义或提供方。`ctx.fs` 的配套插件是 `fs-observation-policy`：`tool-fs` 通过 `ctx.fs` 执行读取／写入／编辑，`fs-sandbox` 按共享沙箱模式限制变更，而 `fs-observation-policy`「通过 `fs/*` 事件门禁贡献基于观测状态的检查」——先读后编辑这类规则因此不需要任何提供方知情。
- **能力事件作为策略挂载点（capability events）**：能力事件是「无需导入循环即可向某个 seam 附加策略和适配器」的通道，事件族按 seam 命名（`fs/*`、`tools/*`、`telemetry/*`）。
  - 何时用：策略需要跨提供方生效时。
  - 怎么做：监听事件族而不是替换提供方。好处是钩子可以跨越不同工具系列，而不让工具与某个策略服务耦合（工具流水线章节的 `tools/pre-execute` 与 `tools/post-execute` 就是这条通道的两个端点）。
- **可替换性论证：共享执行世界（execution world）**：文件系统与进程提供方共享同一个执行世界，因此把它们指向远程沙箱，也就把 Bash、PTY 和 LSP 一并搬了过去，无需提供方专用 fork。
  - 何时用：评估「换底层」的成本时。
  - 怎么做：先找出共享同一个执行世界的那组 seam（`ctx.fs`、`ctx.subprocess`、`ctx.shell`、`ctx.sandbox`、`ctx.terminals`），再确认它们的消费方没有绕过接口。`ctx.ssh` 是这条链的连接所有者：它「负责一条经过认证的 OpenSSH 连接、已安装辅助程序身份、独立程序流，以及配套远端提供方的断连清理」，而 `fs-ssh`、`subprocess-ssh`、`sandbox-ssh` 分别实现三个 seam。
- **完整性守卫（maintenance mode）**：能力图是混合模式——服务从 Cordis 声明中发现，接口、实现和消费方角色在 `scripts/gen-doc-graphs.ts` 中分类，并设有完整性守卫。
  - 何时用：新增或重命名服务、提供方、消费方之后。
  - 怎么做：跑文档图生成；分类缺失会让守卫失败，而不是静默生成一张缺边的图。

## 关键概念

- **能力接缝（capability seam）**：一项可替换能力，含声明接口的 Service Definition、实现它的 Service Provider、使用它的 Consumer 三角。
- **服务定义（Service Definition）**：声明接口与注册面的那一侧，通常是一个只含契约的包。
- **服务提供方（Service Provider）**：实现定义并按该 seam 的注册形态注册进去的包；同一个 seam 可以有零到多个。
- **消费方（Consumer）**：只认定义、不认提供方的调用方，最常见形态是 `tool-*` 这类面向模型的工具。
- **配套插件（companion plugin）**：挂在某个 seam 旁边、通过该类能力事件施加策略或观测的插件，例如 `fs-observation-policy`、`spill-policy`、`sandbox-policy`。
- **能力事件（capability event）**：按 seam 命名的事件族（`fs/*`、`tools/*`、`telemetry/*`），用于附加策略与适配器而不引入导入循环。
- **注册形态**：多提供方共存的方式——命名注册表、单槽、有序尝试、每上下文一实例、注册即绑定。
- **执行世界（execution world）**：文件系统、子进程、shell、沙箱、终端共享的同一套本地或远端执行环境；把它整体指向远端即可整体迁移。
- **服务角色（role）**：能力图给每个 `ctx` 键打的分类标签——`core`、`service`、`seam`、`bundle`。
- **agent 作用域注册（agent.ctx）**：把注册项限定到单个 agent 的手段，同一个 seam 在不同 agent 上可以解析到不同提供方。

## 心智模型

- 当你想「改一下实现」时，先确认这句话里的「实现」是 Provider 还是 Consumer——九成的误改都发生在把策略写进了提供方。
- 把一个 seam 看成插座而不是电器：定义是插孔规格，提供方是插头，消费方是拿着插头的那只手；插座不该知道今天插的是台灯还是电扇。
- 把配套插件看成插在插座旁边的滤波器，而不是插座的一部分——它靠事件工作，卸载后能力照常。

## 反模式

- **单一角色就宣称「这是 seam」**：原文明确「单一角色本身不是 seam」；只写一个接口包而没有提供方或消费方，得到的是没人实现的抽象。
- **把策略写进提供方**：先读后编辑、spill 阈值、审批询问这些规则若落在提供方内部，换一个提供方就整套行为漂移；它们应作为配套插件或 `tools/*`、`fs/*` 事件的监听者存在。
- **在消费方判断当前提供方**：`ctx.subagents` 的六个提供方（进程内 spawn、进程内 fork、ACP、Codex、Claude Code、dsh-sdk）差别极大，从新建一个子 agent 到把一个轮次委派给另一个产品；一旦消费方按名字分支，新增提供方就要改消费方。
- **在定义上做拒绝分类**：`ctx.credentialsController` 把批量扇出、视图投影与拒绝映射都留在控制器里，「而不在 seam Definition 上」；`ctx.settingsController` 同样强调所有拒绝在这里分类。拒绝语义属于暴露它的那一层。
- **让两个强制执行组件各自读配置**：`ctx.sandboxPolicy` 之所以是 core，是因为它「统一保存部署默认模式和工作区根目录」，让 bash 与 fs 不会限制到不同的根；自建策略副本迟早让两侧边界不一致。
- **忘记提供方缺席是合法状态**：`ctx.approval` 没有回答方时以 `unavailable` 关闭失败——消费方必须处理「没有提供方」这条路径，而不是假定总有一个。

## 代码/配置示例

能力图的记录结构（契约签名，逐列对应原文表格）：

```text
seam record := {
  ctxKey        : "ctx.fs"                  // 注册面与消费面共用的键
  role          : core | service | seam | bundle
  owner         : 所属包（定义所在）
  implementers  : 提供方包列表，core/service 常为 "-"
  consumers     : 直接消费方包列表
  companion     : 配套插件，可为 "-"
  note          : 职责边界一句话
}
```

一个典型 seam 的三方关系：

```text
ctx.fs         定义: fs          实现: fs-local | fs-sandbox | fs-ssh      消费: tool-fs        配套: fs-observation-policy
ctx.subprocess 定义: subprocess  实现: subprocess-local | subprocess-ssh   消费: bash-local, bash-sandbox, terminal-bash,
                                                                                  lsp-stdio, subagent-acp/codex/claude-code
ctx.sandbox    定义: sandbox     实现: sandbox-local | sandbox-ssh        消费: bash-sandbox, terminal-bash, api-terminal-controller
```

消费方的调用形状（提供方无关）：

```text
ctx.<seam>.<operation>(...)          // 定义声明的接口
// 提供方缺席 -> 该调用以 provider 专属错误码失败，消费方必须能处理
```

## 参考表

最常用的一组 seam（节选自能力图，角色列保留原文）：

| `ctx` 键 | 角色 | 定义包 | 实现 | 直接消费方 | 说明（压缩） |
|---|---|---|---|---|---|
| `ctx.fs` | `seam` | `fs` | `fs-local`、`fs-sandbox`、`fs-ssh` | `tool-fs` | 读写编辑走 `ctx.fs`；`fs-sandbox` 按共享沙箱模式限制变更；配套插件按 `fs/*` 事件门禁。 |
| `ctx.subprocess` | `seam` | `subprocess` | `subprocess-local`、`subprocess-ssh` | `bash-local`、`bash-sandbox`、`terminal-bash`、`lsp-stdio`、`subagent-*` | 负责进程坐标、进程树／会话生命周期、stdio 处置、终端机制与 kill 升级。 |
| `ctx.shell` | `seam` | `shell` | `bash-local`、`bash-sandbox`、`pwsh-local` | `tool-bash`、`tool-pwsh`、`hooks-claude-code`、`hooks-codex` | 换执行器不需要改工具；沙箱、远程或 PowerShell 执行器可直接替换。 |
| `ctx.sandbox` | `seam` | `sandbox` | `sandbox-local`、`sandbox-ssh` | `bash-sandbox`、`terminal-bash`、`api-terminal-controller` | 消费方交出即将 spawn 的确切 argv，后端按每次调用的策略包装并报告强制执行。 |
| `ctx.sandboxPolicy` | `core` | `sandbox-policy` | - | `bash-sandbox`、`fs-sandbox`、`terminal-bash`、`terminal-panel` | 统一存放部署默认模式与工作区根，保证 bash 与 fs 限制到同一根目录。 |
| `ctx.terminals` | `seam` | `terminal` | `terminal-bash`、`terminal-panel` | `tool-terminal` | 注册表负责精确到 Agent 的会话身份与清理；后端负责终端机制。 |
| `ctx.llm` | `seam` | `llm` | `llm-deepseek`、`llm-pi-ai`、`llm-replay` | `agent-loop`、`compaction-basic` | 适配器注册实现；循环与压缩调用提供方无关的流服务。 |
| `ctx.approval` | `seam` | `user-approval` | - | `tools`、`tool-bash`、`acp` | 一次性权限决策经 `approval/request` waterfall 分派，回答方是监听器；无回答方即 `unavailable`。 |
| `ctx.permissionPresets` | `core` | `permission-presets` | - | - | 预设表（`workspace-write`／`danger-full-access`）组合沙箱模式与审批选项；一次切换写一个 `permission/preset` 事件并贯通到两个选项事件。 |
| `ctx.credentials` | `seam` | `credentials` | `credentials-local` | `api-settings-controller`、`deepseek-auth`、`llm-pi-ai` | 配置只携带引用，提供方拥有实际值；按操作解析，轮换即刻生效。 |
| `ctx.attachments` | `seam` | `attachment` | `attachment-local` | `api-session-controller`、`tool-fs`、`llm-pi-ai`、`llm-deepseek` | 宿主在会话事件之前提交已接受的图片；提供方把已授权引用解析为原生内容。 |
| `ctx.skills` | `seam` | `skill` | `sandbox-windows-acl`、`skill-badge`、`skill-filesystem`、`skill-office` | `tool-skill` | 合并各提供方目录；`tool-skill` 渲染会话前缀目录并加载完整正文。 |
| `ctx.subagents` | `seam` | `subagent` | `subagent-spawn-in-process`、`subagent-fork-in-process`、`subagent-acp`、`subagent-codex`、`subagent-claude-code`、`subagent-dsh-sdk` | `tool-subagent`、`tool-subagent-control`、`tool-ralph` | 提供方准备本地子级或执行外部任务；一个 activation 管理器持有两类生命周期。 |
| `ctx.jobs` | `seam` | `jobs` | `jobs-local` | `tool-bash`、`tool-pwsh`、`tool-terminal`、`tool-jobs`、`api-job-controller` | 生产方登记正在运行的工作；`tool-jobs` 是面向模型的读／列／终止控制器。 |
| `ctx.sessionPersistence` | `seam` | `session-persistence` | `session-persistence-jsonl` | `agent-loop`、`tool-bash`、`hooks-*`、`session-query`、`message-feedback` | JSONL 后端把 `SessionEvent` 词汇持久化为每个 Session 一份产物。 |
| `ctx.lsp` | `seam` | `lsp` | `lsp-stdio` | `tool-lsp` | 提供方注册与选择，加上恰好四种操作的标准化查询；不提供协议逃生口。 |
| `ctx.browserUse` / `ctx.computerUse` | `seam` | 同名包 | 各自实验提供方 | 提供方自身即消费方 | 每实例只注册一个提供方自有名称；共享服务不提供通用操作 API。 |

## 实例演练

目标：把「执行世界」整体搬到远端，让 Bash、PTY、LSP 一起过去，而不 fork 任何提供方。

第一步，承认这是三个 seam 而不是一个。`tool-bash` 消费 `ctx.shell`；`bash-sandbox` 与 `terminal-bash` 消费 `ctx.sandbox` 与 `ctx.subprocess`；`lsp-stdio` 消费 `ctx.subprocess`。三个定义各自不变。

第二步，选提供方组合：`fs-ssh`、`subprocess-ssh`、`sandbox-ssh`。这三个包都消费同一个 `ctx.ssh`——它负责一条经过认证的 OpenSSH 连接、已安装辅助程序身份、独立程序流，以及配套远端提供方的断连清理。于是「远端」这个概念只出现一次，就在连接所有者里，而不是在三个提供方里各写一遍。

第三步，检查策略是否仍成立。`ctx.sandboxPolicy` 仍然统一保存部署默认模式与工作区根，因此 `bash-sandbox` 与 `fs-sandbox` 不会限制到不同的根；`ctx.approval` 仍按 `approval/request` 分派一次性决策，回答方仍是监听器（例如 ACP 为自身 agent 提供的桥接），如果远端组合没有装回答方，就必须接受 `unavailable` 这条失败路径；`ctx.permissionPresets` 的 `workspace-write`／`danger-full-access` 一次切换仍然只写一个 `permission/preset` 事件，并贯通到两个选项事件。

第四步，检查消费方有没有偷偷绑定本地实现：`tool-fs` 只经 `ctx.fs` 读写编辑；`tool-bash` 只经 `ctx.shell`；`tool-lsp` 只经 `ctx.lsp` 的四种标准化查询。任一处如果 `import` 了 `fs-local`，这次迁移就得改消费方——这也是评审时最该看的一行。

第五步，验证配套插件仍在链上：`fs-observation-policy` 通过 `fs/*` 事件贡献基于观测状态的检查，它不关心 `ctx.fs` 背后是本地还是 SSH。这条过了，就说明「换一个提供方就改变整个产品」在此组合上成立。

## 关键要点

1. 判断 seam 只问一句：Definition、Provider、Consumer 三个角色是否都有人承担。
2. 先读能力图的角色列：`seam` 才承诺可替换，`core` 与 `service` 是主干。
3. 写提供方前先确定注册形态（命名注册表／单槽／有序尝试／每上下文一实例／注册即绑定），它决定多提供方如何共存。
4. 策略放配套插件或能力事件，不放提供方；否则换实现时行为会整体漂移。
5. 消费方必须处理「提供方缺席」，这是合法状态而不是异常。
6. 要整体迁移执行世界，就同时改 `ctx.fs`、`ctx.subprocess`、`ctx.sandbox`、`ctx.shell`、`ctx.terminals` 的提供方，并让 `ctx.sandboxPolicy` 继续做唯一真源。
7. 新增或改服务后跑文档图生成；完整性守卫失败说明角色分类缺了一边。

## 关联

- **第 1 章**：架构总览给出「seam 是三件套」的定义与 profile 分层，本章给出 121 个条目的角色、提供方与消费方。
- **第 4 章**：`tools/pre-execute`、`tools/execute`、`tools/post-execute` 三瀑布是能力事件在工具链上的落地。
- **第 6 章**：`fs/*`、`tools/*`、`telemetry/*` 等能力事件的生产者与消费者矩阵。
- **第 30 章**：`ctx.approval`、`ctx.permissionPresets`、`ctx.ptcRuntime`、`ctx.jobs` 的组合用法。
- **第 32 章**：`ctx.fs`、`ctx.subprocess`、`ctx.shell`、`ctx.terminals`、`ctx.sandbox` 的提供方实现细节。
- **外部概念**：端口与适配器（ports & adapters）／六边形架构——Definition 是端口，Provider 是适配器，配套插件是端口上的策略装饰器。
