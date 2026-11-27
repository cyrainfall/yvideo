# 第 9 章：CLI 与命令面

## 核心思想
`dsh` 是一个**profile 启动器**，不是一组硬编码子命令：`--profile` 选中的是一棵「有序的插件 bundle 补丁层（patch layer）」组合树，所有具体能力都由这棵树决定。因此命令面的第一原理是「启动什么组合」，第二原理才是「给这个组合传什么 app 参数」。原文较薄——本章主要事实来自生成式帮助文本，机制细节以第 15–21 章的 Cordis 组合与装载为主。

## 框架与方法

- **Profile 作为启动单元（profile）**：`--profile <name>` 指向 `$DSH_HOME/profiles` 下的一个 profile 目录。帮助文本对 dsh 的一句话定义是「启动一个 DeepSeek Harness profile——一个在你自己的覆盖层之下的、有序的插件 bundle 补丁层栈」。
  - 何时用：任何一次启动。
  - 怎么做：先决定用哪个随附 profile 模板（`web`、`headless`、`acp`、`sdk`、`sdk-minimal`、`tui`），再决定在它之上叠多少层覆盖。

- **分层组合（layer stack）**：组合顺序是固定的三层——随附的 shipped profile 模板 → 用户层 → `--patch` 覆盖层。`--patch <path>` 是可重复的，追加在 profile 层之后。
  - 何时用：要在不改动 profile 的前提下临时加一个插件或改一段配置。
  - 怎么做：用 `--patch` 而不是编辑 profile；一次要叠多个就重复传参。要换掉整棵用户层，用 `--from-default-profile <name>` 用一个随附模板的新副本替换自定义 profile，再启动它。

- **三件 dump（profile 可观测性）**：`--dump-config` 打印组合后的 profile 树并退出；`--dump-default-config` 打印去掉用户层与 `--patch` 覆盖之后的 profile 树并退出；`--dump-config-schema` 打印 profile 条目与 patch 的 JSON Schema，且不挂载任何东西。
  - 何时用：怀疑某一层的覆盖没有生效；要给 patch 文件做编辑器补全。
  - 怎么做：比较 `--dump-default-config` 与 `--dump-config` 的差，就等于看到「用户层 + patch 层究竟加了什么」。这是判断覆盖是否命中的唯一可靠手段，比读配置文件快。

- **launcher flag 与 app arg 的分界**：`dsh [--profile] <name> [options] [app-args...]`——launcher 自己的 flag 在 `<name>` 之后、app 参数之前；launcher flag 之后的一切原样交给 app。
  - 何时用：不确定某个参数归谁。
  - 怎么做：帮助示例写得很直白——`dsh tui --resume <session>` 里 `--resume` 是 app 的参数，`dsh tui --patch ./extra.yml` 里 `--patch` 是 launcher 的。要查某个 profile 自己的 flag，用 `dsh <profile> --help` 或等价的 `dsh --profile <profile> --help`。

- **插件管理转发（pnpm forwarding）**：`dsh plugin --profile <name> <pnpm-args...>` 把剩余参数原样转发给 profile 目录下的 pnpm：`add <pkg>`、`remove <pkg>`、`why <pkg>` 都直接可用。profile 在首次使用时初始化。
  - 何时用：给某个 profile 装/卸插件。
  - 怎么做：不要在 `dsh plugin` 后面写 dsh 自己的 flag——它们会被当成 pnpm 参数。把 `--profile` 放在前面，剩下交给 pnpm。

- **命令面（command surface）**：`dsh` 本体 + `dsh plugin` + 五个协议/界面 profile 入口：`acp`、`headless`、`sdk`、`sdk-minimal`、`web`。帮助文档的编排原则是「同一份帮助只展示一次，并列出所有调用方式」——所以 `dsh acp --help` 与 `dsh --profile acp --help` 是同一段文本。

- **信任边界（browser-trust fence）**：Web profile 的三个 flag 各自守一条边界。`--host` 只接受某个本地接口的一个具体 IPv4/IPv6 字面量，通配地址被拒绝。`--public-url <url>` 把某个 HTTP(S) 根广告到打印、打开、运行时上下文和 `DSH_WEB_URL` 四种形式里，但**不授予任何信任**。`--trusted-host <authority...>` 才是给 `/api` 浏览器信任围栏增补接受方（host 或 host:port，可重复）。
  - 何时用：把 Web UI 放到反向代理后面，或绑到非默认网卡。
  - 怎么做：广告地址归 `--public-url`，放行 authority 归 `--trusted-host`，两件事必须同时配；只配前者不会让请求通过围栏。

- **成对参数（mutual requirement）**：`--tls-cert` 与 `--tls-key` 互相要求，给一个不给另一个是错误用法；证书是 PEM 服务端证书链，私钥是不加密的 PEM 私钥。

