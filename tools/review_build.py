#!/usr/bin/env python3
"""review_build.py — 每集验收包（renders/<ep>-review/）：把「这一集能不能发」压成一个人 3 分钟能判完的目录。

为什么需要它：闸门能证明「自洽、没被手改、时长接得上」，但证明不了三件只能靠眼睛和耳朵的事——
画面在每一帧里到底长什么样、字幕密到读不读得完、那个多音字念对没念对。以前这些散在
`make listen` 的终端输出、`renders/` 里的成片和上一次会话的记忆里，交付时没人能一次拿全。
验收包只做一件事：把这些**本来就能生成**的东西，收进一个按集命名的目录，并记下它描述的是哪一版。

六件套 + 两份底账：
  REVIEW.md        索引：先看哪张图、账在哪、欠账是什么（人从这里进）
  snapshots/       hyperframes snapshot --review：每帧开头+中点、每个切点前后 5 帧、手机宽度
  durations.md     逐帧时长账，外加「成片实测 vs 时间轴」偏差
  captions.md      字幕全表 + 语速分布（>6 字/秒 观众读不完）
  waveform.png     音轨波形，帧边界画了竖线（找空白段、找爆音、找音画错位）
  listen.md        ♪ 复听清单（多音字只能靠耳朵）+ ASR 送检句
  checks.txt       闸门原始输出（G1–G7 + hyperframes check）
  manifest.json    它描述的是哪一版：输入文件指纹 + commit + 成片指纹

为什么记指纹：验收包最容易的死法是「改了文案、重渲了、忘了重做包，然后拿着旧图发布」。
manifest.json 让这件事可以被机器判出来（--check）。

用法（在某一集的工程目录里）：
    python3 ../../tools/review_build.py                # 建/重建
    python3 ../../tools/review_build.py --ep ep08      # 指定集号
    python3 ../../tools/review_build.py --check        # 是否还描述着当前这一版（过期返回 1）
    python3 ../../tools/review_build.py --skip-check   # 只重做图，不重跑 hyperframes check

产物落在 renders/ 下，不进 git（成片本身也是），随时可重建。
"""
from __future__ import annotations

import argparse
import atexit
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from paths import CAPTIONS as CAPTIONS_PATH
from paths import META as META_PATH
from paths import ROOT
from paths import TAKES as TAKES_PATH

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_chain import parse_index  # noqa: E402  （内部自带工程目录防护）

TOOLS = Path(__file__).resolve().parent
HF_CLI = Path(os.environ.get("HF_CLI") or
              Path.home() / ".agents/skills/hyperframes/scripts/plugin-cli.mjs")
CJK = re.compile(r"[\u4e00-\u9fff]")
LAT_RUN = re.compile(r"[A-Za-z][A-Za-z0-9'’.\-]*")


# ── 小工具 ──────────────────────────────────────────────
def sha16(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def run(cmd: list[str], timeout: int = 900) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, f"（命令失败：{e}）"


def hf(*args: str, timeout: int = 900) -> tuple[int, str]:
    return run(["node", str(HF_CLI), *args], timeout=timeout)


def hf_json(*args: str, timeout: int = 900) -> tuple[int, str, dict | None]:
    code, out = hf(*args, timeout=timeout)
    start = out.find("{")
    if start < 0:
        return code, out, None
    try:
        # CLI 在 JSON 前后还会打人类可读的行，raw_decode 只吃第一个对象
        data, _end = json.JSONDecoder().raw_decode(out[start:])
        return code, out, data
    except json.JSONDecodeError:
        return code, out, None


def ffprobe_duration(path: Path) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    code, out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "csv=p=0", str(path)], timeout=120)
    try:
        return float(out.strip().splitlines()[0])
    except (ValueError, IndexError):
        return None


def chars(text: str) -> int:
    """汉字数（总数用）。拉丁词不按字母数——`bash-local` 是一耳朵，不是十个字。"""
    return len(CJK.findall(text))


def units(text: str) -> int:
    """「音节当量」：汉字 1 个算 1，一个拉丁词也算 1（它是一口气读出来的）。

    语速必须用这个口径。按字符数算会把 `unavailable` 记成 11 个字，
    于是正常的一行被标成 8.3 字/秒 —— 那是度量错了，不是字幕太快。
    """
    return len(CJK.findall(text)) + len(LAT_RUN.findall(text))


