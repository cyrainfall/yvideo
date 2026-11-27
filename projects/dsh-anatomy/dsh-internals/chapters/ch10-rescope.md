# 第 10 章：范围重塑 rescope

## 核心思想
Cordis 及其基础库以源码形式 vendored 在 `vendor/` 下，但发布时必须换成 `@deepseek-ai` scope——因为每个 harness 包都把框架声明为 peer dependency，发布 harness 会连带发布这一层，用上游名发布等于在 registry 上占用别人的名字。rescope 就是这次改名的全部规则：它是一份**带白名单的 token 重写**，由脚本执行、由门禁断言、可一键回退；任何引用都不靠手改。

## 框架与方法

- **rescope（范围重塑）**：把 vendored 包的上游名映射为 `@deepseek-ai` scope 下的发布名。
  - 何时用：上游 sync 之后；新增 vendored 包时；发现有引用还写着上游名时。
  - 怎么做：查映射表拿到「目录 → 上游名 → 发布名 → 上游版本 → 角色」五元组，然后让脚本去改，不要手改。

- **名字映射（name mapping）**：九个包，其中 `cordis` → `@deepseek-ai/cordis`（框架核心：`Context`、`Service`、`Fiber`、事件），`cosmokit` → `@deepseek-ai/cosmokit`（框架与 Schemastery 共用的基础工具），`schemastery` → `@deepseek-ai/schemastery`（配置 schema，每个插件的 `Config` 都基于它），以及六个 `@cordisjs/plugin-*`（loader、include、group、timer、hmr、logger-console）。
  - 何时用：写 import、写 `package.json` 依赖键、写 `cordis.yml` 插件条目。
  - 怎么做：映射只换 scope 与包名的前缀部分，**子路径导出保持原路径**——`@cordisjs/plugin-loader/repository` 变成 `@deepseek-ai/cordis-plugin-loader/repository`。

- **改名不碰什么（invariants）**：这是 rescope 最重要的一半。七类东西必须保持不变：
  - **目录名与上游源码版本**：`vendor/hmr/` 仍是 `vendor/hmr/`；清单表记录的是所钉住源码快照的上游版本，因此清单读作一份上游快照。而每个 vendored 包 `package.json` 自身的 `version` 字段是 harness 发布的清单版本，`pnpm run release:vendor` 会提升它，重新 sync 时会恢复成上游版本。
  - **依赖 range**：改名只修改依赖键，不改变范围。Workspace 清单使用 `workspace:` 协议；仓库规则区分精确的 DSH 引用与 vendor/native tilde 范围。
  - **Loader 的 `cordis:` 内建前缀**：`cordis:include`、`cordis:group` 是协议前缀，不是包名。
  - **`cordis.yml` 配置文件家族**：包括 `*.cordis.yml`、`*.cordis.snapshot.yml`、`cordis.patch.yml`。
  - **名字里带这个词的 harness 包**：例如 `@deepseek-ai/dsh-tool-cordis`。
  - **上游运行时标识符**：例如 Schemastery 的 `Symbol.for('schemastery')` 及其 `vendor:` 元数据字段。
  - **产品标识符**：`GENERIC_SKIPS` 列出的文件保留所列上游名称对应的 preset ID、事件名、目录分组名，以及 locale 或输入来源键。同一文件中的 import、export、模块声明和 JSDoc import 类型仍会双向改名，JavaScript/TypeScript 围栏内也如此；YAML 插件的 `name:` 值同样改名。所列名称的其他字符串用法保持不变，其他库名仍受检查。
  - **改名测试夹具**：`scripts/rescope-vendor.spec.ts` 和 `scripts/gen-third-party-notices.spec.ts` 保留两种包名拼写作为测试数据。
  - **`docs/` 之外的散文**：`vendor/*/README.md`、各包 README 与 Agent Note 保留写作当时的名字——那里的裸 `cordis` 也可能是 Python SDK 的选项名或某个 agent-preset 的 id。`docs/` 之内的散文和 Markdown 围栏按 token 规则改名，上述经过核对的标识符除外。

- **施加、核验与回退（apply / check / reverse）**：映射由 `scripts/rescope-vendor.ts` 承载并执行改名，三个动作各自独立。
  - 何时用：`rescope-vendor` 无参数时只报告会改什么；要真正改写用 `--apply`；要在 CI 里断言 post-state 用 `rescope-vendor:check`（它跑在 hygiene 门禁里）；要回到上游名用 `--apply --reverse`。
  - 怎么做：默认先跑报告模式看清影响面，再 `--apply`。永远不要在没有报告的情况下直接施加。

- **上游 sync 后重跑（resync recipe）**：上游 sync 之后重跑脚本，并接上它打印的重生成步骤——`pnpm install` 重生成 lockfile、`pnpm run gen-third-party-notices`、以及对它触及的双语对跑 `pnpm run verify-translation-pairing --write`。
  - 何时用：每次 vendor 同步。
  - 怎么做：把这三步当 rescope 的一部分，而不是可选项；漏掉双语配对记录会让文档门禁失败。

