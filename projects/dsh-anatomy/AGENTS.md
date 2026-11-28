# AGENTS.md — 「拆开 DSH」系列

B站源码级讲解系列。本目录是**系列共用工程**：换集时替换 `compositions/frames/`、`SCRIPT.md`
与生成物，配音/字幕/发布三条链复用。已发布 EP01–EP07，成片在 `renders/`，每集发布物在
`publish/epNN/`，整包归档在 `episodes/epNN/`。

工作区级规则见仓库根 `AGENTS.md` 与 `doc/MAP.md`；本文件只讲这个项目。

## 三层次契约（本项目最大的返工来源）

| 层 | 文件 | 谁写 | 能否手改 |
|---|---|---|---|
| **源** | `SCRIPT.md`、`frame.md`、`STORYBOARD.md`、`BRIEF.md`、`FACTS.md`、`compositions/frames/*.html`、`assets/` 素材、`voice/读法规则.md` | 人 + agent | ✅ 只在这里改 |
| **生成** | `voice_takes.json`、`audio_meta.json`、`caption_groups.json`、`index.html`、`compositions/captions.html` | 仓库根 `tools/` 的脚本 | ❌ 改了必出错 |
| **交付** | `renders/*.mp4`、`publish/epNN/*`、`episodes/epNN/` | 脚本 | ❌ 只读 |

判据一句话：**能由脚本重建的，就不许手改。**改源头，然后重跑链。

这条现在不是倡议，是闸门 **G6**（`tools/gen_manifest.py`）：每份生成物在
`.generated-manifest.json` 里留指纹（自身内容 + 上游 + 生成器）。手改 → 红并指名改哪个源；
改了源头没重跑 → 红并指名重跑哪个脚本。

## 真源速查

| 我想知道 | 看这个 |
|---|---|
| 系列讲什么、分几集 | `SERIES.md`（第一季）/ `SERIES-S2.md`（第二季） |
| 本集任务书与验收 | `BRIEF.md` |
| 画面长什么样 | `frame.md`（Substrate 视觉规范） |
| 每一镜配什么话、事实出处 | `STORYBOARD.md` / `FACTS.md` |
| 旁白原文（唯一可改的文案） | `SCRIPT.md` |
| **英文/缩写怎么念** | `voice/读法规则.md`（人读）+ `voice/lexicon.json`（闸门读） |
| 每个时间点说什么 | `audio_meta.json`（生成物，只读） |
| 字幕怎么分组 | `caption_groups.json`（生成物，只读） |
| 这集发布了没、bvid | `publish/epNN/result.json`（唯一权威） |

## 命令

在本目录跑（共享脚本在仓库根 `tools/`）：

```bash
make readonly   # 读法 + 多音字 + 自检（秒级，改稿时反复跑）
make chain      # G1–G5：旁白覆盖 / 新鲜度 / 音轨 / 帧时长 / 时间轴
make narrate    # 按句合成旁白（句级缓存，改一句只重配一句）
make index      # 重建 index.html 时间轴（依赖 timing）
make frames     # 按旁白帧数铺 frame-NN.html，并校准每帧时长
make captions   # 重算时间 → 重建 index.html → 重建字幕
make check      # hyperframes：lint / runtime / 布局 / 动效 / 对比 / craft
make check-full # 同上 --no-cache 全量（慢，交付前一次）
make verify     # 以上全部（渲染前必须过）
make listen     # 交付前复听清单
make render     # 渲成 MP4
```

顺序由 make 的依赖图保证。跨集命令在仓库根：`make new-episode EP=08 TITLE=…` /
`make verify-all` / `make list`。

**开一集的完整流程与每步期望输出**见 `doc/START-EPISODE.md`（实测推演产物）。
**配音怎么调**见 `doc/配音指导.md`。

## 已知坑（按踩坑频率）

1. **英文标识符被读错**：`install_bundle` → "InstallFumble"、`node_modules` → "Node Madules"、`ctx` → "cats"。闸门 `tools/en_check.py` 读 `voice/lexicon.json`。新增经验 = 同时改 `读法规则.md` 与 `lexicon.json`，跑 `make readonly` 回归。
2. **中文多音字**：TTS 只吃文本，ASR 也听不出 chóng/zhòng。闸门 `tools/polyphone_check.py`，三档：`!` 阻断 / `·` 提示 / `♪` 复听。
3. **改稿后时间轴错位**：`audio_meta.json` 旧于 `voice_takes.json` 时字幕整体错。闸门 G2。
4. **帧时长不守恒**：帧时长 = 旁白 + 0.5s，收尾帧 +1.2s。闸门 G4。
5. **引用行读不完**：`line_unread`，字数 × 0.3s + 0.5s 必须小于停留时间。
6. **`check` 偶发红灯**（约 5 次 1 次）：`make check` 自动复跑一次并告警。判别特征：`dead_stretch` **每帧都报且区间正好是整帧** ＝ 分析器没加载到子组合时间线（工具偶发），别改画面；只有**单帧**静置才是真内容问题，加动效或对故意静止加 `data-hold`。
7. **Makefile 里 `$$变量` 紧跟全角字符会吞字节**：写成 `$$d （无`（留空格）。