def fmt_t(sec: float) -> str:
    m, s = divmod(max(0.0, sec), 60)
    return f"{int(m)}:{s:05.2f}"


def infer_ep() -> str | None:
    m = re.match(r"^ep(\d+)", ROOT.name)
    if m:
        return f"ep{int(m.group(1)):02d}"
    found = sorted({x.group(1) for p in (ROOT / "renders").glob("ep*-*.mp4")
                    if (x := re.match(r"^(ep\d+)", p.name))})
    return found[0] if len(found) == 1 else None


LISTEN_RE = re.compile(r"^\s*♪\s+SCRIPT\.md:\d+\s+(F\d+)\s+「(.+?)」", re.M)


def ep_title(ep: str) -> str:
    """集标题：成片文件名 → 工程目录名 → BRIEF.md 标题里的《》→ 一级标题。

    三级是为了让新建的工程（还没有成片）也不至于把「BRIEF — ep99《…》」整行当标题。
    """
    r = find_render(ep)
    if r:
        m = re.match(rf"^{re.escape(ep)}[-_](.+)$", r.stem)
        if m:
            return m.group(1)
    m = re.match(rf"^{re.escape(ep)}[-_](.+)$", ROOT.name)
    if m:
        return m.group(1)
    for name in ("BRIEF.md", "README.md"):
        f = ROOT / name
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                head = line[2:].strip()
                quoted = re.search(r"《(.+?)》", head)
                return quoted.group(1) if quoted else head
    return ""


def find_render(ep: str) -> Path | None:
    exact = ROOT / "renders" / f"{ep}.mp4"
    if exact.exists():
        return exact
    hits = sorted(p for p in (ROOT / "renders").glob(f"{ep}-*.mp4")
                  if p.is_file())
    return hits[-1] if hits else None


# ── 数据 ────────────────────────────────────────────────
def load(ep: str) -> dict:
    takes = json.loads(TAKES_PATH.read_text(encoding="utf-8"))["takes"]
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    caps = json.loads(CAPTIONS_PATH.read_text(encoding="utf-8"))
    scenes, _audios, timeline = parse_index()
    render = find_render(ep)
    return {
        "takes": takes, "meta": meta, "captions": caps,
        "scenes": scenes, "timeline_s": timeline,
        "render": render,
        "render_s": ffprobe_duration(render) if render else None,
    }


def cap_span(cap: dict) -> tuple[float, float]:
    """字幕的真实占屏区间：优先看词级时间（line 模式 words 只有一条整句）。"""
    words = cap.get("words") or []
    if words:
        return float(words[0]["start"]), float(max(w["end"] for w in words))
    return float(cap["start"]), float(cap["end"])


# ── 图 ──────────────────────────────────────────────────
def sheets_of(snap: dict) -> dict:
    """CLI 的拼图路径：新版本挂在 review.sheets 下，同时有一份扁平的 contactSheets。"""
    rev = snap.get("review") or {}
    sheets = rev.get("sheets") or {}
    if sheets:
        return {"beats": sheets.get("beats") or [], "seams": sheets.get("seams") or [],
                "phone": sheets.get("phone") or []}
    flat = snap.get("contactSheets") or []
    return {"beats": [x for x in flat if "beats" in x],
            "seams": [x for x in flat if "seam" in x],
            "phone": [x for x in flat if "phone" in x]}


def build_snapshots(out: Path) -> tuple[dict, str]:
    """hyperframes snapshot --review：每帧开头+中点、每切点 5 帧、手机宽度。失败即致命。"""
    out.mkdir(parents=True, exist_ok=True)
    last = ""
    for attempt in (1, 2):        # snapshot 起 headless Chrome，偶发失败复跑一次
        code, text, data = hf_json("snapshot", "--review", "--json", "-o", str(out))
        last = text
        if code == 0 and data and data.get("ok"):
            return data, text
        if attempt == 1:
            print(f"  · snapshot 第 1 次失败，复跑（{text.strip().splitlines()[-1][:120]}）")
    raise SystemExit(f"✗ hyperframes snapshot 失败，验收包不生成：\n{last[-800:]}")


