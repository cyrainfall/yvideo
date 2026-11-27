#!/usr/bin/env python3
"""voice_build.py — 按句合成旁白，句级缓存可断点续跑。

规则（yvideo/doc/配音指导.md v2.1）：
  · 一句一条 take，不整段请求
  · 每条先去首尾静音，再统一响度
  · 帧内句间留 GAP_S，帧与帧之间不拼（每帧一条独立 wav）

输出：
  assets/voice/.takes/fNN-SS-<文本哈希>.wav   句级缓存（键含文本，改文案自动失效）
  assets/voice/NN-<slug>.wav       每帧一条
  voice_takes.json                 每帧 duration_s + 逐句 offset
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "http://127.0.0.1:8010/v1/audio/speech"
MODEL = "/Users/cyx/models/Qwen3-TTS-12Hz-1.7B-Base-8bit"
GAP_S = 0.22
SILENCE_DB = -45
TARGET_I = -16.0
VOICE = None
REF_AUDIO = "/Users/cyx/repo/yvideo/voice/短视频走心男青年解说.wav"

# 工程目录 = 当前工作目录（一集一工程，共享这份 tools/）
ROOT = Path.cwd()
if not (ROOT / "hyperframes.json").exists():
    raise SystemExit(f"✗ 请在某一集的工程目录里运行（{ROOT} 下没有 hyperframes.json）")
SCRIPT = ROOT / "SCRIPT.md"
OUTDIR = ROOT / "assets" / "voice"
CACHE = OUTDIR / ".takes"
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
        if line.startswith("#"):
            cur = None
            continue
        if cur is None or not line.strip():
            continue
        if line.lstrip().startswith(("语言：", "全片", "音色：")):
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
    req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        out.write_bytes(r.read())
    if out.stat().st_size < 2000:
        raise RuntimeError(f"empty synthesis for {text!r}")


def clean(inp: Path, out: Path) -> float:
    af = (
        f"silenceremove=start_periods=1:start_threshold={SILENCE_DB}dB:start_silence=0.02,"
        f"areverse,silenceremove=start_periods=1:start_threshold={SILENCE_DB}dB:start_silence=0.02,areverse"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(inp), "-af", af, "-ar", "24000", "-ac", "1", str(out)],
        check=True,
    )
    return duration(out)


def duration(path: Path) -> float:
    return float(
        subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    )


def main() -> int:
    frames = parse_script(SCRIPT.read_text())
    if not frames:
        print("✗ no frames parsed from SCRIPT.md", file=sys.stderr)
        return 1
    OUTDIR.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    takes = []
    for fr in frames:
        text = "".join(fr["lines"])
        sents = sentences(text)
        if not sents:
            continue
        cleaned, spans, cursor = [], [], 0.0
        for i, s in enumerate(sents, 1):
            # 缓存键必须包含文本：位置编号会因中途插句而整体错位，
            # 只按 fNN-SS 命名会让旧句子被当成新句子复用（EP03 踩过）。
            digest = hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]
            cached = CACHE / f"f{fr['n']:02d}-{i:02d}-{digest}.wav"
            if not cached.exists() or cached.stat().st_size < 2000:
                tmp_raw = CACHE / f"f{fr['n']:02d}-{i:02d}-{digest}.raw.wav"
                synth(s, tmp_raw)
                clean(tmp_raw, cached)
                tmp_raw.unlink(missing_ok=True)
            d = duration(cached)
            cleaned.append(cached)
            spans.append({"text": s, "start": round(cursor, 3), "end": round(cursor + d, 3)})
            cursor += d + GAP_S
        out = OUTDIR / f"{fr['n']:02d}-{slugify(fr['title'])}.wav"
        inputs, fc = [], []
        for i in range(len(cleaned)):
            inputs += ["-i", str(cleaned[i])]
            pad = f"apad=pad_dur={GAP_S}" if i != len(cleaned) - 1 else "anull"
            fc.append(f"[{i}:a]{pad}[p{i}]")
        graph = ";".join(fc) + ";" + "".join(f"[p{i}]" for i in range(len(cleaned)))
        graph += f"concat=n={len(cleaned)}:v=0:a=1[cat];[cat]loudnorm=I={TARGET_I}:TP=-1.5:LRA=11[out]"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[out]",
             "-ar", "24000", "-ac", "1", str(out)],
            check=True,
        )
        d = duration(out)
        takes.append({
            "frame": fr["n"], "title": fr["title"], "path": str(out.relative_to(ROOT)),
            "duration_s": round(d, 3), "sentences": spans,
        })
        print(f"  frame {fr['n']}: {len(sents)} 句 → {d:.2f}s  {out.name}", flush=True)
    TAKES.write_text(json.dumps({"takes": takes}, ensure_ascii=False, indent=2))
    print(f"✓ {len(takes)} 帧，旁白总时长 {sum(t['duration_s'] for t in takes):.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
