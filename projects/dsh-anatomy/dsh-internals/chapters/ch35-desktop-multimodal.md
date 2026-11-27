# 第 35 章：桌面与多模态

## 核心思想

模型没有眼睛、手和耳朵，DSH 用五条各自独立的 provider seam 补上：浏览器操作、计算机操作、持久附件、Office 渲染、语音识别。它们的共同形状不是「一个通用多模态服务」，而是**共享服务只登记名字、提供方拥有工具与资源、所有权按 Agent 与 Session 计租、权限默认 fail-closed**。凡是试图把这些通道抽象成一个统一「设备接口」的设计，都会在真实差异（浏览器 vs 桌面、图片 vs 文档、输入 vs 输出）上崩掉。

## 框架与方法

- **只注册名称的共享服务（name-only registration）**：`ctx.browserUse` 与 `ctx.computerUse` 都只有一个 `register(name)`，作用域是「占住唯一提供方槽位直到 disposer 被调用」。
  - 何时用：当一个能力的提供方在形态上无法统一抽象时（Playwright MCP、Chrome DevTools MCP、Stagehand 的工具集各不相同）。
  - 怎么做：共享服务不提供通用操作方法、不持有浏览器/桌面资源、不提供模型可见内容；工具 schema、结果渲染、图像支持、配置与上游限制全部归提供方。第二次注册必须失败，**包括同名实例**——「只有一个」是契约，不是约定。

- **Session 所有权（session ownership）**：启动的浏览器属于使用它的确切实时 Agent 与 Session，跨轮次复用；Session 运行时释放时关闭其启动的资源。
  - 何时用：判断「这个浏览器/桌面实例的生命周期归谁」。
  - 怎么做：重新加载或 fork Session 时创建全新浏览器状态；浏览器 profile 与登录态**不从 Session 日志恢复**。附加（attach）的浏览器归外部所有：提供方在实例内把它保留给一个 Session，拒绝第二个 Session 同时附加，清理时只断开连接、让外部浏览器继续运行。

- **权限三件套（CuaAccess / CuaPrograms / 撤销）**：`ctx.cuaAccess` 暴露系统权限状态、用户主动申请与已保存的应用授权；`ctx.cuaPrograms` 管理 `cua_run_code` 的程序环境；两者都由 Remote 暴露给权限页面。
  - 何时用：任何要操作本机应用或窗口的动作。
  - 怎么做：app/window 操作在**分派前**执行提供方的授权检查；`revoke(id)` 删除已保存与会话内授权，但**已分派的输入不可撤销**；`retryApproval(id)` 只清除拒绝记录，不授予权限、不回放动作。请求权限不等于获得同意。

- **先持久化、后追加事件（persist-then-append）**：生产方把字节交给 `ctx.attachments`，只有对象完成持久化后服务才发布不可变的内容寻址引用；会话事件与模型可见的附件块只包含该引用及其元数据。
  - 何时用：任何进入模型输入或会话历史的二进制。
  - 怎么做：**绝不**写浏览器对象 URL、宿主临时路径、提供方 URL 或 base64 进日志。引用记录固有尺寸与编码长度，让客户端不必解码即可排布历史。

- **准入上限分层（admission limits before normalization）**：源文件限制（单图 ≤50 MiB、64,000,000 像素、单边 65,535 像素；每消息 ≤20 张、≤200 MiB）先于独立的规范化阶段执行；规范化默认长边 2048 像素、编码 ≤4 MiB。
  - 何时用：调图片相关配置或排查「为什么这条提示被拒」。
  - 怎么做：批量准入（`saveImages()`）先逐张验证、全部成功才发布，拒绝不会留下部分对象。

- **借用宿主授权（borrowed authorization）**：office-kit 的消费者负责源文件读取授权与展示；`ctx.officeKit` 只负责引擎、有界准入、临时输出复用与按 Session 划分的私有输出存储，**不创建 Session 事件**。
  - 何时用：把转换/预览接进新入口（Remote、工具、Web 预览）。
  - 怎么做：每次预览读取都重新检查渲染 generation、源文件授权与版本，再共享进行中的转换或缓存 PDF；转换在 Host 用磁盘输入输出，不在浏览器里跑引擎。

