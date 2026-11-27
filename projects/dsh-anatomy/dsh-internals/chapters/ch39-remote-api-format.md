# 第 39 章：远程 API、格式与适配器

## 核心思想

五类「接线型」改动共享同一种危险：它们都跨越一条已经发布的边界——Host 与浏览器之间（Remote）、已发布日志与未来读取器之间（Session 格式）、插件与用户之间（配置表单与系统消息）、模型与提供方之间（适配器）。跨边界的东西不能靠改实现修正，必须先声明契约。因此本章的每一步都以「生成物 + 检查项」收尾，而不是以「代码能跑」收尾。

## 框架与方法

- **新增 Remote 的五步**：声明 API → 声明失败 → 在包上注册 → 在 Client 消费 → 写测试。
  - 何时用：新增或改动一个 `ctx.remote` 端点。
  - 怎么做：owner 是 Host 侧 Cordis 服务，继承 `TypertRemoteService` 把 service 键与 wire namespace 一起绑定，再用 `@Remote` 标注对外方法。签名已符合 wire 约定就直接标注；只有形态需要调整（补 `signal`、换参数顺序、换导出名）才写 `remoteExport*` adapter，由它调用不改名的业务方法。lookup 对象（`Agent`、`Session`）只能占顶层参数位，协作式取消的 `signal: AbortSignal` 放最后一位。

- **单一失败类 + 码表**：不要建域异常家族，也不要写出口映射函数。
  - 何时用：任何新端点声明失败面。
  - 怎么做：失败点直接 `throw new RemoteError(code, message, details)`，域码经声明合并进 `RemoteErrorDetailsMap`。码名是 `<域>/<理由>`。只有「把任意 provider 异常归为一个域码」这一种场景才写 `catch`，并把原始异常挂在 `cause` 上。与本端点无关的异常不预先归类——Gateway 会兜底折成 `gateway/internal`。

- **Client 消费纪律**：调用点直写，不做类型体操。
  - 何时用：功能包要调 Remote。
  - 怎么做：`inject` 里同时声明 `remote` 与 `remote.<namespace>`，调用点写 `ctx.remote.<namespace>.<method>(...)`——不要用 `Pick<ClientRemote, …>` 窄化、不要手写方法签名、不要造 wire 中转对象。结果是 `RemoteResult<T>`，就地 `if (!result.ok)` 分支并判 `code`（会自动窄化 `details`）；异常流的站点写 `throw result.error`，上层用 `isRemoteFailure` 区分 Remote 失败与本地缺陷。

- **Session 格式版本：先判断该不该升**：只有有效判别信息无法阻止不安全解释时才升版本。
  - 何时用：改动 header、事件封装、事件语义或重建结构。
  - 怎么做：先按读取器兼容性规则评估；安全的同版本演进走类型变更流程记录，不升版本。要升时 N 取已接受或已发布版本（已接受 V4 则此次需要 V5）。用共享的 `release/*` 集成基线加写入器、codec、catalog 接线、恒等迁移与验证；各子分支的 PR 目标设为发布分支，而不是另一个子分支。

- **恒等迁移边 + Stage 实现**：恒等正文转换只是接线骨架。
  - 何时用：已经有了 N→N+1 这个版本决定。
  - 怎么做：按包检查清单建库（不是挂载插件），manifest 声明 `dsh.sessionFormatMigration`（数值 `from`／`to`、导出路径、迁移、源 codec、目标 codec、目标 header 校验器、目标恢复器）。复用前一条迁移边导出的源 codec 并依赖它，不要复制已发布 codec。实现 `Stage` 接口的 `transformEvent`／`transformRun`／`finish`，用 `context.emitEvent`／`emitRun` 同步输出零个、一个或多个结果，绝不共享可变 Stage。

- **catalog 是生成的，不是手改的**：`pnpm run gen-session-format-catalog` 只生成已声明的迁移链。
  - 何时用：加了迁移边声明、并把 `SESSION_FORMAT_VERSION` 改成 N+1 之后。
  - 怎么做：修声明而不是改 `generated.ts`。生成器要求从零到写入器版本每步恰好一个相邻迁移包、目录与包名匹配、相邻 codec 导出匹配，并拒绝缺口、重复或多余的边、未知元数据成员，以及未通过对等依赖加开发依赖共享 Session 的 catalog。