def build_waveform(dst: Path, data: dict) -> str:
    """音轨波形；成片存在就用成片的音轨（那才是观众听到的），否则拼 take。"""
    if not shutil.which("ffmpeg"):
        return "（没有 ffmpeg，跳过波形）"
    takes = data["takes"]
    timeline = data["timeline_s"] or max(
        (s["start"] + s["dur"] for s in data["scenes"]), default=1.0)
    width, height = 1800, 280

    src = data["render"]
    if src is not None:
        base = [str(src)]
        chain = "[0:a]aformat=channel_layouts=mono"
        origin = f"成片音轨（{src.name}）"
    else:
        base = [str(ROOT / t["path"]) for t in takes if (ROOT / t["path"]).exists()]
        if not base:
            return "（没有成片也没有音轨，跳过波形）"
        ins = "".join(f"[{i}:a]" for i in range(len(base)))
        chain = f"{ins}concat=n={len(base)}:v=0:a=1,aformat=channel_layouts=mono"
        origin = "旁白 take 拼接（帧尾 pad 未含，仅供看断句与音量）"

    # 帧边界画竖线：波形能直接对上「这一段是第几帧」
    boxes = ""
    span = timeline or 1.0
    for sc in data["scenes"][1:]:
        x = int(round(min(1.0, sc["start"] / span) * (width - 2)))
        boxes += f",drawbox=x={x}:y=0:w=2:h=ih:color=white@0.35:t=fill"

    filt = f"{chain},showwavespic=s={width}x{height}:colors=#8ab4f8{boxes}[out]"
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for b in base:
        cmd += ["-i", b]
    cmd += ["-filter_complex", filt, "-map", "[out]", "-frames:v", "1", str(dst)]
    code, text = run(cmd, timeout=300)
    if code != 0 or not dst.exists():
        return f"（波形生成失败：{text.strip()[:200]}）"
    return origin


# ── 闸门快照 ────────────────────────────────────────────
def run_checks(skip: bool) -> tuple[str, str]:
    """返回 (原始输出, 状态)；状态是 ok / fail / skipped —— 跳过的绝不能记成 ok。"""
    if skip:
        return ("（本次用了 --skip-check，闸门没跑。这一版没有经过验证，不能据此发布。）\n",
                "skipped")
    parts: list[str] = []
    code, out = run([sys.executable, str(TOOLS / "gate_chain.py"), "--strict"])
    parts.append(f"$ make chain  → exit {code}\n{out}")

    # hyperframes check 已知非确定性（约 5 次红 1 次）：首次红复跑一次再判
    code, out = hf("check")
    if code != 0:
        parts.append(f"$ hyperframes check  → 首次 exit {code}（已知 flaky，复跑）\n{out}")
        code, out = hf("check")
    parts.append(f"$ hyperframes check  → exit {code}\n{out}")
    return "\n".join(parts), ("ok" if code == 0 else "fail")


# ── 账 ──────────────────────────────────────────────────
def write_durations(dst: Path, data: dict) -> None:
    takes, scenes, render_s = data["takes"], data["scenes"], data["render_s"]
    lines = ["# 逐帧时长账", "",
             "帧时长 = 旁白时长 + 0.5s（收尾帧 +1.2s）。`帧` 是时间轴上的绝对区间，",
             "`成片` 是 ffprobe 读出来的实际时长。两个数对不上，说明渲染时的时间轴不是这一版。",
             "", "| 帧 | 标题 | 句 | 字 | 旁白 s | 帧 s | 帧区间 |", "|---:|---|---:|---:|---:|---:|---|"]
    total_sent = total_char = total_dur = 0.0
    for i, t in enumerate(takes):
        sc = scenes[i] if i < len(scenes) else {"start": 0.0, "dur": t["duration_s"]}
        sent = len(t["sentences"])
        ch = sum(chars(s["text"]) for s in t["sentences"])
        total_sent += sent
        total_char += ch
        total_dur += t["duration_s"]
        lines.append(f"| {t['frame']} | {t['title']} | {sent} | {ch} | {t['duration_s']:.3f} "
                     f"| {sc['dur']:.3f} | {fmt_t(sc['start'])}–{fmt_t(sc['start'] + sc['dur'])} |")
    lines.append(f"| **合计** | {len(takes)} 帧 | {total_sent:.0f} | {total_char:.0f} "
                 f"| {total_dur:.3f} | {data['timeline_s']:.3f} | 0:00.00–{fmt_t(data['timeline_s'])} |")

    lines += ["", "## 成片对账", ""]
    if data["render"] is None:
        lines.append("- 没有成片（还没 `make render`），只能对上时间轴。")
    elif render_s is None:
        lines.append("- 成片存在，但没有 ffprobe，读不到实测时长。")
    else:
        delta = render_s - data["timeline_s"]
        verdict = "✓ 对得上" if abs(delta) <= 0.10 else "✗ 对不上：渲染用的不是这一版时间轴"
        lines += [f"- 成片：`{data['render'].name}` 实测 **{render_s:.3f}s** "
                  f"（{fmt_t(render_s)}）",
                  f"- 时间轴：**{data['timeline_s']:.3f}s**（{fmt_t(data['timeline_s'])}）",
                  f"- 偏差 {delta:+.3f}s —— {verdict}",
                  "", "偏差的合理来源是容器时间基（60fps 下 1 帧 = 0.0167s）。超过 0.1s 就不要",
                  "再用「四舍五入」解释，去查渲染时 index.html 是不是另一版。"]
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")