## 关键概念
- **vendored**：以源码形式纳入本仓库的上游依赖，位于 `vendor/`，与普通 npm 依赖不同——它参与构建、参与类型检查、参与改名。
- **peer dependency**：每个 harness 包对框架的声明方式；正因为是 peer，发布 harness 才会连带发布这一层。
- **上游名 / 发布名**：`cordis` 与 `@deepseek-ai/cordis` 是同一个包的两个名字，前者是上游，后者是 registry 上的正式身份。
- **子路径导出（subpath export）**：`/<子路径>` 部分在改名中保持不变。
- **`GENERIC_SKIPS`**：产品标识符白名单，列出的文件里若干字符串保持上游原名。
- **manifest 版本 vs 上游版本**：`vendor/*/package.json` 的 `version` 是发布清单版本，映射表的「上游版本」是所钉源码快照的版本。
- **`workspace:` 协议**：Workspace 清单内部的依赖引用形式，改名不动它。
- **reverse**：`--apply --reverse`，把全部引用退回上游名的能力，也是 rescope 可被审阅的前提。

## 心智模型
- 把 rescope 看成一个带白名单的 token 重写器，而不是 `sed`：白名单（`GENERIC_SKIPS`、夹具文件、`docs/` 之外的散文）与重写规则同等重要。
- 把 `vendor/*/package.json` 的 `version` 看成分发布清单的版本号，不是上游版本——两者分属不同层，混读会导致误判 diff。
- 把 `cordis:` 前缀看成协议命名空间而不是包名：`cordis:include` 改掉就废了。
- 把 reverse 看成一次持续的审阅保证：改名的每一步都可逆，所以不需要「一次改对」的运气。

## 反模式
- **手改 import 或依赖键**：映射由脚本唯一承载，手改会漏、会与下一轮 sync 冲突，且 reverse 之后不一致。
- **改目录名**：`vendor/hmr/` 之类必须原地不动，目录名是上游快照的锚点。
- **改依赖 range**：改名只碰依赖键；顺手调整范围会破坏 `workspace:` 与 tilde 范围的分工。
- **改 `cordis:` 内建前缀**：`cordis:include`、`cordis:group` 是协议前缀，改掉就没法装载。
- **改 `cordis.yml` 家族的文件名**：`*.cordis.yml`、`*.cordis.snapshot.yml`、`cordis.patch.yml` 都在不动之列。
- **在 `docs/` 之外的散文里批量改名**：那里的裸 `cordis` 可能指 Python SDK 选项名或某个 agent-preset 的 id，语义已经被历史钉住。
- **改测试夹具里的两种拼写**：那正是测试数据，统一了就测不出双向改名。
- **sync 后只跑 `--apply` 不做重生成**：lockfile、第三方声明与双语配对记录都会过期。

## 代码/配置示例

四个动作：

```sh
pnpm run rescope-vendor            # report what would change
pnpm run rescope-vendor --apply    # rewrite every reference
pnpm run rescope-vendor:check      # assert the post-state; runs in the hygiene gate
pnpm run rescope-vendor --apply --reverse   # return to the upstream names
```

映射表的一行（五元组）：

```text
| vendor/cordis/ | cordis | @deepseek-ai/cordis | 4.0.0-rc.12 | 框架核心：Context、Service、Fiber、事件 |
```

子路径导出保持原路径：

```text
@cordisjs/plugin-loader/repository  →  @deepseek-ai/cordis-plugin-loader/repository
```

## 参考表

九个 vendored 包（原文表）：

| 目录 | 上游名 | 发布名 | 上游版本 | 角色 |
|---|---|---|---|---|
| `vendor/cordis/` | `cordis` | `@deepseek-ai/cordis` | 4.0.0-rc.12 | 框架核心：`Context`、`Service`、`Fiber`、事件 |
| `vendor/cosmokit/` | `cosmokit` | `@deepseek-ai/cosmokit` | 1.8.1 | 框架与 Schemastery 共用的基础工具 |
| `vendor/schemastery/` | `schemastery` | `@deepseek-ai/schemastery` | 3.18.0 | 配置 schema（`Schema`），每个插件的 `Config` 都基于它 |
| `vendor/loader/` | `@cordisjs/plugin-loader` | `@deepseek-ai/cordis-plugin-loader` | 1.0.0-rc.8 | `cordis.yml` 装载、插件解析、repository 缓存 |
| `vendor/include/` | `@cordisjs/plugin-include` | `@deepseek-ai/cordis-plugin-include` | 1.1.1 | 配置包含与 patch 叠加 |
| `vendor/group/` | `@cordisjs/plugin-group` | `@deepseek-ai/cordis-plugin-group` | 1.0.0 | 嵌套插件分组 |
| `vendor/timer/` | `@cordisjs/plugin-timer` | `@deepseek-ai/cordis-plugin-timer` | 1.1.4 | `ctx` 上随 disposal 回收的定时器 |
| `vendor/hmr/` | `@cordisjs/plugin-hmr` | `@deepseek-ai/cordis-plugin-hmr` | 1.0.15 | 插件与配置的热替换 |
| `vendor/logger-console/` | `@cordisjs/plugin-logger-console` | `@deepseek-ai/cordis-plugin-logger-console` | 1.0.0 | 控制台日志导出 |

