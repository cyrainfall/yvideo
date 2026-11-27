---
format: 1920x1080
fps: 30
duration: 223.886
episode: EP05
title: 工具：模型的手
---

# STORYBOARD — EP05《工具：模型的手》

七帧。主线是「模型说一句话，中间经过什么，真的有东西动起来」：
先把上一集留的那件事摆出来（工具在注册表里），再讲注册表怎么按 scope 算出一张菜单，
然后把一次调用拆成三段流水线，单独讲清楚「问人」那一步为什么必然失败，
接着讲返回值不是终稿（post-execute 能改写、能驳回），
用同一份会话日志给出 481 次调用的真实分布，最后收在「手可以换」。

屏幕上每个路径、行号、名字都能在 `packages/` 里找到，或在
`capture/ep04-session.v4.jsonl.zstd`（本机 2026-11-22 17:00 的一份会话日志快照）里数出来。
拍片时机器上另一份会话的日志没有重取，用的就是这一份 —— 所以数字不会随运行而变。

| # | 帧 | 起 | 时长 | 旁白 | 论证角色 |
|---|---|---|---|---|---|
| 1 | 手在谁那里 | 0.000 | 21.23 | 20.73 | 模型只写调用；动手的是注册表 |
| 2 | 算出来的菜单 | 21.233 | 34.53 | 34.03 | 注册 → 分层 → 求交 → 每次请求算一遍 |
| 3 | 三段 | 55.765 | 35.82 | 35.32 | pre-execute / guards / execute / post-execute |
| 4 | 要问人的那一步 | 91.584 | 29.86 | 29.36 | ask 的四种答案；没有通道就是拒绝 |
| 5 | 结果不是终点 | 121.439 | 34.16 | 33.66 | block → isError；finalize；冻结快照 |
| 6 | 真跑一次 | 155.595 | 35.55 | 35.05 | 481 次调用的真实分布与三次失败 |
| 7 | 手可以换 | 191.142 | 32.74 | 31.54 | shell / fs / sandbox 三个 seam；钩子交给 EP06 |

## 逐帧

### F1 — 手在谁那里（0.000–21.233）

- 画面：左上一条真实的 `assistant/message`（`bash` + 真 callId 前缀 + 两行真命令），中间一条发丝线与 `ctx.tools.executable("bash", agent)`，下面一条真实的 `tool/result`（3.224 s、pid 96502）；右侧 `工具 / 模型的手`，以及这一份会话里伸出去 481 次。
- 蓝色焦点：`bash` 这个名字。
- 说明：屏幕上的命令与结果按版面折行（原文一条），文字未改。
- 依据：`capture/ep04-session.v4.jsonl.zstd` 的 turn 7 step 8 —— `tool/call` seq 469，`{"command":"qwen3tts start 2>&1 | tail -2; sleep 2; qwen3tts status | head -2"}`；`tool/result` seq 472，耗时 3.224 s，内容 `up: http://127.0.0.1:8010 (pid 96502, …)`；`packages/core/tools/src/index.ts:251` 的 `executable()`。

### F2 — 算出来的菜单（21.233–55.765）

- 画面：三层注册（`global` / `agent · mcp` / `agent · child` 带 `restrict({ deny })` 划掉 `todo_write`）；右侧 `view()` 的三行真实代码（214 / 215 / 222）与两句注解；下方一张小表说明「全局允许、某一层关掉 → 这一 step 看不见」；最后两个数 37 与 76。
- 蓝色焦点：无（本帧靠层次与线；蓝色留给第 3 帧的流水线）。
- 依据：`packages/core/tools/src/index.ts:128`（`register()`）、`:162`（`restrict()`）、`:214`/`:215`/`:222`（逐层求交、近层覆盖）、`:264`（每次 step 前 `resolve()` 算准入集合）；`packages/mcp/mcp-client/src/tool-loading.ts:149`（MCP 工具注册在服务器自己的 scope）；`packages/subagent/subagent/src/child-agent.ts:223`（子 agent 的 `toolFilter` → `restrict()`）；`packages/experimental/timeline/src/guidance.ts:170`（真实用例 `deny: ['todo_write']`）；`docs/tool-catalog.zh.md`（37 个包、76 个模型可见名字）。

### F3 — 三段（55.765–91.584）

- 画面：一条水平脊柱，五站（`pre-execute` / `guards` / `execute` / `post-execute` / `tool/result`）先整张上屏；蓝点随旁白逐站移动。每站下列出它真实的返回值：pre 的四种决定、guards 的两种（没有 allow）、execute 的 `timeoutMs`/`metrics`、post 的 accept/replace/block；底部四行真实调用（201 / 214 / 311 / 509）。
- 蓝色焦点：移动的那一站。
- 依据：`packages/core/tools/src/pipeline.ts:201`（`tools/pre-execute` 瀑布）、`:214`（`checkGuards`）、`:311`（`tools/execute`）、`:509`（`tools/post-execute`）；`:429`（`tools/result`）；`packages/core/tools/src/contracts.ts:375`（`PreToolDecision` 四种）、`:386`（`PostToolDecision` 两种）、`:410`（`ToolGuard` 只有 `string | ToolGuardDenial | undefined`）；`packages/guard/timeout-policy/src/index.ts:56`（超时是 `tools/execute` 的 wrapper）。

### F4 — 要问人的那一步（91.584–121.439）

