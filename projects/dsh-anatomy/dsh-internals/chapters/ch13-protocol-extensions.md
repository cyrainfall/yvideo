# 第 13 章：协议扩展与实验性持久化

## 核心思想

DSH 在 DeepSeek 官方 API 上叠加了两类东西，并刻意把它们与「模型可见的请求」隔开：一类是走 HTTP 的在线扩展（请求标头加 `dsh_` 前缀的正文字段），一类是不进 schema 的实验性日志记录。前者靠独立版本与事务式接受保证「缺失也安全」，后者靠 `ignorable` 与不参与指纹保证「不污染兼容性历史」。理解这两条隔离线，比记住字段名更重要。

## 框架与方法

- **协议命名空间与独立版本（namespace per位置，version per字段）**：位置决定命名法，命名法本身是协议的一部分。
  - 何时用：新增任何线上字段、标头或带标签的值时。
  - 怎么做：HTTP 字段名用小写 kebab-case（HTTP 匹配仍不区分大小写，如 `user-agent`、`x-deepseek-harness-session-id`）；DeepSeek 请求正文扩展字段用保留 `dsh_` 前缀的 snake case（`dsh_plugin_packages`、`dsh_session_log`）；DSH 持有的嵌套 JSON 成员用 Camel case（`afterSeq`、`throughSeq`、`sessionId`）；带标签的值用 kebab-case 字符串，持久事件采用 `domain/action`（`session-log-deepseek/delivery-accepted`）。每个正文扩展独立持有自身的 `version`，版本仅适用于包含该字段的对象——不同字段的版本之间既不存在兼容关系，也不存在排序关系；JSON 成员顺序不属于协议。

- **注册表的前置校验（`DeepSeekLlmApiExtensionRegistry`）**：每个顶层扩展名只保留一个提供方。
  - 何时用：接入新的正文扩展时。
  - 怎么做：在 HTTP 分派之前就让坏名字失败——空名称、两端带空白的名称、重复注册，以及与 DeepSeek 基础请求冲突的名称，一律拒绝，不要留到运行时才发现。

- **事务式贡献（prepare → merge → accept）**：适配器先序列化包含确切 `messages` 在内的完整基础正文，再让已注册提供方准备字段。
  - 何时用：任何需要随请求携带状态的贡献方。
  - 怎么做：提供方拿到的是不可变正文、请求取消信号，以及可选的 `sessionId` 与辅助调用 `purpose`；返回 `undefined` 表示本次请求省略其字段。系统把「已准备的 JSON 值」与「提供方持有的状态」分离，再把前者作为基础字段的顶层同级成员合并、序列化到同一个 HTTP 正文。三条失败路径要分清：某个贡献方准备失败 → 该次请求只省略它的字段，只记录首次失败，其余字段照常发送；贡献字段与基础字段冲突 → 阻止请求；合并后的正文无法序列化 → 发送不含任何扩展字段的基础正文、跳过接受事务、记录被省略的字段名，让贡献方在之后的请求里重发自身状态。组合未挂载注册表时，直接发未经扩展的基础正文。
  - 接受时机：只有在已配置端点返回 HTTP 2xx 之后、读取 SSE 正文之前才运行 `accept()`。传输失败和非 2xx 不接受任何贡献；接受失败只记告警，不会让模型请求失败。

- **水位与至少一次交付（watermark + at-least-once）**：`dsh_session_log` 每段都带 `afterSeq` 与 `throughSeq`，把「已经确认被端点收下的最大序号」变成可重建的游标。
  - 何时用：任何需要跨请求续传会话状态的场景。
  - 怎么做：首次上传用 `afterSeq: -1`；此后每次从同一会话 id 的最大已接受水位之后开始，携带从该位置起、序列化后能放进 `maxBytes` 的最长连续事件段。发送方只为当前 Session id 与格式 generation 折叠最大的匹配 `throughSeq`——并发到达的接受因此无法让游标倒退，其他 generation 的水位也不能授权当前后缀。恢复后的进程从持久日志重建游标；fork 会忽略命名其他 Session 的继承水位，所以它从序号零开始、按 `maxBytes` 分多次请求上传自身的继承前缀，再以子会话 id 推进。不等式的方向很重要：端点接受后、本地持久化前崩溃可能重发已接受范围，不确定性只产生重复，绝不产生序号缺口。

