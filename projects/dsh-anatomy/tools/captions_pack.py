#!/usr/bin/env python3
"""captions_pack.py — 把 caption 分组从「2 字一组」重打包成整句可读的行。

为什么需要它：`captions.mjs` 的 `wordCap(density)` 是按「词/秒」算容量的，而中文被我们
按**字**送入，于是每行只剩 2 个字。这里改成：
  · 文本真值取 SCRIPT.md（词流只保留汉字/字母/数字，标点与小数点会丢）
  · 时间取 audio_meta 的字级时间戳，按位置对齐
  · 先按标点切小句，再按整句打包成 ≤16 字的行；句末强制断行
  · 连续拉丁/数字合成一个词（WebSocket / 0.32 / 60 不被拆开）
输出：改写 caption_groups.json 与 compositions/captions.html 里的 GROUPS 常量。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEEP = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")
LAT = re.compile(r"[A-Za-z0-9.]")
SENT = set("。！？!?")
CLAUSE = set("，、；：—…,;:")
LIMIT = 16


def frame_scripts() -> dict[int, str]:
    out, cur = {}, None
    for line in (ROOT / "SCRIPT.md").read_text().splitlines():
        m = re.match(r"^##\s+Frame\s+(\d+)", line)
        if m:
            cur = int(m.group(1))
            out[cur] = ""
            continue
        if line.startswith("#"):
            cur = None
            continue
        if cur is None or not line.strip() or line.lstrip().startswith(("语言：", "全片", "音色：")):
            continue
        out[cur] += line.strip()
    return out


def frame_starts() -> tuple[dict[int, float], float]:
    sb = (ROOT / "STORYBOARD.md").read_text()
    starts, acc = {}, 0.0
    for m in re.finditer(r"^## Frame (\d+).*?\n- duration: ([\d.]+)s", sb, re.M | re.S):
        starts[int(m.group(1))] = acc
        acc += float(m.group(2))
    return starts, round(acc, 3)


def main() -> int:
    scripts = frame_scripts()
    am = json.loads((ROOT / "audio_meta.json").read_text())
    starts, total = frame_starts()

    tokens = []
    for v in am["voices"]:
        base = starts[v["frame"]]
        words, wi = v["words"], 0
        for ch in scripts.get(v["frame"], ""):
            if KEEP.match(ch):
                if wi >= len(words):
                    break
                w = words[wi]
                wi += 1
                tokens.append({"frame": v["frame"], "text": ch, "start": base + w["start"],
                               "end": base + w["end"], "brk": None, "sent": False})
            elif tokens:
                prev = tokens[-1]
                if ch in SENT:
                    prev["sent"] = True
                    prev["brk"] = prev["brk"] or "sent"
                elif ch in CLAUSE:
                    prev["brk"] = prev["brk"] or "clause"
                elif ch in ".·" and LAT.match(prev["text"][-1] or " "):
                    prev["text"] += ch

    merged = []
    for t in tokens:
        prev = merged[-1] if merged else None
        if (prev and prev["frame"] == t["frame"] and prev["text"]
                and LAT.match(prev["text"][-1]) and LAT.match(t["text"])):
            prev["text"] += t["text"]
            prev["end"] = t["end"]
            prev["brk"] = t["brk"] or prev["brk"]
            prev["sent"] = prev["sent"] or t["sent"]
        else:
            merged.append(dict(t))

    # 小句：标点 / 句末 / 帧边界 / 长静音
    clauses, cur = [], None
    for w in merged:
        if cur and (cur["frame"] != w["frame"] or w["start"] - cur["_last"] > 0.45):
            clauses.append(cur)
            cur = None
        if cur is None:
            cur = {"frame": w["frame"], "words": [], "sent": False}
        cur["words"].append(w)
        cur["_last"] = w["end"]
        if w["sent"]:
            cur["sent"] = True
        if w["brk"]:
            clauses.append(cur)
            cur = None
    if cur:
        clauses.append(cur)

    # 打包：句末强制断，整句优先
    groups, cur = [], None
    for c in clauses:
        ctext = "".join(w["text"] for w in c["words"])
        clen = len(ctext)
        if cur and (cur["frame"] != c["frame"] or cur["_sent"] or cur["_n"] + clen > LIMIT):
            groups.append({"frame": cur["frame"], "words": cur["words"], "_n": cur["_n"]})
            cur = None
        if clen > LIMIT:
            buf = []
            for w in c["words"]:
                if buf and sum(len(x["text"]) for x in buf) + len(w["text"]) > LIMIT:
                    groups.append({"frame": c["frame"], "words": buf,
                                   "_n": sum(len(x["text"]) for x in buf)})
                    buf = []
                buf.append(w)
            cur = {"frame": c["frame"], "words": buf,
                   "_n": sum(len(x["text"]) for x in buf), "_sent": False}
            continue
        if cur is None:
            cur = {"frame": c["frame"], "words": [], "_n": 0, "_sent": False}
        cur["words"] += c["words"]
        cur["_n"] += clen
        cur["_sent"] = c["sent"]
    if cur:
        groups.append({"frame": cur["frame"], "words": cur["words"], "_n": cur["_n"]})

    out = []
    for i, g in enumerate(groups):
        st = g["words"][0]["start"]
        en = g["words"][-1]["end"]
        nxt = groups[i + 1]["words"][0]["start"] if i + 1 < len(groups) else total
        out.append({
            "id": f"caption-group-{i}",
            "frame": g["frame"],
            "start": round(st, 3),
            "end": min(round(en + 0.24, 3), nxt),
            "text": "".join(w["text"] for w in g["words"]),
            "words": [{"id": f"caption-word-{i}-{j}", "text": w["text"],
                       "start": round(w["start"], 3), "end": round(w["end"], 3)}
                      for j, w in enumerate(g["words"])],
        })

    (ROOT / "caption_groups.json").write_text(json.dumps(
        {"total_duration_s": total, "width": 1920, "height": 1080, "groups": out},
        ensure_ascii=False, indent=2))
    line = "  var GROUPS = " + json.dumps(out, ensure_ascii=False).replace("<", "\\u003c") + ";"
    c = ROOT / "compositions" / "captions.html"
    c.write_text(re.sub(r"^  var GROUPS = .*$", line, c.read_text(), count=1, flags=re.M))
    print(f"✓ {len(out)} 行 · 最长 {max(len(g['text']) for g in out)} 字")
    for g in out:
        print(f"  {g['start']:6.2f}  {g['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
