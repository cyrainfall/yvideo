# 拆开 DSH — 系列视频工程

HyperFrames 工程（HTML → 视频，逐帧 seek 渲染）。本目录是**系列共用**的工程：
`index.html` 是当前这一集，换集时替换 `compositions/frames/`、`SCRIPT.md` 与 `audio_meta.json`。
已交付的集数整包归档在 `episodes/`（帧、脚本、分镜、旁白、成片各一份）。

**第一季六集全部已发布，第二季已开工（EP07 已发布，EP08–EP18 排队）**（成片都在 `renders/`，
每集发布物在 `publish/epNN/`）。工作区当前保留的是 EP07《接缝》（4 分 25.2 秒）。
换集时按「换集」流程替换 `compositions/frames/`、`SCRIPT.md`、`audio_meta.json` 即可，
配音/字幕/发布三条链都复用。

- 系列大纲：`SERIES.md`（第一季）、`SERIES-S2.md`（第二季，滚动更新）、`SERIES-S2-PLAN.md`（策划案与取舍）
- 本集任务书：`BRIEF.md`
- 视觉规范：`frame.md`（Substrate 系统：墨底、暖白、唯一 DeepSeek 蓝、1px 发丝线）
- 分镜与事实出处：`STORYBOARD.md`
- 旁白：`SCRIPT.md` → `assets/voice/NN-*.wav`
- 字幕：`caption_groups.json` → `compositions/captions.html`
- 现场演示的包与收据：`demo/greet/`、`demo/receipts/`

## 重建一条链

```bash
make readonly   # 静态闸门：读法 + 多音字 + 规则自检（秒级，改稿时反复跑）
make chain      # 链路一致性 G1–G6：旁白覆盖 / 新鲜度 / 音轨 / 帧时长 / 时间轴 / 生成物指纹
make narrate    # 按句合成旁白 → assets/voice/*.wav + voice_takes.json
make index      # 重建 index.html 时间轴（依赖 timing，生成 G5 要检查的那份）
make captions   # 重算词级时间 + 重建字幕（依赖 narrate → timing → index，顺序由 make 保证）
make verify     # 全部闸门：静态规则 + 链路 G1–G6 + hyperframes check（增量）
make check-full # hyperframes 全量分析（--no-cache，慢，交付前一次）
make listen     # 交付前复听清单（多音字无法自动判定，逐条给出时间点与试听命令）
make asr        # ASR 冒烟：对含拉丁词的句子做转写回读，只当筛子
make render     # 渲染（前置 verify 通过才跑）
make review     # 验收包 renders/epNN-review/：画面/时长/字幕/波形/复听（渲染后、发布前）
```

改一句文案 = `make captions verify`；要发布 = `make render && make review`。以前靠「记得要从 1 重跑到 3」，现在靠依赖图：
`captions → timing → narrate`，`render → verify`。**顺序不是提醒，是结构。**

- 旁白缓存键 = 帧号+句序+句子文本的哈希：改文案会自动失效重配，绝不按位置复用旧音轨
  （EP03 里中途插句曾导致一句被读两遍）。
- 字幕四种呈现：`make captions MODE=line`（`word` 逐字高亮 / `line` 整行淡入 / `keyword` 术语上色 / `reveal` 逐个浮现）。
- 读法规则有两份：`voice/读法规则.md`（人读）与 `voice/lexicon.json`（闸门读）。
  改词典后 `make readonly` 会跑 selftest 回归；新增一条血泪经验 = 往 lexicon 里加一行。
- 多音字三档：`!` 需改写（阻断）／`·` 提示／`♪` 复听（必用词，只能靠耳朵）。

## 时间轴约定

- 帧时长 = 旁白时长 + 0.5s（收尾帧 +1.2s）；`index.html` 里每个 scene 的
  `data-start` 是**绝对起点**，字幕脚本靠它把帧内时间换算成绝对时间。
- 子组合的时间线跑**帧内本地时间**：`compositions/frames/frame-NN.html` 里的
  `tl.fromTo(..., 3.5)` 指这一帧开始后 3.5 秒，不是全片 3.5 秒。
- 改旁白 → `make captions verify`，并同步 `index.html` 的 `data-start/data-duration`。
- 音频 `<audio>` 的 `data-duration` 用**旁白原始时长**（不是帧时长），避免尾巴被切。

## 链路不变量（`make chain` 必须 6 条全绿）

这几条以前只写在下面的散文里，漏跑一步不会有任何东西报错，只会得到一版整体错位的成片。
现在它们是断言（仓库根 `tools/gate_chain.py`，由 `make chain` 调用）：

| 闸门 | 不变量 | 拦住的是 |
|---|---|---|
| G1 | `SCRIPT.md` 每帧句子 == `voice_takes.json` 每帧句子 | 改了文案没重配 |
| G2 | `audio_meta.json` 不旧于 `voice_takes.json` | 漏跑 `timing.py`，字幕整体错位 |
| G3 | 每条 wav 存在，真实时长 == 记录时长（±0.02s） | 音轨被替换/截断 |
| G4 | 帧时长 == 旁白 + 0.5s（收尾帧 +1.2s） | 尾巴被切 / 画面拖沓 |
| G5 | 帧起点首尾相接、无空隙无重叠，root 总长 == 末帧终点 | 时间轴漂移 |
| G6 | 生成物内容 == 生成时的指纹，且上游未变 | 手改生成物 / 改了源头没重跑 |