- **暴露面分级（exposure tiers）**：三类扩展暴露的信息量递增，接收方的义务也随之递增。
  - 何时用：评审一次线上变更的隐私与兼容影响时。
  - 怎么做：标头只暴露 Harness 应用版本、一个匿名 Harness-home 身份与可选会话身份；`dsh_plugin_packages` 暴露存活 npm 包的名字与版本，属于提供方元数据，绝不进入模型输入；`dsh_session_log` 可能暴露工作目录、系统提示词快照、用户与 Assistant 内容、内嵌 Assistant stream、失败 attempt 输出、工具参数与结果、压缩摘要、反馈和插件持有的事件。适配器 API key 不是会话事件，因此不会进入该字段；通过 `baseURL` 选择的网关会收到与官方端点相同的值。

- **实验性记录的隔离（ignorable, log-only）**：实验性包通过 `PluginRecordMap` 声明自己的记录，这些记录是 `ignorable`、仅日志的。
  - 何时用：一个实验性功能需要持久记录，但还不想承担 schema 契约时。
  - 怎么做：让记录不进入已知事件集合、不进入持久化 schema 指纹、也不进入兼容性历史；格式迁移以尽力而为的方式保留它们。代价是不提供无损保证——想要兼容性承诺，就必须把记录提升为正式事件，而不是靠实验性目录。

- **生成目录纪律（gen / verify）**：实验性记录目录与共享会话事件目录都是生成物。
  - 何时用：发现表格「少了一行」或字段注解过期时。
  - 怎么做：改源码里的 `PluginRecordMap` 声明，然后 `pnpm run gen-persistence-catalog` 重新生成两份目录及其英配对与关联制品；`pnpm run verify-persistence-catalog` 检查所有生成文件。

## 关键概念

- **`dsh_` 前缀**：DeepSeek 请求正文中保留给 DSH 扩展字段的命名空间标记；带此前缀的才是本参考定义的字段。
- **扩展注册表（`DeepSeekLlmApiExtensionRegistry`）**：为每个顶层扩展名保留唯一提供方、并在 HTTP 分派前拒绝非法名称的组件。
- **`accept()` 事务**：在端点返回 2xx 之后、读取 SSE 之前运行的接受动作，只记录端点级 HTTP 成功。
- **水位（watermark）**：同一会话 id 与格式 generation 下被折叠取最大的 `throughSeq`，代表已确认被接受的进度。
- **`delivery-accepted`**：追加到会话日志的权威事件（`session-log-deepseek/delivery-accepted`），携带 `sessionId`、`sessionFormatVersion` 与 `throughSeq`。
- **`maxBytes`**：单次上传字段的字节上限，默认 8 MiB，按 UTF-8 字节计算并包含 header 与数值字段。
- **表层事件（surface event）**：必须携带 `surfaceOp` 的事件；替换范围用数值 `startSeq`/`endSeq`，system、user、tool 事件还可携带数值 `sourceEventSeqs`。
- **实验性记录（experimental record）**：实验性包拥有、`ignorable` 且仅日志的记录，不参与已知事件集合与 schema 指纹。

## 心智模型

- 把正文扩展看成「挂载在基础请求上的旁挂车厢」：不装载也不影响列车运行，所以抛掉任何一节都不该让请求失败。
- 当一次请求被网关收下时，把它看成一个端点级回执，而不是「远端已经存好了」——2xx 与持久化是两件事。
- 把 `afterSeq`/`throughSeq` 看成一个只向前滚的棘轮：允许重复，绝不允许跳过。
- 把实验性记录看成「写在便签上的日志」：能读就用，读不到不算违约，且永远不要让便签影响正式契约。

## 反模式

- **把扩展字段写进 `messages`、系统提示词或工具 schema**：那会占用模型输入 token 并改变模型可见前缀；扩展必须待在这些之外。
- **用 2xx 推断 SSE 完整或远端已持久化**：接受只记录端点级 HTTP 成功；积压补传期间 `throughSeq` 甚至落后于会话最新事件。
- **让一个失败字段带崩整次请求**：准备失败应只省略该字段并记录首次失败；只有与基础字段冲突才阻止请求。
- **按包名折叠 `packages` 数组或据顺序推断激活关系**：同一包的多个存活版本必须保留为独立配置项，接收方必须接受版本缺失。
- **把实验性记录当兼容性契约**：它们不进入指纹、不进兼容性历史，迁移只尽力而为。

## 代码/配置示例

插件包清单：默认启用，每请求重读存活的 Loader 配置项。

