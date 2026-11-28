#!/usr/bin/env python3
"""gate_chain.py — 重建链的完整性闸门（G1–G8）。

为什么需要它：这几个不变量以前只写在 README 的散文里——「改一句文案也要从 1 重跑到 3」、
「帧时长 = 旁白时长 + 0.5s」、「改旁白要同步 data-start」。散文的约束等于没有约束：
漏跑一步不会有任何东西报错，只会得到一版字幕整体错位的成片。

八条不变量（全部确定性、零依赖、秒级）：
  G1 旁白覆盖   SCRIPT.md 每帧的句子 == voice_takes.json 每帧的句子（顺序、文本）
  G2 新鲜度     audio_meta.json 与 voice_takes.json 内容一致（漏跑 timing.py 会错位）
                 —— 比内容不比 mtime：时间戳会被 checkout / cp 改新，内容不会
  G3 音轨       take 的 wav 存在，真实时长 == 记录时长（±0.02s）
  G4 帧时长     index.html 每帧 data-duration == 旁白时长 + 0.5s（收尾帧 +1.2s）
  G5 时间轴     帧起点首尾相接、无空隙无重叠，root 总长 == 末帧终点
  G6 指纹       生成物确实由脚本产生、且未被手改（见 gen_manifest.py）
  G7 目录边界   生成物在 generated/ 下，工程根没有旧布局残留（见 tools/paths.py）
  G8 帧内锚点   frame-NN.html 里的"第几秒：这句话"注释仍对得上旁白（见 frame_anchors.py）

用法：
    python3 ../../tools/gate_chain.py            # 报告
    python3 ../../tools/gate_chain.py --strict   # 任一失败即返回 1（接进 make verify）

退出码：0 通过；1 有失败（--strict）；2 缺关键文件。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from gen_manifest import verify as verify_stamps

# 工程目录 = 当前工作目录（一集一工程，共享这份 tools/）
from frame_anchors import check as check_frame_anchors
from paths import INDEX, LEGACY, META, ROOT, SCRIPT, TAKES

FRAME_RE = re.compile(r"^##\s+Frame\s+(\d+)\s*[—-]\s*(.+?)\s*$")
SKIP_PREFIX = ("语言：", "全片", "音色：", "分句写成")
TOL = 0.02          # 秒；html 里是 3 位小数，留足舍入余量
GAP_TOL = 0.002     # 时间轴首尾相接的容差

SCENE_RE = re.compile(
    r'class="scene"[^>]*data-composition-src="(?P<src>[^"]+)"'
    r'[^>]*data-start="(?P<start>[\d.]+)"[^>]*data-duration="(?P<dur>[\d.]+)"')
AUDIO_RE = re.compile(
    r'<audio[^>]*src="(?P<src>[^"]+)"[^>]*data-start="(?P<start>[\d.]+)"'
    r'[^>]*data-duration="(?P<dur>[\d.]+)"')
ROOT_DUR_RE = re.compile(r'id="root"[^>]*data-duration="([\d.]+)"')


def script_frames() -> dict[int, list[str]]:
    """SCRIPT.md → {帧号: [句子, ...]}（一行一句，与 voice_build 的切分约定一致）。"""
    frames: dict[int, list[str]] = {}
    cur = 0
    for line in SCRIPT.read_text(encoding="utf-8").splitlines():
        m = FRAME_RE.match(line)
        if m:
            cur = int(m.group(1))
            frames[cur] = []
            continue
        if line.startswith("#"):
            cur = 0
            continue
        text = line.strip()
        if cur and text and not text.startswith(SKIP_PREFIX):
            frames[cur].append(text)
    return frames


def wav_duration(path: Path) -> float:
    """读 WAV 头算时长（不依赖 ffprobe，PCM 足够）。"""
    with path.open("rb") as f:
        head = f.read(12)
        if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
            raise ValueError(f"{path.name} 不是 WAV")
        byte_rate = 0
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                raise ValueError(f"{path.name} 缺少 data 块")
            cid, size = hdr[:4], int.from_bytes(hdr[4:8], "little")
            if cid == b"fmt ":
                fmt = f.read(size)
                byte_rate = int.from_bytes(fmt[8:12], "little")
                if size & 1:
                    f.seek(1, 1)
            elif cid == b"data":
                if not byte_rate:
                    raise ValueError(f"{path.name} 缺 fmt 块")
                return size / byte_rate
            else:
                f.seek(size + (size & 1), 1)


def check_g1(frames: dict[int, list[str]], takes: list[dict]) -> list[str]:
    errs: list[str] = []
    by_frame = {t["frame"]: t for t in takes}
    for fno, sents in sorted(frames.items()):
        take = by_frame.get(fno)
        if take is None:
            errs.append(f"G1 F{fno}: 没有对应 take（先跑 tools/voice_build.py）")
            continue
        got = [s["text"] for s in take["sentences"]]
        if got == sents:
            continue
        if len(got) != len(sents):
            errs.append(f"G1 F{fno}: 脚本 {len(sents)} 句 vs take {len(got)} 句")
        for i, (a, b) in enumerate(zip(sents, got)):
            if a != b:
                errs.append(f"G1 F{fno} 第{i + 1}句不一致\n      脚本: {a}\n      take: {b}")
                break
    extra = set(by_frame) - set(frames)
    for fno in sorted(extra):
        errs.append(f"G1 F{fno}: take 里有、脚本里没有")
    return errs


def check_g2(takes: list[dict], meta: dict) -> list[str]:
    """audio_meta 是否跟得上 voice_takes —— 按内容判，不看 mtime。

    旧版比较两者 mtime，这既会误报（git checkout / cp 把时间戳改新、内容没变）
    也会漏报（cp -p 保留旧时间戳）。判据改成内容投影：(帧号, 音轨路径, 时长)。
    「生成器改了但没重跑」这一层由 G6 的 tool_sha 提示兜住，不需要时钟参与。
    """
    errs: list[str] = []
    voices = meta.get("voices", [])
    mf = [v["frame"] for v in voices]
    tf = [t["frame"] for t in takes]
    if mf != tf:
        errs.append(f"G2 audio_meta 帧号 {mf} 与 voice_takes {tf} 不一致："
                    f"漏跑 tools/timing.py")
        return errs
    for v, t in zip(voices, takes):
        if v.get("path") != t["path"]:
            errs.append(f"G2 F{t['frame']}: audio_meta 音轨 {v.get('path')} "
                        f"≠ voice_takes {t['path']}：漏跑 tools/timing.py")
        elif abs(float(v.get("duration_s", 0)) - t["duration_s"]) > TOL:
            errs.append(f"G2 F{t['frame']}: audio_meta 时长 {v.get('duration_s')}s "
                        f"≠ 旁白 {t['duration_s']:.3f}s：漏跑 tools/timing.py"
                        f"（字幕会整体错位）")
    return errs


def check_g3(takes: list[dict]) -> list[str]:
    errs: list[str] = []
    for t in takes:
        wav = ROOT / t["path"]
        if not wav.exists():
            errs.append(f"G3 F{t['frame']}: 缺音轨 {t['path']}")
            continue
        try:
            real = wav_duration(wav)
        except (ValueError, OSError) as e:
            errs.append(f"G3 F{t['frame']}: {e}")
            continue
        if abs(real - t["duration_s"]) > TOL:
            errs.append(f"G3 F{t['frame']}: wav 实际 {real:.3f}s vs 记录 "
                        f"{t['duration_s']:.3f}s（音轨被替换或截断）")
    return errs


def parse_index() -> tuple[list[dict], list[dict], float]:
    html = INDEX.read_text(encoding="utf-8")
    scenes, audios = [], []
    for m in SCENE_RE.finditer(html):
        src = m.group("src")
        if "captions" in src:
            continue                      # 字幕是覆盖全片的图层，不参与帧链
        scenes.append({"src": src, "start": float(m.group("start")),
                       "dur": float(m.group("dur"))})
    for m in AUDIO_RE.finditer(html):
        audios.append({"src": m.group("src"), "start": float(m.group("start")),
                       "dur": float(m.group("dur"))})
    root = float(ROOT_DUR_RE.search(html).group(1))
    return scenes, audios, root


def check_g4(scenes: list[dict], audios: list[dict], takes: list[dict]) -> list[str]:
    errs: list[str] = []
    n = len(scenes)
    if n != len(takes):
        errs.append(f"G4 index.html 有 {n} 帧，voice_takes 有 {len(takes)} 帧")
    for i, (sc, t) in enumerate(zip(scenes, takes)):
        want = t["duration_s"] + (1.2 if i == n - 1 else 0.5)
        if abs(sc["dur"] - want) > TOL:
            errs.append(f"G4 {Path(sc['src']).name}: 帧时长 {sc['dur']:.3f}s，"
                        f"应为旁白 {t['duration_s']:.3f} + "
                        f"{1.2 if i == n - 1 else 0.5} = {want:.3f}s")
    for i, (au, t) in enumerate(zip(audios, takes)):
        if abs(au["dur"] - t["duration_s"]) > TOL:
            errs.append(f"G4 音轨{i + 1} data-duration {au['dur']:.3f}s "
                        f"≠ 旁白 {t['duration_s']:.3f}s（尾巴会被切）")
    return errs


def check_g7() -> list[str]:
    """生成物该在 generated/ 下。工程根出现旧布局文件 = 这一集没迁移，或有人往根上写。

    这条是**结构约束**，不是内容约束：G6 管"这份生成物有没有被改"，G7 管"它该不该在这个位置"。
    区别在于 G6 事后发现，G7 让错误位置根本不该出现——新写脚本时若把路径硬编码成
    ROOT / "voice_takes.json"，第一次跑就在根上留下文件，马上红。
    """
    errs = [f"G7 工程根还有旧布局的生成物 {name}：跑 python3 ../../tools/migrate_layout.py"
            f" 迁到 generated/（见 tools/paths.py）"
            for name in LEGACY if (ROOT / name).exists()]
    if not (ROOT / "generated").is_dir() and not errs:
        errs.append("G7 没有 generated/ 目录：先跑 make captions 生成，或 migrate_layout.py")
    return errs


def check_g5(scenes: list[dict], root: float) -> list[str]:
    errs: list[str] = []
    if not scenes:
        return ["G5 index.html 里没有解析到 scene 帧"]
    if abs(scenes[0]["start"]) > GAP_TOL:
        errs.append(f"G5 首帧起点 {scenes[0]['start']:.3f}s，应为 0")
    for prev, cur in zip(scenes, scenes[1:]):
        end = prev["start"] + prev["dur"]
        if abs(cur["start"] - end) > GAP_TOL:
            kind = "空隙" if cur["start"] > end else "重叠"
            errs.append(f"G5 {Path(cur['src']).name} 起点 {cur['start']:.3f}s "
                        f"与上一帧终点 {end:.3f}s 不接（{kind} "
                        f"{abs(cur['start'] - end):.3f}s）")
    last_end = scenes[-1]["start"] + scenes[-1]["dur"]
    if abs(root - last_end) > GAP_TOL:
        errs.append(f"G5 root data-duration {root:.3f}s ≠ 末帧终点 {last_end:.3f}s")
    return errs


def main() -> int:
    strict = "--strict" in sys.argv
    missing = [p.name for p in (SCRIPT, TAKES, META, INDEX) if not p.exists()]
    if missing:
        legacy = [n for n in LEGACY if (ROOT / n).exists()]
        if legacy:
            print(f"✗ 旧布局：工程根上还有 {', '.join(legacy)}（生成物应放 generated/）——"
                  f"跑 python3 ../../tools/migrate_layout.py", file=sys.stderr)
        else:
            print(f"✗ 缺文件：{', '.join(missing)}", file=sys.stderr)
        return 2

    frames = script_frames()
    takes = json.loads(TAKES.read_text(encoding="utf-8"))["takes"]
    meta = json.loads(META.read_text(encoding="utf-8"))
    scenes, audios, root = parse_index()

    sents = sum(len(v) for v in frames.values())
    gates = [
        ("G1 旁白覆盖", check_g1(frames, takes),
         f"{len(frames)} 帧 / {sents} 句与 voice_takes 逐句一致"),
        ("G2 新鲜度", check_g2(takes, meta), "audio_meta 与旁白逐帧一致（比内容不比 mtime）"),
        ("G3 音轨", check_g3(takes), f"{len(takes)} 条音轨存在且时长与记录一致"),
        ("G4 帧时长", check_g4(scenes, audios, takes),
         f"{len(scenes)} 帧 = 旁白 + 0.5s（收尾帧 +1.2s）"),
        ("G5 时间轴", check_g5(scenes, root), f"起点首尾相接，总长 {root:.3f}s"),
    ]
    stamp_errs, stamp_warns = verify_stamps()
    gates.append(("G6 生成物指纹", stamp_errs, "生成物与脚本一致，未被手改"))
    gates.append(("G7 目录边界", check_g7(), "生成物都在 generated/ 下"))
    anchor_errs, anchor_notes = check_frame_anchors()
    gates.append(("G8 帧内锚点", anchor_errs, "帧内时间码注释与旁白一致"))
    stamp_warns += anchor_notes

    failed = 0
    for name, errs, ok_msg in gates:
        if errs:
            failed += 1
            print(f"  ✗ {name}")
            for e in errs:
                print(f"      {e}")
        else:
            print(f"  ✓ {name}：{ok_msg}")

    for w in stamp_warns:
        print(f"  · {w}")

    print()
    if failed:
        print(f"✗ {failed}/{len(gates)} 条链路不变量失败。")
        print("  改文案的完整修法：make narrate && make captions，再按提示同步 index.html。")
        return 1 if strict else 0
    print(f"✓ {len(gates)} 条链路不变量全部成立")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
