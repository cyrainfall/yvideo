---
format: 1920x1080
fps: 30
duration: 132.17
episode: EP02
title: 一切皆插件
---

# STORYBOARD — EP02《一切皆插件》

七帧。每帧一个论点，帧内按旁白分句揭示；屏幕上的文件名、类名、调用点都来自
`/Users/cyx/repo/deepseek-harness`。字幕走 `line` 模式（整行纸白）。

| # | 帧 | 起 | 时长 | 旁白 | 论证角色 |
|---|---|---|---|---|---|
| 1 | 一个插件到底是什么 | 0.00 | 9.85 | 9.35 | 承接 EP01，把「插件」从配置项改成对象 |
| 2 | 最小的插件 | 9.85 | 14.35 | 13.85 | 给出可复制的最小形态（名字 + apply） |
| 3 | 上下文是容器 | 24.20 | 17.71 | 17.21 | 服务占稳定键；调用方不做 import |
| 4 | 依赖写在 inject 里 | 41.91 | 22.42 | 21.92 | 加载顺序由依赖决定；PENDING 是可观测的 |
| 5 | 插件之间怎么说话 | 64.33 | 24.53 | 24.03 | 五种分发模式；waterfall 即中间件 |
| 6 | 注册是可逆的 | 88.86 | 26.11 | 25.61 | 现场演示：装上→调用→卸载→消失 |
| 7 | 每个节点都是一个 apply | 114.97 | 17.20 | 16.01 | 收束；钩子交给 EP03 |

## 逐帧

### F1 — 一个插件到底是什么（0.00–9.85）

- 画面：`一切皆插件。` 巨字（插件为纸白）；随后问题行；再抛出一行 `cordis.yml` 条目并被划掉；最后 `是一个对象` 以蓝色落定。
- 蓝色焦点：`是一个对象`。
- 依据：`docs/cordis-primer.zh.md`「插件是实现 Service 的对象」。

### F2 — 最小的插件（9.85–24.20）

- 画面：左 `hello.ts` 七行真实代码（行号在左）；名字与 apply 依次上蓝；右侧 `ctx` 说明卡（`ctx.effect / ctx.on / ctx.plugin`），随后换成 `cordis.yml` 一行 + 真实运行输出。
- 蓝色焦点：`ctx`（随后由终端输出承接）。
- 依据：`docs/cordis-tutorial/01-first-plugin.zh.md` 的 `hello.ts` 与 `cordis.yml`；输出为本地实跑。

### F3 — 上下文是容器（24.20–41.91）

- 画面：三行服务键 `ctx.tools / ctx.llm / ctx.sessions`，右侧列真实实现类；左侧发丝括号标出这一组；右侧「按 key 查找」面板，最后把 `import { ToolsService } from …` 划掉。
- 蓝色焦点：查找箭头 `→`。
- 依据：`docs/cordis-primer.zh.md` 的服务键；`packages/core/tools/src/index.ts:99`（`ToolsService`）、`packages/llm/llm/src/index.ts:345`（`ctx, 'llm'` → `LlmRuntime`）、`packages/core/session/src/index.ts:850`（`ctx, 'sessions'` → `SessionStore`）。

### F4 — 依赖写在 inject 里（41.91–64.33）

- 画面：左 `cordis.yml` 四行真实条目（1 system-prompt / 2 tools / 3 tool-logger / 4 greet-tool）；右侧 `greet-tool.ts` 的 `inject = ['tools']`；下面两段说明「列表里的位置不算数」「加载顺序 = 依赖拓扑」；再下面是 fiber 状态机。
- 蓝色焦点：`PENDING` 方块。
- 依据：`docs/cordis-tutorial/07-into-the-harness.zh.md` 的组合顺序；`docs/cordis-tutorial/02-lifecycle-and-effects.zh.md` 的状态机。

### F5 — 插件之间怎么说话（64.33–88.86）

- 画面：左表（mode / await / 顺序 / 返回值，五行真实取值）；说到 waterfall 时表格退后、只留 waterfall 一行上蓝；右侧出现三层嵌套 `tools/pre-execute → tools/execute → tool.execute(args, exec) → tools/post-execute`。
- 蓝色焦点：`waterfall` 行。
- 依据：`docs/cordis-primer.zh.md` 分发模式表；`packages/core/tools/src/events.ts` 的 `@mode waterfall` 注释；`packages/core/tools/src/pipeline.ts:280`（`await tool.execute(exec.arguments, exec)`）。

### F6 — 注册是可逆的（88.86–114.97）

- 画面：左 `greet-tool.ts` 五行（`ctx.effect(() => ctx.toolbox.register(…))`）；下面「register 返回 disposer / ctx.effect 替你挂上 / 不接住它什么也不会发生」；右侧终端四行真实输出，`- greet` 上蓝，`ERROR: no tool named` 落成纸白；底部小字说明 `toolbox` 是本集自建的最小注册表。
- 蓝色焦点：`[toolbox] - greet   0 tool`。
- 依据：本地实跑（`tmp/cordis-tutorial` 风格的独立 demo），输出原样上屏。

### F7 — 每个节点都是一个 apply（114.97–132.17）

- 画面：左插件树（session / tools / llm / agent-loop / greet-tool，最后一行为蓝色左边线 + 「我们写的」）；右侧 `apply(ctx)` 里的三件事（占键 / inject / 监听与注册），说到卸载时三行被一次扫描抹掉；下面收束句与 `EP.03 把树拼出来` 钩子。
- 蓝色焦点：`greet-tool` 的左边线与其标签。
- 依据：`packages/bundle/base/cordis.patch.yml` 的 session / tools / llm / agent-loop 行。

## 节奏

- 帧内一律「说到才放」，不做前 25% 倒完再冻住；每帧底部一条 2px 蓝色进度发丝线，保证没有死段落。
- 转场全部硬切；只有 F3→F4 与 F6→F7 各用一次 0.3s 的透明度交接，避免双重曝光。
