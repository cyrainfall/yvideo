# 拆开 DSH — 系列大纲

> 六集，每集 2–4 分钟。每集只回答一个问题，下一集接着上一集的道具。
> 所有上屏的路径、配置字段、事件名以仓库当前版本为准（`/Users/cyx/repo/deepseek-harness`）。

## EP01 模型只会说话 ✅

**问题**：模型只会吐 token，谁把它变成行动？
**答案链**：三处不能（手 / 记忆 / 时间）→ 缺一台 harness → dsh 没有内核，一切皆插件 → 一句话过六站（启动 / 输入 / 组装 / 请求 / 工具 / 落盘）→ 连 agent-loop 也是插件 → Cordis 是底座。
**证据**：`docs/architecture.zh.md` 的轮次流程图；`packages/core/agent-loop/src/agent.ts:332`（`turn/start`）；`packages/bundle/base/cordis.patch.yml:546`（`agent-loop` 那一行）。
**留的钩子**：下一集从「一行插件」开始。

## EP02 一切皆插件 ✅

**问题**：一个插件到底是什么东西？
**答案链**：插件 = 实现 Service 的对象；上下文是容器，服务挂在稳定键上（`ctx.tools` / `ctx.llm` / `ctx.sessions`）→ 依赖用 `inject` 声明，加载顺序由依赖决定 → 通信靠类型化事件（emit / waterfall / parallel / serial / bail）→ 注册是可逆副作用，必须带回卸载函数。
**现场演示**：一个最小注册表 + 一个工具插件，真跑一遍：`+ greet` → 调用成功 → 卸载 → `ERROR: no tool named "greet"`。
**证据**：`docs/cordis-primer.zh.md` 五件套与分发模式表；`packages/core/tools/src/events.ts` 的 `@mode waterfall` 注释。

## EP03 把树拼出来 ✅

**问题**：`dsh web` 之后，那棵树是怎么长出来的？
**答案链**：profile（具名组装）→ bundle（可被上层 patch 的分发格式）→ patch 按 id 定位一行、整块替换 config 或插入新行 → 叠加顺序：profile 的有序 bundle、`cordis.patch.yml`、home patch、`--patch` overlay。
**现场演示**：`dsh --profile web --dump-config` 真打一次——3491 行 / 235 条，屏幕上按真实行号标出 1 dsh-base、628 web-app、1539 第一个装进来的插件、3460 profile patch、3475 home patch。
**证据**：`packages/bundle/base/cordis.patch.yml` 顶部注释（一行一个 bundle 层）；`packages/boot/app-boot/`。

## EP04 一轮对话 ✅

**问题**：一次「提问—回答」在代码里长什么样？
**答案链**：turn 是排空已接纳输入的循环（不是一次请求）→ 循环里每次模型请求加它引发的工具是一个 step → 每一步都写进同一本日志，只追加 → 只有带 `surfaceOp` 的五类事件进模型可见的历史，`replace` 用于「换掉一条」和「上下文太长把一段换成摘要」→ `deriveMessages()` 把日志投影成消息数组，纯追加时只算新增 → 所以重启、fork、恢复都只是重读日志、从断点往后追加。
**现场演示**：拿本机一份真实会话日志（快照存在 `capture/ep04-session.v4.jsonl.zstd`）逐行指认 turn 8 的十行；同一份日志里数出 3307 条事件 / 996 条带标记 / 17 个 turn / 453 个 step / 481 次工具调用，以及 16 个已收尾 turn 的结局分布（completed 7 · aborted 5 · error 4）。
**证据**：`packages/core/agent-loop/src/agent.ts` 的 `turn()`（:323）与 `step()`（:431）、`:395` 的循环出口；`packages/core/session/src/index.ts:778` 的 `deriveMessages()`；`packages/core/session/src/types.ts:454`、`:477`；`packages/core/session/src/fork.ts:21`。

## EP05 工具：模型的手 ✅

