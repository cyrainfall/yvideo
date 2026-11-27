# 第 34 章：扩展面

## 核心思想

Harness 的每一条扩展轴都长成同一个形状：**一个服务定义（service definition）、一组 provider、一个 consumer**；扩展包从不修改既有插件，只是把自己挂到别的插件旁边，由 Cordis 作用域（scope）决定谁看得见它。关键不是记住有几种扩展，而是认出这个三元结构在 MCP、动态插件、技能、LSP、webhook、代码托管上的投影。

## 框架与方法

- **服务定义 + provider + consumer 的三元结构（service definition / provider / consumer）**：全章总纲，三个角色分属不同的包。
  - 何时用：任何"新增一种外部能力"的需求，例如外部进程、语言服务器、浏览器页面或远端 API。
  - 怎么做：先定共享服务定义的所有者，再让每个来源各自注册 provider，最后由 consumer 在调用方作用域里选择并注册工具。技能族最完整（定义 `dsh-skill`，provider 有文件系统、随包徽章、Office 等多路，consumer 是 `skill` 工具与浏览器目录），LSP 最小（`dsh-lsp` / `dsh-lsp-stdio` / `dsh-tool-lsp`），MCP 把共享面收窄到资源。

- **分层注册表（host layer + per-scope layer）**：provider 注册落进注册者所在作用域的层，而不是进程级平铺。
  - 何时用：注册来源既有宿主全局插件，又有 preset 常驻组合挂载的插件时。
  - 怎么做：按 `scopeOf` 归档——宿主行与 repository 插件进全局层，preset 挂载的进 preset 层；读取时合并全局层与观察 scope 的链，最近层直接赢得重名，`rank` 只在单层内裁决。缓存以解析后的 scope 链为键，重设 scope 父级无需注册表变更即可被下次读取看到。

- **闭合联合而非通用逃生口（closed union）**：能力面用闭合联合定义边界，不暴露底层协议。
  - 何时用：把一个丰富协议（如 LSP）裁剪给模型时。
  - 怎么做：`LspOperation` 只留定义、引用、实现、悬浮四项，新增一项会在 seam、provider、tool 三处编译失败；结果侧同样闭合，consumer 用 `switch` 穷尽处理。seam 不公开协议类型、进程、文档控制，也没有 JSON-RPC 逃生口；`registerProvider` 原子占住 id 与每个点开头的扩展名。

- **扩展宿主的双半结构（Host half / Client half）**：扩展代码可以同时有 Node 侧与浏览器侧。
  - 何时用：需要 UI（面板、槽位、渲染）时；纯后台能力只需 Host 半。
  - 怎么做：Host 半是权威侧（状态、审批、生命周期），Client 半是可丢弃的渲染侧；Client 代码只在 run 被批准且页面存在时下发。

- **三级身份与按 run 授权（Plugin / Package / Run）**：稳定身份、不可变版本、可撤销激活。
  - 何时用：允许模型运行期写代码并立即运行的扩展通道。
  - 怎么做：`define()` 产出 Plugin 与第一个 Package，再 `define()` 是追加 Package；`run()` 针对某个 Package 激活并产出 Run。`stop()` 只停激活留版本，`undefine()` 才删全部。跨半调用按 run 授权：`invoke()` 收 `pluginRunId` 拒绝过期 Client run，`getClientCode()` 只发给恰好是当前激活 run 的那一侧——run 身份是凭证，过期即失效。

- **每服务器一连接的 MCP 客户端（per-server connection plugin）**：MCP 不在核心暴露共享 `ctx.mcp`，而是每台服务器一个客户端条目。
  - 何时用：接入外部 MCP 服务器，也包括反向场景——DSH 自己作为 MCP stdio 服务器对外提供能力。
  - 怎么做：为目标作用域里的每台服务器写一个 `@deepseek-ai/dsh-mcp-client` 条目；客户端消费工具注册表并注册副作用（拥有 `serverName` 与已发现工具），释放时关闭连接。名字只需作用域内唯一，工具名带服务器名。

