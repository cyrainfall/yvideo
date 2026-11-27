# 一集一工程的模板

由 `make new-episode EP=08 TITLE=接缝` 复制到 `projects/ep08-接缝/`，占位符会被替换。

**改模板 = 改以后每一集的样子。** 改完请用 `make new-episode EP=99 TITLE=冒烟` 生成一份验证，
再删掉。

## 什么进模板、什么不进

| 进模板 | 理由 |
|---|---|
| `Makefile` / `hyperframes.json` / `package.json` | 与集数无关，且必须一致 |
| `AGENTS.md` | agent 的操作契约 |
| `frame.md` | Substrate 视觉规范**快照**（权威版本随系列演进；本集一般不改） |
| `voice/读法规则.md` + `voice/lexicon.json` | 读法经验的起点，按本集内容增补 |
| `publish/cover-template.html` | 封面模板，每集只改顶部标题 |

**不进模板**（生成物，`make` 产出）：`index.html`、`audio_meta.json`、`caption_groups.json`、
`voice_takes.json`、`compositions/captions.html`、`assets/voice/*.wav`、`renders/`。