- **生成式帮助（generated help）**：整份 CLI 参考由 `scripts/gen-cli-help.ts` 生成，`pnpm run gen-cli-help` 重新生成，`pnpm run verify-cli-help` 校验是否与当前命令一致。帮助输出保留原文。
  - 何时用：改了任何 flag。
  - 怎么做：不要手改帮助文档；改命令定义再重新生成，让校验门禁通过。

## 关键概念
- **profile**：`$DSH_HOME/profiles` 下一个可启动的插件组合，帮助文本称之为「有序的插件 bundle 补丁层栈」。
- **patch layer**：`--patch` 引入的一层覆盖，可重复，追加在 profile 层之后。
- **用户层（user layer）**：`--dump-default-config` 会去掉的那一层，即「你自己的覆盖」。
- **shipped profile template**：随附的 profile 模板，`--from-default-profile` 用它替换自定义 profile。
- **app-args**：launcher flag 之后的参数，原样传给被启动 profile 的 app。
- **`DSH_WEB_URL`**：`--public-url` 会同步广告的运行时 URL 形式之一。
- **browser-trust fence**：`/api` 上的浏览器信任围栏，由 `--trusted-host` 增补接受方。
- **stdio 协议 profile**：`acp`（Agent Client Protocol）、`sdk` / `sdk-minimal`（stdio JSON-RPC），都服务到客户端断开为止。

## 心智模型
- 把 profile 看成一棵可 dump 的树，而不是一份配置文件——树有三层，`--dump-default-config` 与 `--dump-config` 的差就是你的覆盖。
- 把 `dsh <name> --help` 和 `dsh --profile <name> --help` 看成同一条命令的两种写法，而不是两个不同入口。
- 把 `--public-url` 看成「广告」，`--trusted-host` 看成「放行」：广告不改信任。
- 把 `dsh plugin` 看成 pnpm 的一层薄外壳，参数是 pnpm 的，不是 dsh 的。

## 反模式
- **给 `--host` 传通配地址**：只接受本地接口的一个具体字面量，通配会被拒绝；要对外暴露应该走 `--public-url` 加代理。
- **只配 `--public-url` 就以为反代可用**：`/api` 的信任围栏仍会拦，必须同时给 `--trusted-host`。
- **只给 `--tls-cert` 或只给 `--tls-key`**：两者互相要求，单给是错误。
- **在 `dsh plugin` 后面写 dsh 的 flag**：参数被 verbatim 转发给 pnpm，行为与预期不符。
- **手改 CLI 帮助文档**：它是生成物，`verify-cli-help` 会发现不一致。
- **用 `--from-default-profile` 指望保留自定义内容**：它是「用新副本替换」，自定义层会被丢掉。
- **把 launcher flag 写到 app 参数之后**：那之后的参数一律归 app，launcher 不再解析。

## 代码/配置示例

启动器调用形式与三个 dump 开关：

```text
Usage: dsh [--profile] <name> [options] [app-args...]
       dsh plugin --profile <name> <pnpm-args...>

Options:
  -V, --version                  output the version number
  --profile <name>               the profile under $DSH_HOME/profiles to boot
  --from-default-profile <name>  replace a custom profile with a fresh copy of a
                                 shipped profile template
  --patch <path>                 extra patch-list overlay applied after the
                                 profile layer (repeatable)
  --dump-config                  print the composed profile tree and exit
  --dump-config-schema           print JSON Schema for profile entries and
                                 patches without mounting
  --dump-default-config          print the profile tree without its user layer
                                 or --patch overlays and exit
```

Agent Client Protocol 入口（无自有 flag）：

```text
Usage: dsh --profile acp [options]
Serve automation clients over Agent Client Protocol stdio.
  -h, --help  show this help
```

## 参考表

命令面（调用方式 / 作用 / 边界）：

| 调用 | 作用 | 要点 |
|---|---|---|
| `dsh [--profile] <name>` | 启动一个 profile | flag 之后的一切是 app 参数 |
| `dsh plugin --profile <name> <args>` | 管理 profile 的插件 | 剩余参数 verbatim 转发给 profile 目录下的 pnpm；profile 首次使用时初始化 |
| `dsh acp` | 以 ACP stdio 服务自动化客户端 | 无自有 flag，服务到客户端断开 |
| `dsh headless` | 回答一个任务后退出 | 答案走 stdout、诊断走 stderr；`task` 多词用空格连接，`-` 读 stdin |
| `dsh sdk` / `dsh sdk-minimal` | 以 stdio JSON-RPC 服务 SDK 客户端 | 两个 profile 文字描述相同，各自独立 |
| `dsh web` | 服务浏览器 UI | 见下表 |

`dsh headless` 与 `dsh web` 的 flag 语义：

