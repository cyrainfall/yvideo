# 第 33 章：存储、设置与凭据

## 核心思想

「什么该持久、存在哪、谁能读」是三个独立决策。会话日志有自己的 seam（`SessionPersistence`），其余一切非日志数据走存储 seam（`ctx.storage` + 领域层）；两条 seam 都只交付**机制**，语义归声明方。设置与凭据是第三类东西——设置是可继承、可合并的配置分层，凭据是只能被**授权使用**、不能被读回的值。把凭据的值写进设置存储，是本章唯一要防的致命错误。

## 框架与方法

### 存储 seam：hub / provider / consumer

- **`ctx.storage` 是汇合点，不做 IO**：三段式是 Service Definition（`dsh-storage`）、Service Provider（`json` / `sqlite`）、Consumer 数据形式（`dsh-storage-domain`，**唯一**消费者后端约定的包）。
  - 判据：`backend` 是「名称 → 后端」表，多后端并排；路由归**消费方配置**（领域层路由表）而非枢纽，`register` 的 disposer 只注销名称。
- **数据形式挂在可声明合并的键 map 上**：`StorageForms` 由形式拥有者扩展；`mount` 是 effect，同键二次抛 `duplicate-mount`，未加载时 `form()` 抛 `form-not-mounted`——**排序即契约**。
- **后端 = 一个介质 + 可选操作组**：`kv` 是唯一已交付的组，缺组就省略，解析**响亮失败**而非降级。
  - 危险：**unit 不串行化写入，顺序归调用方**；批次中断**可能只应用一部分**；`unknown-state` 隔离该 unit 到 `close()`；`single` 原子替换后 `fsync` 失败→关闭重开；版本超出「当前 + 兼容」→`version-mismatch`，`per-record` 超出接受集合→**读作缺失**。
- **`DomainSpec` 是单一来源**：`defineDomain` 在**模块加载时**校验（`UNIT_NAME_RE`、global 不接受 `null`——它是「从未写入」哨兵）；读取同步自内存，写排在**逐领域写链**上（持久化 → 内存 → `domain/changed`），返回的记录**不是副本**。

### 持久化 seam：句柄、flush 与崩溃恢复

- **`SessionHandle` 是唯一入口**：全部日志访问 + 单写者所有权 + 跨进程租约；没有平行的持久化事件类型，`read` 句柄上修改是运行时 `SessionReadOnlyError`，二次 `open(id,'write')` 抛 `SessionAlreadyOwnedError`，撕裂尾部**永不返回**；`stat`/`list` 只给轻量快照与不透明修订号（相等即日志未变，不等则**不作任何承诺**），供派生读取模型缓存。
- **`append` 与 `flush` 是两级承诺**：`append` **尽力而为**（已接受、有序、本实例可见，但后端可合法缓冲），**只有 `flush` 承诺熬过崩溃**；从未实体化的会话在崩溃前等于**从未存在**。
  - 怎么做：`session/event` 是**同步**通知，后端路由进**有界 write-behind 窗口**（固定截止，后续事件**不重置**），到期后启动持久 `append`；`session/flush` 排空至停稳，是循环领取下一轮次前的观察点。
- **崩溃恢复是读方职责，修复只在写所有权之下写入**：持久化**不截断、不修复**，只返回物理有效的连续日志，仅丢弃撕裂碎片。
  - 怎么做：resume 经写句柄算 `interruptedTurnClosers`（缺失的工具错误、未闭合 `step/end`、合成的 `turn/end { reason: { kind: 'interrupted' } }`），发布前经同一句柄追加；`interrupted` 是**唯一非循环发出**的 `TurnEndReason`。
- **`SessionHeader` 与日志分居两侧**：元数据不进日志、到不了 `deriveMessages()`，**精确 fork 前缀长度是 Session 状态**；`agentPreset` 与 `delegationDepth` 必须持久（前者决定工具与提示词，后者让递归预算熬过重启）。

### 版本与迁移纪律

