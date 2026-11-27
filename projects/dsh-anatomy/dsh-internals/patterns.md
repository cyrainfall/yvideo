# 技术与模式

<!-- 分组：结构与边界 -->

## seam 三角色与策略归属
**何时**：新增可替换能力，或要加的是策略而非实现。
**做法**：定义包只写 `ctx.<key>` 与词汇类型（Cordis `Service`），再给 provider、consumer；角色按谁声明/实现/消费判。判据：换 provider 是否改变模型发请求的方式，不该变才切对。consumer 直接 import 具体 provider、或需知道「当前哪个」即漏，该信息应成 provider 返回值。跨 provider 仍成立的规则写成接缝旁的事件插件。
**代价**：一个能力三到五包；策略靠事件派发，改名即静默失效。

## 注册形态五选一（registry shapes）
**何时**：写 provider 前，定多 provider 共存形态。
**做法**：命名注册表（`ctx.llm`）、单槽（`ctx.browserUse` 每实例一名）、有序尝试（`ctx.connection.authentication` 短路首个存活）、每上下文一实例（无具名表）、注册即绑定（`ctx.credentials` 只带引用）。
**代价**：形态随发布固化，事后换等于重写消费方。

## inject 表达顺序 + 组合清单补提供方
**何时**：有就绪顺序要求，或写 `cordis.yml`／新增贡献型包。
**做法**：硬依赖 `export const inject = [...]`，Cordis 让插件停 PENDING 到齐，`apply` 内即可用，配置行序无关；可选依赖不写，使用处 `ctx.get()` 探测。`inject` 是持续关系，provider 卸载或热替换连带卸载依赖方。清单前先问「注入的服务谁提供」，沿 `inject` 补齐。
**代价**：缺口只表现为静默 PENDING，须枚举 `ctx.registry.values()` 筛出。

## 作用域三选一与 `isolate`／`disabled`
**何时**：只在子树换语义，或反复编辑 `cordis.yml`。
**做法**：附加元数据 `extend(meta)`；换单服务 `isolate(name,label)`，同 label 同作用域，不传 label 每次新 symbol；服务配置 `intercept(name,config)`。隔离域**不回退**，域内无 provider 前读它抛错。稳定 `id` 才区分改配置与重挂载；临时关闭用 `disabled: true`，保留条目并连带重载 PENDING 方。
**代价**：隔离多出前置顺序依赖；`disabled` 连带停摆依赖方。

## 一份能力两份身份 + 服务存储五件套
**何时**：能力被多插件共用且可替换；常规 `inject` 表达不了。
**做法**：写 `Service` 子类，构造里 `super(ctx,'greeter')` 完成运行时注册，再用 `declare module` 把 `greeter` 加进 `Context`；缺一即「能跑没类型」。取名先查 `cordis-surface`。存储按权限选：`get(name,strict?)` 免注入、`set` 仅提供者、`provide` 归本 fiber 并返 disposer、`accessor` 算属性、`mixin` 转发到 `ctx`。
**代价**：扁平命名重名即冲突；绕过注入则顺序与生命周期全自负。

## 服务符号协议 + 编译期收口
**何时**：要改框架对服务的处理，或给跨包类型面开受控扩展点。
**做法**：注册点只在构造 `super(ctx,name)`；`[Service.init]` 做初始化、`[Service.check]` 声明可用性（依赖方按就绪而非存在判）、`[Service.invoke]` 支持可调用、`[Service.extend]` 派生。类型面用空声明合并 map（事件 payload、Host↔wire、资源 kind），边界用闭合联合 + `assertNever`，品牌判定用全局 symbol 不用 `instanceof`。
**代价**：符号键看不到调用链；每次扩能力都是多点位编译期改动。

## patch 层序与差分可观测
**何时**：改已发布组装装了什么，不动其内部。
**做法**：层序固定 profile 组合包 → 其 `cordis.patch.yml` → home patch → `--patch` overlay。patch 按 `id` 定位、替换整份 config，或插入新条目；临时改动走可重复的 `--patch`。判断是否命中只比对 `--dump-default-config` 与 `--dump-config` 的差。
**代价**：越上层越隐形；整份替换易丢未提及字段。

