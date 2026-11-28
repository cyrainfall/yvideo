#!/usr/bin/env python3
"""frame_anchors.py — 帧内时间码注释与旁白的对账（G8）。

为什么需要它：`compositions/frames/frame-NN.html` 里有一类注释，把"这一句旁白从第几秒开始"
钉在动画代码旁边：

    // 12.80 说到「两百四十八条」——账本整体出现
    // 15.01 两百四十八条，没有缠成一团意大利面。

它们是**人的备忘**，不是生成物，所以没有任何东西会保证它还对。改一句文案 → 重配旁白 →
整帧的句子起点整体平移 → 注释里的数字全部作废，可代码里的 tween 还照着旧数字排。
`hyperframes check` 看不出这件事（它检查布局和动效，不知道旁白在哪一秒），
G1–G7 也看不出（它们只查数据一致性）。这是唯一一条"画面与声音错位、但所有闸门都绿"的路。

判据（只判能判的）：
- 注释里的文字**逐字等于**某一句旁白 → 这条锚点可判，比较数字与该句起点
- 不等于任何一句（比如「说到…——账本整体出现」这种设计说明）→ 不判，它不是锚点

容差 0.06s（注释写到两位小数，作者手写精度就在这个量级）。

已发布的集不改：EP07 已上线，动画面等于改已发布成片（见 corrections 的决策 B）。
所以允许工程根放一份 `frame-anchors-allowlist.json` 显式记账：

    {"frame-04.html:162": "EP07 已发布，决策 B：不动已上线成片"}

名单里的条目仍会以 `·` 打印出来——**记账不等于隐藏**。

用法（在某一集的工程目录里）：
    python3 ../../tools/frame_anchors.py            # 只报告（供 make chain 的 G8 调用）
    python3 ../../tools/frame_anchors.py --fix      # 自动改数字（只改无歧义的）
    python3 ../../tools/frame_anchors.py --list     # 列出所有锚点
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from paths import ROOT, TAKES

FRAMES = ROOT / "compositions" / "frames"
ALLOW = ROOT / "frame-anchors-allowlist.json"
TOL = 0.06
ANCHOR = re.compile(r"(//\s*)(\d+\.\d+)(\s+)(\S.*?)\s*$")
NORM = re.compile(r"[\s，。、：；？！「」『』（）《》…—·,.:;?!\"'()\[\]]")
FRAME_NO = re.compile(r"frame-(\d+)")


def norm(text: str) -> str:
    return NORM.sub("", text)


def sentences() -> dict[int, list[dict]]:
    takes = json.loads(TAKES.read_text(encoding="utf-8"))["takes"]
    return {t["frame"]: t["sentences"] for t in takes}


def allowlist() -> dict[str, str]:
    if not ALLOW.exists():
        return {}
    try:
        return json.loads(ALLOW.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def scan() -> list[dict]:
    """找出所有"可判锚点"：注释文字逐字等于某句旁白。"""
    by_frame = sentences()
    found: list[dict] = []
    for f in sorted(FRAMES.glob("frame-*.html")):
        m = FRAME_NO.search(f.name)
        if not m:
            continue
        fno = int(m.group(1))
        sents = by_frame.get(fno, [])
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            a = ANCHOR.search(line)
            if not a:
                continue
            text = a.group(4)
            hits = [(j, s) for j, s in enumerate(sents) if norm(s["text"]) == norm(text)]
            if not hits:
                continue                      # 设计说明，不是锚点
            found.append({
                "file": f, "name": f.name, "line": i, "frame": fno,
                "commented": float(a.group(2)), "actual": float(hits[0][1]["start"]),
                "text": text, "ambiguous": len(hits) > 1,
                "span": a.span(2),
            })
    return found


def check() -> tuple[list[str], list[str]]:
    """返回 (errors, notes)。errors 让 G8 红；notes 是已记账的漂移。"""
    errs: list[str] = []
    notes: list[str] = []
    allowed = allowlist()
    for a in scan():
        drift = a["commented"] - a["actual"]
        if abs(drift) <= TOL:
            continue
        key = f"{a['name']}:{a['line']}"
        msg = (f"G8 {a['name']}:{a['line']} 锚点 {a['commented']:.2f}s，"
               f"这句旁白实际在 {a['actual']:.2f}s（差 {drift:+.2f}s）"
               f"「{a['text'][:20]}」")
        if key in allowed:
            notes.append(f"{msg} —— 已记账：{allowed[key]}")
        else:
            errs.append(f"{msg} —— 改了文案没同步锚点；跑 tools/frame_anchors.py --fix"
                        f" 或把「确实不改」记进 frame-anchors-allowlist.json")
    if FRAMES.exists() and not any(FRAMES.glob("frame-*.html")):
        errs.append("G8 compositions/frames/ 下没有 frame-*.html")
    return errs, notes


def fix() -> int:
    found = [a for a in scan() if abs(a["commented"] - a["actual"]) > TOL]
    if not found:
        print("✓ 锚点都对得上，不需要改")
        return 0
    by_file: dict[Path, list[dict]] = {}
    for a in found:
        by_file.setdefault(a["file"], []).append(a)
    changed = skipped = 0
    for f, items in by_file.items():
        lines = f.read_text(encoding="utf-8").splitlines(keepends=True)
        for a in items:
            if a["ambiguous"]:
                print(f"  · 跳过 {a['name']}:{a['line']}：同一帧里有重复句，无法确定改哪一句")
                skipped += 1
                continue
            i = a["line"] - 1
            line = lines[i]
            m = ANCHOR.search(line.rstrip("\n"))
            new = line[:m.start(2)] + f"{a['actual']:.2f}" + line[m.end(2):]
            lines[i] = new
            print(f"  ✎ {a['name']}:{a['line']} {a['commented']:.2f}s → {a['actual']:.2f}s")
            changed += 1
        f.write_text("".join(lines), encoding="utf-8")
    print(f"\n✓ 改了 {changed} 条锚点" + (f"，跳过 {skipped} 条" if skipped else ""))
    print("  改的是注释数字，不是动画代码——代码里的 tween 该不该跟着动是人的判断。")
    return 0


def main() -> int:
    if "--fix" in sys.argv:
        return fix()
    found = scan()
    if "--list" in sys.argv:
        for a in found:
            print(f"  {a['name']}:{a['line']:<4} {a['commented']:6.2f}s  (实际 {a['actual']:6.2f}s)"
                  f"  {a['text'][:36]}")
        print(f"  —— 可判锚点 {len(found)} 条")
        return 0
    errs, notes = check()
    for n in notes:
        print(f"  · {n}")
    for e in errs:
        print(f"  ✗ {e}")
    if errs:
        print(f"\n✗ 帧内锚点漂移 {len(errs)} 条")
        return 1
    print(f"✓ 帧内锚点与旁白一致（{len(found)} 条可判锚点）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
