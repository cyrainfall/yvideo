# E01 演示预跑收据 · cordis_inspect

> 采集时间：2026-11-26 22:39 +0800
> 采集方式：本机运行中的 DSH 实例，`cordis_inspect`（Host 平台）
> 原始目录：同目录 `service-catalog.json`（120 个服务，123 KB）

## 结论（先看这个）

**可以落收据，但不能"一屏指认三角色"。**

| 角色 | inspect 能否直接给 | 实际拿法 |
|---|---|---|
| 定义（Definition） | ✅ 能 | `Service.listService {service:"shell"}` 返回活体合约：key、abstract 方法、`access` 双通道 |
| 提供方（Provider） | ❌ 不能直接给 | 服务目录不记 provider 归属，只能靠 `Config.listConfigs`（插件行）+ 源码装配 |
| 消费方（Consumer） | ❌ 不能直接给 | 同上；`tool-bash` 在本实例是 `inactive`，不能拿"工具存在"当消费方证据 |

因此 E01 现场的演示必须改成**三段收据串联**，而不是一个面板指认：

1. `shell` 合约（定义）—— 屏幕上给 `access` 那一段；
2. `Config.listConfigs` 的 `bash-sandbox` / `tool-bash` 两行（插件两侧）；
3. 源码 file:line 的装配（`FACTS.md` 表）—— 把三者钉在同一个能力上。

## 收据 1 · 定义：`ctx.shell` 的双通道访问

`Service.listService {service:"shell"}` 原文：

```json
"access": {
  "optional": {
    "expression": "ctx.get(\"shell\")",
    "requiresUndefinedCheck": true
  },
  "hardDependency": {
    "inject": ["shell"],
    "expression": "ctx.shell"
  }
}
```

描述原文（节选）：

> Abstract bash execution service. Subclass, implement the abstract methods, and load the subclass as a plugin — it registers as `ctx.shell` (**one implementation per context; loading a second throws**, which is cordis' standard duplicate-service behavior).

这段同时证明了 E01 的两个断言：**消费方按 key 取用**、**提供方缺席是合法状态**（走 `ctx.get()` + undefined 检查），不用再找第三份材料。

## 收据 2 · 注册形态（活体合约，全部来自同一次目录扫描）

| 形态 | 服务 | 运行时原文（节选） |
|---|---|---|
| 命名注册表 | `llm` | "The abstract `llm` service: an adapter registry plus a streaming model-call API" · `registerAdapter(providers: string[], adapter)` / `listProviders()` |
| 单槽 | `browserUse` | "Reserve the **sole provider slot** until the contribution is disposed. **A second registration fails even when it repeats the current name.**" |
| 有序尝试 | `deepseekAuth` | `candidates()` "in the order its billing tries them" · `authorize()` "**A later candidate is not read once an earlier one has a credential**, fails to read, or does not resolve." |
| 每上下文一实例 | `shell` | "one implementation per context; loading a second throws" |
| 注册即绑定 | `credentials` | 抽象服务；"presence of the record is the whole fact, and `modifyRecord` is the only write path" |
| （补充）单流每 key | `authorization` | "One flow per key: two plugins claiming the same key would each write a record in their own format…" · 抛 `DUPLICATE_FLOW` / `NO_FLOW` / `ALREADY_IN_FLIGHT` / `NOT_COMMITTED` |

> 注：`authorization` 是"每 key 一条授权流"，与 `deepseekAuth` 的"按顺序试候选"是两种不同纪律，E01 讲"有序尝试"应选 `deepseekAuth`，别混用。

## 收据 3 · 两侧的插件行（本实例真实配置）

`Config.listConfigs`（248 条中的命中）：

```json
{ "id": "include:bash-sandbox", "patchId": "bash-sandbox", "name": "@deepseek-ai/dsh-bash-sandbox", "status": "schema" }
{ "id": "include:tool-bash",    "patchId": "tool-bash",    "name": "@deepseek-ai/dsh-tool-bash",      "status": "inactive" }
```

两个重要事实（对分镜有影响）：

1. **本机运行时只有 `bash-sandbox` 一个 shell 提供方**，没有 `bash-local` 插件行 —— 因为 `bash-sandbox` 直接继承 `bash-local` 的执行机制（源码 `packages/shell/bash-sandbox/src/index.ts` 的 `import { LocalBashExecutor } from '@deepseek-ai/dsh-bash-local'`），`bash-local` 在这里是库依赖而非独立插件。
2. **`tool-bash` 是 `inactive`**，所以不能拿"我这边有 bash 工具"当消费方证据；消费方要落到源码的 `ctx.shell` 取用点。

## 对 E01 分镜的影响（待并入 STORYBOARD）

- 原设想"`cordis_inspect` 真枚举一份服务目录，在真实注册表里指认三角色各是谁" → 改为"**服务目录证明定义与注册形态；插件目录证明两侧存在；源码钉死装配**"，三段各 8–12 秒。
- 顺带得到一个更硬的判据可上屏：**"同一条缝，装第二个实现就抛错"不是文档规定，是运行时自己写出来的**（`shell` 合约原文）。
- 演示备胎：若现场 DSH 版本不同导致 `Config` 行号/状态变化，退回"合约 + 源码 file:line"两段，不影响结论。

## 可复现命令

```text
cordis_inspect {platform:"host", provider:"Service", method:"listService", input:{}}
cordis_inspect {platform:"host", provider:"Service", method:"listService", input:{service:"shell"}}
cordis_inspect {platform:"host", provider:"Config",  method:"listConfigs", input:{name:"@deepseek-ai/dsh-bash-sandbox"}}
cordis_inspect {platform:"host", provider:"Config",  method:"listConfigs", input:{name:"@deepseek-ai/dsh-tool-bash"}}
```
