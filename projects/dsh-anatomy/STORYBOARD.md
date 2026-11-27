# STORYBOARD — EP07《接缝》

> 第二季 S2E01 · 时长目标 **3:30（约 210 s）** · 7 帧 · 一帧一个问题
> 视觉规范见 `frame.md`；本集新增的组件（**三角色接缝图**、**形态清单**）做帧内样式，不扩展系统。
> **上屏唯一依据**：`FACTS.md`（本集事实表）。仓库 HEAD `d98f5d6851`（DSH `0.2.3-alpha.1`，2026-11-22）。
> 索引只作选题：`dsh-internals/ch02`、`ch11`；一切数字与行号回仓库取。

| 帧 | 标题 | 起点 / 时长 | 旁白 | 这一帧回答什么 |
|---|---|---|---|---|
| 01 | 两百个插件的秩序 | — / ≈28s | 7 句 | 问题：插件越多，凭什么越有序 |
| 02 | 一个能力，三个位置 | — / ≈36s | 9 句 | 三角色齐全才算一个能力 |
| 03 | 定义是类，不是一个名字 | — / ≈32s | 8 句 | `ctx.shell` 怎么"拥有"一个 key |
| 04 | 提供方是继承，不是重写 | — / ≈32s | 8 句 | 换 provider = 换执行世界，工具层不动 |
| 05 | 消费方只认 key | — / ≈36s | 9 句 | 不 import 实现；缺席有两种 |
| 06 | 五种挂法，选错要重写 | — / ≈32s | 8 句 | 注册形态先于实现选定 |
| 07 | 判据与下一个问题 | — / ≈22s | 5 句 | 一条可带走的判据 + 钩子 |

合计 **56 句 ≈ 216 s（3:36）**。帧时长 = 旁白 + 0.5 s，末帧 +1.2 s——**配音后按 `voice_takes.json` 回填**（本表起点留空是刻意的，不预填假数）。

## 现场演示（本集唯一的「真跑一次」）

用 `cordis_inspect` 读本机运行中的注册表，但**不做"一屏指认三角色"**——预跑已证明服务目录不记 provider 归属（见 `demo/receipts-s2/E01-inspect/receipts.md`）。改为**三段串联**：

| 段落 | 命令 | 屏幕上给什么 | 落在哪帧 |
|---|---|---|---|
| ① 合约 | `Service.listService {service:"shell"}` | `access` 双通道原文：`ctx.get("shell")` + `requiresUndefinedCheck` / `inject:["shell"]` + `ctx.shell`；"loading a second throws" | F3、F5 |
| ② 插件行 | `Config.listConfigs {name:"@deepseek-ai/dsh-bash-sandbox"}` / `{name:"@deepseek-ai/dsh-tool-bash"}` | 两行真实条目：`bash-sandbox: schema`、`tool-bash: inactive` | F4、F5 |
| ③ 源码 | 见下逐帧出处 | file:line 钉死装配 | F2–F6 |

收据目录 `demo/receipts-s2/E01-inspect/`：

| 文件 | 内容 | 上屏位置 |
|---|---|---|
| `service-catalog.json` | 120 个服务的活体目录（123 KB） | F3（只截 `shell` 段） |
| `plugin-rows.json` | 两条插件行原文 | F4、F5 |
| `receipts.md` | 三段收据 + 预跑结论 | 制作参考，不上屏 |

**备胎**（卡住即切换，不允许示意图冒充真跑）：只放合约 + 源码两段；`tool-bash` 的 `inactive` 状态口头说明，不当作画面证据。

## 逐帧

### F1 两百个插件的秩序