- **探测与挂载分离（probe vs mount）**：管理面需要"试一下但不接入"的能力。
  - 何时用：设置页测试、启用前验证、排障。
  - 怎么做：`probe()` 解析模板、连接、列工具、关闭，不触碰活动实例；`mount()` 才挂载并占用名字。协调与 `restart` 串行化替换，探测独立运行并在替换前取消；清理不完整宁可阻塞。

- **三段式责任切分：适配器 / 规则 / 运行时（adapter / rule / runtime）**：外部事件接入不是一个大插件，而是三个可替换角色。
  - 何时用：把外部交付变成一次 agent 工作。
  - 怎么做：适配器只做身份验证与通用 JSON 接收；受信任的规则拥有条件与外部调用，`run(delivery, signal)` 返回 `null` 或 `WebhookSessionRequest`；`ctx.webhookRuntime` 拥有回调生命周期与 Session 创建。`WebhookEventMap` 可按种类合并，未知种类走 `WebhookEventOf<K>` 的无损 JSON 兜底，树外适配器无需改 runtime。

- **火后即忘分发（fire-and-forget）**：接入通道不承担可靠性。
  - 何时用：外部源自己会重投，或重复一次无害。
  - 怎么做：`dispatch()` 快照匹配规则、彼此独立调度、在任何回调结算前返回，抛出与拒绝按规则分别被包含；disposer 先移除规则再中止并排空活动调用。没有队列、重试、去重或完成结果——重复交付可能创建重复 Session，这是明示取舍。

- **统一服务表 + 未实现即拒绝（one service table, explicit refusal）**：桥接外部插件生态时，用明确服务表换掉"尽量兼容"。
  - 何时用：让 Claude Code 模组这类外部插件在本宿主上跑。
  - 怎么做：`defineMod({ name, version, root, userConfig, register })` 把模组包成普通 DSH 插件，走同一套 cordis.yml；`$` 是唯一途径，表外调用以 `no implementation for <namespace>.<method>` 拒绝，永不触发的事件在加载时点名警告。`next` 只运行一次；`tool.call` 在权限决定之后包裹 `tools/execute`，改写参数的钩子被跳过——日志里记下的调用按原样执行。

- **代码托管变更请求的 provider seam（forge seam）**：把"读 PR/MR"做成 seam，用省略与 head 提交把不确定性挡在写操作之外。
  - 何时用：让 agent 在会话内跟进远端变更请求。
  - 怎么做：`ctx.forge` 是定义，`forge-github` / `forge-gitlab` 是 provider，`ctx.forgeSession` 与 `ctx.forgePanel` 是 consumer。provider 声明 `hosts` 且任意两个不得列同一主机；`changeRequestKey` 不区分大小写，URL 拼法不同的监听方共用一个轮询循环。能力靠省略声明（省略 `viewer` 就不读用户列表，省略 `readReview` 就不能读评审）。评审读写点名 `headSha`：head 一移动，读 `stale`、写 `stale` 且不写入，写永不重试，`unknown` 须回主机核对。Session 绑定从日志折叠：provider 用 `registerCommands` 注册 CLI 规则，把 `gh pr create` 的 URL 记为 `created`、`pr view` 记为 `referenced`、`git push` 与面板分支触发 `discovered`、显式 URL 记为 `tracked`；绑定是 `plugin:forge-session/binding` 记录，在模型可见对话之外。

## 关键概念

