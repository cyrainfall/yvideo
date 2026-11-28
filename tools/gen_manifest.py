#!/usr/bin/env python3
"""gen_manifest.py — 生成物指纹（G6）：手改，和「改了源头没重跑」，都拦得住。

为什么需要它：三层契约里「生成物禁止手改」此前只是一句话。G1–G5 检查的是**一致性**——
人改完只要自洽，闸门全绿，改错这件事完全不可见。这个模块把「这份文件是脚本生成的、
且没被改过」变成可验证的事实。

做法：不动生成物格式，只维护项目根的 `.generated-manifest.json` 边车。每条记录：

  by        生成它的脚本（相对仓库根）
  tool_sha  该脚本当时的 sha256 前 16 位 —— 脚本改了、输出没重跑 → 提示
  inputs    上游文件 → sha256 前 16 位   —— 上游变了没重跑 → 报错
  body_sha  生成物自身的 sha256 前 16 位 —— 任何人手改文件   → 报错

为什么用边车、不往文件里塞字段：`caption_groups.json` 是数组、`index.html` 是 HTML，
塞字段要么改格式、要么得连带改所有消费方。边车对下游零影响，也不引入新的解析分支。

局限（明写）：边车本身可以被一起改掉。它防的是**误改**和**忘重跑**，不是防恶意篡改——
真要作弊的人什么都能改。这条闸门的价值在于：让"我以为我改的是源头"这件事当场暴露。

用法（在某一集的工程目录里）：
    python3 ../../tools/gen_manifest.py verify     # 供 gate_chain 调用
    python3 ../../tools/gen_manifest.py show       # 看当前指纹
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST_NAME = ".generated-manifest.json"

# 应当被指纹覆盖的生成物（用于发现"还是旧文件、没加指纹"）
KNOWN = [
    "voice_takes.json",
    "audio_meta.json",
    "index.html",
    "caption_groups.json",
    "compositions/captions.html",
]


def _sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _manifest_path(project: Path) -> Path:
    return project / MANIFEST_NAME


def load_manifest(project: Path | None = None) -> dict:
    p = _manifest_path(project or Path.cwd())
    if not p.exists():
        return {"version": 1, "files": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "files": {}}
    data.setdefault("files", {})
    return data


def _save(project: Path, data: dict) -> None:
    data["files"] = dict(sorted(data["files"].items()))
    _manifest_path(project).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stamp(rel_path: str, by: str, inputs: list[str], project: Path | None = None) -> None:
    """生成器写完文件后调用：记录它的指纹。"""
    project = project or Path.cwd()
    out = project / rel_path
    tool = REPO / by
    if not out.exists():
        raise SystemExit(f"✗ 指纹：生成物不存在 {rel_path}")
    if not tool.exists():
        raise SystemExit(f"✗ 指纹：生成器不存在 {by}")
    data = load_manifest(project)
    data["files"][rel_path] = {
        "by": by,
        "tool_sha": _sha16(tool),
        "inputs": {i: _sha16(project / i) for i in inputs if (project / i).exists()},
        "body_sha": _sha16(out),
    }
    _save(project, data)


def verify(project: Path | None = None) -> tuple[list[str], list[str]]:
    """返回 (errors, warnings)。errors 会让闸门红。"""
    project = project or Path.cwd()
    data = load_manifest(project)
    files: dict = data["files"]
    errors: list[str] = []
    warnings: list[str] = []

    for rel, rec in files.items():
        path = project / rel
        if not path.exists():
            errors.append(f"{rel}: 生成物不见了（跑 {rec.get('by')} 重新生成）")
            continue
        if _sha16(path) != rec.get("body_sha"):
            errors.append(
                f"{rel}: 内容与指纹不符 —— 被手改过。改源头后重跑 {rec.get('by')}，"
                f"不要直接改生成物")
            continue
        changed = [i for i, h in rec.get("inputs", {}).items()
                   if not (project / i).exists() or _sha16(project / i) != h]
        if changed:
            errors.append(
                f"{rel}: 上游已变（{', '.join(changed)}），生成物是旧的 —— 重跑 {rec.get('by')}")
            continue
        tool = REPO / rec.get("by", "")
        if tool.exists() and _sha16(tool) != rec.get("tool_sha"):
            warnings.append(f"{rel}: 生成器 {rec.get('by')} 已变更，建议重跑一次")

    for rel in KNOWN:
        if rel not in files and (project / rel).exists():
            warnings.append(f"{rel}: 未加指纹（旧文件），跑一次 make captions 补上")

    return errors, warnings


def show(project: Path | None = None) -> int:
    data = load_manifest(project)
    files = data["files"]
    if not files:
        print("（还没有指纹；跑一次 make captions）")
        return 0
    for rel, rec in files.items():
        print(f"  {rel:<28} by {rec['by']:<28} tool {rec['tool_sha']}  body {rec['body_sha']}")
    return 0


def main() -> int:
    if not (Path.cwd() / "hyperframes.json").exists():
        print(f"✗ 请在某一集的工程目录里运行（{Path.cwd()} 下没有 hyperframes.json）",
              file=sys.stderr)
        return 2
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "show":
        return show()
    errors, warnings = verify()
    for w in warnings:
        print(f"  · {w}")
    for e in errors:
        print(f"  ✗ {e}")
    if errors:
        print(f"\n✗ 指纹校验失败 {len(errors)} 项")
        return 1
    print(f"✓ 生成物指纹一致（{len(load_manifest()['files'])} 个文件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