## 按编译器面拆包（双聚合／两份 program）
**何时**：一个包同时有 Node 与 browser 入口。
**做法**：默认不拆，两份运行时产物都在 Client 阶段生成。只有两侧在同一 `Context` 键下做不同声明合并、单 program 会冲突才拆：根 `tsconfig.json` 只作 solution，另带 `tsconfig.host.json` 与 `tsconfig.client.json` 两个 leaf；普通包只登记进一个 aggregate，共享 leaf 两侧同源引用。
**代价**：每拆一个多一套配置与门禁，Client 编译等 Host/Desktop。

---

<!-- 分组：生命周期与数据 -->

## effect 与 disposer 逆序
**何时**：任何装能力的动作，或拆除有先后。
**做法**：在 `apply` 里注册，返回的 disposer 被当前 fiber 收编、卸载时逆序清理；多个就返回生成器逐个 yield。状态放 `ctx.fiber`／插件实例，不放模块级变量。先盘点已属 effect 的注册（`ctx.on`、`ctx.plugin`、服务注册、`ctx.tools.register`）。disposer 逆序但异步并发，有依赖的几步放进**同一个** disposer 依次 await。
**代价**：`apply` 非 async，异步动作只能 `void (async…)()`，异常不冒泡；合并后不能单步重试。

## Config 契约与三态
**何时**：取参、运行中调字段，或排查配置没生效。
**做法**：同时写 `interface Config` 与 `Schema<Config>`，默认值进 schema（`.default()`），不在 `apply` 用 `??` 兜底；校验失败让 fiber FAILED。三态：`rawConfig` 原始输入；`effectiveConfig` 激活前 `undefined`、卸载后仍可读（判断运行中实例另查 `state`）；`resolveConfig()` 纯试算不发布。落地用 `update()`；热更新字段链 `.volatile()`，读到的值只在本操作内可用。
**代价**：`Config` 双重身份（导出普通对象即失效）；volatile 只收可递归冻结的纯数据。

## 事件：三域、分发模式与 waterfall 纪律
**何时**：新增事件、写监听器，或要插一手。
**做法**：三域——事实须重载后仍存→会话事件（追加日志 + `session/event` 广播）；观察/拦截进行中→`agent/*`；给 seam 加策略而不引入导入环→能力事件。可回放消费方只吃 `session/event`。按「要结果/要并发/可否拦截」选 `emit`/`parallel`/`serial`/`waterfall`；`bail` 默认不选，全表仅 `webserver/authorize` 一处。waterfall 里只观察的必须 `await next()` 并原样传回，不调即否决；抢先跑用 `prepend: true`。
**代价**：签名随模式固定；忘 `next()` 静默失效不抛错；bail 把 `0`/`''` 也算终止值。

## 不可变代际与迁移链
**何时**：改会话 header、事件封装或语义，或 `open` 旧会话。
**做法**：已提交 generation 路径绝不重命名/替换/删除；新版先编码校验，再旁路排他发布。读时取最高规范代际、拒未来版本，或只组装静态确定的相邻迁移链（每包只管 `vN→vN+1`，复用前一条边的 codec）。版本号只认 `SESSION_FORMAT_VERSION` 一个手工真源。结构差异不是升版理由，只有「判别信息不足以防不安全解释」才升；头未变也须写显式同版本决策，否则 `decision-required` 失败。
**代价**：每版永久保留旧代际；链条缺口/重复/多余边被生成器拒绝。

## 日志 fail-closed、崩溃留痕与续传水位
**何时**：设计日志兼容与恢复路径，或跨请求续传。
**做法**：未知事件默认「必需」，只纯信息性标 `ignorable: true`；入口 `isJsonValue` 校验，坏事件在 append 处失败。崩溃用「先写开始、后写结束」配对、锁最后释放，留下有 start 无 end 的可检测遗留。恢复不改文件，在写所有权下把缺失收尾当普通批次追加。续传首传 `afterSeq: -1`，此后从同 Session 最大已接受 `throughSeq` 之后带最长连续段；只为当前 Session id 与代际折叠水位，并发接受不能让游标倒退，fork 忽略继承水位从零重传。
**代价**：只读方须在内存配平冷日志且不回写；接收方幂等吞重发，不确定性只致重复、绝不缺口。

