#!/usr/bin/env python3
"""selftest.py — 闸门的红绿回归：把闸门自己当被测对象。

为什么需要它：这一年加的闸门越来越多，但**"它能拦住"这件事大多只被人验证过一次**——
某天手工注入一个故障、看见红、恢复、看见绿，然后就再也没人碰过那条判据。
之后谁改了容差、改了正则、改了列序，闸门可能已经瞎了，而 `make verify` 依然一片绿：
**被削弱的闸门不会自己报警**。所以每条闸门都要有一组"必须红 / 必须绿"的用例。

两种做法，本文件两种都用：
  · 工具自己有 `--selftest` 的（`en_check`、`claim_check`）→ 直接调它，规则表改坏了它自己会红
  · 需要真实工程才能跑出判据的（`gate_chain` / `polyphone_check` / `frame_anchors` /
    `delivery_table`）→ 本文件现场造一个**最小但合法**的工程，注入一处故障，看它红不红

夹具是现场生成的（不落盘、不入库）：两帧、两句话、两条 0.5s 的静音 wav、一份合法的
index.html 与指纹。任何一条比这更小就跑不出 G4/G5 那些判据，比这更大就变成了维护负担。

用法（在仓库根跑）：
    python3 tools/selftest.py              # 全部用例
    python3 tools/selftest.py --list       # 只列用例名
    python3 tools/selftest.py --case G4    # 只跑名字里含 G4 的
    python3 tools/selftest.py --keep       # 保留夹具目录，便于手工复现

退出码：0 全绿；1 有用例不对。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
# 有 --selftest 的工具要在真实工程目录里跑：en_check 的词典在 voice/lexicon.json
PROJ = REPO / "projects" / "dsh-anatomy"
PY = sys.executable

SENT1 = "这句话在第一帧里。"
SENT2 = "这句话在第二帧里。"


# ── 夹具：一个最小但合法的工程 ────────────────────────
def wav(seconds: float, rate: int = 24000) -> bytes:
    """合法的 16-bit 单声道静音 WAV。gate_chain 的时长校验只读 RIFF 头。"""
    data = b"\x00\x00" * int(rate * seconds)
    fmt = (b"fmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
           + (1).to_bytes(2, "little") + rate.to_bytes(4, "little")
           + (rate * 2).to_bytes(4, "little") + (2).to_bytes(2, "little")
           + (16).to_bytes(2, "little"))
    return (b"RIFF" + (36 + len(data)).to_bytes(4, "little") + b"WAVE"
            + fmt + b"data" + len(data).to_bytes(4, "little") + data)


def make_project(dst: Path) -> Path:
    """两帧工程：每帧 0.5s 旁白，帧时长 1.0s / 1.7s，总长 2.7s。"""
    (dst / "assets" / "voice").mkdir(parents=True)
    (dst / "generated").mkdir()
    (dst / "compositions" / "frames").mkdir(parents=True)
    (dst / "renders").mkdir()
    for ep in ("ep01", "ep02"):
        (dst / "episodes" / ep).mkdir(parents=True)
        (dst / "publish" / ep).mkdir(parents=True)

    (dst / "hyperframes.json").write_text('{"id": "selftest"}\n', encoding="utf-8")
    (dst / "SCRIPT.md").write_text(
        f"# 自测夹具\n\n## Frame 1 — 第一帧\n\n{SENT1}\n\n## Frame 2 — 第二帧\n\n{SENT2}\n",
        encoding="utf-8")
    for name in ("01-fixture.wav", "02-fixture.wav"):
        (dst / "assets" / "voice" / name).write_bytes(wav(0.5))

    takes = {"takes": [
        {"frame": 1, "title": "第一帧", "path": "assets/voice/01-fixture.wav",
         "duration_s": 0.5, "sentences": [{"text": SENT1, "start": 0.0, "end": 0.5}]},
        {"frame": 2, "title": "第二帧", "path": "assets/voice/02-fixture.wav",
         "duration_s": 0.5, "sentences": [{"text": SENT2, "start": 0.0, "end": 0.5}]},
    ]}
    (dst / "generated" / "voice_takes.json").write_text(
        json.dumps(takes, ensure_ascii=False, indent=2), encoding="utf-8")

    meta = {"bgm": None, "bgm_pending": False, "sfx": [], "voices": [
        {"frame": t["frame"], "path": t["path"], "duration_s": t["duration_s"],
         "words": [{"id": "w1", "text": t["sentences"][0]["text"], "start": 0.0, "end": 0.5}]}
        for t in takes["takes"]]}
    (dst / "generated" / "audio_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    groups = [{"id": "caption-group-0", "frame": 1, "start": 0.0, "end": 0.5, "text": SENT1,
               "words": [{"id": "caption-word-0-0", "text": SENT1, "start": 0.0,
                          "end": 0.5, "key": False}]}]
    (dst / "generated" / "caption_groups.json").write_text(
        json.dumps(groups, ensure_ascii=False, indent=2), encoding="utf-8")
    (dst / "compositions" / "captions.html").write_text(
        "<!doctype html><html><body>captions</body></html>\n", encoding="utf-8")

    (dst / "index.html").write_text(f'''<!doctype html>
<html><body>
<div id="root" data-composition-id="selftest" data-duration="2.7">
  <div class="scene" data-composition-src="compositions/frames/frame-01.html" data-start="0.0" data-duration="1.0"></div>
  <div class="scene" data-composition-src="compositions/frames/frame-02.html" data-start="1.0" data-duration="1.7"></div>
  <div class="scene" data-composition-src="compositions/captions.html" data-start="0.0" data-duration="2.7"></div>
  <audio src="assets/voice/01-fixture.wav" data-start="0.0" data-duration="0.5"></audio>
  <audio src="assets/voice/02-fixture.wav" data-start="1.0" data-duration="0.5"></audio>
</div>
</body></html>
''', encoding="utf-8")

    for n, sent in ((1, SENT1), (2, SENT2)):
        (dst / "compositions" / "frames" / f"frame-0{n}.html").write_text(f'''<!doctype html>
<html><body>
<div data-composition-id="frame-0{n}">
<script>
  const tl = gsap.timeline();
  // 0.00 {sent}
  tl.to("#x", {{opacity: 1, duration: 0.4}});
</script>
</div>
</body></html>
''', encoding="utf-8")

    for ep, bvid, dur in (("ep01", "BV1selftest", 1), ("ep02", "BV2selftest", 1)):
        (dst / "publish" / ep / "result.json").write_text(json.dumps({
            "bvid": bvid, "submitted_at": "2026-11-28T00:00:00+08:00",
            "duration_reported": dur, "state_after_submit": "开放浏览"},
            ensure_ascii=False, indent=2), encoding="utf-8")
        (dst / "renders" / f"{ep}-fixture.mp4").touch()
    (dst / "README.md").write_text('''# 夹具

## 已交付

| 集 | 成片 | 时长 | 归档 | 发布 |
|---|---|---|---|---|
| EP01 夹具 | `renders/ep01-fixture.mp4` | 0:00.5 | `episodes/ep01/` | `BV1selftest` |
| EP02 夹具 | `renders/ep02-fixture.mp4` | 0:01.0 | `episodes/ep02/` | `BV2selftest` |
''', encoding="utf-8")

    # 指纹用真实代码盖章（gen_manifest 的 REPO 指向真仓库，所以 by 必须写真实路径）
    sys.path.insert(0, str(TOOLS))
    import gen_manifest
    gen_manifest.stamp("generated/voice_takes.json", "tools/voice_build.py",
                       ["SCRIPT.md"], project=dst)
    gen_manifest.stamp("generated/audio_meta.json", "tools/timing.py",
                       ["generated/voice_takes.json"], project=dst)
    gen_manifest.stamp("generated/caption_groups.json", "tools/captions_build.py",
                       ["SCRIPT.md", "generated/audio_meta.json"], project=dst)
    gen_manifest.stamp("compositions/captions.html", "tools/captions_build.py",
                       ["SCRIPT.md", "generated/audio_meta.json"], project=dst)
    gen_manifest.stamp("index.html", "tools/index_build.py",
                       ["generated/voice_takes.json"], project=dst)
    return dst


# ── 变更动作（每个用例只改一处） ──────────────────────
def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"✗ 夹具不含 {old!r}（{path.name}）：selftest 自己写错了")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def g1(d: Path) -> None:
    edit(d / "SCRIPT.md", SENT1, "这句话被改过了。")


def g2(d: Path) -> None:
    p = d / "generated" / "audio_meta.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["voices"][0]["duration_s"] = 0.9
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def g3(d: Path) -> None:
    (d / "assets" / "voice" / "01-fixture.wav").write_bytes(wav(1.0))


def g4(d: Path) -> None:
    edit(d / "index.html", 'data-start="0.0" data-duration="1.0"',
         'data-start="0.0" data-duration="1.3"')


def g5(d: Path) -> None:
    edit(d / "index.html", 'data-start="1.0" data-duration="1.7"',
         'data-start="1.2" data-duration="1.7"')


def g6_tamper(d: Path) -> None:
    p = d / "generated" / "caption_groups.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data[0]["text"] = "手改过的字幕"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def g6_upstream(d: Path) -> None:
    p = d / "SCRIPT.md"
    p.write_text(p.read_text(encoding="utf-8") + "\n备注：改了一句没重跑。\n", encoding="utf-8")


def g7(d: Path) -> None:
    shutil.copy(d / "generated" / "voice_takes.json", d / "voice_takes.json")


def g8(d: Path) -> None:
    edit(d / "compositions" / "frames" / "frame-01.html", "// 0.00 " + SENT1,
         "// 0.40 " + SENT1)


def g8_allowlisted(d: Path) -> None:
    g8(d)
    line = next(i for i, l in enumerate(
        (d / "compositions" / "frames" / "frame-01.html").read_text(encoding="utf-8").splitlines(), 1)
        if "// 0.40" in l)
    (d / "frame-anchors-allowlist.json").write_text(json.dumps(
        {f"frame-01.html:{line}": "selftest：已记账的漂移"},
        ensure_ascii=False, indent=2), encoding="utf-8")


def poly_hard(d: Path) -> None:
    edit(d / "SCRIPT.md", SENT1, "重载这个插件。")


def poly_listen(d: Path) -> None:
    edit(d / "SCRIPT.md", SENT1, "这条接缝很细。")


def delivery_missing(d: Path) -> None:
    p = d / "README.md"
    p.write_text("\n".join(l for l in p.read_text(encoding="utf-8").splitlines()
                           if "BV1selftest" not in l) + "\n", encoding="utf-8")


def delivery_no_table(d: Path) -> None:
    p = d / "README.md"
    p.write_text("# 夹具（表被删了）\n", encoding="utf-8")


def delivery_bvid(d: Path) -> None:
    edit(d / "README.md", "`BV1selftest`", "`BV1wrong`")


# ── 用例表 ────────────────────────────────────────────
CASES: list[dict] = [
    {"name": "裸工程应全绿", "tool": ["tools/gate_chain.py"], "mutate": None,
     "exit": 0, "text": "8 条链路不变量全部成立"},
    {"name": "G1 旁白覆盖", "tool": ["tools/gate_chain.py", "--strict"], "mutate": g1,
     "exit": 1, "text": "G1"},
    {"name": "G2 新鲜度", "tool": ["tools/gate_chain.py", "--strict"], "mutate": g2,
     "exit": 1, "text": "G2"},
    {"name": "G3 音轨时长", "tool": ["tools/gate_chain.py", "--strict"], "mutate": g3,
     "exit": 1, "text": "G3"},
    {"name": "G4 帧时长", "tool": ["tools/gate_chain.py", "--strict"], "mutate": g4,
     "exit": 1, "text": "G4"},
    {"name": "G5 时间轴", "tool": ["tools/gate_chain.py", "--strict"], "mutate": g5,
     "exit": 1, "text": "G5"},
    {"name": "G6 手改生成物", "tool": ["tools/gate_chain.py", "--strict"], "mutate": g6_tamper,
     "exit": 1, "text": "被手改过"},
    {"name": "G6 上游变了没重跑", "tool": ["tools/gate_chain.py", "--strict"], "mutate": g6_upstream,
     "exit": 1, "text": "上游已变"},
    {"name": "G7 目录边界", "tool": ["tools/gate_chain.py", "--strict"], "mutate": g7,
     "exit": 1, "text": "G7"},
    {"name": "G8 帧内锚点", "tool": ["tools/gate_chain.py", "--strict"], "mutate": g8,
     "exit": 1, "text": "G8"},
    {"name": "G8 已记账的漂移放行", "tool": ["tools/frame_anchors.py"], "mutate": g8_allowlisted,
     "exit": 0, "text": "已记账"},
    {"name": "多音字：需改写", "tool": ["tools/polyphone_check.py", "--strict"], "mutate": poly_hard,
     "exit": 1, "text": "需改写"},
    {"name": "多音字：复听档不阻断", "tool": ["tools/polyphone_check.py", "--strict"],
     "mutate": poly_listen, "exit": 0, "text": "复听"},
    {"name": "交付表：已发布没列", "tool": ["tools/delivery_table.py"], "mutate": delivery_missing,
     "exit": 1, "text": "没有它"},
    {"name": "交付表：bvid 不符", "tool": ["tools/delivery_table.py"], "mutate": delivery_bvid,
     "exit": 1, "text": "bvid 不一致"},
    {"name": "交付表：整张表不见了", "tool": ["tools/delivery_table.py"],
     "mutate": delivery_no_table, "exit": 1, "text": "一行都没解析到"},
]

# 有 --selftest 的工具：直接调它自己（规则表改坏了它会红）
SELF = [
    {"name": "en_check 规则自测", "cmd": ["tools/en_check.py", "--selftest"]},
    {"name": "claim_check 规则自测", "cmd": ["tools/claim_check.py", "--selftest"]},
]


# ── 工作区级夹具（doc_facts / corrections_ledger） ────
def make_workspace(dst: Path) -> Path:
    (dst / "tools").mkdir(parents=True)
    (dst / "doc").mkdir()
    (dst / "doc" / "配音指导.md").write_text(
        "端点：http://127.0.0.1:8010/v1/audio/speech\n", encoding="utf-8")
    (dst / "doc" / "本机TTS-Qwen3.md").write_text("同上。\n", encoding="utf-8")
    (dst / "doc" / "START-EPISODE.md").write_text("同上。\n", encoding="utf-8")
    (dst / "tools" / "voice_build.py").write_text(
        'ENDPOINT = "http://127.0.0.1:8010/v1/audio/speech"\n', encoding="utf-8")
    make_ledger(dst)
    return dst


def make_ledger(dst: Path) -> Path:
    p = dst / "corrections.md"
    p.write_text("""# 纠正账本

