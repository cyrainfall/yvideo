# 第 36 章：Web 客户端

## 核心思想

Web Client 不是「给 Host 套一层网页」，而是一个由独立加载插件装配出来的浏览器侧 Cordis 应用。它从 Host 只继承两样东西：`window.__DSH_BOOT__` 里的 entry 图，和类型化的 `ctx.remote`。其余一切——会话历史窗口、资源状态、布局、组件树——都由浏览器侧的 Client model 与 Slots 重新拥有。因此「加一个 Web 功能」的正确姿势几乎从不是改客户端源码，而是登记一条 entry 加若干 slot 贡献。

## 框架与方法

- **分层与所有权（six-layer ownership）**：按 Host 应用 → 传输与 API assembly → Client model → UI adapter → Conversation 数据 → 组合与渲染划分，每层有唯一 owner。
  - 何时用：判断一段状态或逻辑该落在哪个包。
  - 怎么做：依赖方向固定为 Host 状态 → Remote 传输 → Client model → UI adapter → Conversation 或 presentation → Slots → React；用户操作经 callback 反向进入注入的 Client service 或生成的 Remote namespace。硬判据：presentation component 绝不接收 Cordis `ctx`、transport object 或其他功能插件的实现。

- **WebBootGraph 与 lazy CommonJS 模块表**：`GET /plugins` 下的带版本 combo 脚本装配。
  - 何时用：新增浏览器插件，或排查某个插件为什么没被加载。
  - 怎么做：包在 `package.json` 声明 `dsh.client`（`platform: 'web'`、可选 `inject` 边、可选 `immediately`），并在 `exports["./client"]` 导出构建好的 bundle。Host 扫描 Loader entry 组合出 `WebBootEntry`／`WebBootBatch`，注入 `window.__DSH_BOOT__`；浏览器侧加载 bundle 只注册 factory，materialize entry 时才同步 `require` 运行 factory。两个调度阶段：`bootstrap`（parser-blocking）与 `application`（预加载）。完整 roster 到达 settled 且启动审计通过后，`ui-renderer` 才调用唯一一次 `renderSlot('root')`。

- **Remote 通信（generated service face）**：Host 服务在浏览器侧的类型化投影。
  - 何时用：功能要在浏览器读 Host 权威状态。
  - 怎么做：Host service 用 Typert `@Remote` 标注可调用 method，Host generation 产出严格 descriptor、runtime codec、declaration merge 与 source map；Client 侧 `api-remotes` assembly 把这些 method 挂到 `ctx.remote.<namespace>` 与 Session scope 的 `agentCtx.remote.<namespace>`。功能包只依赖生成的 service face，不依赖 Gateway 实现或 Host 包的运行时 entry。

- **Client models（Host face / Client face 配对）**：每个 API controller 包拥有配对的 Host face 与 Client face。
  - 何时用：某类状态要在浏览器渲染并接受命令。
  - 怎么做：Host 侧拥有权威 mutation 与 stream 生产；Client 侧基于同一份生成 wire type 维护 identity 稳定、与 React 无关的 model，公开 observable snapshot 与 command。`ClientSessions → SessionManager → Session` 与 `ClientWorkspaceModel` 是两个范式：前者拥有 list baseline、实时 update、惰性 Session instance 与 pull/后到 update 的冲突顺序；后者拥有顺序、归档、置顶与一元调用和流的竞态合并。

- **Slots（类型化 React 组合）**：`SlotMap` 是编译期注册表。
  - 何时用：往已有 UI 位置加内容。
  - 怎么做：包通过声明合并写入 key、cardinality、scope、owner props、keyed props 与可选 slot 级 inject face；拥有该位置的组件在 `children` 里给出对应运行时条目。贡献方写 `ctx.slots.inject(key, callback)`，callback 内 `ctx.slots.register({ name, id, order, ... }, Component)`。声明一个 child 同时产生三种效果：令该 key 生效、授权 parent 调 `renderSlot`／`renderSlotChain`、记录 dispatch 规格。

- **客户端资源模型（address as live data）**：一个地址变成任何组件都能读的活数据。
  - 何时用：内容由别的包拥有，但多个组件都要按位置读取。
  - 怎么做：地址形如 `dsh-resource://<type>/…`，小写 host 即协议键；协议拥有者在 `ctx.effect` 里 `ctx.resources.register({ protocol, open })`，`open(address, { signal })` 返回 `RemoteResult` 帧流（首帧当前状态，之后每次变化一帧，`signal` 中止即停）。组件侧 `useResource<P>(address)` 得到 `{ status, value, failure }`。持有 = 一个订阅中的 `useResource` 或一次 `ctx.resources.pin(address, signal)`；第一个持有者开流，最后一个释放时中止并丢弃值。