- 画面：`ctx.approval.request({ agent, toolName, callId, signal })`，下面四个真实答案（`allowed-once` / `rejected` / `cancelled` / `unavailable`），`unavailable` 标蓝；右侧「这一份会话」贴出真实事件 `approval/policy { policy: "never" }`，并说明派出去的子 agent 也是 `never`；下方沙箱三档与「这一份会话就是 danger-full-access」。
- 蓝色焦点：`unavailable`。
- 依据：`packages/core/tools/src/pipeline.ts:440` 起 `serviceAsk()`（没有 approval 服务 / 没有 agent → `APPROVAL_UNAVAILABLE`；四种 outcome 一对一映射）；`packages/interaction/user-approval/src/types.ts:32`（四个 outcome）、`index.ts:69`（`ApprovalPolicy = 'ask' | 'never'`）；`packages/subagent/subagent/src/child-agent.ts:240`（子 agent 的 `approvalPolicy: 'never'`）；`capture/ep04-session.v4.jsonl.zstd` 的 seq 1 `sandbox/mode { mode: "danger-full-access" }`、seq 2 `approval/policy { policy: "never" }`；`packages/sandbox/sandbox-policy/src/session-mode.ts:42`（三档）。

### F5 — 结果不是终点（121.439–155.595）

- 画面：左侧一条竖向链条，五道手（`execute()` → `projectContent` → `tools/post-execute` → `finalizeContent` → `tools/result`），第三道标蓝；右侧 `PostToolDecision` 的真实类型与一句注解；底部三条真实 isError 回执。
- 蓝色焦点：`tools/post-execute`。
- 依据：`packages/core/tools/src/contracts.ts:386`（`PostToolDecision`：accept / block，都可带 `additionalContexts`）、`:50`/`:62`（`projectContent` / `finalizeContent` 的语义，后者「同步、只能动内容、在无损物化之前」）、`pipeline.ts:509` 起 `postExecute()`（block → `isError` + feedback）；`packages/guard/timeout-policy/src/index.ts:56`；三条 isError 来自快照：seq 420 `unknown job bash-60d60aa3f3b64be5`、seq 1912 `…/snapshots/fix2/frame-01-at-34s.png: not found`、seq 2103 `Cannot present renders/ep02-一切皆插件.mp4: file not found`。

### F6 — 真跑一次（155.595–191.142）

- 画面：六行调用次数条（bash 353 / read_image 54 / write 50 / job_output 15 / present 7 / skill 2）；右侧三个数（中位数 54 ms、305/480 在百毫秒内、19 次超过一分钟、最慢 152 s）；底部两组：3 次带着错误回来、1 次没有结果（seq 3305 · turn 17）。
- 蓝色焦点：bash 那条。
- 依据：同一份快照。481 条 `tool/call`，480 条 `tool/result`（seq 3305 那次随 turn 17 还在跑）；耗时按 `tool/result.time - tool/call.time` 计；`unknown job` / `not found` / `file not found` 三条文本按原文上屏。

### F7 — 手可以换（191.142–223.886）

- 画面：三列 seam（`ctx.shell` / `ctx.fs` / `ctx.sandbox`），上面对应工具、下面对应本机实现；隔离四个包各自一句；`bwrap` / `Seatbelt` 高亮；最后一行钩子交给 EP06。
- 蓝色焦点：`ctx.sandbox`（讲到「换的不是某个工具，是整条能力」时）。
- 依据：`packages/sandbox/README.zh.md`（四个包与职责；Linux 先 bwrap 再 Landlock，macOS Seatbelt，Windows 受限令牌）；`packages/sandbox/sandbox/src/escalation.ts:64`（`WIDER_MODES` 严格更宽的阶梯）。

## 事实核对（EP05）

| 画面 | 出处 |
|---|---|
| `register()` / `restrict()` / `executable()` / `resolve()` | `packages/core/tools/src/index.ts:128`、`:162`、`:251`、`:264` |
| 逐层求交、近层覆盖 | 同文件 `:214`、`:215`、`:222` |
| `checkGuards()` 只返回拒绝 | 同文件 `:394`；`contracts.ts:410` |
| MCP 工具注册在服务器自己的 scope | `packages/mcp/mcp-client/src/tool-loading.ts:149`、`:162` |
| 子 agent 的 `toolFilter` 走 `restrict()` | `packages/subagent/subagent/src/child-agent.ts:223` |
| `deny: ['todo_write']` 的真实用例 | `packages/experimental/timeline/src/guidance.ts:170` |
| 37 个包 / 76 个模型可见名字 | `docs/tool-catalog.zh.md` 的工具包映射表 |
| pre / guards / execute / post / result 五个事件 | `packages/core/tools/src/events.ts:18`、`:29`、`:41`、`:49` |
| `PreToolDecision` 四种、`PostToolDecision` 两种 | `contracts.ts:375`、`:386` |
| ask → approval 的四种结局与失败即拒绝 | `pipeline.ts:440`–`:495` |
| `ApprovalPolicy = 'ask' \| 'never'` | `packages/interaction/user-approval/src/index.ts:69` |
| 子 agent 的 `approvalPolicy: 'never'` | `packages/subagent/subagent/src/child-agent.ts:240` |
| 沙箱三档 | `packages/sandbox/sandbox-policy/src/session-mode.ts:42` |
| 升权是严格更宽的阶梯 | `packages/sandbox/sandbox/src/escalation.ts:64` |
| 超时是 `tools/execute` 的 wrapper | `packages/guard/timeout-policy/src/index.ts:56` |
| 先读后写是 `fs/*` 门禁 | `packages/fs/fs-observation-policy/src/index.ts:128`（随发行版禁用） |
| 481 次调用 / 6 个工具 / 353 次 bash / 中位数 54 ms / 19 次 >1 min / 最长 152 s | `capture/ep04-session.v4.jsonl.zstd` |
| 三次 isError 的原文 | 同一份快照 seq 420 / 1912 / 2103 |
| seq 3305 没有结果 | 同一份快照，turn 17 未完 |
| 本会话 `danger-full-access` + `never` | 同一份快照 seq 1 / seq 2 |
