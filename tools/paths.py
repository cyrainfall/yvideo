#!/usr/bin/env python3
"""paths.py — 一集工程里「生成物放在哪」的唯一答案。

为什么单独立一个文件：三层契约（源 / 生成 / 交付）以前只写在 AGENTS.md 的表格里，
而路径是散在 9 个脚本里的 `ROOT / "xxx.json"` 字面量。改一次布局要 grep 全仓，
漏一处就是"文件找不到"，或者更糟——脚本写去新位置、闸门还在读旧位置，两边都说自己是对的。
布局收敛到这里之后，「生成物在哪」只有一个答案。

现状（2026-11-28 起，生成物离开工程根）：

    generated/voice_takes.json      旁白 take 清单        voice_build.py 写
    generated/audio_meta.json       词级时间              timing.py 写
    generated/caption_groups.json   字幕分组              captions_build.py 写
    index.html                      ⚠ 必须留在根          index_build.py 写
    compositions/captions.html      ⚠ 必须留在 compositions/  captions_build.py 写

后两个为什么不进 `generated/`：HyperFrames 要求工程根有 `index.html`，字幕组合的位置
又由 `index.html` 里的 `data-composition-src` 相对路径决定。所以结构边界在它们身上只能
部分生效——那两个文件的"禁止手改"仍由 G6 指纹兜（`make chain`）。

这条边界本身也是闸门：`gate_chain.py` 的 G7 检查工程根有没有残留的旧布局
（根上出现 `voice_takes.json` 之类 → 红，提示跑迁移）。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "hyperframes.json").exists():
    raise SystemExit(f"✗ 请在某一集的工程目录里运行（{ROOT} 下没有 hyperframes.json）")

# ── 源（人写，脚本只读） ──────────────────────────────
SCRIPT = ROOT / "SCRIPT.md"

# ── 生成（脚本写，别处只读） ──────────────────────────
GEN = ROOT / "generated"
GEN.mkdir(exist_ok=True)      # 新工程第一次生成时还没有这个目录；建它算环境准备，不算副作用
TAKES = GEN / "voice_takes.json"
META = GEN / "audio_meta.json"
CAPTIONS = GEN / "caption_groups.json"

# ── 必须在固定位置的两份（HyperFrames 契约，见文件头） ──
INDEX = ROOT / "index.html"
CAPTIONS_HTML = ROOT / "compositions" / "captions.html"

# 旧布局残留：出现在这里就说明这一集还没迁移
LEGACY = ("voice_takes.json", "audio_meta.json", "caption_groups.json")
