# 第 1 章：架构总览与模块图谱

## 核心思想

运行中的 `dsh` 不是一块需要打补丁的特权内核，而是一棵由配置层按序叠加出来的插件树：模型适配器、工具注册表、会话日志乃至 agent loop（智能体循环）本身都是插件，因此每一部分都能从配置替换。定位架构问题的正确起点是先问「这属于哪个扩展点」，而不是先问「改哪个文件」。

## 框架与方法

- **Cordis 插件模型（Cordis）**：插件向共享上下文贡献服务、类型化事件和可逆的副作用；注册即副作用，会随插件卸载而撤销。
  - 何时用：要给 dsh 增加任何新行为、或替换任何既有行为时。
  - 怎么做：把新行为挂到其他插件旁边，而不是修改既有插件内部；不要寻找特权内核，因为不存在需要打补丁的那个内核。
- **profile 与组合包（profile / bundle）**：profile 是存放在 Harness home 中的具名组装，列出自己叠放的组合包、存放自己安装的树外插件，并保存用户自己的 `cordis.patch.yml`；组合包是 Cordis 配置项及其挂载代码的分发格式，因此它插入的内容始终可被其上各层 patch。
  - 何时用：要改变某种产品形态（Web、无界面、SDK、ACP）装了什么的时候。
  - 怎么做：两者都在各自的 `package.json` 中通过 `dsh` 字段声明自己——`dsh.profile` 列出一个 profile 的组合包，`dsh.bundle` 指向一个组合包的 patch 文件。
- **四层 patch 次序（layer order）**：各层依次应用在一个空条目列表之上：profile 中有序的组合包、其 `cordis.patch.yml`、home patch，最后是 `--patch` overlay。
  - 何时用：判断「我的改动会被谁覆盖」时。
  - 怎么做：一条 patch 按 id 定位某个条目并替换其整个 config，或插入新条目；`preset` patch 在目标声明的 `config.plugins` 内应用这些操作，沿用相同的层优先级。
- **随附组合包矩阵**：`dsh-base` 是 `web`、`headless`、`sdk` 与 `acp` profile 的共享第一层——模型适配器、工具、持久化、沙箱与审批策略、设置、凭据、遥测；`dsh-web-app` 增加浏览器应用，`dsh-headless` 增加不带服务器的一次性运行器，`dsh-sdk-app` 增加 SDK JSON-RPC 服务器，`dsh-acp-app` 增加仅用于自动化的 ACP 服务器。
  - 何时用：判断某个能力为什么「在 Web 有、在 SDK 没有」时。
  - 怎么做：记住刻意的例外——`dsh-sdk-minimal` 是一个组合包拥有完整显式 SDK 配置树、不应用 `dsh-base`；它位于同一 launcher 之后，是仓库自有独立组合包，而不是由调用方提供的 Cordis 配置树。
- **三域事件（session / agent / capability events）**：事件在三个域内提供扩展点。
  - 何时用：决定一个扩展点该挂哪一类事件。
  - 怎么做：某个事实必须在重新加载后仍然存在 → 用会话事件（追加到日志并经 `session/event` 广播）；要观察或拦截进行中的工作 → 用 agent 事件（`agent/*`，携带活跃 `Agent`：inbox、步骤、状态、请求、验证、续跑）；要给某个 seam（`fs/*`、`tools/*`、`telemetry/*`）附加策略和适配器而不引入导入循环 → 用能力事件。
- **新行为归属映射**：新行为附加到已有文档记录的扩展点；改动循环本身时，该映射随之更新。完整表见参考表。
  - 何时用：拿到一个功能需求的第一步。
  - 怎么做：在表里找到目标行，读出机制列给出的那个 `ctx` 键、事件或工厂调用，再去对应子系统页读签名。
- **图形索引（graph atlas）**：这些图展示生成目录未包含的关系——包之间的关系、能力 seam、事件流、面向模型的工具、应用组合和运行时生命周期路径；精确签名和类型定义仍以子系统页面（类型与生成的 `cordis-surface` 区域）及工具目录为准。英语源文件由 `pnpm run gen-doc-graphs` 重新生成，`pnpm run verify-doc-graphs` 验证新鲜度，中文对侧通过双语配对维护。
  - 何时用：需要「跨包」视角而不是单包 API 时。
  - 怎么做：先看图声明的维护模式（generated / hybrid generated / curated），再决定是否相信它覆盖了你要找的边。

## 关键概念

