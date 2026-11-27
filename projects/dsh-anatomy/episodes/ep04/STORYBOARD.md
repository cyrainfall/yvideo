---
format: 1920x1080
fps: 30
duration: 140.67
episode: EP04
title: 一轮对话
---

# STORYBOARD — EP04《一轮对话》

七帧。主线是「一次提问、一次回答在代码里长什么样」：先说树是静止的、动它的是 turn，
再把 turn 讲成一个排空循环、step 讲成「一次请求 + 它引发的工具」，
然后展开日志（只追加、只有带标记的才进历史），再从日志投影出模型历史，
最后用一份真实会话日志逐行对照，收在「重启 / 复制 / 恢复 都只是重读日志」。

屏幕上每个事件名、seq、数字都能在 `packages/` 里找到，或在
`capture/ep04-session.v4.jsonl.zstd`（本机 2026-11-22 17:00 的一份会话日志快照）里数出来。

| # | 帧 | 起 | 时长 | 旁白 | 论证角色 |
|---|---|---|---|---|---|
| 1 | 树是静止的 | 0.00 | 11.83 | 11.33 | 结构不会自己动；动它的是对话 |
| 2 | turn 是个循环 | 11.83 | 16.83 | 16.33 | turn ≠ 一次请求；一格 step = 请求 + 工具 |
| 3 | 什么时候停 | 28.66 | 20.09 | 19.59 | 两个条件；4 个字 → 68 个 step |
| 4 | 只追加 | 48.75 | 23.86 | 23.36 | 日志与历史不是一回事；替换只有两种 |
| 5 | 历史是算出来的 | 72.61 | 16.96 | 16.46 | `deriveMessages()` 投影；只算新增 |
| 6 | 真跑一次 | 89.57 | 29.39 | 28.89 | 真实日志逐行；五种结局 |
| 7 | 它们都不特殊 | 118.97 | 21.71 | 20.51 | 重启 / 复制 / 恢复 = 重读日志；钩子交给 EP05 |

## 逐帧

### F1 — 树是静止的（0.00–11.83）

- 画面：上一集的三个插件节点（agent-loop / session / tools，各挂 `apply`），右侧一条时间轴，只有刻度、没有事件；说到「一句话进了队列」时，第一格刻度变蓝并标上 `turn 1`。
- 蓝色焦点：`turn 1` 那格刻度 + 输入条前的方块。
- 依据：`packages/core/agent-loop/src/agent.ts:332`（`turn/start` 是日志里的第一条 turn 事件）。

### F2 — turn 是个循环（11.83–28.66）

- 画面：一个 `turn` 方框，里面六格 step（`… 68` 是虚线格）；下方一条回环线回到第一格，标「排空」；下半屏把第 1 格拆开成两个块：请求 `llm.stream(request)` → 工具 `tools.execute({ calls })`。
- 蓝色焦点：第 1 格与「请求」块。
- 依据：`agent.ts:323` 的注释「Open one turn before claiming its first proposed step」；`:580` `tools.execute`；回环条件 `:395`。

### F3 — 什么时候停（28.66–48.75）

- 画面：上半屏 `step 1 → 工具 → step 2`；中间两条停止条件（`turnEnds !== null` / `inbox.nextStep.length === 0`）与真实代码行 `agent.ts:395`；右列是本机实测：这一轮工具分布 bash 36 / write 13 / read_image 11 / job_output 7 / present 1；底部三个数 `4` / `68` / `21:40`。
- 蓝色焦点：`68`。
- 依据：`capture/ep04-session.v4.jsonl.zstd` 的 turn 9（1300.0 s，68 个 `step/start`，68 个 `tool/call`，`turn/end` = completed）。

### F4 — 只追加（48.75–72.61）

- 画面：左列七行真实 seq 的日志（618 turn/start … 628 step/end），带标记的行标 `append`，不带标记的整行压暗；右列 `3307 → 996`（这份日志里带 surfaceOp 的事件）与五个允许带标记的事件类型；底部「替换只有两种」，两行真实数据。
- 蓝色焦点：`996`。
- 依据：`packages/core/session/src/types.ts:454`（`SurfaceEventType` 恰好这五种）、`:477`（`SurfaceOp`）；`packages/compaction/compaction-basic/src/region.ts:513`（摘要事件之后追加一条带 `{ op: 'replace', startSeq, endSeq }` 的 user/message）。

### F5 — 历史是算出来的（72.61–89.57）

- 画面：日志列 → `deriveMessages()`（`session/index.ts:778`）→ 四个消息块；最后一行日志变蓝，标 `只算新增的 1 条 · O(Δ)`，底部 `deep-frozen`。
- 蓝色焦点：新增的那一行日志。
- 依据：`packages/core/session/src/index.ts:778` 起 `deriveMessages()` 的注释（CACHED：纯尾部增长 O(new nodes)；replace 或投影变化才重建；返回冻结副本）。

### F6 — 真跑一次（89.57–118.97）

- 画面：左列是本机日志的 turn 8 原样十行（618 / 620 / 621 / 623 / 624 / 627 / 628 / 629 / 630 / 632）；右列先给日志位置与规模，18.1 s 起换成 `turn/end` 的五种结局与这份日志里的次数（completed 7 / blocked 0 / max-tokens 0 / aborted 5 / error 4）。
- 蓝色焦点：`621 user/message`（输入落成一条消息的那一刻）。
- 依据：同一份日志快照；`turn/end` 的 reason 取值见 `agent.ts:345`（blocked）、`:353`（completed）、`:402`（aborted）、`:409`（error），max-tokens 见 `:366`。

### F7 — 它们都不特殊（118.97–140.67）

- 画面：三行（重启 / 复制 / 恢复）与右侧「同一件事：把日志读回来，再往后追加」；下半屏 `buildForkSeed` 的三件事；底部 EP05 钩子。
- 蓝色焦点：下一集钩子的方块。
- 依据：`packages/core/session/src/fork.ts:21` `buildForkSeed`（`slice(0, boundary+1)` + `session/end-seed { inherited: true }` + `openTurnClosers(prefix, { kind: 'forked' })`）；`packages/bundle/headless/src/index.ts:289`（`--session-id` 走 `agents.resume`）。

## 节奏

- 每帧底部一条 2px 蓝进度发丝线；说到才放元素，不在前 25% 倒完。
- F6 是唯一一处内部换景（日志 → 结局表），18.1 s 交叉完成：右列淡出、结局表淡入，左列日志不动的。
- 长帧（F6 29.4 s）靠「逐行落下 + 换景」撑住，不靠循环动画。

## 这份日志快照

`capture/ep04-session.v4.jsonl.zstd`（3.4 MB，解压 12.3 MB）：

| 量 | 值 |
|---|---|
| 事件 | 3307 条（带 surfaceOp 996 条） |
| turn | 17 个（16 个已收尾） |
| step | 453 个 |
| 工具调用 | 481 次 |
| turn/end 分布 | completed 7 · aborted 5 · error 4 |
| 压缩事件 1 | `replace 10 → 1330`，399 条、186079 token |
| 压缩事件 2 | `replace 1343 → 2841`，453 条、200215 token |

快照是录制过程中取的，之后的会话会继续变长；屏幕上的数字以这份快照为准。