- **`version` 是当前格式，`compatibleVersions` 是旧版本戳清单**（只允许小于 `version`）：接受旧版本**不放宽校验**，单元版本戳无法在混合行里区分同名字段的不同含义，**读取器必须接受混合代际**（v3 读版本戳 2 时要解码其中未改动的 v1 值）。
- **兼容后继 = 提 `version` + 保留仍可读的版本戳 + 扩展同一 schema 的解码与默认规则**：消费者重写记录时才规范化值，**Storage 不分配记录版本**；**移除旧解码前必须重写并验证全部受影响记录**，不兼容变更需可恢复的升级——**没有值迁移执行器**。
- **普通打开不重盖戳**；空批次**不推进版本戳**。**不可逆边界**：JSON 替换后 I/O 失败或 SQLite 回滚本身失败时，**即使被拒绝，已存结果也可能未知**——停止使用、关闭、重开；回退靠写新格式**之前**的备份，**改小版本戳不逆转值转换**，领域兼容也**不迁移**物理 schema 与外层格式。
- `invalidRecords: 'backup-and-skip'` 只给可重建的派生数据（记录移开、open 继续）；**global 槽永远拒绝**。

### 作用域：身份与所有权分层

- **`ScopeKey` 不透明，`Scoped<T>` 是编译期品牌**：loop 用活跃 `Agent` 作 key 但原语**从不检视**它；`scopeTarget` 返回只负责路由的接收器，作用域过滤的事件以它作 `this` 类型，**主体仍作显式参数**。
- **`Scope` 的两个拆卸接口**：`rawDispose` 保留有序复合 effect 所需的 disposer 确切身份，`dispose()` 是公共停稳边界；`ScopeLayer` 整层空了才回收、**不丢兄弟 table**，读取**不创建 layer**。

### 设置：从 Config schema 投影出表单

- **设置服务从活动 profile 条目投影 volatile Config 字段**：配置编辑器经 Cordis patch 持久化，消费者对自己的 Config 引用调 `.get()`。
  - 判据：命名空间是**当前 profile 中可唯一定位条目的本地 id**，普通字段被排除；描述符带实际值、继承值、显式覆盖值与**乐观修订号**。
  - 怎么做：`update` 合并，`replace` 先重置为继承配置再应用，`mutate` 走独立路径并**保留客户端响应中未包含的秘密值**；每次写入验证完整 Config 并拒绝过期修订号。`settings/document-updated` 只是 **UI 通知**，远端每次读取都带 `redactSecrets: true`。

### 凭据：引用、记录与授权

- **凭据 seam 把机密挡在配置之外**：settings 分节与 `cordis.yml` 携带**引用**（POSIX 环境变量名），值归提供方（如 `dsh-credentials-local`）。
  - 判据：消费方**每个操作重新解析**、绝不跨操作缓存——LLM 适配器每次请求解析一次，轮换无需重启就作用于下一次请求；**空的存储值在任何地方都视为不存在**（`resolve` 跳过、`describe` 报未配置）。
  - 怎么做：`CredentialRef` 是品牌化环境变量名，`describe` 只答「能否解析、来自哪层、`set` 能否成功」；本地提供方把自有文件排在启动环境之前，保存值因此总是生效且可写的那层。
- **两种键空间是结构性分界**：`CredentialRef` 问「这个环境变量名背后是什么」，先查提供方存储再查环境后备——**可以分层**；`CredentialKey` 问「这个插件为这个 id 持有什么」，授权记录**没有环境可读**，存在即全部事实。
  - 判据：记录侧**只有 `modifyRecord` 一条写路径**（正确的写依赖当前值，token 刷新是同一把锁内的读-决定-替换），排他性在底层存储支持时**跨进程**成立，否则并发轮换同一 refresh token 会丢掉先写的那份；`listRecords()` 只列地址与标签——记录侧没有 settings schema 那样的发现路径。
- **授权是一次一个 key 的尝试，不是队列**：一个 key 只允许一个 flow（否则各写自己格式的记录→`DUPLICATE_FLOW`）；同一 key 同时只跑一次，第二个调用方**被拒绝而非加入**（`ALREADY_IN_FLIGHT`）；`cancel(key)` 独立于请求 signal（请求/响应传输只能靠第二次调用答复取消）。
  - 判据：`authorization/settled` 对**每种终态**都发；`credentials/record-updated` 与 `reference-updated` 刻意分开，因为两套键语法不相交，合成一个监听方就判断不出主体属于哪个空间；远端**完整机密只单向过线**。

### 启动装配与核心服务