- **Cordis**：dsh 底层的框架，插件向共享上下文贡献服务、类型化事件和可逆的副作用。
- **profile**：存放在 Harness home 中的具名组装，列出自身叠放的组合包、树外插件与用户 `cordis.patch.yml`；随发行版交付 `web`、`headless`、`sdk`、`sdk-minimal`、`acp`。
- **组合包（bundle）**：Cordis 配置项及其挂载代码的分发格式，插入内容始终可被其上各层 patch。
- **patch 层**：按 id 定位条目、替换其整个 config 或插入新条目的配置单位；`preset` patch 在目标 `config.plugins` 内生效。
- **能力接缝（capability seam）**：一项可替换能力，由声明接口的 Service Definition、实现它的 Service Provider、使用它的 Consumer 三角构成。
- **轮次（turn）与步骤（step）**：步骤是一次模型请求加上它调用的工具；轮次包含零个或多个步骤，在领取首条输入之前打开，在不再欠下任何工作时关闭。
- **会话日志**：模型所见上下文的来源，`deriveMessages()` 从中投影出模型历史；纪律是「模型可见即已记录」。
- **投影 seam（projection seam）**：`dsh-session-projection` 提供的 `ctx.sessionProjections`，已注册单元折叠已提交事件，载体通过 `snapshot()` 读取选定的客户端视图。
- **应用启动器（launcher）**：受支持 Node 应用唯一的启动路径，`dsh --profile <name>` 或 `dsh <name>`；`plugin` 表示管理命令，同名 profile 必须用 `--profile plugin` 选择。

## 心智模型

- 当要改行为时，先查归属映射再查目录树：映射表告诉你机制，目录树只告诉你位置。
- 把运行中的 dsh 看成「一个空条目列表 + 一串有序 patch 层」——`--dump-config` 打印出的任何条目，都可以被你自己的 patch 替换。
- 把 seam 看成一纸三方契约，而不是一个接口文件：只写其中一个角色不算接缝。
- 把会话日志看成模型的唯一事实来源：凡是模型能看到的输入，都必须能从日志重建。

## 反模式

- **为换实现而 fork 提供方**：seam 的存在意义就是「替换一个提供方就改变整个产品」；提供方专用 fork 会让这条通路失效，后面每个消费方都得跟着分叉。
- **把持久事实塞进 `agent/*`**：agent 事件携带活跃 `Agent`，是队列与状态的实时协调接口；需要回放的数据必须走 `session/event`。
- **绕过 launcher 直接挂载应用**：`verify-application-entrypoints` 把每个包 bin、可执行源码、根 demo 以及根脚本 `start:web` 与 `dev:web` 归入显式类别，并拒绝任何绕过 `dsh` 的 Node 应用路径。
- **只加消费方就宣称「加了能力」**：单一角色本身不是 seam，添加一项能力意味着把定义、提供方、消费方三者一并设计。
- **用 `dsh plugin` 期望启动同名 profile**：`plugin` 表示管理命令，同名 profile 必须用 `--profile plugin` 选择，直接写 `dsh plugin` 得到的是管理命令而不是那个 profile。

## 代码/配置示例

查看本机实际启动的配置树：

```sh
dsh --profile web --dump-config
```

对空条目列表依次应用的层序：

```text
profile 中有序的组合包
  -> profile 的 cordis.patch.yml
    -> home patch
      -> --patch overlay        (最后应用，优先级最高)
```

patch 的操作面（配置结构，不是语法示例）：

```text
patch 条目 = 定位 id -> 替换该条目整个 config
           | 插入新条目
preset patch = 在目标声明的 config.plugins 内做同样的操作，层优先级不变
```

两处声明字段：

```json
{ "dsh": { "profile": "<该 profile 的组合包列表>", "bundle": "<组合包的 patch 文件>" } }
```

## 参考表

核心包与它们的 `ctx` 键：

| 包 | 职责 | `ctx` 键 |
|---|---|---|
| `core/session` | 仅追加的 `SessionEvent` 日志和内存存储 | `ctx.sessions` |
| `core/system-prompt` | 提示词片段与工具 schema 的组装 | `ctx.systemPrompt` |
| `core/tools` | 作用域化的工具注册表和带把关的执行流水线 | `ctx.tools` |
| `core/agent` | `Agent` 接口、活跃 agent 注册表和 `agent/*` 事件 | `ctx.agents` |
| `core/agent-loop` | 实现该接口的默认驱动器 | `ctx.agentLoop` |
| `core/scope` | 按 agent 划分作用域的注册原语 | 库，无 `ctx` 键 |
| `llm/llm` | 消息与流式词汇表，以及适配器 seam | `ctx.llm` |

新行为归属位置（目标 → 机制）：

