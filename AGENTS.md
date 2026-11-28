# AGENTS.md

DSH 拆解系列视频的生产工作区。**产品是视频，不是软件**：这里的"代码"是文案、分镜、时间轴
和校验脚本。

这份文件是自动加载的入口（DSH 会读项目根的 `AGENTS.md`）。动手前先读另外三份：

- `doc/MAP.md` —— 三层次契约（源 / 生成 / 交付）、真源速查、禁止清单、已知坑
- `doc/START-EPISODE.md` —— 开一集的流程与每步期望输出
- `doc/corrections.md` —— 已固化的坑、仍欠的债

## 命令

所有命令在**某一集的工程目录**里跑（`cd projects/<集>`）：

```bash
make readonly   # 读法 + 多音字 + 自检（秒级，改稿时反复跑）
make chain      # G1–G5：旁白覆盖 / 新鲜度 / 音轨 / 帧时长 / 时间轴
make captions   # 重算词级时间 → 重建 index.html → 重建字幕
make frames     # 按旁白帧数铺 frame-NN.html，并校准每帧时长
make check      # hyperframes：lint / runtime / 布局 / 动效 / 对比 / craft
make verify     # 以上全部（渲染前必须过）
make listen     # 交付前复听清单：必用词 + 时间点 + 试听命令
make render     # 渲成 MP4
```

跨集的事在仓库根：`make new-episode EP=08 TITLE=…` / `make verify-all` / `make list`。

## 硬边界

| 操作 | 规则 |
|---|---|
| 手改 `voice_takes.json`、`audio_meta.json`、`caption_groups.json`、`index.html`、`captions.html` | ❌ 永不 —— 改源头文件后重跑链 |
| 改 `renders/`、`publish/epNN/`、`episodes/epNN/` | ❌ 永不 —— 交付物只读 |
| 在 `learn/` 里改任何东西 | ❌ 永不 —— 第三方克隆，各有自己的 `.git` |
| 提交 `*.wav` / `*.mp4` | ❌ 永不 —— `.gitignore` 已挡 |
| 旁白里写带下划线的标识符 | ❌ 永不 —— 改空格口语形态（`install bundle`），屏幕保留真名 |
| 改了旁白只重配、不重跑 | ❌ 永不 —— `make captions verify` |
| 交付前 | ✅ 必须 `make verify` 全绿 + `make listen` 逐条过 |
| 新增读音 / 多音字经验 | ✅ 同时改 `voice/读法规则.md` 与 `voice/lexicon.json`，跑 selftest |
| `check` 报 `dead_stretch` | ⚠️ 先按 `doc/MAP.md` 已知坑 6 判断，别急着改画面 |

## 别写进这里

HyperFrames 的组合作法（`window.__timelines`、`data-*`、`class="clip"`）在每一集自己的
`AGENTS.md` 里；架构与目录导览在 `doc/MAP.md`。这份文件只放"不照做就会错层"的东西，
两处各写一份同样的规则，早晚会漂。
