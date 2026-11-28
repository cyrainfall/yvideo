#!/usr/bin/env python3
"""timing.py — 由「按句拼接」的句级时间，推出词级时间，写 audio_meta.json。

不需要 ASR：句边界来自 voice_takes.json（合成时累加），句内按字/词权重均分。
中文一字一拍；连续拉丁字母、数字、小数点算一个 token，权重按长度打折。
标点不参与分词，它的时长被摊进两侧的字里 —— 正好是停顿。

输出（faceless-explainer 的形状，时间轴是「帧内相对时间」）：
  { bgm, bgm_pending, voices:[{frame,path,duration_s,words:[{id,text,start,end}]}], sfx:[] }
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from gen_manifest import stamp

# 工程目录 = 当前工作目录（一集一工程，共享这份 tools/）
from paths import ROOT, META, TAKES

TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9.+_-]*|[0-9]+(?:\.[0-9]+)?|[\u4e00-\u9fff]")


def weight(tok: str) -> float:
    if re.match(r"[\u4e00-\u9fff]", tok):
        return 1.0
    return max(1.0, len(tok) * 0.58)


def main() -> int:
    takes = json.loads(TAKES.read_text())["takes"]
    voices = []
    for t in takes:
        words = []
        for sent in t.get("sentences", []):
            toks = TOKEN.findall(sent["text"])
            if not toks:
                continue
            span = max(0.0, sent["end"] - sent["start"])
            total = sum(weight(x) for x in toks)
            cursor = sent["start"]
            for tok in toks:
                dur = span * weight(tok) / total
                words.append({
                    "id": f"w{len(words) + 1}",
                    "text": tok,
                    "start": round(cursor, 3),
                    "end": round(cursor + dur, 3),
                })
                cursor += dur
        voices.append({
            "frame": t["frame"],
            "path": t["path"],
            "duration_s": t["duration_s"],
            "words": words,
        })
    META.write_text(json.dumps({
        "bgm": None, "bgm_pending": False, "voices": voices, "sfx": [],
    }, ensure_ascii=False, indent=2))
    stamp("generated/audio_meta.json", "tools/timing.py", ["generated/voice_takes.json"])
    print(f"✓ {len(voices)} 帧，{sum(len(v['words']) for v in voices)} 个词")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
