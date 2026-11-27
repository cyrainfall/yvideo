# EP07 工作区归档 · 状态说明（2026-11-27 23:48 更新）

## 成片

- `renders/ep07-接缝.mp4` — 1920×1080 · 30fps · H.264 + AAC 48k 立体声 · **4:25.2** · 14.2 MB
- 渲染：2026-11-27 23:45，`--quality high --workers 1 --experimental-fast-capture`（5m45s）
- 本版包含**两轮英文读法修正**，frames 与成片同版

## 英文读法修正（两轮，共 22 处）

第一轮（23:15 成片）：`ctx`→`C T X`、`dsh`→`D S H`、`pwsh`→`P W S H`、`ShellExecutor`→`Shell 执行器`、`PENDING`→`pending`、`browserUse`→`browser use`、`sandboxMode/Policy` 拆词、删 `capability seam` 与 `schemastery`。

第二轮（本版）：用户听出 `subprocess` 读错，遂对全片英文词做了一次完整审计（27 句含英文的句子逐句回听），又修：

| 原写法 | 实际读音 | 改为 |
|---|---|---|
| `subprocess`（2 处） | "sub-price-price / Support Prized" | `sub process` → 回听 "sub-process" |
| `devDependencies` | "DFD Pandencies" | `dev dependencies` |
| `cordis` | "Cortist / Cortes" | `C O R D I S`（屏幕仍小写真名） |
| `ShellExecutor`（F4 s2 漏改一处） | "Shell Xector" | `Shell 执行器` |

规则表：`voice/读法规则.md`（本集归档同目录），已把两轮实测错法与改法都写进去。

## 重跑链（改一句也要走完）

voice_build → timing → index_build → captions_build → **帧时间重排**（F3/F4/F5 受影响，两位帧作者按新句首 offset 重排）→ check → render。

## 校验

- 容器：`duration=265.166667`，4:25.2
- 成片内回听：`CORDIS rules`、`sub-process`、`dev dependencies`（隔离测试）均正确
- 字幕：78 行、覆盖 264.50s（`--mode line`）
- `check`：Lint / Runtime / Layout / Motion / Contrast / Craft / Audio 全 0 error
- 抽帧：F4 134.5s 处继承叠图与 inject 数组的揭示时间与旁白对齐

## 发布物

- `publish/ep07/title.txt` · `desc.txt`（时间轴按新版 4:25 已更新；含封面 CC BY-NC-SA 署名行）
- `publish/ep07/cover.png` · `cover-base.jpg` · `cover-plan.json` · `cover-qa.md`
- `publish/cover-overlay.html`

## 待办

1. ~~投稿与回执归档（`result.json`）~~ — **已完成**：`BV1vj1tzNENa`，2026-11-28 00:05:58 投稿，回执在 `publish/ep07/result.json`。
2. 封面为条件通过（鳍耳非教科书深蓝），W4 复盘时复核。