def caption_rows(caps: list[dict]) -> list[dict]:
    rows = []
    for i, c in enumerate(caps):
        start, end = cap_span(c)
        span = max(end - start, 0.01)
        ch = chars(c["text"])
        rows.append({"i": i, "frame": c.get("frame"), "start": start, "end": end,
                     "text": c["text"], "chars": ch, "cps": units(c["text"]) / span})
    return rows


def write_captions(dst: Path, data: dict) -> list[dict]:
    rows = caption_rows(data["captions"])
    cps = sorted(r["cps"] for r in rows)
    med = cps[len(cps) // 2] if cps else 0.0
    dense = [r for r in rows if r["cps"] >= 6.0]
    slow = [r for r in rows if r["cps"] <= 2.0]
    lines = ["# 字幕全表", "",
             f"共 **{len(rows)} 行**，语速中位数 **{med:.1f} 音节/秒**"
             f"（最低 {cps[0]:.1f} / 最高 {cps[-1]:.1f}）。",
             "", "口径：汉字 1 个算 1、**一个拉丁词也算 1**（`unavailable` 是一耳朵，不是 11 个字），"
             "区间取词级时间。", ">6 是「观众读不完」，<2 是「这一行停留过久」。", ""]
    if dense:
        lines += [f"## ✗ 过密（≥6 音节/秒，{len(dense)} 行）", ""]
        lines += [f"- F{r['frame']} {fmt_t(r['start'])} {r['cps']:.1f} 音节/秒  {r['text']}"
                  for r in dense]
        lines.append("")
    if slow:
        lines += [f"## · 过慢（≤2 音节/秒，{len(slow)} 行）", ""]
        lines += [f"- F{r['frame']} {fmt_t(r['start'])} {r['cps']:.1f} 音节/秒  {r['text']}"
                  for r in slow]
        lines.append("")
    lines += ["## 全部", "", "| # | 帧 | 起 | 止 | 汉字 | 音节/秒 | 文本 |", "|---:|---:|---|---|---:|---:|---|"]
    for r in rows:
        lines.append(f"| {r['i'] + 1} | {r['frame']} | {fmt_t(r['start'])} | {fmt_t(r['end'])} "
                     f"| {r['chars']} | {r['cps']:.1f} | {r['text']} |")
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


# ── 复听 ────────────────────────────────────────────────
def build_listen(dst: Path) -> tuple[str, int]:
    _c, poly = run([sys.executable, str(TOOLS / "polyphone_check.py")])
    _c, asr = run([sys.executable, str(TOOLS / "en_check.py"), "--list"])
    items = LISTEN_RE.findall(poly)
    n_listen = len(items)
    dst.write_text(
        "# 交付前复听清单\n\n"
        "多音字这一档**没有机器判据**：ASR 只写回规范汉字，听不出 chóng/zhòng、"
        "fèng/féng。所以这里只有一件事要做——按下面的时间段逐个听，听完在最后一行签名。\n\n"
        "## ♪ 必须用、改不了（只能靠耳朵）\n\n```\n" + poly.strip() + "\n```\n\n"
        "## 送 ASR 的句子（拉丁词读法筛子，不是判据）\n\n```\n" + asr.strip() + "\n```\n\n"
        "## 判定记录\n\n"
        "| 帧 | 词 | 听的结果 | 备注 |\n|---|---|---|---|\n"
        + ("".join(f"| {fr} | 「{w}」 | ☐ 对 ☐ 错 | |\n" for fr, w in items)
           or "| | | ☐ 对 ☐ 错 | |\n")
        + "\n> 记错的条目别只改 wav：回 `voice/读法规则.md` 加一条规则，"
          "再看能不能落成 `lexicon.json` 里的机械判据。\n",
        encoding="utf-8")
    return poly, n_listen


# ── 索引 ────────────────────────────────────────────────
GATE_LINE = {
    "ok": "✓ G1–G7 全绿，hyperframes check 通过",
    "fail": "✗ 有闸门未通过（见 checks.txt），这一版不能发",
    "skipped": "· 本次跳过了闸门（--skip-check），这一版**没有经过验证**",
}
GATE_TAIL = {
    "ok": "G1–G7 全绿 + `hyperframes check` 通过。",
    "fail": "**有失败项**，先修再发。",
    "skipped": "本次没跑（`--skip-check`），发布前必须补 `make verify`。",
}


def write_review(dst: Path, data: dict, caps_rows: list[dict], manifest: dict,
                 snap: dict, wave_note: str, check_state: str, listen_n: int,
                 checks_note: str) -> None:
    takes = data["takes"]
    sent = sum(len(t["sentences"]) for t in takes)
    ch = sum(chars(s["text"]) for t in takes for s in t["sentences"])
    sheets = sheets_of(snap) if snap else {"beats": [], "seams": [], "phone": []}
    seams = sheets["seams"]
    dense = sorted(caps_rows, key=lambda r: -r["cps"])[:5]
    total = data["timeline_s"]

    L: list[str] = [
        f"# {manifest['ep'].upper()}《{ep_title(manifest['ep'])}》验收包",
        "",
        f"> 生成 {manifest['built_at']} · `tools/review_build.py` · 基准 commit `{manifest['commit']}`",
        f"> 时间轴 **{total:.3f}s**（{fmt_t(total)}）· {len(takes)} 帧 / {sent} 句 / {ch} 汉字 / "
        f"{len(caps_rows)} 行字幕",
        f"> 闸门：{GATE_LINE[check_state]}",
        "",
        "这是**给人判**的目录，不是给机器判的。机器能判的已经在 `make verify` 里了；"
        "这里只放机器判不了的三件事：画面长什么样、字幕读不读得完、读音对不对。",
        "顺序：先看图 → 再看账 → 最后看欠账。",
        "",
        "## 1 画面",
        "",
    ]
    beats = (sheets.get("beats") or [None])[0]
    frames = (snap or {}).get("frames", [])
    n_beat = len([f for f in frames if f.get("role") == "beat"])
    n_seam = len(frames) - n_beat
    if beats:
        L += [f"每帧「开头 +0.3s」和「中点」各一张（{n_beat} 张），一张图看完：", "",
              f"![每帧开头与中点](snapshots/{Path(beats).name})", ""]
        if n_seam:
            L += [f"切点前后 5 帧另有 {n_seam} 张（下面 {len(seams)} 条）。", ""]
    if seams:
        L += ["**切点**——每个切点前后 5 帧连成一条，查跳变、黑闪、错位：", ""]
        L += [f"- [{Path(s).name}](snapshots/{Path(s).name})" for s in seams] + [""]
    phone = (sheets.get("phone") or [None])[0]
    if phone:
        L += ["**缩到 360px 宽**——手机上大概就这么大，查「还认得出、还读得清」"
              "（不是重排后的手机版式）：", "",
              f"![360px 宽](snapshots/{Path(phone).name})", ""]
    L += ["单帧原图在 `snapshots/*.png`（`beat-NN-*` 是帧级，`seam-NN-*` 是切点级）。", ""]

    L += ["## 2 时长账", "",
          f"逐帧明细在 [durations.md](durations.md)。合计旁白 {sum(t['duration_s'] for t in takes):.3f}s，"
          f"帧总长 {total:.3f}s（每帧垫 0.5s，收尾 1.2s）。", ""]
    if data["render"] and data["render_s"]:
        d = data["render_s"] - total
        L.append(f"成片实测 **{data['render_s']:.3f}s**，偏差 {d:+.3f}s —— "
                 f"{'✓ 对得上' if abs(d) <= 0.10 else '✗ 渲染用的不是这一版时间轴'}。")
    else:
        L.append("还没有成片（`make render` 之后重做本包，这一行会有实测值）。")
    L.append("")

    L += ["## 3 字幕账", "",
          f"全 {len(caps_rows)} 行在 [captions.md](captions.md)。最密的几行贴在这里，"
          "读一遍就知道会不会读不完：", "",
          "| 帧 | 起 | 音节/秒 | 文本 |", "|---:|---|---:|---|"]
    L += [f"| {r['frame']} | {fmt_t(r['start'])} | {r['cps']:.1f} | {r['text']} |" for r in dense]
    L.append("")

    L += ["## 4 声音账", "",
          f"![音轨波形](waveform.png)", "",
          f"横轴 = 全片 0–{fmt_t(total)}，竖线是帧边界。来源：{wave_note}。", "",
          f"要复听的 **{listen_n}** 条在 [listen.md](listen.md)（多音字只能靠耳朵，没有机器判据）。", ""]

    L += ["## 5 闸门快照", "",
          "原始输出在 [checks.txt](checks.txt)：" + GATE_TAIL[check_state], ""]

    L += ["## 6 已知欠账", ""]
    debts: list[str] = []
    if listen_n:
        debts.append(f"♪ 复听 {listen_n} 条未由机器判定（多音字声调）——见 listen.md")
    if not (data["render"]):
        debts.append("没有成片：画面与音轨的核对只到合成层，没到编码后的成片")
    dense_n = len([r for r in caps_rows if r["cps"] >= 6.0])
    debts.append(f"字幕语速 ≥6 音节/秒 {dense_n} 行（读一遍判是否可接受）" if dense_n
                 else "字幕语速全部在 6 音节/秒以内")
    if checks_note:
        debts.append(checks_note)
    L += [f"- {d}" for d in debts] + [""]
    L += ["## 这个包描述的是哪一版", "",
          "`manifest.json` 记了输入文件指纹、commit 和成片指纹。改了文案或重渲成片之后，",
          "`python3 ../../tools/review_build.py --check` 会告诉你这个包已经过期；", "",
          f"```bash\nmake review   # 重建（约 40s，含 hyperframes check）\n```", ""]
    dst.write_text("\n".join(L) + "\n", encoding="utf-8")


# ── manifest / 过期判定 ──────────────────────────────────
INPUTS = ["SCRIPT.md", "generated/voice_takes.json", "generated/audio_meta.json",
          "generated/caption_groups.json", "index.html", "compositions/captions.html"]


def build_manifest(ep: str, data: dict) -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = "?"
    render = data["render"]
    return {
        "version": 1,
        "ep": ep,
        "built_at": dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z"),
        "commit": commit or "?",
        "tool_sha": sha16(Path(__file__)),
        "inputs": {i: sha16(ROOT / i) for i in INPUTS if (ROOT / i).exists()},
        "timeline_s": round(data["timeline_s"], 3),
        "render": ({"path": str(render.relative_to(ROOT)), "sha16": sha16(render),
                    "duration_s": (round(data["render_s"], 3) if data["render_s"] else None)}
                   if render else None),
        "counts": {"frames": len(data["takes"]),
                   "sentences": sum(len(t["sentences"]) for t in data["takes"]),
                   "captions": len(data["captions"])},
    }


def do_check(ep: str) -> int:
    out = ROOT / "renders" / f"{ep}-review"
    mf = out / "manifest.json"
    if not mf.exists():
        print(f"· 还没有 {ep} 的验收包（`make review` 生成），跳过")
        return 0
    try:
        old = json.loads(mf.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"✗ {mf.relative_to(ROOT)} 不是合法 JSON，重建")
        return 1
    stale: list[str] = []
    for rel, want in old.get("inputs", {}).items():
        p = ROOT / rel
        if not p.exists():
            stale.append(f"{rel} 不见了")
        elif sha16(p) != want:
            stale.append(f"{rel} 已变")
    render = old.get("render")
    if render:
        p = ROOT / render["path"]
        if not p.exists():
            stale.append(f"{render['path']} 不见了")
        elif sha16(p) != render["sha16"]:
            stale.append(f"{render['path']} 已重渲")
    elif find_render(ep) is not None:
        stale.append(f"成片已出现（{find_render(ep).name}），验收包是渲染前做的")
    if stale:
        print(f"✗ {ep} 验收包已过期：{', '.join(stale)}")
        print(f"  它描述的是 {old.get('built_at')} 那一版；重做：make review")
        return 1
    print(f"✓ {ep} 验收包与当前一版一致（{old.get('built_at')}，"
          f"{old.get('counts', {}).get('frames')} 帧）")
    return 0


# ── 主流程 ──────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--ep", default=None, help="集号（默认按目录名或 renders/ 推断）")
    ap.add_argument("--check", action="store_true", help="只判过期，不重建")
    ap.add_argument("--skip-check", action="store_true", help="跳过 hyperframes check")
    args = ap.parse_args()

    ep = args.ep or infer_ep()
    if not ep:
        print("✗ 推断不出集号：用 --ep ep07 指定（renders/ 里没有唯一的 epNN-*.mp4）",
              file=sys.stderr)
        return 2
    if not ep.startswith("ep"):
        ep = f"ep{int(ep):02d}" if ep.isdigit() else ep
    if args.check:
        return do_check(ep)

    for f in ("generated/voice_takes.json", "generated/audio_meta.json",
              "generated/caption_groups.json"):
        if not (ROOT / f).exists():
            print(f"✗ 缺 {f}：先 make narrate && make captions", file=sys.stderr)
            return 2

    data = load(ep)
    (ROOT / "renders").mkdir(exist_ok=True)   # 新工程第一次交付时可能还没有 renders/
    out = ROOT / "renders" / f"{ep}-review"
    tmp = Path(tempfile.mkdtemp(prefix=f".{ep}-review.", dir=str(ROOT / "renders")))
    # 中途失败（snapshot 超时、check 崩）不要留下半成品临时目录：rename 成功后它已不存在
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    print(f"── 验收包 {ep} → {out.relative_to(ROOT)}/")

    print("   · 抽帧（hyperframes snapshot --review）")
    snap, _raw = build_snapshots(tmp / "snapshots")
    frames_n = len(snap.get("frames", []))
    sh = sheets_of(snap)
    print(f"     {frames_n} 张静帧 + {len(sh['seams'])} 条切点条 + "
          f"{1 if sh['beats'] else 0} 张总览 + {1 if sh['phone'] else 0} 张手机宽度")

    print("   · 波形")
    wave_note = build_waveform(tmp / "waveform.png", data)

    print("   · 闸门快照")
    checks_text, check_state = run_checks(args.skip_check)
    (tmp / "checks.txt").write_text(checks_text, encoding="utf-8")

    print("   · 账：时长 / 字幕 / 复听")
    write_durations(tmp / "durations.md", data)
    caps_rows = write_captions(tmp / "captions.md", data)
    _poly, listen_n = build_listen(tmp / "listen.md")

    manifest = build_manifest(ep, data)
    note = {"ok": "", "fail": "`hyperframes check` 未通过（已复跑一次），见 checks.txt",
            "skipped": "本次 --skip-check：闸门没跑，这一版没经过验证"}[check_state]
    write_review(tmp / "REVIEW.md", data, caps_rows, manifest, snap, wave_note,
                 check_state, listen_n, note)
    (tmp / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if out.exists():
        shutil.rmtree(out)
    tmp.rename(out)

    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"\n✓ {out.relative_to(ROOT)}/  {size / 1e6:.1f} MB")
    print(f"  入口：{out.relative_to(ROOT)}/REVIEW.md")
    print(f"  描述：{manifest['counts']['frames']} 帧 / {manifest['counts']['sentences']} 句 / "
          f"{manifest['counts']['captions']} 行字幕，commit {manifest['commit']}")
    if check_state == "fail":
        print("\n✗ hyperframes check 未通过——验收包已生成，但这一版不能发（先修 checks.txt 里的红）")
        return 1
    if check_state == "skipped":
        print("\n· 本次跳过了闸门：这个包只能当图看，发布前先 make verify")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