## 纯 fold、四级读与位置区间
**何时**：每轮重建历史；或要替换、遮蔽一段历史。
**做法**：派生 = 逐节点纯函数 + 缓存：尾部增长 O(新增)，遇 `replace` 整段重建；无关事件必须返回**同一引用**（`Object.is` 判，不变即零下游）。读配方 = 缓存 + 尾回放 + view，四级：`viewCheckpoint` → `cachedSnapshot` → `restore` → 全量重折；快照带 `asOfSeq` 并过 `viewSchema`。遮蔽范围按**表面顺序**的 seq 列表判，不用 `start/end` 数值（`start` 可大于 `end`），两端成对平衡。
**代价**：状态须纯 JSON、`apply` 须同步；`restoreFloor` 少一格即静默读过期行。

## 附件与不透明句柄
**何时**：二进制进入模型输入/历史；大对象要移出上下文。
**做法**：两级上限分离：源文件准入（尺寸/像素/张数）先于规范化，规范化（长边/字节）独立；批量全成才发布。**先持久化后追加事件**：只有对象落盘才发布不可变内容寻址引用，事件只带引用与固有尺寸，不写临时路径或 base64。句柄只暴露 `locator+bytes+retrievalHint`，按 hint 渲染不解析；本地写 `wx` 排他 + `0600`、根 `0700`，来源字段不是访问控制。
**代价**：多一次落盘与引用翻译；改图必走新对象，排障看不到真实位置。

## 并发写入：事务式贡献与 CAS
**何时**：贡献方随请求带状态；或多 agent 同领任务。
**做法**：贡献先序列化含确切 `messages` 的基础正文，provider 拿不可变正文、取消信号与 `sessionId`/`purpose`，`undefined` 表示省略；已准备 JSON 作顶层同级成员并入正文；失败三分（单方省略、冲突阻止整请求、不可序列化则跳过接受），`accept()` 只在 2xx 后、读 SSE 前。共享状态每条变更存完整快照，`revision` 作 CAS 值，写带 `expectedRevision` 不匹配即重读；依赖边无环，派生值在视图算；所有权用分配时捕获的不可变 agent 路径。
**代价**：贡献方自负重发；CAS 每次写要带修订号并处理重试；写范围只是提示性前缀。

---

<!-- 分组：子系统机制 -->

## 工具流水线层序与可见性
**何时**：判断一个拦截该写在哪一层。
**做法**：`tools/pre-execute`（钩子/权限/沙箱询问）→ 已注册的单调守卫 → `tools/execute` → 工具体 → `tools/post-execute`；`tools/result` 只观察已冻结结果。允许/拒绝/询问用 pre（waterfall 类型化决策）；不可撤销的最终拒绝用 `ctx.tools.guard()`；包裹分发生命周期（截止/重试/指标）用 execute；改结果/阻断/追加可见上下文用 post。模型可见 schema 用显式允许列表，判据「模型要用它决策吗」。
**代价**：层选错不报错，只表现为策略偶尔被绕过或展示与结果不一致。

## 工具内容：值三层与拒绝同构
**何时**：定义工具、定谁有最后改写权，或调试被拒调用仍有结果。
**做法**：`parameters` 只写规约，`defineTool` 转 JSON Schema、推 `args` 并校验；`execute` 只返回 `output.schema` 能表达的规范 JSON（参数错 `ToolArgsError`、返回错 `ToolOutputError`）。内容链：拥有者 `projectContent` 投影 → `post-execute` 接受/阻断/替换/追加 → `finalizeContent` 最后、同步、仅内容；注册表先对候选结果做无损快照，热替换不影响本次调用。模型可见文字 `render`、可回放卡片 `presentationMeta`、`presentCall/presentResult` 只出意图，三者必须纯函数（不做 I/O、不读会话、不用时钟随机）。拒绝跳过工具体但走同一后置链，产出与成功同构。
**代价**：三份表达须同源且被拒也付后置开销；下游须处理「结构合法但被拒」的结果。