- **动态插件（Dynamic Plugin）**：由 agent 在会话内定义、归属于某个 Session 的插件，身份为 `CordisDynamicPluginId`。
- **不可变包（immutable Package）**：某一版本的源码快照，`CordisDynamicPackageId` 一旦铸出就不再改变。
- **激活（Run）**：某个 Plugin/Package 在 Host 或 Client 上的一次具体运行，`CordisDynamicPluginRunId`。
- **检查注册表（inspect registry）**：模型面向的只读元数据通道，`ctx.cordisInspect` 同时持有 Host provider 与镜像的 Client provider 目录，并按平台路由查询。
- **资源提供方（resource provider）**：`McpResourceProvider`，由连接拥有、接收 `McpResourceRequest` 与 `ToolExecution`、返回无损 JSON 的对象。
- **服务器身份（`serverName`）**：在注册作用域内唯一的服务器键，同时充当工具命名空间。
- **调用策略（`SkillInvocationPolicy`）**：`modelInvocable` / `userInvocable` 两个正向布尔，把 frontmatter 归一化进领域模型，而非各 consumer 各判一遍。
- **完整性标记（`complete`）**：`SkillCatalogSnapshot.complete` 区分"确定的没有"与"发现瞬时失败或目录在变"；不完整快照从不缓存，下次查询重试。
- **已验证交付（`VerifiedWebhookDelivery`）**：`kind`、`source`、`deliveryId`、`event`、`receivedAt` 的冻结值；`deliveryId` 只是来源信息，runtime 既不存储也不去重。

## 心智模型

- 新增外部能力时先问"共享服务定义归谁"，而不是"代码放哪个包"——放错所有权，工具注册会跟着某个连接一起死。
- 把 Plugin / Package / Run 看成"仓库 / 提交 / 进程"：仓库稳定、提交不可变、进程可杀。
- 把 Client 半看成可随时丢失的缓存：页面一刷新就可能消失，权威判断永远在 Host 半。
- 把 provider 的可选方法看成一排开关：没装不是 bug，而是该平台不具备这项能力，调用方应降级而非重试。

## 反模式

- **在核心发布共享的 `ctx.mcp` 服务**：会让一台服务器连不上变成所有 MCP 工具消失；资源服务应独立拥有工具注册，只要可见客户端条目仍激活，连接失败就不移除共享工具。
- **用插件名而非 run 身份授权跨半调用**：旧页面会用旧代码调用新 Host；`invoke` 收 `pluginRunId` 就是为了拒绝陈旧 run。
- **把探测写成"挂载后立刻卸载"**：会占用名字、扰动活动实例，并让配置变更与探测互相阻塞。
- **把"不完整发现"当成"没有"**：provider 拒绝或目录在变时返回的是不完整观测而非空集；当成确定会误报 skill 不存在并污染缓存。
- **给 webhook 通道补可靠性**：在 runtime 上加去重会与适配器语义打架（`deliveryId` 只是来源信息）；要么让来源重投，要么在规则里处理重复。
- **把 forge 写操作当成可重试**：`unknown` 时重试可能重复提交评审；先按 `headSha` 重读再决定。

## 代码/配置示例

MCP 资源提供方契约——一个 provider 面对并发请求：

```ts type-equiv
/** One supported resource operation, with server-owned cursors and URIs. */
type McpResourceRequest =
  | { method: 'resources/list' | 'resources/templates/list'; cursor?: string }
  | { method: 'resources/read'; uri: string }
```

```ts type-equiv
/** One configured server's resource access, owned by its MCP connection plugin. */
interface McpResourceProvider {
  /**
   * Run an operation against one live connection generation. The resource tools
   * dispatch in parallel, so one provider may receive several concurrent requests;
   * each must settle independently.
   */
  request(request: McpResourceRequest, exec: ToolExecution): Promise<JsonValue>
}
```

动态插件的定义与激活（签名压缩自 `ctx.dynamicCordisRunner`）：

```ts cordis-catalog
define(request: DynamicCordisDefineRequest): DynamicCordisDefineReceipt
async run(agent, pluginId, packageId, mode, signal?): Promise<DynamicCordisRunResponse>
async runHostHalf(agent, pluginId, packageId, mode,
  requestId: ApprovalRequestId | null,
  approveFutureVersions: boolean): Promise<DynamicCordisHostHalfResult>
@Remote('invoke') async invoke(pluginId, pluginRunId, method, args): Promise<DynamicCordisInvokeResult>
```

技能 provider 的两个方法——`list()` 是"完整数组"或"显式观测"二选一：

