#!/usr/bin/env python3
"""index_build.py — 由 voice_takes.json 生成 index.html 的时间轴（7 帧场景 + 旁白音轨 + 字幕轨）。

规则（README「时间轴约定」）：
  · 帧时长 = 旁白时长 + 0.5s，末帧 +1.2s
  · scene 的 data-start 是绝对起点；字幕脚本靠它把帧内时间换成绝对时间
  · <audio> 的 data-duration 用旁白原始时长，不是帧时长（尾巴不被切）

用法：
  python3 ../../tools/index_build.py            # 读 voice_takes.json，覆写 index.html
"""
from __future__ import annotations

import json
from pathlib import Path

# 工程目录 = 当前工作目录（一集一工程，共享这份 tools/）
ROOT = Path.cwd()
if not (ROOT / "hyperframes.json").exists():
    raise SystemExit(f"✗ 请在某一集的工程目录里运行（{ROOT} 下没有 hyperframes.json）")
TAKES = ROOT / "voice_takes.json"
INDEX = ROOT / "index.html"

TAIL_S = 0.5
LAST_TAIL_S = 1.2

HEAD = """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js" integrity="sha384-sG0Hv1tP1lZCk9KQmrIbY/XNwi+OY84GQqhMscbnsoBFqAz8KNCil1kvfL3Hbbk2" crossorigin="anonymous"></script>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: 1920px; height: 1080px; overflow: hidden; background: #0A0B0D; }
      #root { position: relative; width: 1920px; height: 1080px; overflow: hidden; background: #0A0B0D; }
      .scene { position: absolute; inset: 0; width: 100%; height: 100%; }
    </style>
  </head>
  <body>
"""


def main() -> int:
    takes = json.loads(TAKES.read_text())["takes"]
    takes.sort(key=lambda t: t["frame"])
    if not takes:
        raise SystemExit("voice_takes.json 里没有 take")

    lines: list[str] = []
    cursor = 0.0
    total = 0.0
    for i, t in enumerate(takes):
        last = i == len(takes) - 1
        dur = round(t["duration_s"] + (LAST_TAIL_S if last else TAIL_S), 3)
        start = round(cursor, 3)
        nn = t["frame"]
        title = t["title"]
        audio = t["path"]
        track = "1" if nn % 2 else "0"
        lines.append(f"      <!-- {nn:02d} {title} -->")
        lines.append(
            f'      <div id="el-frame-{nn:02d}" class="scene" data-composition-id="frame-{nn:02d}" '
            f'data-composition-src="compositions/frames/frame-{nn:02d}.html" '
            f'data-start="{start:.3f}" data-duration="{dur:.3f}" data-track-index="{track}"></div>'
        )
        lines.append(
            f'      <audio id="vo-{nn:02d}" src="{audio}" data-start="{start:.3f}" '
            f'data-duration="{t["duration_s"]:.3f}" data-track-index="10" data-volume="1"></audio>'
        )
        cursor = round(cursor + dur, 3)
        total = cursor

    body = "\n".join(lines)
    html = (
        HEAD
        + f'    <div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}" data-width="1920" data-height="1080">\n'
        + body
        + "\n\n      <!-- captions -->\n"
        + f'      <div id="el-captions" class="scene" data-track-kind="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="{total:.3f}" data-track-index="20"></div>\n'
        + "    </div>\n\n"
        + "    <script>\n"
        + "      window.__timelines = window.__timelines || {};\n"
        + '      window.__timelines["main"] = gsap.timeline({ paused: true });\n'
        + "      (function () {\n"
        + '        var tl = window.__timelines["main"];\n'
        + f"        tl.to({{}}, {{ duration: {total:.3f} }}, 0);\n"
        + "      })();\n"
        + "    </script>\n  </body>\n</html>\n"
    )
    INDEX.write_text(html)
    print(f"✓ index.html：{len(takes)} 帧，总时长 {total:.3f}s（{int(total // 60)}:{total % 60:05.2f}）")
    for t in takes:
        print(f"   frame {t['frame']}: {t['duration_s']:.2f}s narration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