- **画面**：左侧大标题与问题；右侧一张"能力账本"——121 条横线，其中 36 条略亮（seam），其余更暗；不出现任何连线，先不给结构。左上角一行小字给活体数：`248 条配置条目（本机运行中）`；底部一行真值：`121 个能力 · 36 条可替换接缝`。
- **旁白落点**：说到"两百四十八条"时账本整体出现；说到"三十六条缝"时亮线分层。
- **上屏真值**：`248`（本机 Config 条目，`demo/receipts-s2/E01-inspect/config-total.json`）；`121` / `64 core` / `36 seam` / `20 service` / `1 bundle`（生成文件，注明来源）。
- **上屏引用**：`docs/capability-seams.md:709-829`（表头 `:707`）。
- **出处**：`docs/capability-seams.md:709-829`。
- **注意**：这是**生成文件**（`scripts/gen-doc-graphs.ts` 产出），上屏标"生成"二字，别当手写文档。

### F2 一个能力，三个位置

- **画面**：本集主图——**三角色接缝图**。一条水平接缝线（`ctx.shell`，唯一蓝焦点）把画面分成两边：上侧是 Definition（`dsh-shell`，占一个位置），下侧左是 Provider（两个叠格：`bash-local`、`bash-sandbox`），下侧右是 Consumer（`tool-bash`，副格 `tool-pwsh`）。Consumer 与 Provider 之间**不画任何箭头**——只各自连到接缝线。
- **旁白落点**：说到"三个位置"时三方依次落位；说到"消费方连的是线不是人"时，Consumer 那根竖线变蓝、Provider 那侧仍灰。
- **上屏真值**：五个包名 + `ctx.shell`；`tool-pwsh` 作为第二个消费方小字。
- **上屏引用**：`packages/shell/shell/src/index.ts:30-32`（Context 声明）、`:64-66`（抽象类）。
- **出处**：`packages/shell/shell/src/index.ts:30-32,64-66`；`packages/shell/tool-bash/src/index.ts:2`（自述 Consumer）；`packages/shell/tool-pwsh/src/index.ts:2-5`。

### F3 定义是类，不是一个名字

- **画面**：三段真实代码竖排——`declare module … { shell: ShellExecutor }`、`export abstract class ShellExecutor extends Service`、`super(ctx, 'shell')`。右侧一个"名额"示意：一个方格，格内只容一个实现；第二个进来时方格边缘闪一道红线并显示真实报错文本。
- **旁白落点**：说到"定义不是 interface"时第一段亮；说到"第二个装载直接抛"时方格出现报错行。
- **上屏真值**：`service "shell" has been registered at <…>`（cordis 原文报错格式）。
- **上屏引用**：`packages/shell/shell/src/index.ts:64-66`、`:30-32`、`:36-39`；`vendor/cordis/src/reflect.ts:326`。
- **出处**：同上；断言测试 `packages/shell/shell/tests/service.spec.ts:83-87`。
- **口播纪律**：**不要说"这是 shell 包的守卫"**——抛错来自 cordis 的标准占位检查，shell 侧只有注释和一条测试。

### F4 提供方是继承，不是重写

- **画面**：提供方叠图。上格 `LocalBashExecutor extends ShellExecutor`；下格 `SandboxBashExecutor extends LocalBashExecutor`，一根短箭头从上格指向下格（继承），旁边一行 `static override inject = ['subprocess','sandbox','sandboxPolicy']` 与上格的 `inject = ['subprocess']` 对照。
- **旁白落点**：说到"不是重写一遍"时继承箭头出现；说到"多要两个缝"时 inject 数组展开。
- **上屏真值**：`super(ctx, 'shell')` 由抽象类完成、两个 `inject` 数组原文、包名 `@deepseek-ai/dsh-bash-local` / `@deepseek-ai/dsh-bash-sandbox`。
- **上屏引用**：`packages/shell/bash-local/src/index.ts:97-98`；`packages/shell/bash-sandbox/src/index.ts:45-46`（doc `:38-44`）。
- **出处**：同上；生成表 `docs/capability-seams.md:801` 列出 3 个实现（另有 `pwsh-local`，源码还有 `pwsh-sandbox`）。
- **口播纪律**：说"这台机器装的是 Bash 的两个"，不说"只有两个提供方"。

### F5 消费方只认 key

