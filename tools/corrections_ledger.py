#!/usr/bin/env python3
"""corrections_ledger.py — 给「纠正账本」本身装一条闸门。

为什么需要它：`doc/corrections.md` 是整个工作区唯一会自我进化的地方——每次纠正 agent，
先问能不能变成确定性检查，不能才允许写散文。但这个机制**此前只靠人记得**：
账本可以漏记一行，也可以记了不填「固化形态」，或者填个 `待办` 就搁在那儿永远不动，
而没有任何东西会因此报警。**用一条 lint 规则去保证 lint 规则的产出**，这是最后一环。

四条判据（都只判"能不能判"的）：
  1. 每一行必须有「固化形态」，且标签是认得的那几个（`G*` / `架构` / `文档` / `待办`）
  2. **不允许 `待办`**：要么固化成检查，要么明确写成 `文档` 并说清为什么机器判不了
  3. 行里点名的 `tools/*.py` 必须真的存在（防止"闸门记了、脚本改名了"这种假固化）
  4. 日期是合法 ISO 日期

它**判不了**的那一半，要说清：账本漏记一整条纠正是查不出来的——有没有发生纠正，
只有当时在场的人和 agent 知道。这条闸门保证的是"记了就得交代清楚"，
不是"一定会记"。想补前者，只能靠收尾时人扫一遍，或者让每个闸门在红的时候顺手写日志。

用法（在仓库根跑）：
    python3 tools/corrections_ledger.py          # 查（接进 make check-ledger / verify-all）
    python3 tools/corrections_ledger.py --list   # 逐行列出：日期 / 固化形态 / 症状摘要
    python3 tools/corrections_ledger.py --ledger PATH   # 查指定账本（selftest 用）
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / "doc" / "corrections.md"
SECTION = re.compile(r"^##\s*账本\s*$")
DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
TOOL = re.compile(r"tools/[A-Za-z0-9_/]+\.py")
# 认得的固化形态。前缀匹配：`G`、`G8`、`G-R2/R3`、`G-♪` 都算 `G` 家族
LABELS = ("G", "架构", "文档", "待办")


def rows() -> list[dict]:
    """把「## 账本」一节里的表格行读出来。"""
    if not LEDGER.exists():
        return []
    out: list[dict] = []
    inside = False
    for i, line in enumerate(LEDGER.read_text(encoding="utf-8").splitlines(), 1):
        if SECTION.match(line):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if not inside or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or not DATE.match(cells[0]):
            continue                      # 表头、分隔行、说明行
        out.append({
            "line": i,
            "date": cells[0],
            "symptom": cells[1] if len(cells) > 1 else "",
            "form": cells[-1] if len(cells) >= 4 else "",
            "cells": len(cells),
        })
    return out


def label_of(form: str) -> str:
    for lab in LABELS:
        if form.startswith("`" + lab) or form.startswith(lab):
            return lab
    return ""


def check() -> tuple[list[str], dict[str, int]]:
    errs: list[str] = []
    stats: dict[str, int] = {}
    items = rows()
    if not items:
        return ["账本里一行都没解析到（文件结构变了？表头或 `## 账本` 标题被改了）"], stats

    for r in items:
        where = f"doc/corrections.md:{r['line']}"
        if r["cells"] < 4:
            errs.append(f"{where}: 只有 {r['cells']} 列，缺「固化形态」——"
                        f"这条纠正还没有交代它怎么固化")
            continue
        if not r["form"]:
            errs.append(f"{where}: 「固化形态」是空的——要么固化成检查，"
                        f"要么写 `文档` 并说清为什么机器判不了")
            continue
        lab = label_of(r["form"])
        if not lab:
            errs.append(f"{where}: 不认识的固化形态「{r['form'][:20]}」"
                        f"（认得的：{', '.join(LABELS)}）")
            continue
        stats[lab] = stats.get(lab, 0) + 1
        if lab == "待办":
            errs.append(f"{where}: 还是 `待办`——这条纠正挂在这里没固化。"
                        f"要么变成检查，要么降级成 `文档` 并写明理由")
        try:
            y, m, d = (int(x) for x in DATE.match(r["date"]).groups())
            dt.date(y, m, d)
        except ValueError:
            errs.append(f"{where}: 日期 {r['date']} 不是合法日期")
        for tool in TOOL.findall(r["form"]):
            if not (REPO / tool).exists():
                errs.append(f"{where}: 写的是 {tool}，但这个文件不存在——"
                            f"假固化（脚本改名/删了，账本还在指着它）")
    return errs, stats


def main() -> int:
    global LEDGER
    if "--ledger" in sys.argv:              # 供 selftest 指到夹具；平时不用
        LEDGER = Path(sys.argv[sys.argv.index("--ledger") + 1]).resolve()
    if "--list" in sys.argv:
        for r in rows():
            print(f"  {r['date']}  {label_of(r['form']) or '（空）':<6}  {r['symptom'][:56]}")
        print(f"  —— {len(rows())} 条")
        return 0
    errs, stats = check()
    for e in errs:
        print(f"  ✗ {e}")
    if errs:
        print(f"\n✗ 账本自检 {len(errs)} 项不通过")
        return 1
    parts = " / ".join(f"{k} {v}" for k, v in sorted(stats.items(), key=lambda kv: -kv[1]))
    print(f"✓ 账本 {sum(stats.values())} 条全部有固化形态（{parts}）；没有欠账")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
