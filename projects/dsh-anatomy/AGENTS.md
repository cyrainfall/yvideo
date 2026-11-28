# AGENTS.md — 「拆开 DSH」系列

B站源码级讲解系列。本目录是**系列共用工程**：换集时替换 `compositions/frames/`、`SCRIPT.md`
与生成物，配音/字幕/发布三条链复用。已发布 EP01–EP07，成片在 `renders/`，每集发布物在
`publish/epNN/`，整包归档在 `episodes/epNN/`。

工作区级规则见仓库根 `AGENTS.md` 与 `doc/MAP.md`；本文件只讲这个项目。

## 三层次契约（本项目最大的返工来源）

| 层 | 文件 | 谁写 | 能否手改 |
|---|---|---|---|
| **源** | `SCRIPT.md`、`frame.md`、`STORYBOARD.md`、`BRIEF.md`、`FACTS.md`、`compositions/frames/*.html`、`assets/` 素材、`voice/读法规则.md` | 人 + agent | ✅ 只在这里改 |
| **生成** | `generated/voice_takes.json`、`generated/audio_meta.json`、`generated/caption_groups.json`、`index.html`、`compositions/captions.html` | 仓库根 `tools/` 的脚本 | ❌ 改了必出错 |
| **交付** | `renders/*.mp4`、`renders/epNN-review/`、`publish/epNN/*`、`episodes/epNN/` | 脚本 | ❌ 只读 |

判据一句话：**能由脚本重建的，就不许手改。**改源头，然后重跑链。

这条现在是两道闸门：

- **G6 指纹**（`tools/gen_manifest.py`）：每份生成物在 `.generated-manifest.json` 里留指纹
  （自身内容 + 上游 + 生成器）。手改 → 红并指名改哪个源；改了源头没重跑 → 红并指名重跑哪个脚本。
- **G7 目录边界**（`tools/paths.py`）：三个纯数据生成物在 `generated/` 下，工程根不再有它们。
  `index.html` 与 `compositions/captions.html` 因为 HyperFrames 的入口契约必须留在原位，
  这两个的"禁止手改"只靠 G6 兜。

**为什么生成物要离开根目录**：源和生成物平铺在一起时，"手改一下看起来更省事"永远是最近的
动作；挪进 `generated/` 之后，动手前要先走进一个明显不是编辑目标的地方。G6 是事后发现，
G7 让错误的位置根本不出现。老工程用 `python3 ../../tools/migrate_layout.py` 迁（幂等，产物逐字节不变）。

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
| **这一集能不能发、长什么样** | `renders/epNN-review/REVIEW.md`（验收包入口，人从这里判） |
| 这集发布了没、bvid | `publish/epNN/result.json`（唯一权威） |
| 交付表和事实对不对 | `make delivery`（`make readonly` 也会对账，只报错不改表） |

## 命令

在本目录跑（共享脚本在仓库根 `tools/`）：

```bash
make readonly   # 读法 + 多音字 + 自检（秒级，改稿时反复跑）
make chain      # G1–G7：旁白覆盖 / 新鲜度 / 音轨 / 帧时长 / 时间轴 / 生成物指纹
make narrate    # 按句合成旁白（句级缓存，改一句只重配一句）
make index      # 重建 index.html 时间轴（依赖 timing）
make frames     # 按旁白帧数铺 frame-NN.html，并校准每帧时长
make captions   # 重算时间 → 重建 index.html → 重建字幕
make check      # hyperframes：lint / runtime / 布局 / 动效 / 对比 / craft
make check-full # 同上 --no-cache 全量（慢，交付前一次）
make verify     # 以上全部（渲染前必须过）
make listen     # 交付前复听清单
make render     # 渲成 MP4
make review     # 验收包（渲染后、发布前跑；约 40s）
make review-check  # 验收包是否还描述着当前这一版
make delivery   # 「已交付」表 vs publish/*/result.json 全表对账
```

