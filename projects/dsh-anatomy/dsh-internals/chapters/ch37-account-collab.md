# 第 37 章：账号、协作与其他

## 核心思想

这一组子系统的共同纪律是：**对外只暴露最小面，授权与撤销都在 Host 侧闭环**。账号不把 token 交给消费方，而是发一份「按请求的凭据」；LiveShare 不让 viewer 拿到所有者的工具，而是在所有者宿主机上以 viewer 自己的 Peer 分派；后台任务不靠 id 保密，而是用拥有者会话围栏。凡是能撤销的东西，都配一个明确的失效信号。

## 框架与方法

- **请求凭据（request credential）**：`resolveRequestCredential(url)` 仅限 Host。
  - 何时用：某个出站请求要用账号授权，但插件不该看到 token。
  - 怎么做：调用方只说明目标地址，拿回 `AccountRequestCredential`——`headers` 以 `x-dsh-auth-token` 携带 token、`reject()` 仅在已存授权仍与该 token 一致时删除它、`revoked` 在该 token 所属登录退出时中止。未登录、凭据删除进行中、或目标地址不在配置的 `inferenceOrigin` 之内时返回 `undefined`。消费方不直接调用它：`ctx.deepseekAuth` 代 `deepseek-account` 模型路由和 DeepSeek Web 提供方索取。

- **运行中任务报告（running task report）**：让退登能提醒「这会打断什么」。
  - 何时用：插件会因退登而失去正在进行的计费工作。
  - 怎么做：在 `ctx.effect()` 内 `registerRunningTaskReport(() => boolean)`；只要有报告回答 true，`hasRunningAccountTasks()` 就为 true。`deepseek-account/signed-out` 之后取消这些工作由路由插件负责；活得比插件更久的请求靠 `revoked` 结束。

- **LiveShare 的档位与上限（tier and ceiling）**：分享把源会话交给外部 viewer 驱动。
  - 何时用：要把会话分享出去而仍然限制读者能做什么。
  - 怎么做：`ViewerSessionMode` 只有 `view` 与 `write` 两档，两档都对应一个沙箱。`view` 在授予工作区的只读沙箱里驱动 loop，`write` 在受宿主写入上限约束的可写沙箱里运行。fork 不是一档，分享自带独立 `allowsFork` 开关；附件上传也不是一档。分叉会话的工具面由 `READ_ONLY_FORK_CEILING`（读取与检索面 + `run_code`）与 `WRITE_FORK_CEILING`（再加有界 `edit`／`write`）界定；`bash`、`pwsh`、`cua`、`plugin_manager`、`schedule_*` 及任何未列出的名字一律拒绝。

- **执行层挂在会话上，只约束 viewer 轮次**：`agent/pre-step` 在 Host 内存中记录一个轮次的已准入输入是否带 share-viewer principal。
  - 何时用：同一会话既被所有者自己用，也被 viewer 驱动。
  - 怎么做：守卫与受限替代定义对该轮次的每次执行读取这一结论；查看者发起的轮次只能运行替代定义，所有者自己发起的轮次保留原生工具（含 `bash` 与不受限文件工具）。该结论不写入会话日志，重启后从下一个准入步骤重新计算。

- **后台任务运行时（job runtime）**：把长跑工作的身份、访问、生命周期与输出环交给注册表。
  - 何时用：工具要 `run_in_background`，或工作结果是一个值而非一条流。
  - 怎么做：`ctx.jobs.start({ kind, label, owner, output?, run })`。运行时先做访问与清理预检，再调 `run(job)`；`run` 抛异常则什么也不注册。生产方拥有执行资源，运行时拥有身份、访问、生命周期状态与输出环。`JobHooks.done` 在生产方**释放资源后** resolve，而不是工作一结束就 resolve。

- **输出环（output ring）的两种写入**：拉取源与推送追加并存。
  - 何时用：子进程输出要走 `readFrom` 家族，插件自述进度要走 `append`。
  - 怎么做：拉取源由注册表按 `pumpPollMs`（默认 150）泵送，并在结算封环前再排干一次；`JobHandle.append` 的推送整块落地。模型的消费式游标（`read`）与观察者的绝对字节偏移（`readAt`）读同一批字节且互不干扰。`log` channel 只到达观察者，从不进入模型消耗式读取。

- **产出物（deliverables）**：一轮交给用户的两样东西。
  - 何时用：要在轮末展示「模型声明交付的文件」与「本轮实际改动的文件」。
  - 怎么做：前者由模型经 `present` 工具声明，记在 `deliverables/presented`；后者由轮开始与轮结束的 git 工作树快照对比得出，git 覆盖不到的路径由文件工具每次编辑前后的整文件捕获得出，在顶层轮停止时追加 `workspace/changes` 事件。两个事件都是仅写日志，绝不进入模型请求。

- **消息反馈（message feedback）**：针对单条 assistant 消息的可编辑反馈。
  - 何时用：人类要对某条回答表态并可改可删。
  - 怎么做：权威日志保存 `feedback/message-put` 与 `feedback/message-delete`，写入带 `ifVersion` 乐观比较；`null` 表示要求该条目不存在。不可变的 Session 级备注仍走 `feedback/record`，两者共用 `FeedbackCategory` 分类表。