你的代码要改什么（原文表）：

| 位置 | 改前 | 改后 |
|---|---|---|
| 模块 import | `import { Context } from 'cordis'` | `import { Context } from '@deepseek-ai/cordis'` |
| 类型事件声明合并 | `declare module 'cordis'` | `declare module '@deepseek-ai/cordis'` |
| `package.json` 依赖键 | `"@cordisjs/plugin-hmr": "^1.0.15"` | `"@deepseek-ai/cordis-plugin-hmr": "^1.0.15"` |
| `cordis.yml` 插件条目 | `name: '@cordisjs/plugin-include'` | `name: '@deepseek-ai/cordis-plugin-include'` |

## 实例演练

一次上游 sync 之后的完整 rescope 闭环。

第一步，同步上游源码。此时 `vendor/` 下的源码已经换成新版本，但仓库里所有引用仍然指向 `@deepseek-ai` 的旧名，而新增的上游文件里写着上游名——两边不一致。

第二步，报告模式。`pnpm run rescope-vendor` 不写任何文件，只打印「会改什么」。这一步的价值在于核对白名单是否覆盖到了新出现的上下文：如果脚本报告要改某个 `GENERIC_SKIPS` 里的产品标识符，或者要动 `vendor/*/README.md` 这类 `docs/` 之外的散文，说明识别规则需要先修，而不是硬施加。同理，夹具文件 `scripts/rescope-vendor.spec.ts` 与 `scripts/gen-third-party-notices.spec.ts` 里两种拼写都应该出现在「不改」一侧。

第三步，施加。`pnpm run rescope-vendor --apply` 重写每一处引用：模块 import、`declare module` 的声明合并、`package.json` 依赖键、`cordis.yml` 插件条目的 `name:`、以及 `docs/` 之内散文与 Markdown 围栏里的 token——同时跳过上面列出的七类不动项。子路径导出保持原路径，所以 `@cordisjs/plugin-loader/repository` 只会变成 `@deepseek-ai/cordis-plugin-loader/repository`，`/repository` 不被触碰。

第四步，核验。`pnpm run rescope-vendor:check` 断言 post-state，并且它跑在 hygiene 门禁里，所以本地忘记跑也不会漏到 CI 之外。

第五步，接重生成。脚本会打印需要接着跑的步骤：`pnpm install` 重生成 lockfile（依赖键变了，lockfile 必须跟着变）、`pnpm run gen-third-party-notices`（发布名变了，第三方声明必须重生成）、以及对脚本触及的双语对跑 `pnpm run verify-translation-pairing --write`（改名改到了 `docs/` 之内的 Markdown，配对记录必须重记）。这三步任何一步漏掉，都会在对应门禁上失败。

回退路径随时可用：`pnpm run rescope-vendor --apply --reverse` 把全部引用退回上游名。这也是为什么「不要手改」是硬规矩——只要有一处是手改的，reverse 之后那一处就会留在半途，而脚本无从知道它的存在。

## 关键要点
1. 发布名统一 `@deepseek-ai` scope，理由是不占用上游在 registry 上的名字；这由 peer dependency 的发布连带关系决定。
2. 改名只换名字：目录、目录名、上游源码版本、依赖 range、`cordis:` 前缀、`cordis.yml` 家族、上游运行时标识符、产品标识符、夹具、`docs/` 之外的散文全部不动。
3. 子路径导出保持原路径，只换 scope 与包名前缀。
4. 引用永远由 `scripts/rescope-vendor.ts` 改写；默认先跑报告模式。
5. `rescope-vendor:check` 在 hygiene 门禁里断言 post-state，是唯一的自动化防线。
6. sync 之后必须补齐 lockfile、第三方声明、双语配对三处重生成。
7. `--apply --reverse` 保证可回退；手改会破坏这个保证。

## 关联
- **第 15–21 章 Cordis 入门到进入 Harness**：`@deepseek-ai/cordis` 就是那几章讲的框架本体，本章解释它为什么叫这个名字。
- **第 19 章 配置**：Schemastery 的 `Schema` 是每个插件 `Config` 的基础，也是「不动的上游运行时标识符」之一。
- **第 12 章 文档规范**：`docs/` 之内按 token 改名、`docs/` 之外保留历史名字，这条边界与双语配对记录同属文档门禁体系。
- **第 33 章 存储、设置与凭据**：`pnpm install` 与 lockfile 的关系、`workspace:` 协议的使用都在仓储与依赖层。
- **npm scope 与 registry 命名空间**：rescope 的本质是在别人的命名空间之外为自己的发布层取得唯一身份。
- **源码 vendoring（源码内联依赖）**：与 fork/patch-package 不同，vendored 源码参与本仓构建与类型检查，因此才需要一套可逆的改名机制。