- **装配顺序是契约**：`form-not-mounted`、`already-open` 都在说「插件顺序错了」。`ctx.configEditor.edit` 验证、持久化并**经正常 Loader 路径**协调下一份配置；设置页读的分层值就是 profile 的继承/覆盖层。
- **`scope/` 是核心组唯一的非服务包**：零依赖库，位于 `session/` 与 `system-prompt/` 之下以免成环；键走品牌化 `Branded<B>`（结构是字符串、类型上不可互换）。
- **创建/恢复是持久化元数据的唯一入口**：`ctx.agents.create({ sessionId, seed, meta })` 折叠 header，`resume()` 先加载持久会话；`AgentHandle.dispose()` 停循环、注销 agent、**把会话从 store 移除**、解作用域。

## 关键概念

- **枢纽 / 数据形式（hub / data form）**：`ctx.storage` 只登记名称与挂载点，`StorageForms` 经声明合并扩展。
- **`DomainSpec`**：领域声明的单一来源——`version`、`layout`、`compatibleVersions`、`invalidRecords`、`global`、`tables`。
- **`domain/changed`**：持久写入在后端确认后发出的通知（global 写时 `table`/`key` 为 `''`，`deleted` 是无值墓碑）。
- **`SessionHandle`**：通向已存会话的单所有者通道，`close()` 是唯一拆除路径。
- **flush 检查点**：唯一承诺「已熬过崩溃」的操作，也是循环领取下一轮次前的观察点。
- **`CredentialRef` / `CredentialKey`**：可分层解析的环境变量引用 / 不可分层、存在即事实的记录键。
- **`SessionFormatUnsupportedError`**：本构建拒绝解读某日志，与 `SessionPersistenceCorruptionError` 区分——数据没坏。

## 心智模型

- 存东西前先分 seam：**会话里发生过的事**归 `SessionPersistence`，**其余一切**归 `ctx.storage` 加一条领域声明。
- 把 `ctx.storage` 看成装配点而非数据库：一张名称表加一排挂载位，**全局默认路由就是设计错误**。
- 把 `append` 看成「进了缓冲区」、`flush` 看成「进了磁盘」：任何「我已 append 所以安全」都会在崩溃处翻车。
- 把 `compatibleVersions` 看成发给**旧数据**的通行证，不是给新代码的许可证：只覆盖解码，不覆盖校验与物理布局。

## 反模式

- **产品包直接 import 某个后端**：绕过「后端拥有介质、领域拥有语义」，换后端就得改产品代码。
- **在枢纽上配全局后端**：路由归领域插件，塞进枢纽会让两个消费方互相绑架。
- **把 `append` 的 resolve 当持久化成功**：后端可合法缓冲，只有 `flush` 承诺崩溃后仍在。
- **就地修改返回的记录**：拿到的是存储对象本身，必须整体 `put`/`update`。
- **把机密值写进 settings 分节或 `cordis.yml`**：配置要被读、投影、同步，那里只放引用。

## 代码/配置示例

```ts
const spec = defineDomain({
  name: 'projection-cache',
  version: 3,
  layout: 'per-record',              // 记录大、稀疏、可单独丢弃
  compatibleVersions: [1, 2],        // 当前 schema 仍解得开这两代
  invalidRecords: 'backup-and-skip', // 派生数据：坏记录移开并继续
  tables: { entries: domainTable<ProjectionKey, ProjectionEntry>(entrySchema) },
})
```

```ts
const domain = await ctx.storageDomain.open(spec)
ctx.effect(() => () => void domain.close())   // consumer 拥有这次 close
domain.table('entries').update(key, (prev) => ({ ...prev, hits: prev.hits + 1 }))
```

```ts
await handle.append(batch)   // 已接受、有序、本实例可见；崩溃即可能丢
await handle.flush()         // 唯一持久化屏障：此后其他进程也能看到
```

```yaml
# 形状示意：配置里出现的是引用名，不是机密值
llm:
  apiKeyRef: DEEPSEEK_API_KEY   # CredentialRef，值由 dsh-credentials-local 管理
```

## 参考表