## 账本

| 日期 | 症状 | 根因 | 固化形态 |
|---|---|---|---|
| 2026-11-28 | 好的一条 | 根因 | `G`：`tools/gate_chain.py` 已拦 |
| 2026-11-28 | 散文的一条 | 根因 | `文档`：判断力，机器判不了 |
""", encoding="utf-8")
    return p


def ws_cases(root: Path) -> list[dict]:
    def doc_bad(_d: Path) -> None:
        edit(root / "doc" / "配音指导.md", "127.0.0.1:8010",
             "100.64.0.8:3900")

    def ledger_form(form: str, symptom: str = "测试行") -> callable:
        def _mutate(_d: Path) -> None:
            p = root / "corrections.md"
            p.write_text(p.read_text(encoding="utf-8")
                         + f"| 2026-11-28 | {symptom} | 根因 | {form} |\n", encoding="utf-8")
        return _mutate

    return [
        {"name": "doc_facts 一致时绿", "cmd": [PY, "tools/doc_facts.py", "--root", str(root)],
         "mutate": None, "exit": 0, "text": "与代码一致"},
        {"name": "doc_facts 端点不符", "cmd": [PY, "tools/doc_facts.py", "--root", str(root)],
         "mutate": doc_bad, "exit": 1, "text": "以代码为准"},
        {"name": "账本：待办red", "cmd": [PY, "tools/corrections_ledger.py",
                                       "--ledger", str(root / "corrections.md")],
         "mutate": ledger_form("`待办`：以后再说"), "exit": 1, "text": "没固化"},
        {"name": "账本：空固化形态", "cmd": [PY, "tools/corrections_ledger.py",
                                         "--ledger", str(root / "corrections.md")],
         "mutate": ledger_form(""), "exit": 1, "text": "是空的"},
        {"name": "账本：假固化", "cmd": [PY, "tools/corrections_ledger.py",
                                      "--ledger", str(root / "corrections.md")],
         "mutate": ledger_form("`G`：`tools/nope.py`"), "exit": 1, "text": "假固化"},
    ]


# ── 跑 ────────────────────────────────────────────────
def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    args = sys.argv[1:]
    if "--list" in args:
        for c in CASES + SELF:
            print(f"  {c['name']}")
        for c in ws_cases(Path("/tmp/ws")):
            print(f"  {c['name']}")
        return 0

    only = None
    if "--case" in args:
        only = args[args.index("--case") + 1]
    keep = "--keep" in args
    tmp = Path(tempfile.mkdtemp(prefix="yvideo-selftest-"))
    base = make_project(tmp / "base-project")
    ws = make_workspace(tmp / "base-ws")
    failures: list[str] = []

    def wanted(name: str) -> bool:
        return only is None or only.lower() in name.lower()

    try:
        for i, case in enumerate(CASES):
            if not wanted(case["name"]):
                continue
            work = tmp / f"case{i}"
            shutil.copytree(base, work)
            if case["mutate"]:
                case["mutate"](work)
            code, out = run([PY, str(REPO / case["tool"][0]), *case["tool"][1:]], work)
            ok = code == case["exit"] and case["text"] in out
            print(f"  {'✓' if ok else '✗'} {case['name']}"
                  + ("" if ok else f" —— 期望 exit {case['exit']} 且含「{case['text']}」，"
                                   f"实得 exit {code}"))
            if not ok:
                failures.append(case["name"])
                print("    " + out.strip().replace("\n", "\n    ")[:800])

        for case in SELF:
            if not wanted(case["name"]):
                continue
            if not (REPO / case["cmd"][0]).exists():
                print(f"  · {case['name']}：没有 {case['cmd'][0]}，跳过")
                continue
            code, out = run([PY, str(REPO / case["cmd"][0]), *case["cmd"][1:]], PROJ)
            ok = code == 0
            print(f"  {'✓' if ok else '✗'} {case['name']}")
            if not ok:
                failures.append(case["name"])
                print("    " + out.strip().replace("\n", "\n    ")[:800])

        ws_root = tmp / "ws-case"
        for case in ws_cases(ws_root):
            if not wanted(case["name"]):
                continue
            if ws_root.exists():
                shutil.rmtree(ws_root)
            shutil.copytree(ws, ws_root)
            if case["mutate"]:
                case["mutate"](ws_root)
            code, out = run([c.replace("/tmp/ws", str(ws_root)) for c in case["cmd"]], REPO)
            want_text = case["text"]
            ok = code == case["exit"] and want_text in out
            print(f"  {'✓' if ok else '✗'} {case['name']}"
                  + ("" if ok else f" —— 期望 exit {case['exit']} 且含「{want_text}」，"
                                   f"实得 exit {code}"))
            if not ok:
                failures.append(case["name"])
                print("    " + out.strip().replace("\n", "\n    ")[:800])
    finally:
        if keep:
            print(f"\n  夹具保留在：{tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"✗ 闸门回归 {len(failures)} 项不通过：" + "、".join(failures))
        return 1
    print("✓ 闸门回归全部通过：每条判据都还在拦，没有一条被悄悄削弱")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
