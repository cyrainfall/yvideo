#!/usr/bin/env python3
"""voice_build.py — faceless-explainer Step 3.1, local Qwen3-TTS narration.

HeyGen TTS 在本机不可达（UND_ERR_CONNECT_TIMEOUT）且该账号只有英文音色，
所以这里用本机 Qwen3-TTS（127.0.0.1:8010，24k mono）按句合成，逐帧拼轨。

规则（与 yvideo/doc/配音指导.md 一致）：
  · 一句一条 take，不整段请求
  · 每条先去首尾静音（Qwen3 固定带 ~50ms），再统一响度
  · 帧内句间留 GAP_S，帧与帧之间不拼（每帧一条独立 wav）

输出：
  assets/voice/NN-<slug>.wav      —— 每帧一条
  voice_takes.json                —— 每帧 duration_s + 逐句 offset（供无 ASR 时的比例分词）
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ENDPOINT = "http://127.0.0.1:8010/v1/audio/speech"
MODEL = "/Users/cyx/models/Qwen3-TTS-12Hz-1.7B-Base-8bit"
GAP_S = 0.22          # 帧内句间静音
SILENCE_DB = -45      # silenceremove 阈值
TARGET_I = -16.0      # 整帧响度
VOICE = None          # Base = 克隆模型，靠 ref_audio 定音色
REF_AUDIO = "/Users/cyx/repo/yvideo/voice/短视频走心男青年解说.wav"

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "SCRIPT.md"
OUTDIR = ROOT / "assets" / "voice"
TAKES = ROOT / "voice_takes.json"

FRAME_RE = re.compile(r"^##\s+Frame\s+(\d+)\s*[—-]\s*(.+?)\s*$")
SENT_RE = re.compile(r"[^。！？!?]+[。！？!?]?")


def slugify(text: str) -> str:
    keep = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text).strip("-")
    return keep[:24] or "frame"


def parse_script(md: str) -> list[dict]:
    frames: list[dict] = []
    cur = None
    for raw in md.splitlines():
        line = raw.rstrip()
        m = FRAME_RE.match(line)
        if m:
            cur = {"n": int(m.group(1)), "title": m.group(2), "lines": []}
            frames.append(cur)
            continue
        if line.startswith("#"):        # 其他标题：退出当前帧
            cur = None
            continue
        if cur is None or not line.strip():
            continue
        if line.lstrip().startswith(("语言：", "全片")):
            continue
        cur["lines"].append(line.strip())
    return frames


def sentences(text: str) -> list[str]:
    out = []
    for m in SENT_RE.finditer(text):
        s = m.group(0).strip()
        if s and re.search(r"[\w\u4e00-\u9fff]", s):
            out.append(s)
    return out


def synth(text: str, out: Path) -> None:
    payload = {
        "model": MODEL,
        "input": text,
        "lang_code": "chinese",
        "response_format": "wav",
    }
    if VOICE:
        payload["voice"] = VOICE
    if REF_AUDIO:
        payload["ref_audio"] = REF_AUDIO
    body = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        out.write_bytes(r.read())
    if out.stat().st_size < 2000:
        raise RuntimeError(f"empty synthesis for {text!r}")


def clean(inp: Path, out: Path) -> float:
    """去首尾静音 → 统一响度（单句 take 用的轻处理）。"""
    af = (
        f"silenceremove=start_periods=1:start_threshold={SILENCE_DB}dB:start_silence=0.02,"
        f"areverse,silenceremove=start_periods=1:start_threshold={SILENCE_DB}dB:start_silence=0.02,areverse"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(inp), "-af", af,
         "-ar", "24000", "-ac", "1", str(out)],
        check=True,
    )
    return float(
        subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(out)],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    )


def duration(path: Path) -> float:
    return float(
        subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    )


def main() -> int:
    frames = parse_script(SCRIPT.read_text())
    if not frames:
        print("✗ no frames parsed from SCRIPT.md", file=sys.stderr)
        return 1
    OUTDIR.mkdir(parents=True, exist_ok=True)
    takes = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for fr in frames:
            text = "".join(fr["lines"])
            sents = sentences(text)
            if not sents:
                print(f"  frame {fr['n']}: no narration (silent)")
                continue
            cleaned, spans = [], []
            cursor = 0.0
            for i, s in enumerate(sents, 1):
                raw = tmp / f"f{fr['n']}-{i}.wav"
                subprocess.run(["rm", "-f", str(raw)])
                synth(s, raw)
                cw = tmp / f"f{fr['n']}-{i}-c.wav"
                d = clean(raw, cw)
                cleaned.append(cw)
                spans.append({"text": s, "start": round(cursor, 3), "end": round(cursor + d, 3)})
                cursor += d + GAP_S
            # 拼帧（句间插 GAP_S 静音）
            parts, filters, idx = [], [], 0
            concat_inputs = []
            for i, cw in enumerate(cleaned):
                concat_inputs += ["-i", str(cw)]
                parts.append(f"[{idx}:a]")
                idx += 1
            # 用 concat + 中间静音：改为直接生成 with gaps 的 filter_complex
            graph = []
            n = len(cleaned)
            for i in range(n):
                graph.append(f"[{i}:a]")
                if i != n - 1:
                    graph.append(f"apad=pad_dur={GAP_S}[a{i}]")
            # 简化：先各自 pad 再 concat
            fc = "".join(
                f"[{i}:a]apad=pad_dur={GAP_S}[p{i}];" if i != n - 1 else f"[{i}:a]anull[p{i}];"
                for i in range(n)
            ) + "".join(f"[p{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[cat];[cat]loudnorm=I={TARGET_I}:TP=-1.5:LRA=11[out]"
            out = OUTDIR / f"{fr['n']:02d}-{slugify(fr['title'])}.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", *concat_inputs,
                 "-filter_complex", fc,
                 "-map", "[out]",
                 "-ar", "24000", "-ac", "1", str(out)],
                check=True,
            )
            d = duration(out)
            takes.append({
                "frame": fr["n"],
                "title": fr["title"],
                "path": str(out.relative_to(ROOT)),
                "duration_s": round(d, 3),
                "sentences": spans,
            })
            print(f"  frame {fr['n']}: {len(sents)} 句 → {d:.2f}s  {out.name}")
    TAKES.write_text(json.dumps({"takes": takes}, ensure_ascii=False, indent=2))
    total = sum(t["duration_s"] for t in takes)
    print(f"✓ {len(takes)} 帧，旁白总时长 {total:.2f}s → {TAKES.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