- **即时配置表单（config card）**：`Volatile<T>` 字段 + 产品所属的设置卡片。
  - 何时用：插件有需要热改、且不该等重启的字段。
  - 怎么做：Config schema 里声明 `z.string().volatile()` 之类的字段，接口类型写 `Volatile<string | undefined>`；在操作开始时读 `.get()`，需要一致快照的请求一次性捕获。跨字段校验用 `.check()`——它在持久化前由 Host 执行，不进序列化后的表单 schema。监听 `loader/volatile-update` 做响应。`role('secret')` 阻止值进入表单响应；由凭据域管理的值用凭据引用。

- **LLM 适配器的协议义务**：`StreamChunk` 的文档就是契约。
  - 何时用：接入新模型提供方。
  - 怎么做：`finish` **之前**发 `usage`，`finish` 之后**不再发任何内容**（稳健做法是缓冲到提供方的流结束标记再统一 flush）；工具调用 `arguments` 全程是原始 JSON 字符串，流式片段用 `argumentsDelta`，提供方返回已解析对象就在 `block-end` 重新 stringify；按首次出现的流顺序分配块 `index`，同块 delta 复用该 index；遵守 `options.signal`；无法支持的字段抛 `LlmError(..., 'UNSUPPORTED_OPTION')` 而不是静默丢弃。错误只有两条合法路径：从 `stream()` 抛出（传输与协议故障），或以 `finish { kind: 'error' | 'aborted' }` 结束（提供方带内故障）。

- **贡献系统消息**：一次注册 + 可撤通知。
  - 何时用：插件要往系统提示词加一段指令。
  - 怎么做：`inject = ['systemPrompt']`，`ctx.systemPrompt.section({ name, order, text, interpolate: false, replacement, retirement })`。`order` 不要写裸数字——第一方贡献应通过 `getSectionOrder()` 取所属位置。会变的内容保留一次注册、让同步 `text` 回调读当前状态，而不是反复 `section()` 覆盖。

## 关键概念

- **`TypertRemoteService`**：把 service 键与 wire namespace 一起绑定的基类，`@Remote` 的宿主。
- **`RemoteErrorDetailsMap`**：经声明合并扩展的码表；码名格式 `<域>/<理由>`。
- **`gateway/bad-request`／`gateway/cancelled`／`gateway/internal`**：protocol 已声明的载体码，直接用，不要复制。
- **`SessionFormatMigration`**：不可变的迁移声明，提供 `migrateHeader`、`validateTargetHeader`、`createStage`。
- **`headerInheritedEventCount`**：继承截点，是**逻辑事件数量**而非物理行数；只在 EOF 前已知时才公开。
- **`Volatile<T>`**：Config 里的可热改字段引用；`.get()` 在操作开始时读取当前值，`loader/volatile-update` 是热改后的通知。
- **`replayState`**：适配器发出的最小无损 JSON 原生元数据；只有历史路由与目标路由由完全相同的适配器实例拥有时才会被传递。
- **`UNSUPPORTED_OPTION`**：提供方无法支持某个 `GenerateOptions` 字段时的法定拒绝码。
- **`retirement`**：字面退役通知，trim 后必须非空；由最后一个被释放且曾被观察到的注册提供。

## 心智模型

- 把 Remote 看成「一张生成出来的类型面」：手写签名的地方就是错的地方。
- 把 Session 格式版本看成一个整数代表的**一族**受支持表示，而不是一个固定 schema——同版本日志会跳过相邻迁移，恢复后可能混合分支。
- 把配置表单看成两段式：页面只提交 `form.mutate(operations, expectedRevision)`，完整 Config 由 Host 校验并经 ConfigEditor 与 volatile HMR 落地。
- 把适配器的两条错误路径看成故障分类题：传输与协议故障「抛」，提供方带内故障「结流」。

## 反模式