- **右侧 Sidebar（address-addressed docking）**：会话区旁一列 pane 与 tab，每个会话恰有一个停靠面。
  - 何时用：新增一种可按文件或页面打开的内容。
  - 怎么做：一个 tab 类型是共用定义 `id` 的两次注册——`ctx.sidebarRightTabs.register(definition)` 声明 `kind`／`patterns`／`priority`／`canOpen`／`title`／`keepMounted`，一次 keyed slot `sidebar.right.pane.tab` 提供正文。路由是一次排序认领：先按 priority 档（`extension` > `builtin` > `fallback`），再按最长命中模式长度，最后按注册顺序，`canOpen` 可同步否决。

- **HTTP 载体与准入**：`dsh-host-webserver` 只做监听、匹配、准入与 index 渲染。
  - 何时用：需要一条自定义 HTTP 端点或页面。
  - 怎么做：`register({ kind, path, handler | resource, auth })`；匹配顺序为精确 → 最长前缀 → 唯一 owner 的回退，upgrade 为精确匹配。`auth` 解析为 `anonymous`／`required`（默认）／`deny`；`deny` 不触发准入事件直接 403，其余触发同步 `webserver/authorize` 并采用首个决策。`renderIndex` 先渲染结构化 `IndexInjection` 行，再按注册顺序应用 `tapIndex` 逃生口。

- **Web 访问 seam（capability, not client）**：`ctx.web` 把 search 与 fetch 两项操作放进同一个中间层。
  - 何时用：区分「Harness 如何访问 Web」与「浏览器这一侧长什么样」——两者只是共享 web 一词。
  - 怎么做：提供方注册的是能力（`WebSearchProvider`／`WebFetchProvider`），不是工具；面向模型的名称、schema、提示词引导与展示全集中在唯一消费方 `dsh-tool-web`。选择在执行时解析，绝不依赖注册、配置或 HMR 顺序。

## 关键概念

- **`WebBootGraph`**：Host 组合出的浏览器 entry 图，含 `rev`、`release`、按 module-graph 顺序的 `entries` 与 `batches`；每个 entry 恰好归属一个初始 combo descriptor。
- **`dsh.client`**：包清单里声明「我是浏览器插件」的字段，同时给出 platform、inject 边与 `immediately` 预取标记。
- **`ctx.remote.<namespace>`**：生成的 Remote method 面，Host 服务在浏览器侧唯一被允许的调用入口。
- **`SlotMap`**：编译期 slot 注册表；cardinality 分 `single`／`list`／`keyed`／`chain`／`hoc`，scope 分 `root`／`session-maybe`／`session`。
- **`useResource(address)`**：全局标准 prop，返回 `status` ∈ `none`／`loading`／`live`／`failed` 的地址快照。
- **资源地址 vs 页面地址**：`dsh-resource://<type>/…` 指向资源；`sidebar://<kind>` 由 Sidebar 自己在 `openTab(kind)` 时写入，调用方从不拼。
- **`PeerScope`（Peer）**：一次调用的已准入主体；handler 与 resource 都从末尾参数取得它，`readResource` 复用调用方传入的 Peer。
- **`IndexInjection`**：index.html 的结构化注入行；每次 index 渲染重新采集，所以行数据在 emit 时刻是新鲜的。
- **`WebError`**：`extends HarnessError`，`code` 为开放字符串而非封闭联合，提供方可在不改 `dsh-web` 的前提下抛自己的码。

## 心智模型

- 当要给浏览器加功能时，把它看成「登记一条 entry + 若干 slot 贡献」，而不是「改客户端源码」。
- 把 `useResource(address)` 看成以地址为键的引用计数订阅：订阅即持有，最后一个离开才关流。
- 把 Remote 看成 Host 服务的类型化投影，而不是一条通用 RPC 通道——它只能调用被 `@Remote` 标注过的方法。
- 把右侧 Sidebar 看成按 `(kind, address)` 去重的历史栈：导航只是往这个栈上追加一条记录。

## 反模式

- **在 component store 里复制 transport state**：UI 包会拥有第二份业务真相，延迟响应与新 baseline 的合并规则无处安放。状态应留在 Client model，slot store 只承载共享的视图与交互状态。
- **功能包之间运行时 import 值**：跨包行为必须走注入的 Cordis service，跨包 UI 必须走 Slots；只有 `import type` 共享声明是允许的。
- **把 `web_fetch` 当沙箱内操作**：文件 sandbox preset 不管辖 Web 网络访问，HTTP 提供方也不限制目的地址——loopback、内网与云元数据主机都可达。要拦必须用网络隔离、`tools/pre-execute` 策略或不挂载抓取工具。
- **让 `available()` 发网络调用**：它被定义为廉价的本地检查（凭证是否存在、配置是否可解析），执行时用它选提供方；真正的「能否发得出去」由 `ready(llmProvider)` 回答，而就绪判断不是选择输入。
- **用注册顺序决定提供方**：多个可用提供方却未配置 id 时必须抛 `WEB_PROVIDER_AMBIGUOUS`，而不是选最先注册的那个。
- **依赖 `resync()`**：架构里没有统一 Client `Runtime`、`HostFrame`、`events.host` 或通用重同步 API，恢复语义由各数据域自己定义。