## 单调守卫与审批闸门
**何时**：有安全边界、所有者策略这类不得重排的规则。
**做法**：注册成守卫，只能 `deny`/`abstain`，身份受保护，不是第二套允许列表。`ctx.approval` 在守卫前处理询问：pre 的 `ask` 进入一次性审批，`allowed-once` 才回到守卫——「先问人、再过闸」固定。`absent or unanswerable` 即 deny，守卫抛异常也不放行。软引导（提示词）与硬闸门（沙箱/审批）分开强制。
**代价**：放宽只能撤守卫；每个需人工放行的工具多一次往返。

## 子进程：argv 包装 + fail-closed 归因
**何时**：受限模式跑外部命令，或区分没跑与被拦。
**做法**：`confine(argv,policy,signal)` 返回新 `argv` 加 `enforcement` 与 stderr 分类器，不建进程；`danger-full-access` 不在受管模式，直接 spawn 原 argv。会话 cwd 即 `workspace-write` 边界，按文件实际位置规范化根；额外可写根运行时专属，resume/fork 后重注册。静默透传永不合法，失败给显式码。归因顺序：runner 失败规则 → 拒绝签名 → 进程自身失败；签名是**本后端方言**。spawn 零默认：不过 shell，省略 `spill` 只留内存尾部，`DSH_*` 先丢弃再合并。
**代价**：每后端维护文本方言表；每个调用点写全选项，`timedOut`/`aborted` 互斥。

## 子执行用 `stopReason` 而非异常
**何时**：写消费子代理或子执行的调用方。
**做法**：读四字段：`output`（最后非空 assistant 消息，退回累积流）、`structured`（仅 outputSchema 满足时）、`diagnostic`（抹掉工具输入/文件/环境/凭据，有上限）、`stopReason`（completed/aborted/error/max-tokens/refusal）。`result` 不因子级失败 reject：模型或传输失败结算成 `error`，由工具层映射 `isError`；只有无法表达成 stopReason 的基础设施故障才 reject。
**代价**：漏一个 stopReason 分支就把失败当成功。

## Remote 五步 + 单一失败类
**何时**：新增或改动 `ctx.remote` 端点。
**做法**：①owner 是 Host 侧服务，继承基类并绑 service 键与 wire namespace；签名合约定直接 `@Remote`，仅调形态才写 adapter；`signal` 放最后。②失败直接 `throw new RemoteError(code,msg,details)`，码名 `<域>/<理由>`，不建异常家族/出口映射，只有归并任意 provider 异常才 `catch` 挂 `cause`。③Client `inject` 声明 `remote` 与 `remote.<ns>`，就地判 `result.ok`。④写测试。⑤无关异常交 Gateway 折 `gateway/internal`。
**代价**：参数表必须纯业务词汇，取消/身份全在带外。

## 实例管理：三级身份与探测/挂载分离
**何时**：允许模型运行期写码即跑；或管理面试而不接。
**做法**：身份拆 Plugin（稳定）/Package（不可变版本）/Run（可撤销激活）：`define()` 出身份与首版，`run()` 起激活，`stop()` 只停激活、`undefine()` 才删；跨半调用带 `pluginRunId` 当能力凭证，下发源码只认当前激活 run 那侧。`probe()` 走完整流程但不碰活动实例，`mount()` 才挂载占名；替换与探测串行化，清理不完整就阻塞替换直到宿主重启。
**代价**：三层簿记，旧代码热更新后可能调旧实现；探测与 mount 平行，协议适配易漂移。

## 地址即活数据：首个持有者开流
**何时**：内容归别包所有，多组件按位置读同一份。
**做法**：资源给带协议的地址（`<proto>://<type>/…`），协议所有者 `ctx.effect` 注册 `{protocol, open}`；`open(address,{signal})` 返回帧流：首帧当前状态、之后每变一帧。组件 `useResource<P>()` 拿 `{status,value,failure}`；首个持有者开流，最后一个释放即中止并丢值。
**代价**：取一次性快照反而更绕；地址语法成跨包契约。