| 维度 | `SessionPersistence` | `ctx.storage` + 领域层 | 凭据 seam |
| --- | --- | --- | --- |
| 管什么 | 会话日志、header、fork 前缀 | 一切非日志数据 | 机密引用与授权记录 |
| 形状 | 按 id 开**句柄** | 按名挂**后端**，领域声明 schema | 按引用解析 / 按记录键读写 |
| 并发 | 进程内单写者 + 跨进程租约 | unit **不**串行化，顺序归调用方 | `modifyRecord` 读改写排他 |
| 持久化 | `append` 尽力而为，`flush` 是屏障 | 写入完成即持久；批次可能部分应用 | 引用可分层，记录不可分层 |
| 通知 | `session/event`、`session/flush` | `domain/changed` | `credentials/reference-updated`、`credentials/record-updated` |
| 版本拒绝 | `SessionFormatUnsupportedError` | `version-mismatch` / `malformed-medium` / `invalid-record` | — |
| 并发拒绝 | `SessionAlreadyOwnedError` | 无此概念 | `ALREADY_IN_FLIGHT` |

| `layout` | 语义 | 适用 | 版本粒度 |
| --- | --- | --- | --- |
| `single`（默认） | 整个 unit 一份文档 | 权威、整块读写 | unit 级，超出接受集合即拒绝 |
| `per-record` | 每条记录一份文档 | 大、稀疏、可单独丢弃（投影缓存） | 逐文档，超出集合**读作缺失** |

## 实例演练

**投影缓存从 v2 升到 v3，历史混着 v1 的值。**

1. **声明**：`version: 3`、`compatibleVersions: [1, 2]`、`layout: 'per-record'`、`invalidRecords: 'backup-and-skip'`。`defineDomain` 在模块加载时校验名字匹配 `UNIT_NAME_RE`、global schema 不接受 `null`——介质还没被碰过。
2. **打开**：名字未打开（否则 `already-open`）→ 解析路由（`backend-not-found`）→ 要求 `kv` facet（`facet-unsupported`）→ 打开 unit → 逐条 zod 校验。两条派生记录失败，被 `backupRecord` 移开并记日志，open 继续、它们缺席。
3. **读写**：读取同步自内存；v2 时期未改动的值可能仍是 v1——当前 schema 必须解得开，`compatibleVersions` 只**允许**它们存在，校验没松。`update` 在自己的写链 slot 里原子读-改-写，顺序是「持久化 → 内存 → 发 `domain/changed`」。
4. **迁移**：没有迁移执行器。做法是扩展同一 schema 的解码与默认规则让读者接受混合代际；真要不兼容，必须先做可恢复的升级并留备份。
5. **失败**：某次 `single` 原子替换在目录 `fsync` 处报错——调用方看到拒绝，新文件可能已落地。正确的下一步是关闭后端及其领域、重开、检查已存状态，而不是重试。

**一次模型请求里的凭据路径。** 适配器带配置里的凭据引用（`CredentialRef`）发起请求，**在这一次请求上**调 `resolve(ref)`，拿到值与来源层；用户在设置页保存新 key，`set` 持久化后发 `credentials/reference-updated`，配置界面据此刷新徽标——但适配器**不需要**这个事件，下一次请求会重新解析，轮换立即生效。空字符串被 `set` 拒绝（要用 `unset`），因为空值在整条 seam 上都算不存在。

## 关键要点

1. 先分 seam 再选后端：会话日志走 `SessionPersistence`，其他一切走 `ctx.storage` 加一条领域声明。
2. 后端拥有介质、领域拥有语义；枢纽不做 IO，也不该有全局后端。
3. 领域名、表名、版本在 `defineDomain` 阶段校验，别等介质被写坏才发现。
4. `append` ≠ 持久；必须熬过崩溃处一律 `flush`；崩溃恢复由读方算、在写所有权之下写。
5. `compatibleVersions` 只发解码通行证：不放松校验、不规范化值、不迁移物理布局。
6. 出现「已存结果未知」时停止写入、关闭、重开——唯一安全的处置。
7. 配置里只放凭据引用；消费方按操作解析、不缓存，两个键空间不可混用。
8. 组合顺序是契约：`form-not-mounted` / `already-open` 是排序错误，不是重试信号。

## 关联

- **第 28 章（Session）**：仅追加的 `SessionEvent` 日志才是真源，本章的持久化 seam 只是让它落地；`interrupted` 也由那一章定义。
- **第 2 章（能力 seam）**：存储、持久化、凭据都是「Definition + Provider + Consumer」三段式，本章是最完整的三份落地。
- **第 34 章（扩展面）**：仓库外 provider 只要实现同一契约就能替换后端、存储后端或凭据来源。
- **第 36 章（Web 客户端）**：`stat` / `list` 的轻量修订号与投影缓存服务于派生读取模型。
