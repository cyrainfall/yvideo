# yvideo 工作区地图

DSH 拆解系列视频（B站）的生产工作区。**产品是视频，不是软件**；这里的"代码"是文案、分镜、时间轴与校验脚本。
本文件是 agent 与人的唯一入口。细节规范在 `doc/`，操作命令在 `make`。

---

## 1. 三层次契约（最重要）

**改错层就是这个项目最大的返工来源。**

| 层 | 文件 | 谁写 | 能否手改 |
|---|---|---|---|
| **源** | `SCRIPT.md`、`frame.md`、`STORYBOARD.md`、`BRIEF.md`、`FACTS.md`、`compositions/frames/*.html`、`assets/` 素材、`voice/读法规则.md` | 人 + agent | ✅ 只在这里改 |
| **生成** | `voice_takes.json`、`audio_meta.json`、`caption_groups.json`、`compositions/captions.html` | `tools/` 里的脚本 | ❌ 改了必出错 |
| **交付** | `renders/*.mp4`、`publish/epNN/*`、`episodes/epNN/` | 脚本 | ❌ 只读 |

判据一句话：**能由脚本重建的，就不许手改。**改成源头文件，然后重跑链。

---

## 2. 目录职责

| 路径 | 是什么 |
|---|---|
| `doc/` | 生产规范（`配音指导.md` 是配音的权威；`本机TTS-Qwen3.md` 是环境事实） |
| `projects/dsh-anatomy/` | **当前活跃工程**（系列共用，换集替换内容） |
| `projects/dsh-anatomy/episodes/epNN/` | 已交付集数的整包归档（帧/脚本/分镜/旁白） |
| `projects/dsh-anatomy/publish/epNN/` | 发布物（title/desc/cover + `result.json` 投稿回执） |
| `projects/dsh-anatomy/tools/` | 校验与生成脚本（发音闸门在这） |
| `projects/dsh-ydesk-explainer/` | 另一支已交付工程（工具与本工程**已分叉**，待合并） |
| `voice/` | 音色参考样本（`*.wav` 不入库） |
| `learn/` | 第三方克隆（各自有 `.git`，**永不修改、不入库**） |
| `.agents/` | 共享技能安装目录，等价于 `node_modules`，不入库 |

---

## 3. 真源速查

| 我想知道 | 看这个 |
|---|---|
| 系列讲什么、分几集 | `projects/dsh-anatomy/SERIES.md` |
| 本集任务书与验收 | `BRIEF.md` |
| 画面长什么样（视觉规范） | `frame.md` |
| 每一镜配什么话、事实出处 | `STORYBOARD.md` |
| 旁白原文（唯一可改的文案） | `SCRIPT.md` |
| **英文/缩写怎么念** | `voice/读法规则.md` |
| 每个时间点说什么 | `audio_meta.json`（生成物，只读） |
| 字幕怎么分组 | `caption_groups.json`（生成物，只读） |
| 这集发布了没、bvid 是什么 | `publish/epNN/result.json` |
| 配音怎么调、语气怎么定 | `doc/配音指导.md` |

> 已交付事实以 `publish/epNN/result.json` 为唯一权威（bvid / 提交时间）；README 的表格跟它对齐。

---

## 4. 禁止清单

1. ❌ 手改生成物（`audio_meta.json` / `caption_groups.json` / `voice_takes.json` / `captions.html`）
2. ❌ 在 `learn/` 里改任何东西
3. ❌ 提交 `*.wav` / `*.mp4` / `renders/` / `learn/`（`.gitignore` 已挡）
4. ❌ 改了一句旁白却只重跑配音——`timing` 与 `captions` 必须跟着重跑
5. ❌ 旁白里写带下划线的标识符（TTS 会读成连读），屏幕保留真名、口播用空格形态

---

## 5. 命令

命令都在工程目录里跑：

```bash
cd projects/dsh-anatomy
make readonly   # 静态闸门（秒级）：读法 + 多音字 + 规则自检
make verify     # 全部闸门（+ hyperframes check）
make captions   # 重算时间 + 重建字幕（依赖 narrate → timing）
make listen     # 交付前复听清单（多音字只能靠耳朵）
make asr        # ASR 冒烟（只当筛子）
make render     # 渲染（前置 verify 通过才跑）
```

完整目标见 `make help`。**顺序由 make 的依赖图保证，不靠记性。**

---

## 6. 已知坑（按踩坑频率排序）

1. **英文标识符被读错**：`install_bundle` → "InstallFumble"、`node_modules` → "Node Madules"、`ctx` → "cats"。闸门 `tools/en_check.py` 读 `voice/lexicon.json`（人读版 `voice/读法规则.md`）。新增一条血泪经验 = 往 lexicon 加一行 + `make readonly` 回归。
2. **中文多音字/易错读音**：TTS 只吃文本，没有拼音门控，ASR 也听不出 chóng/zhòng。闸门 `tools/polyphone_check.py`，三档：`!` 阻断 / `·` 提示 / `♪` 复听（必用词，给出时间点与试听命令）。
3. **改稿后时间轴错位**：`audio_meta.json` 旧于 `voice_takes.json` 时字幕整体错。
4. **帧时长不守恒**：帧时长 = 旁白时长 + 0.5s，收尾帧 +1.2s。
5. **引用行读不完**：`line_unread`，字数 × 0.3s + 0.5s 必须小于停留时间。