**问题**：模型说「跑一下测试」，中间经过什么？
**答案链**：工具是注册进来的，不是写死在循环里 → 注册可以写在全局或某个 agent 名下，近的盖住远的；`allow`/`deny` 只对全局工具生效、逐层求交 → 所以模型每步拿到的是一张**算出来的菜单**（工具目录 37 个包 / 76 个名字；这一份会话只用了 6 个）→ 一次调用过五站三段：`tools/pre-execute`（放行 / 拒绝 / 取消 / 问人）→ 单调守卫（只有拒绝和不管，没有 allow，顺序翻不回来）→ `tools/execute`（超时、指标挂在环绕分发上）→ 工具自己的 `execute()` → `tools/post-execute`（接受 / 换内容 / 接上下文 / 驳回）→ 只有 `ask` 会离开程序：交给 approval 服务，没有通道就等于拒绝，子 agent 被钉成 `never`，沙箱升权又是一次 `ask` → 返回值不是终稿：`projectContent` → `post-execute` → `finalizeContent` → 冻结快照 → `tools/result` → 手可以换：`ctx.shell` / `ctx.fs` / `ctx.sandbox` 三个 seam。
**现场演示**：还是那份真实会话日志（`capture/ep04-session.v4.jsonl.zstd`）：481 次工具调用 / 6 个工具 / 353 次 bash；中位数 54 ms、305 次在百毫秒内、19 次超过一分钟、最慢 152 s；三次以 isError 回来（unknown job / .png not found / file not found）；一次（seq 3305）在快照定格时还没有结果。
**证据**：`packages/core/tools/src/index.ts:128`、`:162`、`:214`–`:222`、`:251`、`:264`、`:394`；`pipeline.ts:201`、`:214`、`:311`、`:429`、`:509`；`contracts.ts:375`、`:386`、`:410`；`events.ts:18`、`:29`、`:41`、`:49`；`interaction/user-approval/src/index.ts:69`；`subagent/subagent/src/child-agent.ts:223`、`:240`；`sandbox/sandbox/src/escalation.ts:64`；`guard/timeout-policy/src/index.ts:56`；`docs/tool-catalog.zh.md`。

## EP06 改它 ✅

**问题**：我想加一个自己的东西，从哪下手？
**答案链**：加东西是加一个包，包有三个出口——工具（`ctx.tools.register`，面向模型）、命令（`ctx.commands.register`，面向人）、界面（`ctx.slots.inject/register`，面向界面）→ 工具跑完是 `tool/call → tool/result`，进日志也进模型历史；命令跑完是成对的 `command/run → command/done`，**log-only**，永远不进模型可见的历史 → 命令也分层：全局的与挂在 agent 名下的，近的盖住远的（和工具同一套规矩）→ 界面半边只注册一个工厂，真正挂上去是 `ctx.slots.inject('conversation.composer.dock', …)` 加 `ctx.slots.register({ id, order }, Dock)` → 一个包 = `package.json`（`dsh.bundle.patch` / `dsh.client`）+ `cordis.patch.yml`（`- insert: id / name`），安装就是第三集的 patch 再走一遍 → 装的结果看 `application`：`applied` 是已经活了，`restart-required` 带五种原因之一。
**现场演示**：造一个真包 `demo/greet/`（一个工具 + 一条命令 + 一个 dock 面板），`plugin_manager install_bundle` 装进本机 `web` profile（`application: applied`，工具清单多出 `greet`，dock 多出 `{ id: "greet", order: 50, active: true }`），再 `remove_bundle` 卸干净（占位 7→6，profile 的 package.json / patch / node_modules 无残留）。收据在 `demo/receipts/`。
**证据**：`packages/core/tools/src/index.ts:128`；`packages/interaction/commands/src/index.ts:285`、`types.ts:34`、`:105`、`:112`；`packages/goal/command-goal/src/index.ts:193`；`packages/client/ui-slots/src/index.ts:1269`；`packages/client/modules/README.md`；`packages/boot/plugin-manager/src/types.ts:52`、`:174`；`packages/boot/hmr/src/index.ts:937`；`packages/client/hmr/README.md`。
