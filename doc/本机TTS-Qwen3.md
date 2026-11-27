# 本机 TTS：Qwen3-TTS（MLX）· 部署与运维

> 2026-11-16 部署。跑在 **这台 MacBook Air（M4 / 16 GB）** 上，纯本地、离线、不花 API 费用。
> 与另一条路的分工：`100.64.0.8:3900` 的 **VoiceStudio（OmniVoice）** 在 Windows 机上，负责**音色克隆**（工作区默认音色 `d38028e2`）；这台上的 Qwen3-TTS 负责**内置音色 + 情绪指令**，克隆要另装 Base 模型（见末节）。

## 1. 装了什么

| 项 | 位置 |
|---|---|
| Python 环境 | `~/.venvs/qwen3tts`（python 3.12，`mlx-audio[server]` + `hf_transfer`） |
| 模型 | `~/models/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit`（2.9 GB，MLX 8bit） |
| 启动器 | `~/.local/bin/qwen3tts`，并软链到 `/opt/homebrew/bin/qwen3tts`（与 `heygen` 同样的做法，保证非登录 shell 也能解析） |
| 运行态 | `~/.local/state/qwen3tts/{server.pid,server.log}` |
| 端口 | `127.0.0.1:8010`（只绑回环，默认不对外） |

```bash
qwen3tts start [--port 8010] [--host 127.0.0.1]
qwen3tts status | stop | log [行数]
```

## 2. 用起来

OpenAI 兼容端点，和 VoiceStudio 同一个形状（`POST /v1/audio/speech`），所以能直接替换调用：

```bash
curl -s -X POST http://127.0.0.1:8010/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"/Users/cyx/models/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit",
       "input":"算出来五百零八，量出来五百。一模一样。",
       "voice":"Dylan","lang_code":"chinese",
       "instruct":"克制的青年男声，语速偏慢",
       "response_format":"wav"}' \
  -o take.wav
```

- **必须给 `model`**（可写本地目录或 HF id）。服务端按 model 懒加载并缓存，模型常驻内存后不再重新加载；
- `response_format` 默认是 **mp3**，要 wav 得显式写；
- 输出 **24 kHz / 单声道 / s16**；
- `instruct` **有效**（实测同样一句 3.2 s → 3.9 s，语气随指令变），这一点已在 HTTP 端验证过；
- `stream: true` 可流式返回。

### 内置音色（CustomVoice，已确认 8 个）

| voice | 描述 | 母语 |
|---|---|---|
| `Dylan` | 北京口音的年轻男声，音色清亮自然 | 中文（京腔） |
| `Eric` | 成都口音的活泼男声，略带沙哑的亮度 | 中文（川话） |
| `Uncle_Fu` | 年长男声，低厚 | 中文 |
| `Vivian` | 明亮、略带锋利感的年轻女声 | 中文 |
| `Serena` | 温暖柔和的年轻女声 | 中文 |
| `Ryan` | 动态强、节奏感强的男声 | 英文 |
| `Aiden` | 阳光美式男声，中频清晰 | 英文 |
| `Ono_Anna` | 轻快跳跃的日语女声 | 日文 |

> 配音选型里「走心男青年」最接近的是 **`Dylan`**（但带京腔，念标准普通话解说会有口音底色）；要「无口音的标准男声 + 指定气质」目前得靠 `instruct` 调，或改用 VoiceStudio 那个克隆音色。

## 3. 实测（M4 Air / 16 GB / 8bit）

| 场景 | 时长 | 墙钟 | 倍率 |
|---|---|---|---|
| 单句 ~20 字 | 3.4 s | 2.3 s | **1.5× 实时** |
| 单句 ~30 字 | 6.4 s | 4.4 s | 1.5× |
| 整段 360 字（一次请求） | 92.6 s | **367.8 s** | **0.25× 实时** |
| 整段 360 字（16 句分开请求） | 71.1 s | ~35 s | 2× |

结论：**按句合成**，不要一次丢整段。长文本不只慢 4 倍，逐词判读也更不可靠。

响度：原始输出约 **-23.8 LUFS / 真峰 -5.3 dBFS**，比 VoiceStudio 还低 5 dB 左右 —— 进混音前照例走 §7 的两遍 loudnorm。

## 4. 已知坑