- **建域异常类家族或出口映射函数**：失败面必须收敛到一张码表，否则 Client 无法只判 `code`。
- **写防御性 catch**：Remote 调用不 reject，装配错误就该炸；吞掉它只会把接线错误变成静默降级。
- **在 Client 侧断言 `instanceof`**：`instanceof` 在跨包、跨构建时不成立；判 `code` 才会自动窄化 `details`。
- **为了接纳当前功能放宽旧 codec**：已发布 codec 必须保留已接受的解释，历史可读性优先。
- **添加同版本迁移，或只依赖 `restoreCurrent` 归一化**：用 transformed 校验的当前版本 JSONL 读取会跳过该 hook。
- **以零替代未知截点**：`headerInheritedEventCount` 未知时必须不公开，而不是写 0。
- **把前代快照重命名成目标文件名或只改 header**：这会伪造一次升级，实际没有经过相邻迁移链。
- **省略 `interpolate: false`**：默认值是 `true`（为兼容性保留），可能替换 `{{name}}` 或因未知变量失败，即使文本由回调返回也一样。

## 代码/配置示例

Remote 服务与码表：

```ts
export class NotesController extends TypertRemoteService {
  constructor(ctx: Context) {
    super(ctx, 'notesController', { namespace: 'notes' })
  }

  @Remote('list')
  async remoteExportList(agent: Agent, signal: AbortSignal): Promise<NoteRow[]> {
    return await this.list(agent, signal)
  }

  async list(agent: Agent, signal: AbortSignal): Promise<NoteRow[]> {
    signal.throwIfAborted()
    return await Promise.resolve([{ noteId: `${agent.id}-1`, title: 'draft' }])
  }
}
```

```ts
declare module '@deepseek-ai/dsh-typert-protocol' {
  interface RemoteErrorDetailsMap {
    'note/not-found': { readonly noteId: string }
    'note/rejected': { readonly noteId: string }
  }
}
```

包清单要补的两个生成入口：

```json
{
  "exports": {
    "./typert": { "types": "./lib/typert.host.d.ts", "default": "./lib/typert.host.js" },
    "./remote": { "types": "./lib/typert.remote-client.d.ts", "default": "./lib/typert.remote-client.js" }
  },
  "peerDependencies": { "@deepseek-ai/dsh-typert-protocol": "workspace:*" },
  "devDependencies": { "@deepseek-ai/dsh-typert-protocol": "workspace:*" }
}
```

## 参考表

Remote 五步的产出与验证：

| 步 | 产出 | 验证方式 |
|---|---|---|
| 1 声明 API | `@Remote` 方法或 `remoteExport*` adapter | 签名：lookup 占顶层、`signal` 在末位 |
| 2 声明失败 | `RemoteError` 抛点 + 码表条目 | 测试用 `remoteErrorOf` + `toMatchObject` 比对 `code` 与 `details` |
| 3 注册包 | `./typert` 与 `./remote` 导出 + protocol 对等依赖 | 改签名／码表／namespace／导出名后重跑 `pnpm run build:lib` |
| 4 Client 消费 | `inject` 含 `remote` 与 `remote.<ns>` | 就地 `if (!result.ok)`，判 `code` |
| 5 测试 | 两侧 spec | `pnpm run typecheck` 过 Host 与 Client 两个 program，再 `npx vitest run <owner spec> <client spec>` |

错误码声明落点（四条）：

| 情形 | 落点 |
|---|---|
| 只有一个生产者 | 生产者包，紧挨抛出点 |
| 多个包共同生产 | 双方共同依赖的最低层域包（如 `session/not-found` 在 `core/session`） |
| 载体码与 Gateway 基础设施码 | 已在 protocol／gateway 声明，直接用 |
| 不上 wire 的本地失败 | 不进码表，用调用方自己的类型表达 |

版本轴必须分开：

| 版本 | 标识什么 | 不能替代 |
|---|---|---|
| Session 格式整数 | 日志代际 | — |
| 包发布版本 | npm 包发布序列 | Session 代际 |
| SQLite schema 版本 | 存储布局 | Session 代际 |
| 投影单元版本 | 缓存单元身份 | Session 代际 |
| 协议包装 `sessionFormatVersion` | 嵌入的 Session 代际 | 外层 schema 版本 |

适配器协议义务：

| 规则 | 违反后的现象 |
|---|---|
| `usage` 在 `finish` 之前，`finish` 后不再发 | 用量丢失或被消费方忽略 |
| `arguments` 全程原始 JSON 字符串，流式用 `argumentsDelta` | 工具调用参数无法拼装 |
| 块 `index` 按首次出现顺序分配、同块复用 | 内容块错序或串块 |
| 遵守 `options.signal` | 取消后仍占着连接 |
| 不支持字段抛 `UNSUPPORTED_OPTION` | 静默丢弃选项，行为与配置不符 |
| 错误只走「抛」或 `finish{error|aborted}` | 消费方一半路径收不到故障 |

