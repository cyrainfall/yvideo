#!/usr/bin/env python3
"""en_check.py — 旁白里英文标识符的发音闸门。

为什么需要它：Qwen3-TTS 只吃文本，没有音素/词典覆盖；下划线会被读成含糊连读
（实测 install_bundle → "InstallFumble"、node_modules → "Node Madules"、
remove_bundle → "Remove Bumble"），而 tools/polyphone_check.py 只管中文多音字。

两层：
  1. 静态闸门（默认，零成本，接在重建链里）：扫描 SCRIPT.md 的旁白行。
     规则来自 voice/lexicon.json（机器可读版 voice/读法规则.md）：
       R1 下划线标识符                → 硬失败（install_bundle → install bundle）
       R2 屏上写法原样出现            → 硬失败（ctx → C T X / PENDING → pending）
       R3 驼峰                        → 硬失败（browserUse → browser use）
       R4 连续 3+ 大写字母            → 提示（PENDING 会被拼读成 pinned in ding ding）
       R5 点号标识符                  → 硬失败（ctx.get → C T X 点 get）
       R6 一句内逐字母缩写 > 2 个      → 提示（会读成串字母）
     实测读得清的写法在 lexicon.json 的 spoken_ok 里。
  2. ASR 冒烟（交付前跑，--asr）：
     对 voice_takes.json 里含拉丁词的句子切片转写（本机 whisper-cli），
     把期望词与转写词做词级比对，打印没对上的词供复听。

用法：
    python3 ../../tools/en_check.py                  # 静态检查（重建链用）
    python3 ../../tools/en_check.py --strict         # 静态检查，命中即退出 1
    python3 ../../tools/en_check.py --asr            # 静态 + ASR 报告（交付前）
    python3 ../../tools/en_check.py --asr --strict-asr   # ASR 也当作闸门
    python3 ../../tools/en_check.py --list           # 列出会被 ASR 检查的句子
    python3 ../../tools/en_check.py --selftest       # 校验规则本身（回归用）

退出码：0 通过；1 命中（--strict / --strict-asr）；2 缺 whisper 或模型；
        3 voice_takes.json 比 SCRIPT.md 旧（先跑 voice_build.py）。
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# 工程目录 = 当前工作目录（一集一工程，共享这份 tools/）
ROOT = Path.cwd()
if not (ROOT / "hyperframes.json").exists():
    raise SystemExit(f"✗ 请在某一集的工程目录里运行（{ROOT} 下没有 hyperframes.json）")
TAKES = ROOT / "voice_takes.json"
SCRIPT = ROOT / "SCRIPT.md"
LEXICON = ROOT / "voice" / "lexicon.json"
# ASR 只当筛子，但筛子本身要够密：优先 large-v3-turbo（本机已有），退化到 base
MODEL_CANDIDATES = [
    Path.home() / ".cache" / "whisper.cpp" / "models" / "ggml-large-v3-turbo-q5_0.bin",
    Path.home() / ".cache" / "whisper" / "ggml-large-v3-turbo.bin",
    Path.home() / ".cache" / "whisper" / "ggml-base.bin",
]

LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[._/\-][A-Za-z0-9]+)*")
SPLIT = re.compile(r"[._/\-]+")
CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
TRANSCRIPT_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9'’]*")
FRAME_RE = re.compile(r"^##\s+Frame\s+(\d+)\s*[—-]\s*(.+?)\s*$")

# 实测读得清的下划线写法；其余下划线一律要求改写成空格口语形态
UNDERSCORE_OK = {"plugin_manager"}

# ── 读法词典（voice/lexicon.json） ────────────────────────────
SPOKEN: dict[str, str] = {}      # 屏上写法 → 口播写法
DOTTED: dict[str, str] = {}      # 点号写法 → 口播写法
SPOKEN_OK: set[str] = set()      # 实测正常、放行的写法

CAMEL_TOKEN = re.compile(r"(?<![A-Za-z0-9_])[a-z][a-z0-9]*[A-Z][A-Za-z0-9]*")
DOTTED_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_\-]*\.[A-Za-z][A-Za-z0-9_\-]*")
ALLCAPS_TOKEN = re.compile(r"(?<![A-Za-z0-9_])[A-Z]{3,}(?![A-Za-z0-9_])")
SPELLED_ABBR = re.compile(r"(?<![A-Za-z])(?:[A-Z]\s+){2,}[A-Z](?![A-Za-z])")


def load_lexicon(path: Path = LEXICON) -> bool:
    """读 lexicon.json；缺文件时退化为只查下划线（老行为）。"""
    global SPOKEN, DOTTED, SPOKEN_OK
    if not path.exists():
        SPOKEN, DOTTED, SPOKEN_OK = {}, {}, set()
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    SPOKEN = dict(data.get("spoken", {}))
    DOTTED = dict(data.get("dotted", {}))
    SPOKEN_OK = set(data.get("spoken_ok", []))
    return True


def _boundary(key: str) -> re.Pattern[str]:
    flags = re.IGNORECASE if key.islower() else 0
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(key) + r"(?![A-Za-z0-9_])", flags)


def _split_camel(token: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", token).lower()


def speech_hits(text: str) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """按 lexicon 规则扫一句旁白。返回 (硬失败, 提示)，每项 (规则号, 命中词, 建议写法)。"""
    hard: list[tuple[str, str, str]] = []
    soft: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    # R2 屏上写法原样出现
    for key, fix in SPOKEN.items():
        for m in _boundary(key).finditer(text):
            surface = m.group(0)
            if surface in SPOKEN_OK or surface in seen:
                continue
            seen.add(surface)
            hard.append(("R2", surface, fix))

    # R5 点号标识符（先查词典，再查通用形态）
    for key, fix in DOTTED.items():
        for m in _boundary(key).finditer(text):
            surface = m.group(0)
            if surface in seen:
                continue
            seen.add(surface)
            hard.append(("R5", surface, fix))
    for m in DOTTED_TOKEN.finditer(text):
        surface = m.group(0)
        if surface in seen or surface in SPOKEN_OK:
            continue
        seen.add(surface)
        hard.append(("R5", surface, surface.replace(".", " 点 ")))

    # R3 驼峰
    for m in CAMEL_TOKEN.finditer(text):
        surface = m.group(0)
        if surface in SPOKEN_OK or surface in seen:
            continue
        seen.add(surface)
        hard.append(("R3", surface, _split_camel(surface)))

    # R4 连续大写（提示，不阻断：API 这类 3 字母缩写通常读得对）
    for m in ALLCAPS_TOKEN.finditer(text):
        surface = m.group(0)
        if surface in SPOKEN_OK or surface in seen:
            continue
        seen.add(surface)
        soft.append(("R4", surface, "改成小写，或逐字母空格分开"))

    # R6 一句里逐字母缩写太多（提示）
    groups = SPELLED_ABBR.findall(text)
    if len(groups) > 2:
        soft.append(("R6", f"{len(groups)} 处", "拆成两句，一句不超过两个缩写"))
    return hard, soft


# 已知的、可接受的同音/近音写法（ASR 侧常见）
ALIASES: dict[str, set[str]] = {
    "json": {"jason", "eason", "jayson"},
    "ctx": {"ktx", "context"},
    "plugin": {"plugging", "plug"},
    "dsh": {"deesh"},
    "yml": {"uml", "umo", "yaml"},
}
# 短词（≤3 字母）只接受精确匹配或别名：ASR 对 id / dsh / yml 这类词太不稳
SHORT = 3
# 词级模糊阈值：低于它才算「读歪了」；ASR 自身的拼写误差常在 0.6 以上
FUZZY = 0.6


def words_of(text: str) -> list[str]:
    out: list[str] = []
    for run in LATIN_RUN.findall(text):
        for part in SPLIT.split(run):
            for piece in CAMEL.split(part):
                piece = piece.strip("-_/.")
                if piece:
                    out.append(piece.lower())
    return out


def transcript_words(text: str) -> list[str]:
    return [w.lower() for w in TRANSCRIPT_LATIN.findall(text)]


def matches(expected: str, seen: list[str]) -> tuple[bool, str]:
    """期望词是否被转写覆盖；返回 (是否匹配, 最接近的转写词)。"""
    if expected in seen:
        return True, expected
    for alias in ALIASES.get(expected, ()):
        if alias in seen:
            return True, alias
    if len(expected) <= SHORT:
        return False, ""
    best, ratio = "", 0.0
    for word in seen:
        r = difflib.SequenceMatcher(None, expected, word).ratio()
        if r > ratio:
            best, ratio = word, r
    return ratio >= FUZZY, best


def underscore_hits(text: str) -> list[str]:
    """旁白里出现的、不在白名单里的下划线标识符。"""
    hits: list[str] = []
    for run in LATIN_RUN.findall(text):
        if "_" not in run:
            continue
        if run.lower() in UNDERSCORE_OK:
            continue
        hits.append(run)
    return hits


def narration_lines() -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    frame = 0
    for line in SCRIPT.read_text().splitlines():
        m = FRAME_RE.match(line)
        if m:
            frame = int(m.group(1))
            continue
        if line.startswith("#"):
            frame = 0
            continue
        text = line.strip()
        if frame and text and not text.startswith(("语言：", "全片", "音色：")):
            out.append((frame, text))
    return out


def stale() -> bool:
    try:
        return TAKES.stat().st_mtime + 1 < SCRIPT.stat().st_mtime
    except FileNotFoundError:
        return False


def whisper_bin() -> str | None:
    return os.environ.get("EN_CHECK_WHISPER") or shutil.which("whisper-cli")


def model_path() -> Path | None:
    env = os.environ.get("EN_CHECK_MODEL")
    if env:
        p = Path(env).expanduser()
        return p if p.exists() else None
    for cand in MODEL_CANDIDATES:
        if cand.exists():
            return cand
    return None


def transcribe(binary: str, model: Path, audio: Path, workdir: Path) -> str:
    # whisper-cli 写 <of>.txt，所以 -of 给不带后缀的路径
    out = workdir / audio.stem
    proc = subprocess.run(
        [binary, "-m", str(model), "-l", "auto", "-nt", "-otxt", "-of", str(out), str(audio)],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    txt = workdir / (audio.stem + ".txt")
    if proc.returncode != 0 and proc.stderr:
        print(f"    ! whisper 失败：{proc.stderr.strip().splitlines()[-1][:200]}", file=sys.stderr)
    return txt.read_text(encoding="utf-8", errors="replace").strip() if txt.exists() else ""


def static_check(strict: bool) -> int:
    has_lexicon = load_lexicon()

    under: list[tuple[int, str, list[str]]] = []
    hard: list[tuple[int, str, str, str, str]] = []
    soft: list[tuple[int, str, str, str, str]] = []

    for frame, text in narration_lines():
        u = underscore_hits(text)
        if u:
            under.append((frame, text, u))
        h, s = speech_hits(text)
        for rule, token, fix in h:
            hard.append((frame, text, rule, token, fix))
        for rule, token, fix in s:
            soft.append((frame, text, rule, token, fix))

    if not (under or hard or soft):
        note = "" if has_lexicon else "（未找到 voice/lexicon.json，只查了下划线）"
        print(f"✓ 旁白读法全部通过{note}")
        return 0

    if under:
        print("✗ R1 下划线标识符（会被读成含糊连读）")
        for frame, text, tokens in under:
            print(f"  F{frame}  {', '.join(tokens)}")
            print(f"      {text}")
        print()

    if hard:
        print("✗ 读法硬失败（改 SCRIPT.md 的口播写法；屏幕与字幕保留真名）")
        for frame, text, rule, token, fix in hard:
            print(f"  F{frame}  [{rule}] {token}  →  {fix}")
            print(f"      {text}")
        print()

    if soft:
        print("· 提示（不阻断，交付前扫一眼）")
        for frame, _text, rule, token, fix in soft:
            print(f"  F{frame}  [{rule}] {token}  →  {fix}")
        print()

    print("规则来源：voice/lexicon.json（人读版 voice/读法规则.md）")
    print("      下划线一律改空格口语形态；屏上写法的口播形态见词典的 spoken 表。")
    return 1 if (strict and (under or hard)) else 0


def asr_check(strict: bool, ignore: set[str], only_list: bool) -> int:
    if not TAKES.exists():
        print("✗ 没有 voice_takes.json：先跑 python3 ../../tools/voice_build.py", file=sys.stderr)
        return 1
    if stale():
        print("✗ voice_takes.json 比 SCRIPT.md 旧：先重跑 python3 ../../tools/voice_build.py", file=sys.stderr)
        return 3

    takes = json.loads(TAKES.read_text())["takes"]
    jobs = []
    for take in takes:
        for s in take["sentences"]:
            if LATIN_RUN.search(s["text"]):
                jobs.append((take["frame"], take["path"], s["text"], s["start"], s["end"]))
    if not jobs:
        print("✓ 旁白里没有拉丁词，跳过 ASR")
        return 0
    if only_list:
        for frame, _, text, *_ in jobs:
            print(f"  F{frame}  {text}")
        print(f"  —— {len(jobs)} 句含拉丁词")
        return 0

    binary, model = whisper_bin(), model_path()
    if binary is None or model is None:
        print("! 缺 whisper-cli 或 whisper 模型，跳过 ASR（静态检查仍然有效）", file=sys.stderr)
        return 2 if strict else 0

    bad: list[tuple[int, str, list[tuple[str, str]]]] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        for idx, (frame, path, text, start, end) in enumerate(jobs, 1):
            expected = [w for w in words_of(text) if w not in ignore]
            if not expected:
                continue
            clip = tmpdir / f"s{idx:02d}.wav"
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, start - 0.08):.3f}",
                 "-to", f"{end + 0.08:.3f}", "-i", str(ROOT / path),
                 "-ar", "16000", "-ac", "1", str(clip)],
                check=True,
            )
            heard = transcribe(binary, model, clip, tmpdir)
            seen = transcript_words(heard)
            missing = []
            for word in expected:
                if len(word) <= SHORT:
                    continue  # id / dsh / yml 这种短词 ASR 经常直接丢，不作为证据
                ok, near = matches(word, seen)
                if not ok:
                    missing.append((word, near))
            if missing:
                bad.append((frame, text, missing))
                print(f"  ✗ F{frame}  {text}")
                print("      没对上：" + "，".join(f"{w}（听到 {n or '—'}）" for w, n in missing))
                print(f"      转写：{heard}")
            else:
                print(f"  ✓ F{frame}  {text}")

    print()
    if bad:
        print(f"✗ {len(bad)} 句进了复听清单（ASR 只是筛子：base 模型会把 command 听成 Comment、")
        print("  把 id 听成 Add，所以这里只挑可疑句，判定要靠耳朵）：")
        for frame, text, missing in bad:
            print(f"    F{frame}  {text}")
        print("    误判可用 --ignore 词 放行；确属读歪就改成空格口语形态后重配。")
        return 1 if strict else 0
    print(f"✓ {len(jobs)} 句含拉丁词的旁白全部对上")
    return 0


def selftest() -> int:
    load_lexicon()
    failures: list[str] = []

    under_cases = {
        "包进 node_modules，patch 插一条。": ["node_modules"],
        "plugin_manager 的 install_bundle。": ["install_bundle"],
        "remove_bundle，也是 applied。": ["remove_bundle"],
        "是 plugin_manager 的 install bundle。": [],          # 白名单放行
    }
    for text, want in under_cases.items():
        got = underscore_hits(text)
        if got != want:
            failures.append(f"R1 {text!r}: want {want}, got {got}")

    # 必须拦住的读法错误：文本 → 期望命中的规则号
    bad_cases = {
        "它拥有 ctx 这个键。": "R2",
        "写 ctx.get 取值。": "R5",
        "用 setTimeout 先顶着。": "R3",
        "状态一直是 PENDING。": "R2",
        "连 cordis 都没有。": "R2",
    }
    for text, rule in bad_cases.items():
        hard, _ = speech_hits(text)
        if not any(r == rule for r, *_ in hard):
            failures.append(f"{rule} 未拦住 {text!r}（实得 {hard}）")

    # 必须放行的正确写法（EP07 实际口播）
    good_cases = [
        "包叫 D S H shell，它拥有 C T X 点 shell 这个键。",
        "最后是 C O R D I S 的规矩。",
        "沙箱那个多要两个缝：inject 里写着 sub process、sandbox、sandbox policy。",
        "插件停在 pending。",
        "本地那个继承的是 Shell 执行器。",
        "bash-local 只在 dev dependencies。",
    ]
    for text in good_cases:
        hard, _ = speech_hits(text)
        if hard:
            failures.append(f"误报 {text!r}: {hard}")

    if failures:
        for f in failures:
            print(f"  ✗ {f}")
        return 1
    print(f"✓ selftest 通过：下划线 / 读法硬规则 / 放行白名单（词典 {len(SPOKEN)} 条）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="静态命中即返回 1")
    ap.add_argument("--asr", action="store_true", help="额外跑 ASR 冒烟")
    ap.add_argument("--strict-asr", action="store_true", help="ASR 不匹配即返回 1（隐含 --asr）")
    ap.add_argument("--list", action="store_true", help="只列出会被 ASR 检查的句子")
    ap.add_argument("--ignore", default="", help="逗号分隔的 ASR 放行词")
    ap.add_argument("--selftest", action="store_true", help="校验规则本身")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    code = static_check(args.strict)
    if args.asr or args.strict_asr or args.list:
        ignore = {w.strip().lower() for w in args.ignore.split(",") if w.strip()}
        asr = asr_check(args.strict_asr, ignore, args.list)
        if asr:
            code = asr
    return code


if __name__ == "__main__":
    raise SystemExit(main())