| 目标 | 机制 |
|---|---|
| 添加模型提供方 | 在 `ctx.llm` 上注册其适配器 |
| 添加面向模型的能力 | 在 `ctx.tools` 上注册；其 schema 加入提示词组装 |
| 让某个会话拥有不同的能力集合 | 组装一个 agent preset；其中的服务行需要 `isolate` realm |
| 添加 shell 执行 | 注册 `ctx.shell` 后端；本地后端通过 `ctx.subprocess` spawn 进程 |
| 添加持久化终端执行 | 注册 `ctx.terminals` 后端和 `dsh-tool-terminal` |
| 添加用户命令 | 在 `ctx.commands` 上注册；它无需模型轮次即可分派 |
| 管理后台任务 | 在 `ctx.jobs` 上注册；`job_*` 工具读取或停止任务 |
| 从外部 webhook 启动 Session | 在 `ctx.webhookRuntime` 上注册可信规则，并挂载提供方适配器 |
| 添加文件系统访问或策略 | 注册 `ctx.fs` 提供方，或监听 `fs/*` 事件 |
| 限制所启动的进程 | 使用 `ctx.sandbox` 后端；消费方在启动进程前包装 argv |
| 拦截请求、工具或轮次 | 使用相应的 `agent/*` 或 `tools/*` 事件；`agent/turn-stopping` 会停止轮次 |
| 添加模型可见上下文 | 调用 `agent.inject()`；它会落到下一次获准的请求中 |
| 添加 UI 或编辑器集成 | 驱动 `ctx.agents` 并从 `session/event` 渲染 |
| 添加 Web Client Chat 节点 | 注册 `ConversationNodeDefinition` + keyed renderer |
| 添加持久会话状态 | 扩展 `SessionEventMap`；从日志渲染和回放 |
| 生成会话标题 | 注册唯一的 `ctx.sessionTitle` 提供方 |
| 管理同会话目标 | 使用 `ctx.goals`；通过 `agent/*` 续跑 |
| 在轮次边界 fork 会话 | `ctx.agents.create({ sessionId, source, inheritedEventCount, meta: { isSeeded: true } })` |
| 在新后端存储会话 | 基于共享句柄脚手架实现 `SessionPersistence`（`create`/`open`/`stat`/`list`/`export`） |
| 将注册项限定到单个 agent | 使用该 agent 的 `agent.ctx` |

文档图索引：

| 图 | 模式 |
|---|---|
| 模块依赖图 | `generated` |
| 工具 schema 目录与包映射 | `generated` |
| 能力 seam 与核心服务 | `hybrid generated` |
| dsh 共享基础组合 | `hybrid generated` |
| 事件生产方／消费方矩阵 | `hybrid generated` |
| agent 轮次与步骤生命周期 | `curated` |
| 工具执行流水线 | `curated` |

## 实例演练

目标：给 Web 形态换掉模型提供方，同时不碰循环。

第一步是看清本机装了什么：`dsh --profile web --dump-config` 打印出配置树，它打印出的任何条目都可以由自己的 patch 替换。读这份树时按层序理解它：`web` profile 先叠 `dsh-base`（模型适配器、工具、持久化、沙箱与审批策略、设置、凭据、遥测），再叠 `dsh-web-app`（浏览器应用），之后才是 profile 自己的 `cordis.patch.yml` 与 home patch，最后是命令行 `--patch` overlay。

第二步是把需求对到映射表：目标是「添加模型提供方」，机制是在 `ctx.llm` 上注册其适配器。于是要做的事落在 `llm` 这个 seam 上——提供方注册实现，而 agent loop 与压缩功能调用的是提供方无关的流服务。这就是为什么换模型不需要改循环：循环只认 `ctx.llm` 的流式词汇表。

第三步才是配置动作：把要改的条目的 id 写成一条 patch，让它替换该条目整个 config，或插入一个新条目；如果希望它只对某些会话生效，则改为组装 agent preset，并给其中的服务行声明 `isolate` realm。

同一个需求在桌面形态下的边界不同：Electron 桌面应用在签名资源中携带精确匹配的 dsh 生产运行时，拥有保留的 `$DSH_HOME/profiles/desktop`；它与 npm CLI 共享产品数据，但包、启用选择与锁文件保持独立。所以桌面上的「换提供方」要在自己的 profile 与锁文件里做，而不是去改 CLI 的安装。

## 关键要点

1. dsh 没有特权内核；每部分都是插件，扩展方式是挂到旁边而不是打补丁。
2. 覆盖关系的唯一解释是层序：profile 组合包 → 其 `cordis.patch.yml` → home patch → `--patch`。
3. 选择事件域只需问一句：这个事实是否需要重新加载后仍存在。
4. seam 是 Definition + Provider + Consumer 三件套，加能力就三者一起设计。
5. 会话日志是模型上下文的来源，「模型可见即已记录」；改模型可见输入必须新增会话事件。
6. 图索引只负责生成目录未覆盖的关系，精确签名回子系统页与工具目录查。
7. 桌面、SDK、headless 共享产品数据但不共享包与锁文件，跨形态迁移要按各自的 profile 做。

## 关联

- **第 2 章**：本章只说 seam 是三件套，第 2 章给出已登记服务的角色、提供方与消费方全表与替换边界。
- **第 3 章**：本章的轮次流程只是骨架，第 3 章展开成交互时序与持久化纪律。
- **第 6 章**：三域事件的生产者／消费者矩阵。
- **第 15 章**：Cordis 插件模型本身（服务、事件、配置、HMR）。
- **第 38 章**：新增包、工具与插件的分步手册。
- **外部概念**：依赖注入容器与「组合根（composition root）」——profile 与 patch 层就是 dsh 的组合根。
