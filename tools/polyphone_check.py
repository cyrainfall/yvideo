#!/usr/bin/env python3
"""polyphone_check.py — 旁白里的多音字/易错读音检查。

为什么需要它：本机 TTS（Qwen3-TTS Base）只吃文本，API 上没有拼音或读音门控；
ASR 侧也只会写回规范汉字，听不出 chóng/zhòng。所以「读音正确」不能靠模型自觉，
只能靠脚本里不出现歧义词 —— 这个脚本就是那道闸门。

用法：
    python3 ../../tools/polyphone_check.py            # 只报告
    python3 ../../tools/polyphone_check.py --strict   # 有「需改写」项即返回 1，可接进重建链

每条命中给出：位置、命中的词、两种读法、建议改写。

三档（这是本脚本的核心设计）：
    !  需改写   —— 可替代且读错概率高 → 硬失败（--strict 时退出 1）
    ·  提示     —— 读错概率低，或改写会伤语气 → 只报告
    ♪  复听     —— 必须用、无法改写的词（接缝 / 重写 / 重名）→ 不阻断，
                  但列入交付前复听清单；ASR 听不出声调，这一档只能靠耳朵。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# 工程目录 = 当前工作目录（一集一工程，共享这份 tools/）
ROOT = Path.cwd()
if not (ROOT / "hyperframes.json").exists():
    raise SystemExit(f"✗ 请在某一集的工程目录里运行（{ROOT} 下没有 hyperframes.json）")
SCRIPT = ROOT / "SCRIPT.md"
FRAME_RE = re.compile(r"^##\s+Frame\s+(\d+)\s*[—-]\s*(.+?)\s*$")

# 词 → (歧义说明, 建议改写)
WORDS: dict[str, tuple[str, str]] = {
    "重载": ("chóng zài（重新载入）／zhòng zài（负载很重）", "重新载入 / 热载入"),
    "重新": ("chóng xīn", "一般读对；若前文有「重」连读可改成「再次」"),
    "重复": ("chóng fù", "再次 / 一遍"),
    "重要": ("zhòng yào", "关键"),
    "重力": ("zhòng lì", "—"),
    "长大": ("zhǎng dà", "成年"),
    "长度": ("cháng dù", "—"),
    "角色": ("jué sè（角色）／jiǎo sè（角落的颜色）", "身份"),
    "银行": ("yín háng", "—"),
    "行走": ("xíng zǒu", "—"),
    "载体": ("zài tǐ", "—"),
    "下载": ("xià zài", "拉取"),
    "上传": ("shàng chuán", "—"),
    "传记": ("zhuàn jì", "—"),
    "传说": ("chuán shuō", "—"),
    "参与": ("cān yù", "—"),
    "人参": ("rén shēn", "—"),
    "将来": ("jiāng lái", "以后"),
    "将军": ("jiāng jūn", "—"),
    "教学": ("jiāo xué", "—"),
    "角度": ("jiǎo dù", "—"),
    "血液": ("xuè yè", "—"),
    "处理": ("chǔ lǐ", "—"),
    "处所": ("chù suǒ", "—"),
    "差事": ("chāi shì", "—"),
    "参差": ("cēn cī", "—"),
    "数组": ("shù zǔ", "—"),
    "数落": ("shǔ luò", "—"),
    "薄荷": ("bò he", "—"),
    "剥皮": ("bāo pí", "—"),
    "模样": ("mú yàng", "样子"),
    "尺寸": ("chǐ cùn", "—"),
    "供给": ("gōng jǐ", "—"),
    "教书": ("jiāo shū", "—"),
    "量变": ("liàng biàn", "—"),
    "片子": ("piān zi", "—"),
    "认识": ("rèn shi", "—"),
    "熟悉": ("shú xī", "—"),
    "便宜": ("pián yi", "—"),
    "澄清": ("chéng qīng", "说清"),
    "露天": ("lù tiān", "—"),
    "背包": ("bēi bāo", "—"),
    "塞车": ("sāi chē", "—"),
    "恶习": ("è xí", "—"),
    "干活": ("gàn huó", "做事"),
    "冲突": ("chōng tū", "—"),
    "冲床": ("chòng chuáng", "—"),
    "尽兴": ("jìn xìng", "—"),
    "尽快": ("jǐn kuài", "—"),
    "着急": ("zháo jí", "—"),
    "着落": ("zhuó luò", "—"),
    "露脸": ("lòu liǎn", "—"),
    "一行": ("yī háng（一行配置）／yī xíng（一行人）", "一条"),
    "一句": ("yí jù", "—"),
    "一致": ("yī zhì", "—"),
    "一般": ("yī bān", "—"),
    "一样": ("yí yàng", "同一套"),
    "不去": ("bú qù", "—"),
    "不对": ("bú duì", "—"),
    "得分": ("dé fēn", "—"),
    "为人": ("wéi rén", "—"),
    "因为": ("yīn wèi", "所以"),
    "应当": ("yīng dāng", "应该"),
    "接缝": ("jiē fèng（缝隙）／jiē féng（缝合）", "本系列必用词，无法改写 → 进复听清单"),
    "重写": ("chóng xiě（重新写）／zhòng xiě", "重做 / 再写一遍"),
    "重名": ("chóng míng（名字重复）／zhòng míng", "名字撞了"),
    "载入": ("zài rù（装载）／zǎi rù", "装载"),
}

# 只提示、不阻断的词：读错概率低，或改写会伤语气
SOFT = {"重新", "重要", "重力", "长度", "银行", "行走", "上传", "传说", "参与", "人参",
        "将军", "教学", "角度", "血液", "处所", "数组", "薄荷", "剥皮", "尺寸", "供给",
        "教书", "量变", "片子", "认识", "熟悉", "便宜", "露天", "背包", "塞车", "恶习",
        "冲突", "冲床", "尽兴", "尽快", "着急", "着落", "露脸", "一句", "一致", "一般",
        "不去", "不对", "得分", "为人", "因为", "应当", "重力", "载入", "载体", "下载"}

# 必须用、无法改写的词：不阻断，但必须进交付前的复听清单（ASR 听不出声调，只能靠耳朵）
MUST_LISTEN = {"接缝", "重写", "重名"}


def resolve_take(frame: int, word: str) -> str:
    """把命中词定位到 voice_takes.json 里的具体 take 与句内时间段，给出可直接试听的命令。"""
    try:
        takes = json.loads((ROOT / "voice_takes.json").read_text(encoding="utf-8"))["takes"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return ""
    for take in takes:
        if take.get("frame") != frame:
            continue
        for s in take.get("sentences", []):
            if word in s.get("text", ""):
                wav = take["path"]
                return (f"        {wav}  {s['start']:.2f}–{s['end']:.2f}s\n"
                        f"        {s['text']}\n"
                        f"        试听：ffmpeg -v error -y -ss {s['start']:.2f} -to {s['end']:.2f} "
                        f"-i {wav} /tmp/listen.wav && afplay /tmp/listen.wav")
    return "         （voice_takes.json 里没定位到这句：先跑 tools/voice_build.py）"


def main() -> int:
    strict = "--strict" in sys.argv
    if not SCRIPT.exists():
        print("✗ SCRIPT.md not found", file=sys.stderr)
        return 2

    hits: list[tuple[int, str, str, str, str]] = []
    frame = 0
    for lineno, line in enumerate(SCRIPT.read_text().splitlines(), 1):
        m = FRAME_RE.match(line)
        if m:
            frame = int(m.group(1))
            continue
        if line.startswith("#") or line.lstrip().startswith(("语言：", "全片", "音色：")):
            continue
        if not frame:
            continue          # 帧外是说明文字，不是旁白（与 en_check 的叙事行口径一致）
        for word, (why, fix) in WORDS.items():
            # 前面紧跟数字/量词的不算（「九十一行」里的「一行」不是量词用法）
            pat = re.compile(r"(?<![0-9一二三四五六七八九十百千万亿])" + re.escape(word))
            for _ in pat.finditer(line):
                hits.append((lineno, f"F{frame}", word, why, fix))

    if not hits:
        print("✓ 旁白没有命中多音字清单")
        return 0

    hard = [h for h in hits if h[2] not in SOFT and h[2] not in MUST_LISTEN]
    listen = [h for h in hits if h[2] in MUST_LISTEN]
    for lineno, fr, word, why, fix in hits:
        if word in MUST_LISTEN:
            level = "♪"
        elif word in SOFT:
            level = "·"
        else:
            level = "!"
        print(f"  {level} SCRIPT.md:{lineno}  {fr}  「{word}」  {why}   → 建议：{fix}")

    if listen:
        print("\n♪ 复听清单（必须用、改不了；交付前逐条听，判定靠耳朵不靠 ASR）")
        for lineno, fr, word, _why, _fix in listen:
            frame_no = int(fr[1:]) if fr.startswith("F") and fr[1:].isdigit() else 0
            print(f"\n  {fr}  「{word}」  SCRIPT.md:{lineno}")
            print(resolve_take(frame_no, word))
        print("\n    ASR 只写回规范汉字，听不出 chóng/zhòng、fèng/féng —— 这一档只能靠耳朵。")

    print(f"\n{'✗' if hard else ('♪' if listen else '⚠')} 命中 {len(hits)} 处"
          f"（需改写 {len(hard)} / 复听 {len(listen)} / 提示 {len(hits) - len(hard) - len(listen)}）")
    if strict and hard:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
