#!/usr/bin/env python3
"""migrate_layout.py — 把旧布局（生成物散在工程根）迁到 generated/。

为什么需要它：G7 会在工程根发现 `voice_takes.json` 之类就报红，但报红不解决问题——
得有一个明确的、可重复的动作把旧工程迁过来，而不是留一句"手动 mv 一下"。

做三件事：
  1. `git mv`（未跟踪时用 shutil.move）把三个 JSON 挪进 `generated/`
  2. 重写 `.generated-manifest.json` 里的路径键与上游路径（否则 G6 会报"生成物不见了"）
  3. 打印迁完该跑什么

幂等：已经迁过的工程再跑一次什么都不做。

用法（在某一集的工程目录里）：
    python3 ../../tools/migrate_layout.py
    python3 ../../tools/migrate_layout.py --dry-run
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "hyperframes.json").exists():
    raise SystemExit(f"✗ 请在某一集的工程目录里运行（{ROOT} 下没有 hyperframes.json）")

GEN = ROOT / "generated"
MOVES = ("voice_takes.json", "audio_meta.json", "caption_groups.json")
MANIFEST = ROOT / ".generated-manifest.json"


def tracked(rel: str) -> bool:
    return subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", rel],
                          capture_output=True).returncode == 0


def move_one(name: str, dry: bool) -> bool:
    src, dst = ROOT / name, GEN / name
    if not src.exists():
        return False
    if dst.exists():
        raise SystemExit(f"✗ {dst.relative_to(ROOT)} 已存在，拒绝覆盖：先确认哪一份是新的")
    print(f"  {name} → generated/{name}")
    if dry:
        return True
    if tracked(name):
        subprocess.run(["git", "-C", str(ROOT), "mv", name, f"generated/{name}"], check=True)
    else:
        shutil.move(str(src), str(dst))
    return True


def rewrite_manifest(dry: bool) -> None:
    if not MANIFEST.exists():
        print("  （没有 .generated-manifest.json，跳过：跑一次 make captions 会重建）")
        return
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = data.get("files", {})
    changed = False
    new_files: dict[str, dict] = {}
    for rel, rec in files.items():
        new_rel = f"generated/{rel}" if rel in MOVES else rel
        inputs = {}
        for k, v in rec.get("inputs", {}).items():
            inputs[f"generated/{k}" if k in MOVES else k] = v
        new_files[new_rel] = {**rec, "inputs": inputs}
        changed |= new_rel != rel or inputs != rec.get("inputs", {})
    if not changed:
        print("  （manifest 里没有旧路径键）")
        return
    data["files"] = dict(sorted(new_files.items()))
    print(f"  .generated-manifest.json：{len(files)} 条记录的键已改写")
    if not dry:
        MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")


def main() -> int:
    dry = "--dry-run" in sys.argv
    print(f"── 迁移布局 {ROOT.name}（{'预览' if dry else '执行'}）")
    GEN.mkdir(exist_ok=True)
    moved = sum(move_one(n, dry) for n in MOVES)
    rewrite_manifest(dry)
    if not moved:
        print("  已经在 generated/ 布局下，无需迁移")
        return 0
    print("\n下一步：make chain（应 7 条全绿）→ make verify")
    print("产物应与迁移前**逐字节相同**：这只是搬位置，不是重新生成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