- **转写不是会话事件（transcription ≠ input）**：语音识别本身不写入 Session 事件，`transcribe()` 只返回文本；插入是一次可撤销的纯文本编辑，只有当录制前捕获的选区版本仍有效且提交状态允许编辑时才执行。
  - 何时用：接入新的输入通道。
  - 怎么做：切换 Session 或释放插件使迟到结果失效；音频不会回退到其他 provider；本地 provider 串行执行、限制队列。

## 关键概念

- **BrowserUseRegistry / ComputerUseRegistry**：只登记名称的唯一提供方槽位服务（`ctx.browserUse`、`ctx.computerUse`）。
- **CuaAccess**：系统权限与应用授权的 Remote 控制面（`applications()`、`systemStatus()`、`requestPermission()`、`revoke()`、`retryApproval()`）。
- **CuaPrograms**：`cua_run_code` 的程序环境宿主控制（`release()`、`releaseInputs()`、`screenshotRequestTarget()`）。
- **AttachmentStore**：不可变二进制附件的抽象 seam（`saveImage()` / `readImage()` / `admitPromptContent()` / `saveFileStream()`）。
- **FileUploads**：把浏览器上传与暂存凭证绑定到接收方 Agent 的 Host 服务（`ctx.fileUploads`）。
- **imageHostPath()**：只公开提供方所持对象的宿主位置，**不判断**当前工具执行环境能否读取它。
- **请求版本（RequestImageAttachment）**：按确切路由目标尺寸与字节目标派生的确定性编码版本，缓存键覆盖 attachment id、策略与固定编码参数。
- **SpeechProvider / SpeechSpec**：识别器与「已绑定 provider 的输入」；`resolve()` 之后不再回退。
- **OfficeKitGeneration**：提供方生命周期；替换后缓存 PDF 不再可复用。
- **cua-mcp profile**：把 computer use 提供给其他 harness 的独立组合包，每连接一个 Agent，不运行模型回合。

## 心智模型

- 把 browser-use 与 computer-use 看成**按 Session 计租的器官**：租期随 Session 释放结束，fork 等于换一具新身体，登录态不会跟着日志复活。
- 把附件看成**内容寻址的不可变对象，日志里只有指针**：日志永远不该出现字节、临时路径或 bearer URL。
- 把语音识别看成**草稿编辑器，不是输入通道的终点**：它只往输入框写字，提交仍是人的动作。
- 把 office-kit 看成**借用宿主算力的纯函数**：给它已授权的源与上限，它还你 PDF/PNG 字节，不产生任何会话事实。

## 反模式

- **在共享服务里补通用方法**：一旦 `ctx.browserUse` 长出 `click()` 之类的方法，所有 provider 都被迫实现一个公共词汇表，而它们的工具集本就不同。
- **允许第二个同名 provider 注册**：会让「当前是谁在控制浏览器」变成竞态；契约要求第二次注册直接失败。
- **把 base64 或临时路径写进会话事件**：日志是模型上下文的唯一真源，写进去就无法保证跨进程、跨 fork 可重建。
- **假设 fork 或 reload 后浏览器状态延续**：新的浏览器状态是刻意的安全默认值，profile 与登录态不恢复。
- **把转写结果直接写进会话**：识别不是提交；这会让「用户没发出去的话」进入模型历史。
- **用 office 转换触发 Agent 或 Session 事件**：转换是宿主算力调用，不是模型行为。

## 代码/配置示例

只注册名称的服务契约（提供方必须先停自己的工具并等待自有工作结束，才能释放注册）：

```ts cordis-catalog
/**
 * Reserve the sole provider slot until the contribution is disposed.
 * A second registration fails even when it repeats the current name.
 */
register(name: BrowserUseProviderName): () => Promise<void>
```

附件准入：把一张 base64 图片换成一个不可变引用，任何写入都发生在事件追加之前：

```ts
// Host prompt：每张图片计入单条消息张数与总字节上限；
// 已存储的图片按其上传字节数计入。被拒绝的内容不产生任何写入。
admitPromptContent(
  content: readonly AttachmentAdmissionPart[],
): Promise<AdmittedPromptContentPart[]>
```

撤销授权：已分派的输入不可回滚，这是设计而不是缺陷：

```ts
@Remote revoke(id: CuaApplicationId): Promise<void>
```

## 参考表

