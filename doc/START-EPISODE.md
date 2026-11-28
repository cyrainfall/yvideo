# 开一集：从零到绿（EP08 起的标准流程）

> 适用范围：**「拆开 DSH」项目**（`projects/dsh-anatomy/` 及其后的 `epNN-*` 工程）。
> 工作区级规则见根 `AGENTS.md` 与 `doc/MAP.md`；本项目细则见 `projects/dsh-anatomy/AGENTS.md`。

本文件是**实测推演**的产物，不是设想：用 `make new-episode` 真建了一个三帧工程，
跑通了 `narrate → timing → index → frames → captions → chain → check → verify`，
记录每一步的实际输出、撞到的坑、以及现在还剩哪些只能靠人和环境的部分。

目标只有一句：**agent 从零开工时，每一步都有确定的期望输出；红了代表真问题。**

---

## 1. 标准流程（每步都给出期望输出）

```bash
cd /Users/cyx/repo/yvideo
make new-episode EP=08 TITLE=<标题>
cd projects/ep08-<标题>
```

| # | 命令 | 期望输出（实测样例） |
|---|---|---|
| 0 | `make readonly` | `✓ 旁白读法全部通过` / `✓ selftest 通过`（写 SCRIPT 之后跑） |
| 1 | `make narrate` | `frame 1: 1 句 → 1.78s  01-<标题>.wav` + `✓ 3 帧，旁白总时长 4.00s` |
| 2 | `make captions` | 依次 voice_build → timing → index_build → captions_build；`✓ index.html：3 帧，总时长 6.201s` |
| 3 | `make frames` | `+ frame-02.html 1.62s 第二帧` / `~ frame-01.html DUR → 2.283s` |
| 4 | `make check` | **此时应全绿**：Lint/Runtime/Layout/Motion/Contrast/Craft/Audio 全部 `0 errors, 0 warnings` |
| 5 | 写画面（逐帧） | 每改一帧 `make check`，红了按提示修 |
| 6 | `make listen` | 多音字 `♪` 复听清单（含 wav 路径、时间区间、试听命令） |
| 7 | `make verify` | `✓ 7 条链路不变量全部成立` + `◇ Check passed` + `✓ 全部闸门通过` |
| 8 | `make render` | 前置 verify 必须通过，产出 `renders/ep08.mp4` |
| 9 | `make review` | 验收包 `renders/ep08-review/`：`REVIEW.md` + 每帧开头/中点的连拍 + 每个切点的 5 帧连拍 + 波形 + 时长账 + 复听清单 |

第 4 步是关键：**新工程在没写任何画面时就是绿的**。此后 agent 的每次改动都是"绿 → 绿"，
红一定是自己弄红的，不存在"一开始就一片红、只能无视"的状态。

---

## 2. 推演中撞到并已修掉的五个坑

| 坑 | 现象 | 修法 |
|---|---|---|
| 模板缺字体 | `runtime: 404 loading assets/fonts/Inter-Variable.woff2`（×3） | 字体进模板：`templates/episode/assets/fonts/*.woff2` |
| 帧根缺 composition id | `root_missing_composition_id` + `timeline_id_mismatch` + `missing_or_empty_sub_composition`（3 条 error 同源） | 起步帧根元素写 `data-composition-id="frame-NN"` |
| 小字低于字号下限 | `text_below_floor: ... 20 px ... 至少 28 px` | 眉标抬到 `1.5cqw`（≈28.8px） |
| 帧生成器 id 重写错配 | `console_warning: GSAP target #f2-eyebrow not found` ×18 | 先改 `id="f1` 前缀、再改 `#f1` 选择器；顺序反了就错配 |
| 起步帧占位文案过长 | `line_unread: 7 words 需 2.60s，短帧只给 1.33s` | 占位改成「待写」，任何时长都装得下 |

前四个是"结构性"的（不修则每集必踩），第五个是起步文案的细节。全部已进模板，
所以 EP08 开工时不会再撞。

---

## 3. 还不能自动化的三件事（必须人/环境到位）

1. **本地 TTS 服务得在听。** `tools/voice_build.py` 打的是 `http://127.0.0.1:8010/v1/audio/speech`
   （Qwen3-TTS，`ref_audio` = `voice/短视频走心男青年解说.wav`）。推演时它返回 200，
   但返回的是 **MP3 流写进 .wav 文件**——ffmpeg 按内容嗅探，不影响下游，别被扩展名骗了。
   > 注意：`doc/配音指导.md` 与旧的 VoiceStudio 记忆指向 `100.64.0.8:3900`；
   > 推演时该地址不可达（curl 000）。**以 `tools/voice_build.py` 里的端点为准**，
   > 或先确认 VoiceStudio 起来了再改端点。

2. **发布不在 make 里。** `make render` 出 MP4 就结束了；投稿走 `bilibili-skills`，
   回执写 `publish/epNN/result.json`。这一步有平台交互，不适合塞进 make。
   **发布后要回填 README 的「已交付」表**：`make readonly` 里的 `delivery_table.py`
   会对账（已发布没列 / bvid 不符 / 成片或归档不见了 → 红），但标题与括号注释仍归人写。
   表里写**发布那一版**的时长；本地之后重渲过就让它不同，别改表去迎合本地文件。

3. **选题、事实核对、审美判断、复听。** 闸门能保证"不出现下划线标识符""帧时长守恒"，
   保证不了"这一集讲得对、讲得好"。`BRIEF.md` / `FACTS.md` / `make listen` 是给人的接口。

---

## 4. 已知的边角（不影响开工，但要知道）

- **模板更新不回灌已建工程。** `make new-episode` 只在创建时复制；之后模板改了，
  老工程不会自动获得。推演时 `projects/ep08-推演` 就因为没有 `frames` 目标撞了一次。
  → 需要时手动同步单集 `Makefile`，或直接重建工程（源文件在 `episodes/` 里有归档）。
- **`make check` 有已知偶发红灯**，判别特征与处理见 `projects/dsh-anatomy/AGENTS.md` 已知坑第 6 条；
  交付前用 `make check-full`（`--no-cache`）拿准信。
- **`frames_scaffold` 不覆盖已有帧**（只校准 `var DUR`）。`--force` 会覆盖画面，慎用。

---

## 5. agent 开机自检（贴进 BRIEF 也行）

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8010/v1/audio/speech   # 405/200 都算在听
ls voice/短视频走心男青年解说.wav 2>/dev/null || echo "ref 音频缺失"
```

两个都过了，才有资格跑 `make narrate`；否则先去修环境，别在配音链上瞎试。