## 代码/配置示例

注册一条资源协议（Host / Client 两侧的协议键必须同名）：

```ts ignore-check
import type { Context } from '@deepseek-ai/cordis'
import type { RemoteResult } from '@deepseek-ai/dsh-typert-protocol'
import type {} from '@deepseek-ai/dsh-client-resources/client'

interface NoteView { readonly title: string; readonly updatedAt: string }

declare module '@deepseek-ai/dsh-client-ui-slots' {
  interface ResourceProtocolMap { note: NoteView }
}

export const inject = ['resources', 'remote']

export function apply(ctx: Context): void {
  ctx.effect(() => ctx.resources.register<'note'>({
    protocol: 'note',
    async *open(address, { signal }): AsyncIterable<RemoteResult<NoteView>> {
      const id = new URL(address).pathname.slice(1)
      yield await ctx.remote.notes.read(id, signal)
      for await (const change of ctx.remote.notes.follow(id, signal)) yield change
    },
  }), 'my-notes: note resource provider')
}
```

注册一个 tab 类型，并把正文挂到 keyed slot：

```ts ignore-check
export function apply(ctx: Context): void {
  ctx.effect(() => ctx.sidebarRightTabs.register({
    id: '@acme/dsh-client-ui-image',
    kind: 'image',
    patterns: ['*.png', '*.jpg', '*.gif', '*.svg'],
    canOpen: address => address.startsWith('dsh-resource://file/'),
    title: address => address.slice(address.lastIndexOf('/') + 1),
  }), 'image type')
  ctx.effect(() => ctx.slots.inject('sidebar.right.pane.tab', () => ctx.slots.register(
    { name: 'sidebar.right.pane.tab', key: '@acme/dsh-client-ui-image' },
    ImageBody,
  )), 'image body')
}
```

## 参考表

分层与 owner：

| 层 | 主要 owner | 职责 |
|---|---|---|
| Host 应用 | 业务 service 与 `packages/api/*-controller` Host entry | 权威状态、持久化、mutation 顺序、访问策略、stream 生产 |
| 传输与 API assembly | `client/connection`、`api/gateway`、`api/remotes` | 建立 Client generation、公开生成 method 与 stream、转发选定 Cordis event、承载取消 |
| Client model | `api/session-controller/client`、`api/workspace-controller/client` | 不依赖 React 的 Host 状态镜像、竞态处理、object identity、收窄的 command service |
| UI adapter | `client/ui-session`、`client/ui-workspace` | model observable → Session Slot source、视图级导航与状态策略 |
| Conversation 数据 | `client/ui-conversation`、`ui-chat`、`ui-trajectory` | 标准 event + 紧凑 Assistant 批次 → 相互独立的 target snapshot |
| 组合与渲染 | `client/ui-slots`、`ui-renderer`、`ui-layout`、各 UI 功能包 | 声明扩展位置、推导 props、绑定 observable、挂载组件树 |

数据通路：

| 路径 | 顺序 |
|---|---|
| 持久 Session 展示 | Host Session log → packed Remote `follow`／`page` → `SessionEventLikeEntry` window → Conversation Context → target snapshot → Slot view → React |
| 瞬态 Session control | Host control baseline → Remote snapshot stream → `SessionManager` projection store → Session 与 list snapshot → 标准 hook → component |
| 后台任务 | Host job 注册表 → `job.list`／`job.follow` → `ClientJobs` 名册与输出视图 → 列表与面板 |
| Workspace 状态 | Host baseline 与 increment → `ClientWorkspaceModel` → `ctx.workspaces.list` → `useWorkspaces` → sidebar／hero／navigation |
| scoped interaction | Host Cordis waterfall → API Remotes `$events` → Session Context 的 `ctx.remote.$on()` → 所属 UI 包 → result 或 `next()` |

恢复方式由数据语义决定：

| 数据 | 断开后如何恢复 |
|---|---|
| 持久 Session journal | 校验逻辑 seq range，按每代 opening snapshot 替换窗口；`page()` 补更早历史并修复后续 gap |
| Session control 与 Workspace stream | 保留最后一次发布的值，用新 opening baseline 原子替换 |
| 普通 forwarded notification | 不 replay；需要可靠恢复的域必须自备 baseline、cursor 或显式 query |
| scoped waterfall | 保留自身 request lifetime |

