#!/usr/bin/env python3
"""new_episode.py — 从 templates/episode 生成一集新工程。

为什么需要它：一集一工程的全部价值在于「每集都长一样」。靠手抄目录会让第一集和第二集
在命名、Makefile、闸门接线上慢慢分叉——那种分叉当时看不出来，等到要批量改的时候才发现
有 11 个版本。所以脚手架必须是脚本，模板必须入库。

用法：
    python3 tools/new_episode.py --ep 08 --title 接缝
    python3 tools/new_episode.py --ep 08 --title 接缝 --dry-run     # 只看会建什么
    python3 tools/new_episode.py --ep 08 --title 接缝 --force       # 目录已存在时覆盖

产物：projects/ep08-接缝/（占位符已替换），并打印下一步该做什么。
模板在 templates/episode/；改模板 = 改以后每一集的样子。
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "templates" / "episode"
TEXT_SUFFIXES = {".md", ".json", ".html", ".txt", ".mjs", ".js", ".yml", ".yaml"}
TEXT_NAMES = {"Makefile", "package.json"}


def normalize_ep(raw: str) -> str:
    """08 / ep08 / EP8 → ep08。"""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise SystemExit(f"✗ --ep 需要数字，收到 {raw!r}")
    return f"ep{int(digits):02d}"


def is_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", required=True, help="集号：08 / ep08")
    ap.add_argument("--title", required=True, help="集标题，如 接缝")
    ap.add_argument("--root", default="projects", help="生成到哪个目录下（默认 projects）")
    ap.add_argument("--dry-run", action="store_true", help="只列出会创建的文件")
    ap.add_argument("--force", action="store_true", help="目标目录已存在时覆盖")
    args = ap.parse_args()

    if not TEMPLATE.is_dir():
        print(f"✗ 找不到模板目录 {TEMPLATE}", file=sys.stderr)
        return 2

    ep = normalize_ep(args.ep)
    title = args.title.strip()
    if not title:
        raise SystemExit("✗ --title 不能为空")
    dest = (REPO / args.root / f"{ep}-{title}").resolve()
    subs = {"__EP__": ep, "__TITLE__": title,
            "__DATE__": dt.datetime.now().astimezone().isoformat(timespec="seconds")}

    if dest.exists() and not args.force:
        print(f"✗ {dest} 已存在（要覆盖加 --force）", file=sys.stderr)
        return 1

    files = sorted(p for p in TEMPLATE.rglob("*") if p.is_file())
    if args.dry_run:
        print(f"将生成 {dest}（{len(files)} 个文件）")
        for p in files:
            print(f"  {p.relative_to(TEMPLATE)}")
        return 0

    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(TEMPLATE, dest)

    replaced = 0
    for p in dest.rglob("*"):
        if p.is_file() and is_text(p):
            s = p.read_text(encoding="utf-8")
            out = s
            for k, v in subs.items():
                out = out.replace(k, v)
            if out != s:
                p.write_text(out, encoding="utf-8")
                replaced += 1

    print(f"✓ 已生成 {dest.relative_to(REPO)}")
    print(f"  {len(files)} 个文件，其中 {replaced} 个替换了占位符")
    print()
    print("下一步：")
    print(f"  cd {dest.relative_to(REPO)}")
    print("  1. 写 BRIEF.md（这一集要讲清的一件事）")
    print("  2. 写 SCRIPT.md，然后 make readonly —— 读法规则先过闸门再配音")
    print("  3. make narrate && make captions")
    print("  4. 写 compositions/frames/*.html（先读 AGENTS.md 的 HyperFrames 契约）")
    print("  5. make verify && make listen && make render")
    print(f"  6. make review —— 验收包 renders/{ep}-review/，发布前先看 REVIEW.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