```json
{
  "dsh_plugin_packages": {
    "version": 1,
    "packages": [
      {
        "name": "@deepseek-ai/dsh-example",
        "version": "0.1.1-rc.2"
      }
    ]
  }
}
```

会话日志后缀（示例借用逻辑 Session 格式 2，仅说明协议字段）：

```json
{
  "dsh_session_log": {
    "version": 1,
    "sessionFormatVersion": 2,
    "session": {
      "version": 2,
      "id": "session-id",
      "createdAt": 1780000000000
    },
    "afterSeq": -1,
    "throughSeq": 0,
    "events": [
      {
        "type": "turn/start",
        "seq": 0,
        "time": 1780000000001,
        "data": { "turn": 1 }
      }
    ]
  }
}
```

接受之后追加的水位事件：

```json
{
  "type": "session-log-deepseek/delivery-accepted",
  "seq": 8,
  "time": 1780000000002,
  "data": {
    "sessionId": "session-id",
    "sessionFormatVersion": 2,
    "throughSeq": 7
  }
}
```

## 参考表

命名空间与版本：

| 位置 | 命名方式 | 示例 |
|---|---|---|
| HTTP 字段名 | 小写 kebab-case，匹配不区分大小写 | `user-agent`、`x-deepseek-harness-session-id` |
| 正文扩展字段 | 保留 `dsh_` 前缀的 snake case | `dsh_plugin_packages`、`dsh_session_log` |
| DSH 持有的嵌套 JSON 成员 | Camel case | `afterSeq`、`throughSeq`、`sessionId` |
| 带标签的值 | kebab-case 字符串，持久事件用 `domain/action` | `session-log-deepseek/delivery-accepted` |

请求标头：

| 标头 | 出现条件 | 值 |
|---|---|---|
| `user-agent` | 每个提供方 HTTP 请求，含 Files API 操作 | `product/version (+url)` 形式的应用身份，后接 `dsh-profile/<profile>`；`tchar` 以外的字节与 `%` 做百分号编码；默认产品 `deepseek-harness` |
| `x-deepseek-harness-user-id` | 每个已授权的模型请求 | 已解析 Harness home 的稳定匿名 UUID |
| `x-deepseek-harness-session-id` | 携带会话 id 的模型请求 | 确切的请求 `sessionId` 字符串 |
| `x-deepseek-harness-compact` | 用途为 `compaction` 的模型请求 | 字面字符串 `1` |

`dsh_session_log` 顶层成员：

| 成员 | 类型 | 含义 |
|---|---|---|
| `version` | `1` | 本扩展的 schema 版本 |
| `sessionFormatVersion` | 非负整数 | 该后缀所表示的 Session 格式 generation |
| `session` | 对象 | 当前 Session header 的不可变协议投影 |
| `afterSeq` | 整数 | 本次请求前记录为已接受的最大序号，或 `-1` |
| `throughSeq` | 非负整数 | 本次请求所表示的最大序号 |
| `events` | 数组 | 从 `afterSeq + 1` 到 `throughSeq` 的连续事件 |

Session header 投影：

| 成员 | 出现条件 | 含义 |
|---|---|---|
| `version` | 必需 | 来自 `Session.header` 的逻辑 Session 格式版本 |
| `id` | 必需 | 确切的会话 id |
| `createdAt` | 必需 | 非负安全整数 Unix epoch 毫秒 |
| `cwd` | 可选 | 创建会话时记录的绝对工作目录 |
| `parentSession` | 可选 | fork 的父会话 id |
| `seedLength` | 仅 seeded Session | 确切的继承事件数量，空继承前缀为零 |
| `origin` | 可选 | subagent 子项使用的字面值 `subagent` |
| `delegationDepth` | 可选 | 持久化的非负 subagent 委派深度 |
| `agentPreset` | 可选 | 组合该会话的 agent preset id |

实验性记录（按所属包归组，均为 `ignorable`、仅日志）：