- **下载走 hf-mirror**。这台机器上 `huggingface.co` 直连与 7890 代理都拿不到数据（0 B/s），`HF_ENDPOINT=https://hf-mirror.com` 是 **14–17 MB/s**（同一个文件 `curl` 实测）。但 `hf`/`hf_transfer` 客户端走镜像只有 ~0.2 MB/s —— 下大文件直接 `curl` 单个文件最快。
- **长文本一次合成会「听起来完整、判词却塌」**：整段 92 s 那次，whisper 判读塌掉了约 100 字，切片后再判又都在 —— 是判读不可靠，不是真的漏。hence：按句合成 + 逐句判词。
- **`lang_code` 必须显式**。默认 `"a"`（英文音系），中文文本不显式给 `chinese` 会念得怪。
- 模型常驻约 4 GB 内存；16 GB 的 Air 上再开 Chrome + DSH 就接近交换边缘。不用时 `qwen3tts stop`。
- 它的 `/v1/audio/transcriptions` 是**同一台机器**上跑 ASR（会抢内存/GPU），判词建议仍用 `whisper-cli` 或在别的机器做。

## 5. 下一步（可选）

- **克隆音色**：再下 `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit`（约 3 GB），把工作区默认音色 `d38028e2` 的参考音频（VoiceStudio 里那个 `-37d1b650.wav`，≤20 s）+ `ref_text` 喂进去，就能在本机复现同一个声音。
- **接进 MCP**：把 8010 注册成 MCP 服务器（`~/.dsh/profiles/web/cordis.patch.yml`），agent 就能直接调。
- **接进流程**：`projects/*/tools/voice_gen.py` 的 `VOICESTUDIO_URL` 换成本机地址即可，接口形状一致（注意 `lang_code` 与 `instruct`）。

## 变更记录

| 日期 | 改动 |
|---|---|
| 2026-11-16 | 首版：mlx-audio + Qwen3-TTS-1.7B-CustomVoice-8bit 部署到本机 8010，launcher / 实测数字 / 坑 |

## 6. 音色克隆（Base 模型）

`Qwen3-TTS-12Hz-1.7B-Base-8bit` 已一并装好（`~/models/Qwen3-TTS-12Hz-1.7B-Base-8bit`，2.9 GB）。Base 没有内置音色，靠 `ref_audio` + `ref_text` 零样本克隆。

```bash
curl -s -X POST http://127.0.0.1:8010/v1/audio/speech -H 'Content-Type: application/json' \
  -d '{"model":"/Users/cyx/models/Qwen3-TTS-12Hz-1.7B-Base-8bit",
       "input":"这条路，只放一种包——ping。",
       "lang_code":"chinese","response_format":"wav",
       "ref_audio":"/Users/cyx/repo/yvideo/voice/clone/ref24k.wav",
       "ref_text":"故事发生在澳大利亚偏远的小镇，……"}' -o take.wav
```

硬要求：

- **参考音频必须是 24 kHz 单声道**（speaker encoder 会直接 assert 采样率），48 kHz 参考先 `ffmpeg -ar 24000 -ac 1` 转；
- `ref_text` 要**逐字对应**参考音频，ASR 转写出来的同音错字（尘土→成都、宽檐→宽颜、淬→翠）必须先改对，否则音色会飘；
- **不要再传 `voice`**：CustomVoice 的 speaker 名和 `ref_audio` 同时给会配置冲突；
- `x_vector_only`（只要音色不要文本）在 mlx-audio 0.6.5 里没有暴露，`ref_text` 是必需的。

实测（2026-11-16，参考音频 23.05 s 影视解说片段）：

| 指标 | 值 |
|---|---|
| speaker embedding 余弦相似度 | **0.985**（跨 4 条 take：0.985 / 0.988 / 0.992 / 0.986） |
| 单句合成速度 | 3–8 s 音频 / 5–9 s 墙钟（含克隆编码） |
| 16 句总量 | 语音 68.7 s（含句间 0.30 s 空白 72.3 s） |

附录：`Qwen3-TTS-12Hz-0.6B-Base` 也可以克隆，体积约一半，音色相似度略低；16 GB 的 Air 上 1.7B 更稳。

## 7. 一次完整配音的记录（克隆音色读一段 SRT）

见 `projects/icmptun-intro/BUILD-LOG.md` 的 S34：16 句逐句合成 → 逐句 ASR 判词 → 裁剪首尾静音 → 拼两条轨（自然语速 / 按字幕槽位 atempo 贴合）→ 两遍 loudnorm 到 -16 LUFS。
关键数字：自然版 72.28 s、贴合版 65.93 s（逐句 atempo 1.00–1.25），克隆相似度 0.985–0.992。

再接进成片时另建了一条**按镜头切点**（不是按 SRT）的 master，逐句 atempo 1.00–1.31，
混音后渲染出预览 `out/icmptun-69s.qwen3.mp4`（-14.0 LUFS）。记录见同一份 BUILD-LOG 的 S35。
