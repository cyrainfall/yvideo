#!/usr/bin/env python3
"""word_timing.py — 用 whisper.cpp 给每帧旁白打词级时间，并写 audio_meta.json。

为什么不用比例分词：句子内部有逗号和破折号造成的真实停顿，等分会让高亮提前于声音。
做法：whisper 逐字给时间（-ml 1），文本一律取 SCRIPT.md 的原文（whisper 可能听成繁体或
错字，但**字数**对得上时逐字直配）。字数对不上时退回到"按标点分句 + 句内按字数比例"。

输出 audio_meta.json（faceless-explainer 的形状）：
  { bgm, bgm_pending, voices:[{frame,path,duration_s,words:[{id,text,start,end}]}], sfx }
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# 工程目录 = 当前工作目录（一集一工程，共享这份 tools/）
from paths import META, ROOT, TAKES
SCRIPT = ROOT / "SCRIPT.md"
WHISPER = Path.home() / ".cache/whisper/ggml-base.bin"
TAIL_S = 0.40          # 每帧末尾留白，避免最后一个字被切在剪辑点上
CJK = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")
FRAME_RE = re.compile(r"^##\s+Frame\s+(\d+)\s*[—-]\s*(.+?)\s*$")


def duration(path: Path) -> float:
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True).stdout.strip())


def script_chars() -> dict[int, str]:
    """每帧的旁白原文，去掉标点与空白，只留可上屏的字。"""
    out, cur = {}, None
    for line in SCRIPT.read_text().splitlines():
        m = FRAME_RE.match(line)
        if m:
            cur = int(m.group(1)); out[cur] = ""
            continue
        if line.startswith("#"):
            cur = None
            continue
        if cur is None or not line.strip():
            continue
        if line.lstrip().startswith(("语言：", "全片")):
            continue
        out[cur] += line.strip()
    return {k: "".join(c for c in v if CJK.match(c)) for k, v in out.items()}


def whisper_words(wav: Path) -> list[tuple[str, float, float]]:
    out = Path("/tmp") / f"whisper-{wav.stem}"
    subprocess.run(
        ["whisper-cli", "-m", str(WHISPER), "-f", str(wav), "-oj", "-ml", "1", "-l", "zh",
         "-of", str(out)],
        check=True, capture_output=True,
    )
    data = json.loads(Path(f"{out}.json").read_text())
    words = []
    for seg in data["transcription"]:
        text = "".join(c for c in seg["text"] if CJK.match(c))
        if not text:
            continue
        words.append((text, seg["offsets"]["from"] / 1000.0, seg["offsets"]["to"] / 1000.0))
    return words


def proportional(text: str, spans: list[dict]) -> list[tuple[str, float, float]]:
    """按 voice_takes.json 的逐句真实起止，句内按字数比例分配。"""
    words = []
    for span in spans:
        chars = [c for c in span["text"] if CJK.match(c)]
        if not chars:
            continue
        d = max(span["end"] - span["start"], 0.05)
        step = d / len(chars)
        for i, c in enumerate(chars):
            words.append((c, span["start"] + i * step, span["start"] + (i + 1) * step))
    return words


def main() -> int:
    takes = json.loads(TAKES.read_text())["takes"]
    text_by_frame = script_chars()
    voices = []
    for t in takes:
        n = t["frame"]
        wav = ROOT / t["path"]
        want = text_by_frame.get(n, "")
        got = whisper_words(wav)
        if len(got) == len(want):
            mode = "whisper"
            timed = [(want[i], got[i][1], got[i][2]) for i in range(len(want))]
        else:
            mode = "proportional"
            timed = proportional(want, t["sentences"])
            print(f"  frame {n}: 字数不符 (whisper {len(got)} / 原稿 {len(want)}) → 比例分词")
        words = [
            {"id": f"w{i+1}", "text": c, "start": round(s, 3), "end": round(e, 3)}
            for i, (c, s, e) in enumerate(timed)
        ]
        voices.append({
            "frame": n,
            "path": t["path"],
            "duration_s": round(duration(wav) + TAIL_S, 3),
            "words": words,
        })
        print(f"  frame {n}: {len(words)} 字 · {mode} · {duration(wav):.2f}s +{TAIL_S}s 尾")
    META.write_text(json.dumps(
        {"bgm": None, "bgm_pending": False, "voices": voices, "sfx": []},
        ensure_ascii=False, indent=2))
    total = sum(v["duration_s"] for v in voices)
    print(f"✓ audio_meta.json · {len(voices)} 帧 · 成片时长 {total:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