## 检查门槛（check 必须 0 error / 0 warning）

- 字号下限 28px（≈1.5cqw），行号、chrome 这类纹样用小字必须带 `data-layout-ignore`。
- `--faint` 只能用在纹样上；要读的字用 `--muted`。
- 每帧底部一条 2px 蓝进度发丝线，避免 `dead_stretch`。
- 一帧只有一个蓝焦点。
- 引用行（cite）要短：字数 × 0.3s + 0.5s 必须小于它在屏幕上停留的时间，否则 Craft 报 `line_unread`。
- 旁白里的标识符用**空格口语形态**：下划线会被 TTS 读成含糊连读（`install_bundle` → "InstallFumble"、`node_modules` → "Node Madules"），斜杠也会（`tool/result` → "兔.e-silt"）。屏幕保留真名，字幕用 `caption_groups.json` 的显示映射还原。
- 仓库根 `tools/en_check.py` 是这道闸门：静态规则扫 `SCRIPT.md`（下划线一律失败，白名单只有 `plugin_manager`），`--asr` 再用本机 whisper 生成复听清单。ASR 只是筛子（base 模型会把 command 听成 Comment、把 id 听成 Add），不当作判定。

## 事实核对（EP06）

屏幕上出现的每个事件名、行号、字段、数字都能在 `/Users/cyx/repo/deepseek-harness` 找到，
或是本机 2026-11-22 真实安装/卸载的收据：

| 画面 | 出处 |
|---|---|
| `ctx.tools.register()` 的参数与返回值契约 | `packages/core/tools/src/index.ts:128` |
| `ctx.commands.register()` | `packages/interaction/commands/src/index.ts:285` |
| 命令结果只有 success / error | `packages/interaction/commands/src/types.ts:34` |
| `command/run` / `command/done` 成对、log-only | `packages/interaction/commands/src/types.ts:105`、`:112` |
| 命令分层：全局 / agent，近的盖住远的 | `packages/interaction/commands/src/index.ts:263` |
| 真实命令注册对象（`/goal`） | `packages/goal/command-goal/src/index.ts:193` |
| slot 注册字段 `{ id, order, label }` + 组件 | `packages/client/ui-slots/src/index.ts:1269` |
| `conversation.composer.dock` 的用途与占位 | 本机 Web 的 `cordis_inspect` slot 目录（真值，非示意） |
| 客户端包只注册工厂、懒加载 | `packages/client/modules/README.md` |
| `dsh.bundle.patch` 与 `dsh.client` | `demo/greet/package.json` |
| `- insert: id / name` | `demo/greet/cordis.patch.yml` |
| 装的结果 `applied` / `restart-required` | `packages/boot/plugin-manager/src/types.ts:174` |
| 五种重启理由 | `packages/boot/plugin-manager/src/types.ts:52` |
| 安装后重新组合 profile | `packages/boot/hmr/src/index.ts:937` |
| 页面跟随模块图、启用/禁用不用刷新 | `packages/client/hmr/README.md` |
| 真装收据：`application: applied`、`changed: true`、`warnings: []` | `demo/receipts/install.json` |
| 落点：工具 `greet`、dock `{ id: "greet", order: 50, active: true }` | `demo/receipts/tool-entry.json`、`slot-before.json` |
| 真卸收据：`stage: "remove"`、`application: "applied"` | `demo/receipts/remove.json` |
| 卸载后 dock 回到 6 个占位 | `demo/receipts/slot-after.json` |

## 已交付

| 集 | 成片 | 时长 | 归档 | 发布 |
|---|---|---|---|---|
| EP01 模型只会说话 | `renders/ep01-模型只会说话.mp4` | 2:04.8 | `episodes/ep01/` | `BV1PHyVzrEcn` |
| EP02 一切皆插件 | `renders/ep02-一切皆插件.mp4` | 2:12.2 | `episodes/ep02/` | `BV1YwyVzsEdL` |
| EP03 把树拼出来 | `renders/ep03-把树拼出来.mp4` | 1:52.5 | `episodes/ep03/` | `BV18uyVzSEzJ` |
| EP04 一轮对话 | `renders/ep04-一轮对话.mp4` | 2:20.7 | `episodes/ep04/` | `BV1zSyGzYE6Z` |
| EP05 工具：模型的手 | `renders/ep05-模型的手.mp4` | 3:43.9 | `episodes/ep05/` | `BV11yyjzpEXS` |
| EP06 改它（第一季完结） | `renders/ep06-改它.mp4` | 4:06.3 | `episodes/ep06/` | `BV11yyjzpEsU` |
| EP07 接缝（S2E01） | `renders/ep07-接缝.mp4` | 4:25.2 | `episodes/ep07/` | `BV1vj1tzNENa` |

## 发布物

每集一个包：`publish/epNN/` 里是 `title.txt`、`desc.txt`、`cover.png`、`result.json`
（投稿回执：bvid / aid / 封面 URL / 提交时间）。投稿命令见 `bilibili-skills` 技能，
路径全部用绝对路径传给 CLI。

封面统一由 `publish/cover-template.html` 生成：改顶部 `EP.NN — 标题`、`h1` 主标题、
`h2` 副标题（`<em>` 是唯一蓝词）和右侧那一列等宽文字，然后截 1920×1080：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
  --hide-scrollbars --force-device-scale-factor=1 --window-size=1920,1080 \
  --screenshot=publish/ep06/cover.png publish/cover-template.html
```