系统消息准入检查（5 条）：

| # | 操作 | 期望 |
|---|---|---|
| 1 | 准入初始文本，再准入未变文本 | 第二次不增加系统更新 |
| 2 | 改变回调读取的状态 | 下次接受的组装只增加该节文本与替换通知 |
| 3 | 只改首尾空白 | 不增加更新 |
| 4 | 清理所有可见注册 | 已接收该节的 Session 收到一次撤回；新 Session 收不到 |
| 5 | 两次准入之间清理并恢复相同文本 | 不增加撤回或替换消息 |

## 实例演练

给 `notes` 域加一个 Remote，端到端走五步。

第一步声明：`NotesController extends TypertRemoteService`，构造时 bind `'notesController'` 与 `namespace: 'notes'`；`@Remote('list')` 标在 `remoteExportList(agent, signal)` 上，它委托给不改名的 `list(agent, signal)`。`Agent` 是 lookup 参数，`signal` 在末位。

第二步声明失败：在 protocol 上合并 `'note/not-found'` 与 `'note/rejected'` 两个码。`rename` 先 `stored.has(noteId)` 判断，不存在就抛 `note/not-found` 并带 `{ noteId }`；`persist` 抛错时归成 `note/rejected`，把原异常挂 `cause`——这是码表规则允许写 `catch` 的唯一场景。

第三步注册：包清单补 `./typert` 与 `./remote` 两个导出、protocol 的 peer 与 dev 依赖。因为改了签名与码表，必须重跑 `pnpm run build:lib`，否则 Client 拿不到新的声明与 codec。

第四步消费：调用插件 `inject: ['remote', 'remote.notes']`，`const result = await ctx.remote.notes.list()`；`if (!result.ok)` 里先判 `error.code === 'note/not-found'` 走空列表，其余 `throw result.error`。上层 `renderTitles` 用 `isRemoteFailure(error)` 判断：是 Remote 失败就渲染 `unavailable (code)`，不是就继续往上抛。

第五步测试：owner 侧用 `remoteErrorOf(failure)` 取失败，再 `toMatchObject({ code: 'note/not-found', details: { noteId: 'n-404' } })`——不要 `toEqual` 深比对错误对象，也不要断言 `instanceof`。Client 侧从 `@deepseek-ai/dsh-client-test-runtime` 取 `RemoteError` 与 `TestRemote`（从 `api-remotes` facade 值 import 会拉起尚未构建的装配链），`TestRemote.$host` 是普通字段，直接赋值即可。

最后跑 `pnpm run typecheck`：它会把 Host 与 Client 两个 program 都过一遍，码表的 merge 落点错了会在这里红——这是最省时间的一道门。

## 关键要点

1. 跨边界的改动先声明契约，再写实现；生成物（descriptor、codec、catalog、声明）是契约的落地形态。
2. 失败面收敛成一个 `RemoteError` 加一张码表；码名 `<域>/<理由>`，落点按四条规则选。
3. Client 只判 `code`，不判 `instanceof`；Remote 不 reject，所以不写防御性 catch。
4. 升 Session 格式版本前先证明「不升不行」；同版本演进要走类型变更流程记录。
5. 迁移用 Stage 而不是整份产物转换；截点是逻辑事件数，未知就不公开，绝不以零替代。
6. 配置字段用 `Volatile` + `.volatile()`，读取在操作开始时 `.get()`，跨字段校验用 `.check()`。
7. 适配器记住三件事：`usage` 在 `finish` 前、`arguments` 是字符串、错误只有两条路径。
8. 系统消息一律显式 `interpolate: false`，并把 `retirement` 写成有意义的字面文本。

## 关联

- **第 5 章**：API 网关——Remote 的 generation、取消、logical stream 与 `/api` 路由属于机制，本章只给动作。
- **第 3 章**：Agent 生命周期与会话格式——`SESSION_FORMAT_VERSION` 与已发布格式状态是升版本的输入。
- **第 33 章**：存储、设置与凭据——`Volatile` 的热提交与设置分层解析同源。
- **第 31 章**：模型流式与可观测——`StreamChunk` 与 `usage` 的时序约束出自那里。
- **第 38 章**：新增工具、包与插件——两条清单（包不变式、扩展点阶梯）在本章复用。