| Flag | 归属 | 语义 |
|---|---|---|
| `--json` | headless | 输出按行分隔的运行事件，代替最终消息 |
| `--session-id <id>` | headless | 采用该 id 的已持久化 Session；未知 id 是错误 |
| `--permission-mode <preset>` | headless | 为本次任务选一个已配置的权限预设，恢复会话时同样适用 |
| `--approval-policy <policy>` | headless | 在选定权限预设之后设置审批行为，取值 `ask` / `never` |
| `--add-dir <path>` | headless | 在 `workspace-write` 下额外允许一个物理绝对目录，可重复 |
| `--host <host>` | web | 本地接口的一个具体 IPv4/IPv6 字面量；通配地址被拒绝 |
| `--port <port>` | web | 监听端口；`0` 表示让操作系统挑一个空闲端口 |
| `--no-open` | web | 不在默认浏览器里打开 UI |
| `--public-url <url>` | web | 在打印/打开/运行时上下文与 `DSH_WEB_URL` 中广告该 HTTP(S) 根；不授予信任 |
| `--trusted-host <authority...>` | web | `/api` 浏览器信任围栏额外接受的 authority（host 或 host:port），可重复 |
| `--tls-cert <file>` | web | PEM 服务端证书链，需要 `--tls-key` |
| `--tls-key <file>` | web | 不加密的 PEM 私钥，需要 `--tls-cert` |

## 实例演练

场景一：把 Web UI 放到一个会剥前缀的 HTTPS 反向代理后面。原始命令形态是：

```text
dsh --profile web --public-url https://app.example/ui/ --trusted-host app.example
```

推演这三层含义。`--profile web` 选的是随附 web 模板这棵树。`--public-url https://app.example/ui/` 把外部看到的根换成带 `/ui/` 前缀的 HTTPS 地址，并让这个值同时出现在四处：控制台打印的地址、自动打开的地址、注入页面的运行时上下文、以及 `DSH_WEB_URL`。`--trusted-host app.example` 则是另一件事——它把 `app.example` 加进 `/api` 浏览器信任围栏的接受列表。省略后者，页面能加载但 `/api` 调用会被围栏挡掉；省略前者，围栏放行了但打印出来的地址仍然是内部监听地址，代理前缀不会被剥掉。这两件事必须成对出现，正是因为帮助文本特意写明「广告不授予信任」。

如果要连 TLS 一起自备，再加 `--tls-cert ./server-chain.pem --tls-key ./server-key.pem`——这一对是互相要求的，缺一个就是非法组合。

场景二：重建一个坏掉的 profile。`dsh rescue --from-default-profile web` 的含义是「用随附的 web 模板重新造一个 rescue，然后启动它」。它不保留 rescue 原有的任何自定义内容——这是替换，不是合并。要保留自定义内容又只想加一层，应该走 `--patch`：

```text
dsh tui --patch ./extra.yml
```

推演顺序正好对应三层：shipped `tui` 模板 → 用户层 → `./extra.yml`。验证覆盖是否命中不必读文件，跑 `dsh tui --dump-default-config` 与 `dsh tui --dump-config` 对比即可；后者多出来的部分就是用户层加 patch 层的净效果。要做 patch 文件的编辑器校验，用 `--dump-config-schema` 拿 JSON Schema——它不挂载任何插件，所以可以在 profile 本身跑不起来的时候使用。

## 关键要点
1. `dsh` 的抽象单位是 profile，不是子命令；`--profile` 决定组合树。
2. 层的顺序固定：shipped 模板 → 用户层 → `--patch`（可重复）。
3. 用 `--dump-config` 与 `--dump-default-config` 的差来验证覆盖是否生效。
4. launcher flag 与 app 参数以位置分界，flag 之后一律归 app。
5. `dsh plugin` 的参数是 pnpm 的，dsh 自己的 flag 要放在 `--profile` 一侧。
6. `--public-url` 只广告、`--trusted-host` 才放行，反代场景必须成对配置。
7. `--tls-cert` 与 `--tls-key` 互相要求；`--host` 拒绝通配地址。

## 关联
- **第 15–21 章 Cordis 入门到进入 Harness**：profile 的「有序插件 bundle 补丁层栈」由 loader 与 include/patch 插件实现，本章只讲命令面。
- **第 7 章 开发工作流**：`pnpm run dev:web` 会把参数转发给 `dsh web`，开发期命令是本章命令面的封装。
- **第 19 章 配置**：`--dump-config-schema` 输出的 JSON Schema 来自 Schemastery 的 `Schema`。
- **第 36 章 Web 客户端**：`--public-url`、`--trusted-host`、`--tls-*` 最终作用在 webserver 与 `/api` 信任围栏上。
- **第 30 章 工具、审批与调度**：`--permission-mode` 与 `--approval-policy` 是权限预设与审批策略的命令行入口。