- **用户交互 seam（user questions）**：工具或权限插件需要人类回答时使用的提供方无关词汇。
  - 何时用：要阻塞等一个决定，或不阻塞地问一批问题。
  - 怎么做：`AskUserQuestionItem` 带稳定 `id`，答案按 id 回填。`intent` 只改变呈现方式——`plan-review` 用 `approve` 显式点名批准项（不看选项顺序），`approval` 要求只有一个阻塞式问题且不支持多选或计时——答案编码在两种情况下完全一致。

- **系统提示词段落（prompt section）**：`ctx.systemPrompt.section()` 注册具名指令。
  - 何时用：要往系统提示词加一段可控、可撤的文本。
  - 怎么做：`name` 用稳定且带命名空间的写法；最近作用域的同名注册遮蔽外层，同一作用域内最后一个活跃注册生效；`order` 必须是有限数值。新节一律显式写 `interpolate: false`，动态文本用回调或模板字符串自算。退役只发生在可见作用域链上再无注册时，且只发给观察过该名称并提交过的 Session。

## 关键概念

- **`AccountRequestCredential`**：仅限 Host 的一次性凭据，含 `headers`、`reject()` 与 `revoked` 信号。
- **`AccountClientMetadata`**：调用方版本、界面 `locale` 与操作发起时采样的 `timezoneOffsetSeconds`（本地减 UTC 的秒数，UTC+8 为 `28800`），不含凭证。
- **`share-viewer` principal**：Gateway 依据 `remote-access` 策略判定的读者主体；分享档位已确立且其会话受沙箱限制时策略放行。
- **`JobView`**：每个读者都消费的唯一投影（模型工具、浏览器名册、观测流共用一份形状）。
- **`producerReported`**：生产方通过兑现 `done` 报告了终态；强制销毁或 promise 拒绝时为 false，且不独立确认资源已释放。
- **`WorkspaceChangesSummary`**：一轮改动的摘要，`total` 与 `added`／`deleted` 覆盖被上限截掉的文件。
- **`MessageFeedbackVersion`**：仅供相等性比较的 compare-and-set 令牌，每次实质写入都会被替换。
- **`pending`（计时问题）**：问题仍可回答，既不是空答案也不是拒绝、确认或授权。
- **`PromptSection`**：系统提示词的一段，带 `order`、可选 `replacement` 与 `retirement` 通知。

## 心智模型

- 当要把能力交给外部时，把它看成「借用」而不是「转交」：LiveShare 的 viewer 拿不到所有者的工具，账号消费方拿不到 token。
- 把 jobs 的访问控制看成会话围栏而非命名空间隔离：id 可预测也无所谓，授权才是边界。
- 把日志事件分成两类来读：`deliverables/presented`、`workspace/changes`、`feedback/*` 都是仅写日志，可以在 UI 回放，但永远不进模型上下文。
- 把 `intent` 看成 UI 的提示标签：认识它的界面可以换一种画法，不认识的就退回通用选项列表，协议层不动。

## 反模式

- **让插件自己读 token**：一旦消费方能读已存 token 或自选请求头，撤销就只对「听话的插件」有效。
- **靠 id 保密做访问控制**：`JobId` 是可预测的 `<kind>-<short-uuid>`；用会话围栏，不要用不可猜测性。
- **把 `pending` 当拒绝**：`pending` 表示问题仍可回答；把超时折成「用户拒绝了」会让模型做出与事实相反的决策。
- **给会话加同版本迁移**：同版本日志跳过相邻迁移，恢复后可能混合历史与较新记录分支；归一化不能只靠 `restoreCurrent`。
- **在 `complete: true` 上做扩展**：它抑制整个正常系统消息，会连带移除其他插件的指令。
- **把 fork 当成第三档**：fork 是独立开关，与 `view`／`write` 正交；任何环节都不会推断出 `write`。
- **在响应式注册里只在 `available()` 做网络探测**：账号与 Web 两个 seam 都把「本地能否选它」与「远端能否发出去」分开，混用会让每次调用都变慢且不稳定。

## 代码/配置示例

贡献一段系统提示词，并保持可更新、可撤回：

```ts
import type { Context } from '@deepseek-ai/cordis'
import '@deepseek-ai/dsh-system-prompt'

export function registerInstructions(ctx: Context, initialText: string) {
  let currentText = initialText
  const dispose = ctx.systemPrompt.section({
    name: 'example:workspace-policy',
    order: 200,
    text: () => currentText,
    interpolate: false,
    replacement: 'The workspace policy has changed.',
    retirement: 'The workspace policy no longer applies.',
  })
  return {
    update(text: string) { currentText = text },
    dispose,
  }
}
```

声明一个后台任务生产方，注意 `done` 的语义是「资源已释放」：