资源读取状态：

| `status` | 含义 | `value` | `failure` |
|---|---|---|---|
| `none` | 协议没有注册提供方，或地址不是资源地址 | `undefined` | `undefined` |
| `loading` | 流已打开、尚未产出 | `undefined` | `undefined` |
| `live` | 最新一帧成功 | 最新 `ok` 值 | `undefined` |
| `failed` | 最新一帧报告失败 | 保留的上一个 `ok` 值 | 该帧的 `RemoteFailure` |

## 实例演练

给右侧栏加一个「图片预览」类型，完整走一遍。

第一步是定义，不是组件。`ctx.sidebarRightTabs.register` 声明 `id: '@acme/dsh-client-ui-image'`、`kind: 'image'`、`patterns: ['*.png', '*.jpg', '*.gif', '*.svg']`、`canOpen: address => address.startsWith('dsh-resource://file/')`，`title` 取路径末段。priority 省略即 `extension`，因而压过内置的 `text`（它是 `fallback`，`patterns` 为 `dsh-resource://file/**`）。

第二步是注册时的副作用边界：两次注册都包在 `ctx.effect` 里，所以插件卸载时定义与正文一起消失，`extension` 注销后 `builtin` 自动恢复。

第三步是打开。用户在文件树里点一个 `.png`，文件树调用 `openResource(address)`；地址由 `fileAddressFor(sessionId, cwd, path)` 构造，含 Session 作用域。Sidebar 走四步：认领 → 聚焦已显示同一 `(kind, address)` 的 tab → 否则落新 tab → 展开这一列，然后把导航记入 Tab 域。认领阶段 `text` 与 `image` 都命中 glob，排序时 `image` 的 `extension` 档胜出。

第四步是稳定性。Tab 域为这条打开的记录保住一个 occurrence，等于在资源模型里钉住该地址；因此切到别的 tab 卸载正文不会丢内容，记录消失才中止并丢弃。撤销恢复的记录是新的 occurrence。

第五步是正文读取。`ImageBody` 的 props 里有 `useTabInfo()`（拿到 `panel.isFloating`、`tab.navigation.params`、会在记录消失时中止的 `tab.signal`）与 `useResource<'file'>`。`file` 提供方的值只是 `WorkspaceFileStat { absolutePath, version, bytes? }`——元数据，不是内容；真正读字节要经 `remote.workspaceFiles.readBytes`，失败时状态转 `failed`，此时旧值仍在，可以继续显示上一张图而不是空白。

一处容易踩空：`canOpen` 只在 glob 命中后生效，而含 `:` 的模式匹配整个地址、不含 `:` 的模式只匹配 URL 的路径部分且任意深度都中；`sidebar://guide` 不是资源地址，读作 `none`，不能靠资源模型判断它。

## 关键要点

1. 先分层再动手：状态归 Client model，位置归 Slots，跨包行为归注入的 service，跨包声明只走 `import type`。
2. 浏览器插件的入口是 `dsh.client` + `exports["./client"]`，不是修改 Web 应用本身；缺 bundle 会在组合期聚合报错并使 fiber 失败。
3. 组合期失败要响，稳态失败只记警告——启动审计拒绝启动的条件是必需名单中的 entry 未激活。
4. 用地址而不是对象引用传内容：`useResource` 让多个组件共享同一次观察，`pin` 让内容在正文卸载后继续存活。
5. tab 身份是 `(kind, address)` 二元组：同地址同类型复用，同地址两类型是两 tab。想增量扩展就新增 list／hoc id 或未占用的 keyed key。
6. 重连没有银弹：物理恢复归 Gateway mux，逻辑恢复归每个 `RemoteStream` 与各域自己的 replacement／resume 语义。
7. 别混淆两个 web：`ctx.web` 是 search／fetch 的能力 seam（提供方注册能力，工具在 `dsh-tool-web`），与 Web 客户端分层无关。
8. HTTP 侧只做载体：路由 auth 由载体执行，来源检查归 Connection，凭据验证归 ConnectionAuthentication，`readResource` 刻意跳过来源与凭据检查，但 `deny` 仍 403。

## 关联

- **第 14 章**：UI 设计与样式系统，是本层 slot 内容与视觉规则的判断依据。
- **第 5 章**：API 网关，定义 Remote 的 generation、取消、logical stream 与 `/api` carrier。
- **第 2 章**：能力接缝，解释为什么 `ctx.web` 用「一项能力两项操作」而不是一个通用 net 服务。
- **第 34 章**：扩展面，浏览器插件与 MCP、skills 同属「不改循环就加能力」的路径。
- **Cordis 生命周期**：`ctx.effect` 与 fiber dispose 是 slot 注册、资源提供方、路由注册三者共同的注销机制。