- **画面**：左半边是消费方代码（`ctx.shell.sandboxMode` / `ctx.shell.execute`），右半边是 `package.json` 的依赖事实（定义包在 peer，运行期依赖只有 schemastery，`bash-local` 只在 devDependencies）。下半：**缺席两态**分支——`inject` 缺席 → `PENDING`；`ctx.get` 缺席 → `unavailable`。
- **旁白落点**：说到"只认 key"时左边代码亮；说到"连实现的名字都不需要知道"时右边依赖表亮；说到"缺席有两种"时下半分支展开——蓝焦点给 `unavailable` 那一支。
- **上屏真值**：`ctx.shell`、`"@deepseek-ai/dsh-shell": "workspace:*"`（peer）、`ToolContextUnavailableError`、`foregroundOnly`。
- **上屏引用**：`packages/shell/tool-bash/src/index.ts:36`、`:251`、`:320`、`:592`；`packages/shell/tool-bash/package.json:36,49-51,60`。
- **出处**：同上；`unavailable` 词表 `packages/interaction/user-approval/src/types.ts:29-32`；真实路径 `packages/sandbox/sandbox/src/escalation.ts:256-260`。
- **口播纪律**：**不要说"只 import 类型"**——消费方确实从定义包 import 了运行期值 `DSH_ENV_PREFIX`（`tool-bash:29`）。正确说法是"依赖的只有定义包，而且只是 peer；提供方不在运行期依赖里"。

### F6 五种挂法，选错要重写

- **画面**：五行清单，每行"形态名 + 真实键 + 一句判据"，行间用发丝线；`ctx.shell` 那一行左缘加一道蓝线（本集主角）。
- **旁白落点**：五行按旁白顺序逐行出现，说完第五行，底部压一句"形态是发布时决定的"。
- **上屏真值**（全部可查）：
  - 命名注册表 `ctx.llm` —— 只拒绝重名；
  - 单槽 `ctx.browserUse` —— 第二次注册无条件抛错；
  - 有序尝试 认证链 —— 按注册顺序问，首个存活 Peer 赢；
  - 每上下文一实例 `ctx.shell` —— 没有注册表，只有一个名额；
  - 注册即绑定 `ctx.credentials` —— 插件名就是凭据作用域的键。
- **上屏引用**：`packages/llm/llm/src/index.ts:336-337,383,425`；`packages/browser-use/browser-use/src/index.ts:16,35-38`；`packages/client/connection/src/authentication.ts:44-55`；`vendor/cordis/src/reflect.ts:326`；`packages/credentials/credentials/src/index.ts:205-214`。
- **出处**：同 `FACTS.md` 表 B。
- **口播纪律**：认证链要说"**传输层**的 seam，不是模型侧"；"选错=重写消费方"是**评论句**，不要说成仓库事实。

### F7 判据与下一个问题

- **画面**：一句话判据压在中间——"**消费方写 `inject` 还是 `ctx.get`，决定缺席时是停摆还是降级**"；下方两行字：`PENDING` / `unavailable`。右下起钩子：一条虚线从接缝线延伸出画面。
- **旁白落点**：判据整句一次性出现；钩子句说到"听见彼此"时虚线走到画面边缘。
- **上屏真值**：`PENDING`、`unavailable`。
- **上屏引用**：`packages/shell/tool-bash/src/index.ts:36`（inject）与 `:592`（ctx.get）为同一集的正反对照。
- **钩子**：消费方不 import 提供方，那插件之间怎么"听见"彼此？→ **事件**。

## 制作备注

- **新图形**：三角色接缝图（F2）、形态清单（F6）进 `w0-samples/` 的样张体系；F3 的"名额"格与 F4 的继承叠图是帧内样式，不新增系统组件。
- **蓝焦点**：F1 无（开场留白）、F2 接缝线、F3 `super(ctx,'shell')`、F4 inject 差异、F5 `unavailable`、F6 `ctx.shell` 行、F7 判据句。每帧只有一个。
- **字幕安全区**：所有正文压在 y<900；F1 的账本底部、F6 的第五行都要留 17% 空。
- **时长纪律**：56 句是上限，配音后若超 3:45，优先砍 F6 的旁白（五行保留、解释压缩），不砍 F5 的缺席两态——那是本集真正的判据。