顺序由 make 的依赖图保证。跨集命令在仓库根：`make new-episode EP=08 TITLE=…` /
`make verify-all` / `make list` / `make gc`（磁盘体检，默认只报告）。

**开一集的完整流程与每步期望输出**见 `doc/START-EPISODE.md`（实测推演产物）。
**配音怎么调**见 `doc/配音指导.md`。

## 验收包（`make review`）

`renders/epNN-review/` 是**给人判**的目录，不进 git（成片也不进），随时可重建：

| 文件 | 判什么 |
|---|---|
| `REVIEW.md` | 入口。一屏看完：结论 + 图 + 账 + 欠账 |
| `snapshots/review-beats.jpg` | 每帧开头与中点，14 张一张图——画面本身对不对 |
| `snapshots/review-seam-0N.jpg` | 每个切点前后 5 帧——跳变、黑闪、错位 |
| `snapshots/review-phone.jpg` | 缩到 360px 宽——手机上还认不认得出 |
| `durations.md` | 逐帧时长账 + **成片实测 vs 时间轴**偏差 |
| `captions.md` | 78 行字幕全表 + 语速分布（≥6 音节/秒 读不完） |
| `waveform.png` | 音轨波形，竖线是帧边界——空白段、爆音、音画错位 |
| `listen.md` | ♪ 复听清单（多音字只能靠耳朵）+ 判定记录表 |
| `checks.txt` | 闸门原始输出（G1–G7 + hyperframes check） |
| `manifest.json` | 它描述的是哪一版：输入指纹 + commit + 成片指纹 |

**为什么不接进 `make verify`**：改稿循环里每改一句就被逼重建 40s 的包，人一定会绕过它。
它属于交付动作，所以接在 `make verify-all`（仓库根的全量扫）里——只在交付路径上拦。

**为什么记指纹**：验收包最常见的死法是「改了文案、重渲了、忘了重做包，拿旧图发布」。
`make review-check` 会当场判出过期并指名变了哪个文件。

## 已知坑（按踩坑频率）

1. **英文标识符被读错**：`install_bundle` → "InstallFumble"、`node_modules` → "Node Madules"、`ctx` → "cats"。闸门 `tools/en_check.py` 读 `voice/lexicon.json`。新增经验 = 同时改 `读法规则.md` 与 `lexicon.json`，跑 `make readonly` 回归。
2. **中文多音字**：TTS 只吃文本，ASR 也听不出 chóng/zhòng。闸门 `tools/polyphone_check.py`，三档：`!` 阻断 / `·` 提示 / `♪` 复听。
3. **改稿后时间轴错位**：`audio_meta.json` 与 `voice_takes.json` 对不上时字幕整体错。闸门 G2——
   比**内容**不比 mtime（时间戳会被 `git checkout`/`cp` 改新，2026-11-28 因此误报过一次）。
4. **帧时长不守恒**：帧时长 = 旁白 + 0.5s，收尾帧 +1.2s。闸门 G4。
5. **引用行读不完**：`line_unread`，字数 × 0.3s + 0.5s 必须小于停留时间。
6. **`check` 偶发红灯**（约 5 次 1 次）：`make check` 自动复跑一次并告警。判别特征：`dead_stretch` **每帧都报且区间正好是整帧** ＝ 分析器没加载到子组合时间线（工具偶发），别改画面；只有**单帧**静置才是真内容问题，加动效或对故意静止加 `data-hold`。
7. **README 交付表靠人回填**：表停在 EP06 而 EP07 已发布，过了三集才被发现。
   闸门：`make readonly` 跑 `tools/delivery_table.py`（已发布没列 → 红；bvid/成片/归档不符 → 红）。
   它**不代笔**：标题、括号注释、「4:06.3 还是 4:09.0」这类判断仍归人。
8. **Makefile 里 `$$变量` 紧跟全角字符会吞字节**：写成 `$$d （无`（留空格）。