---

<!-- 分组：工程流程 -->

## 按要证明什么选测试层 + 只 mock 边界
**何时**：新增断言之前。
**做法**：先写命题再选层：局部行为/清理→单元；无未执行行→覆盖率；真模型对接→API e2e；组装后 CLI/进程→预期输出；耗时/堆/缩放→基准；组装后 transcript→快照；渲染/ARIA→浏览器快照。只 mock 高开销/不确定的三类边界（LLM 适配器、网络、时钟），其余真实；桥接测试用 `makeBridgeHarness()` 挂真注册表与管线，只 mock 适配器。
**代价**：同改动维护多条通道；测试更慢、定位面更大。

## 断言必须验证外部世界且能变红
**何时**：写涉及文件/命令副作用的断言，或新增回归守卫。
**做法**：e2e 重新运行命令或从外部重读文件，不对 agent 输出做关键词探测；对「未修改」断言逐字节一致。落笔先问：若 agent 撒谎，这条还绿吗？回归守卫必须引入一次回归 → 观察到变红 → 还原；两种状态都过的守卫什么也守不住。别只信委派回报，亲自在实际代码树重跑门禁。
**代价**：每条守卫先制造一次真实坏状态，验证成本翻倍且须准确还原。

## 测试真实入口路径（real entry path）
**何时**：新插件、新 CLI 入口、新 bundle。
**做法**：测已发布产物——`bin` 跑构建后的 `lib/bin.js`，由普通 `node` 执行，暴露 tsx 掩盖的结算竞态与解析；产品可见插件须有非单元的真实组合测试：经 Loader 与 app 进程启动测试用 `cordis.yml`，只 mock 外部服务或非确定输入。手写 `ctx.plugin()` 套件不够。
**代价**：要等构建，反馈从毫秒变分钟，失败可能来自构建。

## 生成物与文档预算
**何时**：生成物少一行/声明不符源码，或 `verify-doc-budgets` 变红。
**做法**：先分类：事件矩阵由 TypeScript Program 生成（`BEGIN/END GENERATED` 内可重写）；doc graph、`cordis-surface`、各 catalog、`cli-help` 由脚本再生成并受 freshness 校验；`ts type-equiv` 围栏在 `type-equiv.manifest.json` 登记镜像源。永不自改生成物。预算按 Relocate → Condense → Raise，ceiling 是护栏：低于目标留 5% 余量，高于目标冻结上限。
**代价**：小改走三步；预算冻结后写入节奏被牵着走。

## 命名：rescope 只改名 + 一概念一术语
**何时**：上游 sync 后、新增 vendored 包；或概念首次落地。
**做法**：查五元组（目录/上游名/发布名/版本/角色）让脚本改，只换 scope 与前缀，子路径导出不变；守七类不变量（目录与版本、依赖 range、`cordis:` 前缀、`*.cordis.yml` 家族、含该词的 harness 包、上游运行时标识符、`GENERIC_SKIPS`）。纪律：报告→施加→校验→回退，`--apply` 才写、`:check` 断言 post-state。概念保留唯一规范词，先判角色/层级/所有权再取名。
**代价**：白名单漏一项即改坏静默协议名；术语表需持续裁决。

## 堆叠评审：修复落在引入问题的 PR
**何时**：评审意见落在 `A ← B ← C` 链的多个 PR。
**做法**：每 PR 一 worktree，并行修复不共享 checkout。先对照代码验证评论，再把接受的发现映射到**引入它的** PR，按序向下传播。以 GitHub stack 对象为权威（`stack`/`stackEntry.position`），不凭分支链自称堆叠。每修独立 commit，只有未推送未评审的可 amend；传播用启用 rerere 的 rebase，改写历史推送受 lease 保护，禁 `--force`。
**代价**：同一修复在多 PR 重复，review 面变大；rebase 改 OID 需重新对账。
