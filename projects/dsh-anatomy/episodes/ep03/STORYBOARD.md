---
format: 1920x1080
fps: 30
duration: 112.50
episode: EP03
title: 把树拼出来
---

# STORYBOARD — EP03《把树拼出来》

七帧。主线是「层」：先说没有完整文件，再说两种拼装件（profile / bundle），
再给叠加顺序，再讲 patch 的两个动作，然后用一次真跑把整棵树的层号指出来，
最后落在改动成本上。屏幕上每个数字都来自本机 2026-11-22 的 `--dump-config`。

| # | 帧 | 起 | 时长 | 旁白 | 论证角色 |
|---|---|---|---|---|---|
| 1 | 上一集留了个问题 | 0.00 | 9.75 | 9.25 | 没有单一文件描述整棵树 |
| 2 | profile 与 bundle | 9.75 | 16.90 | 16.40 | 两种拼装件，各自的 `dsh` 字段 |
| 3 | 四层，从下往上 | 26.65 | 14.96 | 14.46 | 叠加顺序；同 id 后写赢 |
| 4 | patch 只做两件事 | 41.61 | 16.88 | 16.38 | 按 id 整块替换 / insert |
| 5 | 真跑一次 | 58.49 | 19.18 | 18.68 | 用真实行号标出每一层 |
| 6 | 改一行会怎样 | 77.67 | 19.63 | 19.13 | HMR 的边界；临时 overlay |
| 7 | 树是叠出来的 | 97.30 | 15.20 | 14.00 | 收束；钩子交给 EP04 |

## 逐帧

### F1 — 上一集留了个问题（0.00–9.75）

- 画面：右上角是上一集认识的插件片段（session / agent-loop，各挂着 apply），随后退到 34%；主体是问题「可这棵树，是谁拼出来的？」；下方给出 `dsh --profile web --dump-config`。
- 蓝色焦点：命令提示符 `$`。
- 依据：`docs/architecture.zh.md`「要查看你的机器启动的配置树」。

### F2 — profile 与 bundle（9.75–26.65）

- 画面：左列 profile（web / headless / sdk / sdk-minimal / acp，本机在跑 web）；右列 bundle（`@deepseek-ai/dsh-base` 是 web / headless / sdk / acp 共用的第一层，`@deepseek-ai/dsh-web-app` 加浏览器应用）。底部两段 `package.json` 字段。
- 蓝色焦点：两列的来源标签。
- 依据：`docs/architecture.zh.md`「Profile 与组合包」；`packages/bundle/base/package.json` 的 `dsh.bundle.patch`；`~/.dsh/profiles/web/package.json` 的 `dsh.profile.bundles`（18 条）。

### F3 — 四层，从下往上（26.65–41.61）

- 画面：四条层带 ① 有序 bundle（18 个）② profile 的 `cordis.patch.yml`（2158 行）③ `~/.dsh/cordis.patch.yml` ④ `--patch` overlay；底部用同一个 id 的两行演示「后写的赢」。
- 蓝色焦点：生效的那一行 15000。
- 依据：`docs/architecture.zh.md`（叠加顺序）；`packages/bundle/base/cordis.patch.yml` 顶部注释（last write wins per row）。

### F4 — patch 只做两件事（41.61–58.49）

- 画面：左 patch 文件、右 dump 结果，两对。第一对是按 id 替换整块 config（`typert-gateway` / `websocketHeartbeatIntervalMs: 15000`）；第二对是 `insert`（`panel-mcp-ypicture`）。
- 蓝色焦点：`- insert:` 一行。
- 依据：真实用户 patch 文件里的这两段；`base/cordis.patch.yml` 顶部「A patch replaces the targeted row's whole `config` rather than merging into it」。

### F5 — 真跑一次（58.49–77.67）

- 画面：`$ dsh --profile web --dump-config`；三个数字 3491 行 / 235 条 / 54 处 `# ==`；随后逐行给出层在文件里的起始行：1 dsh-base、628 dsh-web-app、1539 dshmarket、3460 profile patch、3475 home patch。
- 蓝色焦点：3460 那一行（你的 patch 层）。
- 依据：本机实跑输出（2026-11-22）。

### F6 — 改一行会怎样（77.67–97.30）

- 画面：左 base 里的 hmr 配置（`config: root: []`）与三步流程「保存 → 重新组合 → 只有那一条换掉」；右四层 + `--patch` 临时 overlay；底部长期/一次性的取舍。
- 蓝色焦点：`→ profile 的 patch`。
- 依据：`packages/bundle/base/cordis.patch.yml` 的 hmr 行（`# Profile configuration reloads by default; module roots are opt-in.`）。

### F7 — 树是叠出来的（97.30–112.50）

- 画面：压缩的四层带，第二层（你的 patch）以蓝边与淡底标出；右侧两句收束；底部 EP04 钩子。
- 蓝色焦点：你的那一层。
- 依据：同 F3。

## 节奏

- 帧内「说到才放」；每帧底部一条 2px 蓝进度发丝线。
- F4 是唯一一处内部换景（替换 → insert），用 0.3s 交叉完成，避免双重曝光。