| 所属包 | 记录 | 用途摘要 |
|---|---|---|
| `@deepseek-ai/dsh-experimental-client-ui-forge` | `plugin:client-ui-forge/worktree` | Session 起始 worktree 的请求、撤回或创建 |
| `@deepseek-ai/dsh-experimental-forge-session` | `plugin:forge-session/binding` | 绑定、恢复或隐藏一个变更请求的调用方或发现动作 |
| `@deepseek-ai/dsh-experimental-translator` | `plugin:translator/request`、`plugin:translator/result` | 提供方无关的翻译输入（分派前）与成功结果（返回消费方前） |
| `@deepseek-ai/dsh-experimental-worktree` | `plugin:worktree/created`、`plugin:worktree/entered` | 服务为 Session 创建并进入的 checkout；Session 进入的既有 checkout 及其来源 |
| `@deepseek-ai/dsh-timeline` | `plugin:timeline/tree`、`select`、`priority`、`remove`、`import`、`import-ready` | 任务树的保存、选中、优先级、移除与导入 |
| `@deepseek-ai/dsh-timeline` | `plugin:timeline/annotation`、`reply`、`request`、`report`、`delivery`、`failure` | 讨论与控制请求、agent 回复、区间报告及其请求/接受/失败 |

## 实例演练

走一遍一次会话日志上传的完整链路。

起点：会话已有事件 `seq 0`，端点从未接受过任何东西，本地游标是 `-1`；请求带存活会话且至少有一个事件，因此字段不被省略。

准备：适配器序列化基础正文（含确切 `messages`），`dsh-session-log-deepseek` 提供方拿到不可变正文、取消信号、`sessionId` 与 `purpose`。它按当前水位切出 `afterSeq: -1`、`throughSeq: 0` 的连续段。假设 `maxBytes`（默认 8 MiB）装得下，就一次发完；装不下就只带最长可行前缀，剩下的留给后续请求——积压多时分多次已接受请求传完。

合并：扩展对象作为基础字段的顶层同级成员并入同一 HTTP 正文。会话 header 是投影：未 seeded 的会话不带 `seedLength`，逻辑 `isSeeded` 标志不出现；外层 `dsh_session_log.version` 选本扩展 schema，`session.version` 选逻辑 Session 格式。

接受：端点返回 2xx。适配器在读取 SSE 正文之前运行 `accept()`，于是向同一会话追加 `delivery-accepted`，`seq: 8`、`throughSeq: 7`——注意它标识的是一项更早的事件，水位事件自身属于下一段未发送后缀。此后游标折到 7，下一次请求用 `afterSeq: 7`。

失败分支：如果传输失败或返回非 2xx，什么水位都不追加，下次仍从 `-1` 起；如果接受成功但进程在本地持久化前崩溃，下次可能重发同一个范围——重复是允许的，缺口不允许。恢复后的进程会从持久日志重建游标，所以「内存里丢了」不构成理由。

fork 分支：子会话继承了一段前缀，但继承水位命名的是别的 Session，会被忽略。子会话因此从序号零开始，把继承前缀按 `maxBytes` 分多次上传，然后才以自己的 id 推进。

接收方一侧：先校验连续序号范围，再解释事件类型。遇到不带 `ignorable: true` 的未知权威事件，就无法无损重建；而积压补传期间 `throughSeq` 落后于会话最新事件，所以这次 2xx 不能当作「接收方已持有当前完整日志」。实验性记录即使出现在这段流里，也只是可忽略的旁挂信息，不影响重建。

## 关键要点

1. 扩展必须待在 `messages`、系统提示词与工具 schema 之外，否则就改了模型可见前缀。
2. 每个正文扩展自己持版本；字段之间无兼容关系，别用「统一版本号」替代。
3. 只省略失败贡献的字段，只有与基础字段冲突才阻止请求；不可序列化时退回无扩展基础正文。
4. 只有 2xx 之后才接受；接受不等于 SSE 完整，也不等于远端已持久化。
5. 水位只折叠同一会话 id 与同一 generation 的最大 `throughSeq`；fork 从零开始。
6. 允许重复、禁止缺口——这是崩溃后重发的前提。
7. 实验性记录不进指纹与兼容性历史，因此不能当契约用；要契约就提升为正式事件。

## 关联

- **第 3 章 Agent 生命周期与会话格式**：`sessionFormatVersion`、Session header 投影与格式 generation 的权威定义。
- **第 5 章 API 网关**：请求标头与 `baseURL` 解析发生在网关一侧，扩展随已解析端点发送。
- **第 31 章 模型流式与可观测**：SSE 读取与「接受发生在读取之前」的顺序关系。
- **第 33 章 存储、设置与凭据**：持久化目录、凭据解析与匿名身份文件的边界。
- **第 12 章 文档规范**：本目录属生成参考，只能经 `gen-persistence-catalog` / `verify-persistence-catalog` 更新。
- **外部概念**：消息投递中的 at-least-once（至少一次）语义与 watermark（水位）游标，对应本文的重复优先、缺口禁止。
