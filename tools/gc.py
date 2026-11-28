#!/usr/bin/env python3
"""gc.py — 工作区体检与清理：先说清"删掉要多久才能长回来"，再决定删不删。

为什么需要它：这个工作区 1.1G，其中真正需要人工保住的东西（脚本、文案、分镜、发布物）
不到 300K。其余都是**可重建物**——但"可重建"不等于"该删"：
  `.takes/` 删了要重配 53 句音（47M）
  `renders/*.mp4` 删了要重渲 10 分钟（133M）
  `learn/` 删了要重新 clone（452M，还要网络）
把这三类混在一起说"清缓存"，等于用一次误删换十分钟的清爽。

所以这个工具的核心不是删除，是**分类 + 代价**：每一条规则都必须回答"删了怎么长回来、
要多久"。默认什么都不删，只报告。

一条容易被忽略的代价：`.takes/` 不只是"省时间"。G2/G3 和「重跑一遍音频逐字节不变」这个
验证前提，都建立在**缓存命中**上；缓存一删，重配出来的音是否与原版逐字节相同就没有保证了。
所以 cache 类不是"无损清理"，是"放弃可复现性换几十兆"——这个交换值不值，要人来判断。

规则分类（顺序即可删性从高到低）：
  safe       删了不收代价：`__pycache__`、`.DS_Store`、check 报告、波形/缩略图缓存
  cache      删了要重算：TTS 句级缓存 `.takes/`（每句 ~4s）
  derived    删了要重跑一个 make 目标：`renders/epNN-review/`（40s）
  expensive  删了要重渲 / 重配 / 重下：成片、旁白 wav、`learn/`
  keep       不删：被别处引用的快照、工具自己的编辑历史

用法（在仓库根跑）：
    python3 tools/gc.py                      # 只报告（默认）
    python3 tools/gc.py --list               # 报告 + 逐条列出会被删的路径
    python3 tools/gc.py --apply safe         # 只删 safe
    python3 tools/gc.py --apply safe,cache   # 再删缓存
    python3 tools/gc.py --apply expensive --yes   # 极不推荐，需要显式 --yes

安全约束（代码里硬挡）：
  - **git 跟踪的文件永不删除**（哪怕规则命中）
  - 永不删除仓库之外的路径
  - `keep` 类即使 `--apply all` 也不动
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CAT_ORDER = ["safe", "cache", "derived", "expensive", "keep"]
CAT_LABEL = {
    "safe": "删了不收代价",
    "cache": "删了要重算",
    "derived": "删了重跑一个 make 目标",
    "expensive": "删了要重渲/重配/重下",
    "keep": "不删（被引用或工具自己的状态）",
}


def rules() -> list[dict]:
    """(名字, 通配, 类别, 重建代价)。通配相对于仓库根；先匹配到的规则占住路径。"""
    return [
        {"name": "Python 字节码", "glob": "**/__pycache__", "cat": "safe",
         "cost": "跑一次就回来（含其中的 .pyc）"},
        {"name": "系统垃圾", "glob": "**/.DS_Store", "cat": "safe", "cost": "系统自己重建"},
        {"name": "macOS 资源叉", "glob": "**/._*", "cat": "safe", "cost": "系统自己重建"},
        {"name": "check 报告", "glob": "projects/*/.hyperframes/artifacts", "cat": "safe",
         "cost": "make check（20s）"},
        {"name": "波形缓存", "glob": "projects/*/.waveform-cache", "cat": "safe",
         "cost": "用到时重算（秒级）"},
        {"name": "缩略图缓存", "glob": "projects/*/.thumbnails", "cat": "safe",
         "cost": "用到时重算（秒级）"},
        {"name": "TTS 句级缓存", "glob": "projects/*/assets/voice/.takes", "cat": "cache",
         "cost": "重配全部旁白（每句约 4s）；且失去「重跑逐字节一致」的验证前提"},
        {"name": "归档集的 TTS 缓存", "glob": "projects/*/episodes/*/takes", "cat": "cache",
         "cost": "只有重渲那一集才需要；删了重配是逐句 TTS"},
        {"name": "验收包", "glob": "projects/*/renders/*-review", "cat": "derived",
         "cost": "make review（40s）"},
        {"name": "hyperframes 编辑历史", "glob": "projects/*/.hyperframes/video-state.json",
         "cat": "keep", "cost": "删了没法 undo——工具自己的状态，不算缓存"},
        {"name": "预览状态", "glob": "projects/*/.hyperframes/preview", "cat": "keep",
         "cost": "预览在跑时删会打断 Studio 交接"},
        {"name": "抽帧快照", "glob": "projects/*/snapshots", "cat": "keep",
         "cost": "被 STORYBOARD 引用（如 episodes/ep06 的 ep06-final/）"},
        {"name": "成片 MP4", "glob": "projects/*/renders/*.mp4", "cat": "expensive",
         "cost": "重渲（5–15 分钟）"},
        {"name": "当前集旁白 wav", "glob": "projects/*/assets/voice/*.wav", "cat": "expensive",
         "cost": "重配旁白（TTS 逐句）"},
        {"name": "归档集旁白 wav", "glob": "projects/*/episodes/*/voice/*.wav", "cat": "expensive",
         "cost": "重配旁白（TTS 逐句）"},
        {"name": "第三方克隆", "glob": "learn/*", "cat": "expensive",
         "cost": "重新 clone（网络 + 时间）"},
        {"name": "音色参考样本", "glob": "voice/*", "cat": "keep",
         "cost": "TTS 复刻音色的唯一输入，删了声音就变了"},
        {"name": "插画/封面产出", "glob": "out/*", "cat": "keep",
         "cost": "这是产品，不是缓存"},
        {"name": "共享技能安装", "glob": ".agents/*", "cat": "keep",
         "cost": "等价于 node_modules，另处维护"},
    ]


def tracked_files() -> set[Path]:
    try:
        out = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z"],
                             capture_output=True, text=True).stdout
    except OSError:
        return set()
    return {REPO / p for p in out.split("\0") if p}


def path_size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    total = 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            try:
                total += (Path(root) / f).lstat().st_size
            except OSError:
                pass
    return total


def human(n: float) -> str:
    for unit in ("B", "K", "M", "G"):
        if n < 1024 or unit == "G":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}G"


def collect(tracked: set[Path]) -> list[dict]:
    found: list[dict] = []
    claimed: list[Path] = []          # 已被前一条规则算过的路径（父子重叠时不再重复计入）
    for rule in rules():
        items = sorted(REPO.glob(rule["glob"]))
        items = [p for p in items if REPO in p.parents and p != REPO]
        keep: list[Path] = []
        skipped_tracked = 0
        for p in items:
            # 只在「p 已被前面某条规则算过（相等或在其内部）」时跳过；
            # 反过来（p 是某个已计入路径的父目录）不能跳，否则一个大目录会因为里面
            # 有个 __pycache__ 整个消失——那会把 143M 报成 184K。
            if any(c == p or c in p.parents for c in claimed):
                continue
            # git 跟踪的一律留下（目录里只要有一个跟踪文件，整个目录都不删）
            hit = p in tracked or any(t == p or p in t.parents for t in tracked)
            if hit:
                skipped_tracked += 1
                continue
            keep.append(p)
        claimed.extend(keep)
        found.append({**rule, "paths": keep, "bytes": sum(path_size(p) for p in keep),
                      "tracked": skipped_tracked})
    return found


def report(found: list[dict], show_paths: bool) -> None:
    print(f"── 工作区体检（{REPO.name}）\n")
    print(f"{'规则':<22}{'类':<11}{'数量':>5}{'大小':>9}  重建代价")
    print("─" * 96)
    total = {c: 0 for c in CAT_ORDER}
    for r in found:
        if not r["paths"]:
            continue
        total[r["cat"]] += r["bytes"]
        note = f"（{r['tracked']} 个被 git 跟踪，跳过）" if r["tracked"] else ""
        print(f"{r['name']:<22}{r['cat']:<11}{len(r['paths']):>5}"
              f"{human(r['bytes']):>9}  {r['cost']}{note}")
        if show_paths:
            for p in r["paths"][:40]:
                print(f"    {p.relative_to(REPO)}")
            if len(r["paths"]) > 40:
                print(f"    …… 还有 {len(r['paths']) - 40} 条")
    print("─" * 96)
    for c in CAT_ORDER:
        if total[c]:
            print(f"  {c:<11} {human(total[c]):>8}   {CAT_LABEL[c]}")
    reclaim = total["safe"] + total["cache"] + total["derived"]
    print(f"\n  可回收（safe+cache+derived）= {human(reclaim)}；"
          f"expensive {human(total['expensive'])} 建议留着，keep {human(total['keep'])} 不动")
    print("\n  删什么先看代价：`--apply safe` 是零成本的；带 cache/derived 的要想一下。")
    print("  报告不是清单——它只是把「你正在背多少东西」摆出来。")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", default="", help="要删的类别，逗号分隔：safe,cache,derived")
    ap.add_argument("--list", action="store_true", help="逐条列出会被删的路径")
    ap.add_argument("--yes", action="store_true", help="删 expensive/keep 时必须显式确认")
    args = ap.parse_args()

    if not (REPO / ".git").exists():
        print(f"✗ 请在仓库根运行（{REPO} 下没有 .git）", file=sys.stderr)
        return 2

    tracked = tracked_files()
    found = collect(tracked)
    report(found, args.list)
    if not args.apply:
        return 0

    cats = [c.strip() for c in args.apply.split(",") if c.strip()]
    bad = [c for c in cats if c not in CAT_ORDER]
    if bad:
        print(f"\n✗ 不认识的类别：{', '.join(bad)}（可选 {', '.join(CAT_ORDER)}）", file=sys.stderr)
        return 2
    if "keep" in cats:
        print("\n✗ keep 类不删：它们被别处引用或是工具自己的状态", file=sys.stderr)
        return 2
    if "expensive" in cats and not args.yes:
        print("\n✗ expensive 要加 --yes：重渲一集是 5–15 分钟，别顺手删", file=sys.stderr)
        return 2

    print(f"\n── 删除 {'/'.join(cats)}")
    freed = 0
    removed = 0
    for r in found:
        if r["cat"] not in cats:
            continue
        for p in r["paths"]:
            try:
                size = path_size(p)
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                freed += size
                removed += 1
            except OSError as e:
                print(f"  · 跳过 {p.relative_to(REPO)}：{e}")
    print(f"✓ 删了 {removed} 项，回收 {human(freed)}")
    if "expensive" in cats:
        print("  成片/旁白/克隆被删了：需要时重跑 make render / make narrate，或重新 clone。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