```ts
ctx.jobs.start({
  kind: 'bash',
  label: command,
  owner: exec.agent,
  output: [{ read: fromByte => shell.readFrom(fromByte) }],
  run(job) {
    const child = spawn(command)
    return {
      cancel(reason) { child.kill(reason) },
      done: child.exited.then(code => ({ status: 'completed', exitCode: code })),
    }
  },
})
```

## 参考表

账号 Remote 面（不含凭据）：

| 方法 | 回答 | 退登或凭据变化时 |
|---|---|---|
| `getState` | 本地是否存在账号与最近一次登录尝试 | 返回快照，不含凭证与 PKCE secret |
| `getProfile` | Platform 资料 | `null` |
| `getBalance` | 充值钱包 `value` 与赠送钱包 `bonusWallets`，各留币种与十进制余额字符串 | `null`，失败时不带钱包数组 |
| `getNotifications` | `nextPollAfterSeconds` + 按服务端顺序的通知 | `null` |
| `signOut` | 本地移除 grant 后的已退登状态，保留 API 密钥 | 远端失败也不恢复 grant |

任务生命周期与状态：

| `JobStatus` | 含义 | 生产方事实落在哪里 |
|---|---|---|
| `running` | 正在执行 | `JobView.progress`（实时行） |
| `stopping` | 已请求终止、尚未结算 | 同上 |
| `completed` | 正常完成 | `JobView.detail` |
| `killed` | 被取消；注册表会附加 kill 原因 | `JobView.detail` |
| `failed` | 出错或被强制失败 | `JobView.detail` |

LiveShare 读取结束时的处理：

| Relay 回答 | 处理 |
|---|---|
| 404 或 410 | 撤回分享：结束其持有的授权，停止 viewer 发起的轮次 |
| 401 或 403 | 结束准入但不撤回分享：停止服务 viewer 输入，释放已打开的调用与流，所有者自己的轮次继续 |
| 超时、其他状态、响应无法解析 | 保留已持有的声明与其允许的一切；viewer 入口在读取重新成功前保持拒绝 |

## 实例演练

一个 viewer 对共享会话说「把这个文件改一下」，端到端走一遍。

所有者创建分享时选 `write` 档并打开 `allowsFork`。来源会话在自己的作用域里被 `installSourceSessionAccess` 装上执行层：为部署提供的每个读取与检索面工具注册受限替代，并因为存在可写分享而额外注册有界 `edit` 与 `write` 替代。

viewer 的 prompt 经 Gateway 分派，策略据 `remote-access` 判出 `share-viewer` principal。`Session Controller` 在 `prompt` 投递前、以及与 `cancel` 同一同步步骤内重新读取 `remoteAccess.allows()`，所以「Gateway 放行之后访问权才结束」的查看者既不会投递也不会取消任何内容。

`agent/pre-step` 把「本轮输入带 share-viewer principal」记进 Host 内存。此后该轮次每次工具执行都读这个结论：受限 `edit` 解析自己参数声明的每个路径，检查获授根目录包含每个目标，再以目标的规范路径委托，并用 `fs/edit-intent` 发布 `editText` 返回的版本。异步意图等待后，Host 再解析当前沙箱策略并重新检查分享授权。

若这时所有可写分享降为 `view`，执行层被重装为只读：后续写入被拒，不授予任何新工具，也不承诺立即取消正在运行的轮次。若分享被移除，已记录的分叉会话被撤销，由 viewer 发起的那一轮被停止；所有者自己发起的轮次继续运行，并按各自源会话记录的来源判定。

## 关键要点

1. 凭证只在 Host 侧解析，消费方只说明目标地址；撤销靠 `revoked` 信号，而不是靠调用方自觉。
2. 分享的能力用「档位 + 独立开关 + 上限名单」三件套表达，不要试图用一个枚举涵盖所有组合。
3. 后台任务的授权边界是拥有者会话，不是 id；结算 first-wins，`done` 的语义是资源已释放。
4. 输出环区分消费式游标与观察者偏移，两者永不相扰；拉取源与推送追加可以同时用。
5. 展示面数据（交付、改动、反馈）走仅写日志事件；它们可回放，但绝不进入模型请求。
6. `intent` 只改呈现，`pending` 只表状态，`retirement` 只在无可见注册时发出——三者都是「协议比呈现更严格」的例子。
7. 系统提示词按节拆分：稳定的回答规则与频繁变化的工作区指令分开，只更新变化的那一节。
8. 时间偏移用「本地减 UTC 的秒数」，UTC+8 是 `28800`；别写成时区名或带符号的小时数。

## 关联

- **第 33 章**：存储、设置与凭据——账号凭据就是凭据 seam 里的一条记录。
- **第 30 章**：工具、审批与调度——`approval` intent 与审批 seam 是同一套决策词汇的两端。
- **第 28 章**：会话与对话——`job/registered`、`job/settled`、`workspace/changes` 都是 Session 日志里的仅写日志事件。
- **第 29 章**：Agent 与子代理编排——分叉会话与 subagent 共用同一条「新会话由谁拥有」的判断。
- **第 12 章**：文档规范——子系统目录的「每子系统一页 + 生成 Cordis API 段」结构与本章表格同源。