```ts type-equiv
interface SkillProvider {
  readonly name: string
  readonly list: (options: SkillLookupOptions) =>
    Promise<readonly SkillCandidate[] | SkillProviderObservation>
  readonly get: (candidate: SkillCandidate, options: SkillLookupOptions) =>
    Promise<SkillDefinition | undefined>
}
```

LSP 结果的闭合联合——新增分支会编译失败：

```ts type-equiv
type LspQueryResult =
  | { readonly kind: 'locations'; readonly locations: readonly LspLocation[]
      readonly resolvedWorkspaceUri: string }
  | { readonly kind: 'hover'; readonly hover: LspHover | null }
```

Webhook 规则与分发（`run` 返回 `null` 就是"这条交付不创建 Session"）：

```ts cordis-catalog
register<K extends string>(rule: WebhookRule<K>): () => Promise<void>
dispatch<K extends string>(delivery: VerifiedWebhookDelivery<K>): void
```

Forge provider 的"省略即能力"（节选）：

```ts type-equiv
interface ForgeProvider {
  readonly forge: string
  readonly hosts: readonly string[]           // 两个 provider 不得列出同一主机
  readonly viewer?: ForgeViewerCapability     // 省略：不读登录用户列表
  readReview?(ref: ChangeRequestRef, headSha: string, signal: AbortSignal):
    Promise<ForgeReviewData | ForgeFailure>   // 省略：不能读评审
  merge(ref: ChangeRequestRef, request: MergeRequest, signal: AbortSignal):
    Promise<ForgeActionFailure | undefined>   // request.headSha 仍是 head 才合并
}
```

## 参考表

本地技能提供方的扫描顺序（rank 越小越优先，`<projectRoot>` 为含 `.git` 的最近祖先，找不到时用当前 cwd）：

| Rank | Source | Root |
|---|---|---|
| 100 | `project-dsh` | `<projectRoot>/.dsh/skills` |
| 200 | `project-agents` | `<projectRoot>/.agents/skills` |
| 300 | `custom` | `Config.customSkillDirs` |
| 400 | `user-dsh` | `<dshHome>/skills`（跳过其 `.system`） |
| 500 | `user-agents` | `<agentsHome>/skills` |
| 600 | `bundled` | 配置了 `Config.bundledSkillDir` 时使用 |

动态插件的生命周期方法归属：

| 方法 | 作用 | 是否保留版本 |
|---|---|---|
| `define` | 新建 Plugin 或追加 Package | —— |
| `run` / `runHostHalf` | 激活某个 Package（Client 半需批准） | 保留 |
| `stop` / `stopFromPanel` | 停止当前激活 | 全部保留 |
| `undefine` / `undefineFromPanel` | 删除 Plugin 及其全部 Package | 不保留 |

LSP 错误码分层（调用方按 `code` 路由，不要解析 `message`）：

| 错误码 | 抛出方 | 含义 |
|---|---|---|
| `LSP_INVALID_PROVIDER` / `LSP_CONFLICT` | Seam | id 或扩展名非法、或已被占用 |
| `LSP_UNAVAILABLE` | Seam | 没有 provider 处理该扩展名 |
| `LSP_WORKSPACE_REQUIRED` | `lsp` 工具 | 调用没有 Agent Session 工作区 |
| `LSP_FILE_OUTSIDE_WORKSPACE` | stdio provider | 源文件解析到规范工作区之外 |
| `LSP_SERVER_EXITED` / `LSP_PROTOCOL_ERROR` | stdio provider | 进程退出（消息带保留的 stderr 尾部）或分帧损坏 |

forge 的扩展点同样是三元结构：

| 扩展点 | Service Definition | Service Provider | Consumer |
|---|---|---|---|
| 评审数据 | `ctx.forge` 与 `forge/review-changed` 事件 | 各 forge 提供方 | 面板 Host 与其他 Host 插件 |
| 筛选透镜 | `ctx.forgePanel.registerLens` | Host 插件 | 经 `changesLens` 使用它的变更视图 |
| 变更视图接口 | `ctx.forgeChanges` | forge 面板的 Client 插件 | 打开视图、给透镜起名、加注解的 Client 插件 |
| Session 数据 | `forgeChangeRequests` / `forgeWorktree` 投影 | forge-session 与 forge 面板 | Client 插件经 `useProjection`，Host 插件经 `ctx.forgeSession.changeRequests` |

