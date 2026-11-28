#!/usr/bin/env python3
"""doc_facts.py — 文档里抄的代码常量，必须与代码一致。

为什么需要它：`doc/配音指导.md` 曾经写着「服务地址与 key 走 `TTS_URL` / `TTS_KEY`」，
而 `tools/voice_build.py` 早就是硬编码的本机端点、且不发 key。这类分歧不会自己消失——
**文档写的是一个世界，代码跑的是另一个世界**，两边都能自圆其说，只有新来的人会被骗。
2026-11-28 定下的规则是「文档与代码冲突时以代码为准」，那就让机器来判，而不是再靠人记得。

做法：把「文档里抄了哪段代码常量」写成一张表。每条事实声明：
  src     常量所在的源文件
  const   常量名（用正则从源码里抓值）
  pattern 文档里这段值的样子（抓出来的每一段都必须与常量相等）
  docs    要在哪些文件里查

只查**能从源码抓出唯一值**的事实，且只查「值长这样」的文本片段——所以它不会去理解散文，
只回答一个问题：文档里出现的那个端点/路径，跟代码里现在这个，是不是同一个。

用法（在仓库根跑）：
    python3 tools/doc_facts.py          # 查（接进 make check-docs / verify-all）
    python3 tools/doc_facts.py --list   # 只看表里有哪些事实、各自的当前值
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 事实表：一条事实 = 一个"文档抄了代码常量"的地方
FACTS = [
    {
        "name": "TTS 端点",
        "src": "tools/voice_build.py",
        "const": "ENDPOINT",
        "pattern": r"https?://[A-Za-z0-9.\-]+(?::\d+)?/v1/audio/speech",
        "docs": ["doc/配音指导.md", "doc/本机TTS-Qwen3.md", "doc/START-EPISODE.md",
                 "templates/episode/AGENTS.md", "templates/episode/BRIEF.md",
                 "projects/*/SCRIPT.md", "projects/*/BRIEF.md", "projects/*/AGENTS.md"],
    },
]

# 历史账本不查：那里写的是"当时是什么"，与"现在是什么"本来就不该一致
SKIP_DOCS = {"doc/corrections.md"}


def const_value(src: str, const: str) -> str | None:
    path = REPO / src
    if not path.exists():
        return None
    m = re.search(rf'^{const}\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def doc_files(patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    for pat in patterns:
        for p in sorted(REPO.glob(pat)):
            if p.is_file() and str(p.relative_to(REPO)) not in SKIP_DOCS:
                out.append(p)
    return out


def check() -> list[str]:
    errs: list[str] = []
    for fact in FACTS:
        want = const_value(fact["src"], fact["const"])
        if want is None:
            errs.append(f"{fact['name']}：抓不到 {fact['src']} 里的 {fact['const']}，"
                        f"事实表失效了（改了常量名就同步这里）")
            continue
        rx = re.compile(fact["pattern"])
        seen = 0
        for doc in doc_files(fact["docs"]):
            text = doc.read_text(encoding="utf-8")
            for i, line in enumerate(text.splitlines(), 1):
                for got in rx.findall(line):
                    seen += 1
                    if got != want:
                        errs.append(f"{doc.relative_to(REPO)}:{i} 写的是 {got}，"
                                    f"而 {fact['src']} 的 {fact['const']} 是 {want}"
                                    f" —— 文档与代码不一致，以代码为准")
        if seen == 0:
            errs.append(f"{fact['name']}：文档里一处都没提到 {want}"
                        f"（要么该写的地方漏了，要么 pattern 该改了）")
    return errs


def main() -> int:
    if "--list" in sys.argv:
        for f in FACTS:
            print(f"  {f['name']:<12} {f['src']}::{f['const']} = {const_value(f['src'], f['const'])}")
        return 0
    errs = check()
    for e in errs:
        print(f"  ✗ {e}")
    if errs:
        print(f"\n✗ 文档与代码有 {len(errs)} 处不一致")
        return 1
    print(f"✓ 文档里抄的 {len(FACTS)} 项代码常量与代码一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
