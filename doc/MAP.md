# yvideo 工作区地图

DSH 拆解系列视频（B站）的生产工作区。**产品是视频，不是软件**；这里的"代码"是文案、分镜、时间轴与校验脚本。
本文件是 agent 与人的唯一入口。细节规范在 `doc/`，操作命令在 `make`。

---

## 1. 三层次契约（最重要）

**改错层就是这个项目最大的返工来源。**

| 层 | 文件 | 谁写 | 能否手改 |
|---|---|---|---|
| **源** | `SCRIPT.md`、`frame.md`、`STORYBOARD.md`、`BRIEF.md`、`FACTS.md`、`compositions/frames/*.html`、`assets/` 素材、`voice/读法规则.md` | 人 + agent | ✅ 只在这里改 |
| **生成** | `voice_takes.json`、`audio_meta.json`、`caption_groups.json`、`compositions/captions.html` | 仓库根 `tools/` 的脚本 | ❌ 改了必出错 |
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
| `tools/`（仓库根） | **全系列共享**的校验与生成脚本（发音/链路闸门都在这）。一集一工程，只此一份 |
| `templates/episode/` | 新一集的模板。**改模板 = 改以后每一集的样子** |
| `Makefile`（仓库根） | 跨集的事：`new-episode` / `verify-all` / `list` |
| `projects/dsh-ydesk-explainer/` | 另一支已交付工程（**冻结**：仍用自带的旧 `tools/`，不再维护；新片一律用仓库根 `tools/`） |
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
| 开一集怎么走、每步该看到什么 | `doc/START-EPISODE.md` |

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
make chain      # 链路不变量 G1–G5：旁白覆盖 / 新鲜度 / 音轨 / 帧时长 / 时间轴
make verify     # 全部闸门（+ hyperframes check）
make index      # 重建 index.html 时间轴（依赖 timing）
make captions   # 重算时间 + 重建字幕（依赖 narrate → timing → index）
make listen     # 交付前复听清单（多音字只能靠耳朵）
make asr        # ASR 冒烟（只当筛子）
make render     # 渲染（前置 verify 通过才跑）
```

完整目标见 `make help`。**顺序由 make 的依赖图保证，不靠记性。**

### 加一集

```bash
make new-episode EP=08 TITLE=接缝    # 从 templates/episode 生成 projects/ep08-接缝/
make list                            # 看哪些工程活跃、哪些冻结
make verify-all                      # 跑所有活跃工程的闸门
```

新集从零到绿的**完整流程、每步期望输出、已知坑**见 **`doc/START-EPISODE.md`**（实测推演产物）。骨架：

`BRIEF.md` → `SCRIPT.md` → `make readonly` → `make narrate captions`
→ `make frames`（按旁白帧数铺骨架，**此时 check 应全绿**）→ 写画面
→ `make listen`（复听）→ `make verify render`。

---

## 6. 已知坑（按踩坑频率排序）

1. **英文标识符被读错**：`install_bundle` → "InstallFumble"、`node_modules` → "Node Madules"、`ctx` → "cats"。闸门 `tools/en_check.py` 读 `voice/lexicon.json`（人读版 `voice/读法规则.md`）。新增一条血泪经验 = 往 lexicon 加一行 + `make readonly` 回归。
2. **中文多音字/易错读音**：TTS 只吃文本，没有拼音门控，ASR 也听不出 chóng/zhòng。闸门 `tools/polyphone_check.py`，三档：`!` 阻断 / `·` 提示 / `♪` 复听（必用词，给出时间点与试听命令）。
3. **改稿后时间轴错位**：`audio_meta.json` 旧于 `voice_takes.json` 时字幕整体错。闸门 G2（`make chain`）。
4. **帧时长不守恒**：帧时长 = 旁白时长 + 0.5s，收尾帧 +1.2s。闸门 G4。
5. **引用行读不完**：`line_unread`，字数 × 0.3s + 0.5s 必须小于停留时间。
6. **`hyperframes check` 偶发红灯**（约 5 次 1 次）：已知非确定性，`make check` 会自动复跑一次并打印告警；交付前用 `make check-full`（`--no-cache`）拿准信。
   **判别特征**：`dead_stretch` 若**每帧都报、且区间正好是整帧**（0.00–30.10、30.54–68.17…），是分析器没加载到子组合时间线，不是画面静止——重跑即可；只有**单帧**静置才是真内容问题，用 `data-hold` 或加动效。
7. **Makefile 里 `$$变量` 紧跟全角字符会吞字节**：`echo "$$d（无"` 会丢掉 `（` 的 EF 字节并把变量吃掉。写成 `$$d （无`（中间留空格）即可。