| 通道 | 共享服务（`ctx.*`） | 提供方 | 模型侧消费者 |
|---|---|---|---|
| 浏览器操作 | `ctx.browserUse` | Playwright MCP、Chrome DevTools MCP、Stagehand | 提供方自带工具，走常规执行管线 |
| 计算机操作 | `ctx.computerUse` + `ctx.cuaAccess` / `ctx.cuaPrograms` | macOS CUA（Swift helper）、Windows CUA（.NET helper）、Cua Driver MCP、Cua Driver 原生 | `cua_run_code` 等提供方工具 |
| 附件 | `ctx.attachments` + `ctx.fileUploads` | 本地内容寻址后端 | 图片/文件块，经会话事件引用 |
| Office | `ctx.officeKit` | `@deepseek-ai/libreoffice-kit`（原生或 WASM 引擎） | `office_render` / `office_convert` / `office_recalculate` |
| 语音 | `ctx.speechToText` + `ctx.speechController` | SenseVoice（本地）等 | 无（写入输入框，不写会话） |

| 权限类型 | 含义 |
|---|---|
| `CuaApplicationId` / `CuaApplicationGrant` | 平台提供的应用身份，以及显示给用户的已保存决定 |
| `CuaSystemPermission` | 用户选择申请的辅助功能或屏幕录制权限 |
| `CuaPermissionProcess` / `CuaSystemPermissionState` | 以 `darwin` / `windows` 标记的原生访问状态 |
| `CuaApplicationState` | 持久授权、拒绝记录，以及能否持久保存 |

| 限制（本地附件后端） | 值 |
|---|---|
| 每消息图片数 | ≤ 20 |
| 每消息图片总字节 | ≤ 200 MiB |
| 单张源图 | ≤ 50 MiB、≤ 64,000,000 像素、单边 ≤ 65,535 像素 |
| 规范化默认 | 长边 ≤ 2048 像素、编码 ≤ 4 MiB |

## 实例演练

用户把一张截图拖进输入框，随后提问。完整链路：

1. 浏览器把图片上传到 Host，`ctx.fileUploads.uploadImageStream()` 读取不超过部署上限的字节，校验、规范化并存储，返回一个**暂存凭证（receipt）**。取消发生在存储开始之前则什么都不存；已开始的存储仍留在内容寻址库里，但不会得到凭证。
2. 用户点发送，prompt 带着 receipt 进入 Agent inbox；`bindPrompt()` 把 receipt 绑定到这次 prompt 的 requestId，提交成功才保留绑定。
3. Host 在创建任何消息之前调用 `ctx.attachments.admitPromptContent()`：base64 图片被替换为 `ImageAttachmentRef`，逐张计入张数与字节上限；被拒绝则整批不写。
4. 只有这时才追加 `user/message`，事件里是引用与元数据，不是字节。
5. 模型请求组装时按该路由的 `ImageRequestTarget` 调 `readImageRequest()`：命中缓存只做有界元数据探测，未命中则编码出确定性版本，字节与尺寸都在硬上限内。
6. 若这条路由不支持图像，则不挂附件存储，提供方退化为文本诊断——不会出现「图片静默丢弃」。

对照的失败面：如果第 3 步失败（超张数或超字节），用户看到的是明确的拒绝，而不是一条「模型好像没看见图」的会话。

## 关键要点

1. 共享服务只登记名称；工具、资源、渲染与限制一律归提供方，第二次注册必须失败。
2. 浏览器与桌面实例按 Session/Agent 计租；fork 与 reload 得到全新状态，登录态不从日志恢复。
3. 授权检查发生在分派之前；`revoke` 之后已分派的输入不可撤销，`retryApproval` 只清拒绝记录。
4. 二进制先持久化、后追加事件；会话日志里只允许出现内容寻址引用与元数据。
5. 源文件限制先于规范化执行，批量准入要么全成功要么全不写。
6. office-kit 借消费者之权读源、只产出字节，不创建 Session 事件；语音转写同理，插入才是提交。
7. 判断一条通道是否接好：看它能否在「无 provider、无权限、被拒绝」三种情况下给出明确失败，而不是静默降级。

## 关联

- **第 28 章 会话与对话**：附件引用如何进入会话日志、`deriveMessages()` 如何把引用还原成模型输入。
- **第 30 章 工具、审批与调度**：`tools/pre-execute` 与 `ctx.approval` 是这些通道的授权入口。
- **第 26 章 Service API**：只注册名称的服务为何仍是一个完整的 Cordis Service。
- **第 31 章 模型流式与可观测**：`RequestImageAttachment` 的缓存身份与路由目标从何而来。
- **第 36 章 Web 客户端**：权限页面与 Office 预览如何通过 Remote 投影这些控件。