MCP 各关注点由谁维护：

| 选择 | 配置维护位置 |
|---|---|
| 服务器身份、本地进程或 HTTP 端点、凭据和进程环境 | 客户端配置 |
| 工具与资源请求超时、启动失败策略和重连 | 客户端配置 |
| 资源发现与读取 | 随附 profile 已包含 MCP 资源服务；该服务没有配置字段 |
| 服务器指令大小限制 | 客户端 `maxInstructionBytes`；组合提供系统提示词装配 |
| 权限决策和受支持的图像输出 | 工具执行与附件 |

## 实例演练

一次"模型想跑一个带 UI 的动态插件"的完整链路：

1. 模型调用 `define()`，传入 Session 归属、插件选择、元数据与源码。Host 铸出 Plugin 身份与第一个不可变 Package，回执带"声明了哪一半"的元数据。
2. 模型调用 `run(mode)`。若该 Client Package 未获授权，激活不会直接执行而是等批准：`cordis/request-run` 把关联身份、归属、目标版本、模式与审批要求广播给页面；Plugin 级授权可覆盖后续版本。
3. Host 半由 `runHostHalf()` 启动（`requestId` 为 `null` 表示用户在面板上的直接手势；`approveFutureVersions` 决定是否连后续版本一起批）。
4. 浏览器侧用 `getClientCode()` 取源码，只发给"恰好是当前激活 run"的那一侧；页面加载完成后用 `settleUserRun()`（用户手势）或 `resolveRequestRun()`（模型驱动）提交结果，二次结算被拒。
5. 运行期两条上报通道：渲染失败走 `reportRenderFailure`（槽位、消息、条目退休结果），被守卫拒绝走 `reportClientGuardFailure`（原始消息与堆栈）；都按 run 身份匹配，陈旧报告被忽略。
6. 浏览器调用 Host 方法走 `@Remote('invoke')`，携带 `pluginRunId`；想先了解运行时则走 `ctx.cordisInspect`：`list()` 拿两侧 provider 目录，`query(platform, providerId, methodName, ...)` 在归属平台执行。
7. 收尾：`stop()` 停激活留版本，`undefine()` 连版本一起删；两个 "FromPanel" 变体额外把状态变化排进模型下一步的上下文——用户点了按钮，模型下一轮就知道了。

同一个结构在代码托管上的走法：用户点合并时带上自己看到的 `headSha`；provider 合并前再核对 head，若有人推了新提交就返回 `stale` 而不是合错提交。成功后 `ctx.forge` 立即轮询，新状态经共享轮询循环送到所有监听方。

## 关键要点

1. 新增扩展前先定所有权：共享服务定义要独立于任何单个连接，否则一个连接失败会带走全部工具。
2. 动态插件用三级身份治理：稳定 Plugin、不可变 Package、可撤销 Run；只停激活不删版本，只有 `undefine` 才真正删除。
3. 跨半调用一律按 run 授权，`pluginRunId` 是凭证不是参数装饰。
4. MCP 一服务器一连接；名字在作用域内唯一，工具名带服务器前缀，资源调用必须显式点名。
5. 探测与挂载分离，替换串行化，清理不完整宁可阻塞也不要半替换。
6. 可选方法即能力开关：省略要在契约里写明语义，调用方降级而不是重试。

## 关联

- **第 2 章**：能力缝（capability seam）与本章三元结构是一体两面——缝决定"谁能替换谁"，本章决定"扩展怎么挂上去"。
- **第 20 章**：Cordis 组合决定作用域，作用域决定扩展可见性与继承。
- **第 36 章**：Client 半的运行环境就是 Web 客户端，浏览器一侧在那里展开。
- **第 4 章**：MCP 工具最终进入工具执行管线，权限与结果替换规则由该章维护。
