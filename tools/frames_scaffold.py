#!/usr/bin/env python3
"""frames_scaffold.py — 按旁白帧数铺出 frame-NN.html 骨架，并把每帧时长写对。

为什么需要它：`index.html` 由 index_build 按 voice_takes 的帧数生成，会引用
`compositions/frames/frame-01.html … frame-NN.html`。少一个文件，`make check` 就报
`missing_or_empty_sub_composition`；而每帧的动画时长（进度线那条）必须等于该帧时长
（旁白 + 0.5s，收尾帧 +1.2s），写错就会留下 dead_stretch —— 都是"看起来能跑、其实在
骗自己"的坑。所以铺帧这件事应该是脚本，不是手抄。

规则：
  · 已存在的帧文件**不覆盖**（你的画面不会被抹掉），只把 `var DUR = x;` 校准成该帧时长
  · 缺失的帧从 frame-01.html 复制，替换 id（f1 → fN）与 data-composition-id / 时间线名
  · 帧数与时长的唯一来源是 voice_takes.json（与 index_build 同源）

用法（在某一集的工程目录里）：
    python3 ../../tools/frames_scaffold.py            # 只补缺失 + 校准 DUR
    python3 ../../tools/frames_scaffold.py --dry-run  # 只报告会做什么
    python3 ../../tools/frames_scaffold.py --force    # 连已存在的帧也重写（危险，会覆盖画面）
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "hyperframes.json").exists():
    raise SystemExit(f"✗ 请在某一集的工程目录里运行（{ROOT} 下没有 hyperframes.json）")

TAKES = ROOT / "voice_takes.json"
FRAMES = ROOT / "compositions" / "frames"
STARTER = FRAMES / "frame-01.html"
TAIL_S, LAST_TAIL_S = 0.5, 1.2
DUR_RE = re.compile(r"var DUR = [\d.]+;")


def frame_duration(dur: float, index: int, total: int) -> float:
    return round(dur + (LAST_TAIL_S if index == total - 1 else TAIL_S), 3)


def rename_ids(html: str, n: int) -> str:
    """把 frame-01 的 id 空间映射到 frame-NN，避免两帧撞 id 撞时间线名。"""
    tag = f"{n:02d}"
    # 先改 HTML 的 id 前缀（id="f1"、id="f1-eyebrow" 都要覆盖），
    # 再改 CSS/JS 里的 #f1 选择器；顺序反了会得到 "#f2" 指向 id="f1-eyebrow" 的错配。
    html = html.replace('id="f1', f'id="f{n}')
    html = html.replace("#f1", f"#f{n}")
    html = html.replace("data-composition-id=\"frame-01\"", f'data-composition-id="frame-{tag}"')
    html = html.replace('window.__timelines["frame-01"]', f'window.__timelines["frame-{tag}"]')
    html = html.replace("frame-01 · 起步帧", f"frame-{tag} · 起步帧")
    return html


def set_duration(html: str, dur: float) -> tuple[str, bool]:
    new, n = DUR_RE.subn(f"var DUR = {dur};", html)
    return new, n > 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="已存在的帧也重写（会覆盖画面）")
    args = ap.parse_args()

    if not TAKES.exists():
        print("✗ 没有 voice_takes.json：先跑 make narrate", file=sys.stderr)
        return 2
    if not STARTER.exists():
        print(f"✗ 缺少母版 {STARTER.relative_to(ROOT)}（模板应自带 frame-01.html）", file=sys.stderr)
        return 2

    takes = json.loads(TAKES.read_text(encoding="utf-8"))["takes"]
    total = len(takes)
    base = STARTER.read_text(encoding="utf-8")

    created, calibrated, kept, no_const = [], [], [], []
    for i, take in enumerate(takes):
        n = take["frame"]
        dur = frame_duration(take["duration_s"], i, total)
        path = FRAMES / f"frame-{n:02d}.html"
        if path.exists() and not args.force:
            if path == STARTER:
                body = base
            else:
                body = path.read_text(encoding="utf-8")
            new, ok = set_duration(body, dur)
            if not ok:
                print(f"  ! frame-{n:02d}.html 里没有 `var DUR = x;` 这行，跳过时长校准", file=sys.stderr)
                no_const.append(n)
                continue
            if new != body:
                if not args.dry_run:
                    path.write_text(new, encoding="utf-8")
                calibrated.append((n, dur))
            else:
                kept.append(n)
            continue

        html = rename_ids(base, n)
        html, ok = set_duration(html, dur)
        if not ok:
            print("✗ 母版里没有 `var DUR = x;`，无法写时长", file=sys.stderr)
            return 2
        if not args.dry_run:
            if args.force and path.exists() and path != STARTER:
                shutil.copy2(path, path.with_suffix(".html.bak"))
            path.write_text(html, encoding="utf-8")
        created.append((n, dur, take.get("title", "")))

    for n, dur, title in created:
        print(f"  + frame-{n:02d}.html  {dur}s  {title}")
    for n, dur in calibrated:
        print(f"  ~ frame-{n:02d}.html  DUR → {dur}s")
    if kept:
        print(f"  = {len(kept)} 帧已存在且时长正确，未动")
    if no_const:
        print(f"  ! {len(no_const)} 帧没有 DUR 常量（内联时长写法），未参与校准")
    if args.dry_run:
        print("（dry-run：没有写任何文件）")
    print(f"✓ {total} 帧：新建 {len(created)}，校准 {len(calibrated)}，未动 {len(kept)}，无 DUR 常量 {len(no_const)}")
    print("  下一步：逐帧把 .plane 里的内容换成真画面，再 make check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
