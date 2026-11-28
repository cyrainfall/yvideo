#!/usr/bin/env python3
"""delivery_table.py — README 的「已交付」表与实际发布物对账。

为什么需要它：那张表是人工回填的，已经出过一次事故——EP07 发布后表还停在 EP06
（见 doc/corrections.md）。人工表格的问题不是"写错一个数"，而是**没有任何东西会因为它
过期而报警**：新集发布、旧集成片重渲、bvid 换掉，表格都可以静静地留在过去。

判据只认 `publish/epNN/result.json`（发布了什么、bvid 是什么）和磁盘（成片、归档目录
在不在了）。凡是从这两处能机械判出来的，都判；判不出来的（标题起得好不好、4:06.3 和
4:09.0 哪个"对"）不判，只报告。

三种模式：
    python3 ../../tools/delivery_table.py            # --check：只报错（接进 make readonly）
    python3 ../../tools/delivery_table.py --report   # 全表对账，含提示信息
    python3 ../../tools/delivery_table.py --missing  # 列出已发布但表里没有的集

它只读不写：**不自动改 README**。表格里的标题是人的判断（「改它（第一季完结）」这种
括号注释机器写不出来），机器只负责指出哪一行与事实不符。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "hyperframes.json").exists():
    raise SystemExit(f"✗ 请在某一集的工程目录里运行（{ROOT} 下没有 hyperframes.json）")

README = ROOT / "README.md"
SECTION_RE = re.compile(r"^##\s+已交付\s*$")
EP_RE = re.compile(r"ep(\d+)", re.I)   # 表里写 EP07，目录是小写 ep07
TIME_RE = re.compile(r"^(?:(\d+):)?(\d+(?:\.\d+)?)$")
TICK = re.compile(r"`([^`]+)`")


def parse_table() -> dict[int, dict]:
    """README 的「已交付」表 → {集号: 行的各格}。没有这张表就返回空。"""
    if not README.exists():
        return {}
    rows: dict[int, dict] = {}
    in_section = False
    for line in README.read_text(encoding="utf-8").splitlines():
        if SECTION_RE.match(line):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        m = EP_RE.search(cells[0])
        if not m:
            continue          # 表头 / 分隔行
        ticks = [TICK.findall(c) for c in cells]
        rows[int(m.group(1))] = {
            "ep": int(m.group(1)),
            "title": cells[0],
            "render": ticks[1][0] if ticks[1] else "",
            "duration": cells[2],
            "archive": ticks[3][0] if ticks[3] else "",
            "bvid": ticks[4][0] if ticks[4] else "",
        }
    return rows


def parse_time(text: str) -> float | None:
    m = TIME_RE.match(text.strip())
    if not m:
        return None
    return int(m.group(1) or 0) * 60 + float(m.group(2))


def ffprobe(path: Path) -> float | None:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                              "format=duration", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, timeout=60).stdout
        return float(out.strip().splitlines()[0])
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None


def published() -> dict[int, dict]:
    """publish/epNN/result.json → {集号: 结果}。bvid 是"发过"的唯一机械证据。"""
    out: dict[int, dict] = {}
    for f in sorted((ROOT / "publish").glob("ep*/result.json")):
        m = EP_RE.search(f.parent.name)
        if not m:
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("bvid"):
            out[int(m.group(1))] = data
    return out


def audit() -> tuple[list[str], list[str], dict[int, dict], dict[int, dict]]:
    rows, pub = parse_table(), published()
    errors: list[str] = []
    notes: list[str] = []

    for ep, data in sorted(pub.items()):
        row = rows.get(ep)
        if row is None:
            errors.append(f"EP{ep:02d} 已发布（{data['bvid']}）但「已交付」表里没有它 —— "
                          f"补一行（表是给人看的，机器只负责指出缺口）")
            continue
        if row["bvid"] != data["bvid"]:
            errors.append(f"EP{ep:02d} bvid 不一致：表里 {row['bvid'] or '（空）'} vs "
                          f"publish/ep{ep:02d}/result.json 的 {data['bvid']}")
        if row["render"] and not (ROOT / row["render"]).exists():
            errors.append(f"EP{ep:02d} 表里写的成片不见了：{row['render']}"
                          f"（重渲过？还是文件被移走？）")
        if row["archive"] and not (ROOT / row["archive"]).exists():
            errors.append(f"EP{ep:02d} 表里写的归档目录不存在：{row['archive']}")
        want = parse_time(row["duration"])
        reported = data.get("duration_reported")
        if want is not None and isinstance(reported, (int, float)):
            # 平台只给整数秒，且是向上取整，所以对得上就是 ±1s 以内
            if abs(want - float(reported)) > 1.05:
                errors.append(f"EP{ep:02d} 时长与平台报的不一致：表 {row['duration']}"
                              f"（{want:.1f}s） vs 平台 {reported}s")
        if row["render"]:
            local = ffprobe(ROOT / row["render"])
            if local is not None and want is not None and abs(local - want) > 0.5:
                notes.append(f"EP{ep:02d} 本地成片 {local:.1f}s ≠ 表内 {row['duration']}"
                             f"（{want:.1f}s）：本地这一版可能重渲过，表写的是发布那一版")

    for ep, row in sorted(rows.items()):
        if ep not in pub:
            notes.append(f"EP{ep:02d} 在表里但没有 publish/ep{ep:02d}/result.json："
                         f"发布回执丢了，或这集没真发过")
        if row["render"] and not (ROOT / row["render"]).exists() and ep not in pub:
            errors.append(f"EP{ep:02d} 表里的成片不存在：{row['render']}")

    return errors, notes, rows, pub


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    errors, notes, rows, pub = audit()

    if mode == "--missing":
        for ep in sorted(set(pub) - set(rows)):
            d = pub[ep]
            print(f"  EP{ep:02d}  {d['bvid']}  {d.get('submitted_at', '')[:10]}")
        if not set(pub) - set(rows):
            print("✓ 已发布的集都在表里")
        return 0

    if not rows:
        if pub:
            for ep in sorted(pub):
                print(f"  ✗ EP{ep:02d} 已发布（{pub[ep]['bvid']}），但「已交付」表"
                      f"一行都没解析到 —— 表被删了、标题被改了，还是格式变了？")
            print(f"\n✗ 「已交付」表不见了，而 {len(pub)} 集已发布")
            return 1
        if mode == "--report":
            print("· 没有 README 或没有「已交付」表，跳过（新工程正常如此）")
        return 0

    if mode == "--report":
        print(f"  表里 {len(rows)} 行，发布回执 {len(pub)} 份")
        for ep, row in sorted(rows.items()):
            flag = "✓" if ep in pub and row["bvid"] == pub[ep]["bvid"] else "·"
            local = ffprobe(ROOT / row["render"]) if row["render"] else None
            local_s = f"{local:6.1f}s" if local is not None else "   —   "
            print(f"  {flag} EP{ep:02d}  {row['duration']:>7}  本地 {local_s}  "
                  f"{row['bvid'] or '（无 bvid）'}")
        print()

    for n in notes:
        print(f"  · {n}")
    for e in errors:
        print(f"  ✗ {e}")
    if errors:
        print(f"\n✗ 「已交付」表与发布物对不上 {len(errors)} 处")
        return 1
    print(f"✓ 「已交付」表与发布物一致（{len(rows)} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
