# 术语表

**agent.ctx** — agent 的带作用域上下文，可见性与生命周期同源（第 2、11 章）
**aggregate** — 一张独立可检查的 Project Reference 图（第 7 章）
**ApprovalPolicy** — 会话级审批策略：ask 委托链，never 确定性拒绝（第 30 章）
**AttachmentStore** — 不可变二进制附件的抽象 seam（第 35 章）
**brand** — 全局 symbol 为键的跨副本类型标识，Context.is 的判据（第 22 章）
**bundle** — Cordis 配置项及挂载代码的分发格式，内容可被上层 patch（第 1 章）
**canonical generation** — 同 Session 目录下数值最高、格式受支持的已提交产物（第 3 章）
**capability event** — 按 seam 命名的事件族（fs/*、tools/*），附加策略而不生导入循环（第 2 章）
**capability seam** — 三角色齐全的可替换能力整体：Service Definition＋Service Provider＋Consumer，绝非其中任一角色（第 1、2、11 章）
**card union** — generic/terminal/diff/read/search/web 六种 card 渲染意图（第 38 章）
**companion plugin** — 挂在 seam 旁、凭该类能力事件施加策略的插件（第 2 章）
**Config** — 双重身份：TS 接口给编译器，运行时 schema 给加载器（第 19 章）
**Consumer** — 只认定义不认提供方的调用方，典型是 tool-*（第 2 章）
**Context** — 服务容器，插件经 ctx 注册全部贡献（第 15 章）
**Cordis** — 底层框架：插件贡献服务、类型化事件与可逆副作用（第 1 章）
**declaration merging** — 用 declare module 扩充 Context/Events，只给类型（第 17、21 章）
**defineTool** — 把参数规约、输出 schema、渲染器与执行体打包成可注册工具（第 21、30、38 章）
**deriveMessages()** — 把会话日志投影为模型所见的 Message[]，缓存于 surface（第 1、28 章）
**dialect** — 某后端对被拒文件效果产生的 stderr 特征文本（第 32 章）
**disposer** — 撤销一次注册的资源释放函数，与注册成对（第 15、16 章）
**dsh.client** — 包清单声明浏览器插件身份的字段（第 36、38 章）
**dsh_ 前缀** — DeepSeek 请求正文中保留给 DSH 扩展字段的命名空间标记（第 13 章）
**DSH_SNAPSHOT=replay** — CI 强制的只读回放模式，录制留本地（第 8 章）
**effect** — 插件加载期间建立的、可被撤销的注册（第 16 章）
**exchange** — 从首个接纳真人输入的轮次到下一个这样的轮次的连续轮次（第 11 章）
**fail-closed** — 响应未过 schema 或 ID 校验时整批标为不明确（第 40 章）
**fiber** — 插件实例的运行时句柄，即 ctx.plugin() 的返回值（第 16、24 章）
**FinishReason** — 可合并扩展的结束原因，aborted/error 携带失败载荷（第 31 章）
**flush 检查点** — 唯一承诺「写入已熬过崩溃」的操作（第 33 章）
**Goal Round** — 为目标接纳的一次续行周期，触发一个轮次（第 29 章）
**hairline** — 中性 0.5px 边框，Chromium 绘为一个设备像素（第 14 章）
**harness 自有事件** — 由 harness 包而非内核声明并派发的事件（第 6 章）
**HMR** — 保存即卸载旧实例、加载新代码（第 20 章）
**human command** — 斜杠指令，经 ctx.commands 执行，不成模型消息（第 11 章）
**inherited** — vendor 源码固定提供的 ctx 成员与事件（第 25 章）
**inject** — 插件声明的服务依赖，未满足则停在 PENDING（第 15、17 章）
**inspect registry** — 模型面向的只读元数据通道 ctx.cordisInspect（第 34 章）
**JobView** — 每个读者消费的唯一作业投影（第 37 章）
**launcher** — Node 应用唯一启动路径 dsh --profile <name>（第 1 章）
**Loader** — 读 cordis.yml、解析指定符并挂载子插件的插件（第 15、20 章）
**managed range** — 提供方能观察并终止的进程集合（第 32 章）
**Mode** — 派发模式：emit/serial/waterfall/parallel/bail（第 6、23 章）
**monotonic guard** — 只能 deny 或 abstain 的闸门，在审批后、执行前（第 4 章）
**Native renderer** — output.render，把规范值转成可持久化内容（第 21 章）
**next()** — waterfall 中交棒下游的 continuation（第 18、23 章）
**patch layer** — 按 id 替换 config 或插入新条目的配置单位（第 1、9 章）
**PeerScope** — 一次调用的已准入主体（第 36 章）
**PENDING** — 依赖未满足，apply 未运行（第 16、17 章）
**Plugin** — 插件入口点联合：Function｜Constructor｜Object（第 26 章）
**pre-step** — 轮内、派生请求之前的步骤，计划唯一追加点（第 29 章）
**profile** — Harness home 中的具名组装：组合包、树外插件与 cordis.patch.yml（第 1、9 章）
**projection seam** — ctx.sessionProjections：折叠已提交事件，snapshot() 读客户端视图（第 1 章）
**PTC** — run_code 模式下的子调用，共用同一流水线（第 4、30 章）
**Ralph handoff** — 传给下一个 Round 的规范化有界结构化报告（第 11 章）
**Ralph loop** — 面向不可变目标的前台全新 agent 工作流运行（第 11 章）
**Ralph Round** — Ralph 循环中的一个全新子会话，不接收对话种子（第 11 章）
**Remote method descriptor** — 构建期生成的严格调用契约（第 5 章）
**replayState** — 适配器发出的最小无损 JSON 元数据（第 39 章）
**Round** — 承载一个轮次的外层策略迭代，计数器归策略（第 3、11 章）
**SandboxExecutionPolicy** — 一次调用解析出的完整沙箱策略（第 32 章）
**scope** — 按 agent 划分的注册单位，两层扁平不继承（第 2、11 章）
**scope carrier** — scope 过滤分发携带的 thisArg（第 11 章）
**scope key** — scope 的不透明标识，按对象同一性比较（第 11 章）
**scoped dispatch** — agent 活动以其 carrier 分发；注册表事件不过滤（第 11 章）
**Service** — 服务基类，子类加载时注册为 ctx.<name>（第 17、27 章）
**Service Definition** — 声明接口与注册面的那一侧（第 2 章）
**Service Provider** — 实现定义并按其注册形态注册的包（第 2 章）
**session log** — 模型所见上下文的来源，「模型可见即已记录」（第 1 章）
**SessionEventMap** — 仅追加的事件词汇表，可声明合并扩展（第 28 章）
**SessionHandle** — 通向已存会话的打开通道，close() 是唯一拆除路径（第 33 章）
**settlement** — 一次 attempt 的终局，落成 message 或 attempt（第 3 章）
**setup window** — 组装 agent 作用域环境的时隙，只做注册（第 11 章）
**shadowing** — 带作用域项仅在本 scope 内替换同名全局项（第 11 章）
**smoke test** — 启动已交付 profile、发一条提示词、检查外部世界（第 8 章）
**standing order** — root AGENTS.md 的常驻指令，一到三行并链接到家（第 12 章）
**step** — 一次模型请求及其引发的工具执行（第 1、3、11 章）
**StreamChunk** — 原始流式协议，封闭七变体联合（第 31 章）
**subagent tree** — 创建关系构成的执行拓扑，根为 lead（第 29 章）
**SurfaceOp** — 进入 surface 的方式：append 或闭区间 replace（第 28 章）
**tier** — 事实的归属层，「不属于此层」也是规则（第 12 章）
**TokenUsage** — 逐调用记账，计数互不重叠（第 31 章）
**ToolDefinition** — 模型 schema＋强制 output＋execute＋调度元数据（第 30 章）
**ToolExecutor** — 被选中的执行器：解析、调度、取消、记录（第 4、30 章）
**ToolGuard** — 作用域感知的最终预派发策略，只能缩减权限（第 30 章）
**ToolRestriction** — 单作用域对继承工具的实时过滤器，取交集（第 30 章）
**tools/execute** — 环绕分发瀑布，承担超时、重试、指标（第 4、38 章）
**tools/post-execute** — 结果侧瀑布，可接受、阻断、替换、追加（第 4 章）
**tools/pre-execute** — 第一个瀑布：钩子、权限、沙箱判断（第 4 章）
**turn** — 会话中一次对已接纳输入的排空（第 1、3、11 章）
**tutorial** — 沿有序路径走向结果，只引入当前所需概念（第 12 章）
**TypertRemoteService** — 绑定服务 key 与默认 Remote namespace 的基类（第 5、39 章）
**vendored** — 以源码纳入 vendor/ 的上游依赖，参与构建与改名（第 10、25 章）
**volatile field** — .volatile() 字段，变化时更新引用而不重挂载（第 19、25 章）
**waterfall** — 环绕中间件式分发，可包装下游返回值（第 15、18 章）
**watermark** — 同会话与 generation 下折叠取最大的 throughSeq（第 13 章）
**WebBootGraph** — 浏览器 entry 图（rev/entries/batches）（第 36 章）
**wire identity** — 复杂 Host 对象的 wire 稳定标识（第 5 章）
