#!/usr/bin/env python3
"""captions_build.py — 生成 compositions/captions.html + caption_groups.json。

分组服务中文阅读：按脚本里的标点切小句，小句拼到一行不超过约 15 个字宽；
行内逐字高亮（当前字蓝、已读字纸白、未读字灰）。

时间：audio_meta.json 的词级时间是帧内相对时间，加上 index.html 里每个 scene 的
data-start，换成全片绝对时间。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "audio_meta.json"
INDEX = ROOT / "index.html"
SCRIPT = ROOT / "SCRIPT.md"
OUT_HTML = ROOT / "compositions" / "captions.html"
OUT_JSON = ROOT / "caption_groups.json"

SCENE_RE = re.compile(r'id="el-frame-(\d+)"[^>]*data-start="([0-9.]+)"')
FRAME_RE = re.compile(r"^##\s+Frame\s+(\d+)\s*[—-]\s*(.+?)\s*$")
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9.+_-]*|[0-9]+(?:\.[0-9]+)?|[\u4e00-\u9fff]")
CLAUSE = re.compile(r"[^，、；：—。！？!?]+[，、；：—。！？!?]?")
MAX_W = 15.0

# 术语表：keyword 模式只给这些词上色（源码级讲解里，这些词就是要教给观众的概念）
KEYWORDS = {
    "token", "harness", "dsh", "plugin", "plugins", "agent-loop", "ctx",
    "inject", "effect", "turn", "step", "session", "stream", "tools",
    "Cordis", "profile", "bundle", "patch", "内核", "插件", "日志", "轮次",
    "上下文", "事件", "工具", "模型", "流", "卸载", "服务", "依赖",
}


def token_width(tok: str) -> float:
    return 1.0 if re.match(r"[\u4e00-\u9fff]", tok) else max(1.0, len(tok) * 0.6)


def frame_starts() -> dict[int, float]:
    return {int(n): float(s) for n, s in SCENE_RE.findall(INDEX.read_text())}


def script_lines() -> dict[int, list[str]]:
    """一行旁白 = 一屏字幕；只有超长行才在标点处再拆。"""
    out: dict[int, list[str]] = {}
    cur = None
    for line in SCRIPT.read_text().splitlines():
        m = FRAME_RE.match(line)
        if m:
            cur = int(m.group(1))
            out[cur] = []
            continue
        if line.startswith("#"):
            cur = None
            continue
        if cur is None or not line.strip() or line.lstrip().startswith(("语言：", "全片", "音色：")):
            continue
        out[cur].append(line.strip())
    return out


def build() -> list[dict]:
    meta = json.loads(META.read_text())
    starts = frame_starts()
    lines = script_lines()
    groups: list[dict] = []

    for voice in meta["voices"]:
        f = voice["frame"]
        base = starts[f]
        words = voice["words"]

        plan: list[dict] = []
        bucket: list[str] = []
        bucket_text: list[str] = []
        width = 0.0
        for line in lines.get(f, []):
            toks = TOKEN.findall(line)
            if not toks:
                continue
            if sum(token_width(t) for t in toks) <= (28 if MODE == "line" else 19):
                if bucket:
                    plan.append({"tokens": "".join(bucket), "text": "".join(bucket_text), "count": len(bucket)})
                    bucket, bucket_text, width = [], [], 0.0
                plan.append({"tokens": "".join(toks), "text": line, "count": len(toks)})
                continue
            for m2 in CLAUSE.finditer(line):
                ct = TOKEN.findall(m2.group(0))
                if not ct:
                    continue
                w = sum(token_width(t) for t in ct)
                if bucket and width + w > MAX_W:
                    cut = "".join(bucket_text).rstrip("，、；：—")
                    plan.append({"tokens": "".join(bucket), "text": cut, "count": len(bucket)})
                    bucket, bucket_text, width = [], [], 0.0
                bucket.extend(ct)
                bucket_text.append(m2.group(0).strip())
                width += w
        if bucket:
            plan.append({"tokens": "".join(bucket), "text": "".join(bucket_text), "count": len(bucket)})

        # 长句切分可能留下两三个字的尾块（「话」「新」）。孤字字幕读不及，
        # 并回前一块；完整短句以句末标点结尾，不参与合并。
        merged: list[dict] = []
        for item in plan:
            narrow = sum(token_width(t) for t in TOKEN.findall(item["tokens"])) < 3
            if merged and narrow and not item["text"].rstrip().endswith(("。", "！", "？")):
                merged[-1]["tokens"] += item["tokens"]
                merged[-1]["text"] += item["text"]
                merged[-1]["count"] += item["count"]
            else:
                merged.append(dict(item))
        plan = merged

        idx = 0
        for item in plan:
            count = item["count"]
            chunk = words[idx: idx + count]
            idx += count
            if not chunk:
                continue
            groups.append(make_group(groups, f, base, chunk, item["text"]))
        if idx < len(words):
            groups.append(make_group(groups, f, base, words[idx:]))

    # 旁白为了发音清楚会用口语形态（node modules / install bundle），
    # 但字幕应该和屏幕上的真名一致：这里只改显示文本，不动时间。
    for g in groups:
        for spoken, shown in (("node modules", "node_modules"),
                              ("install bundle", "install_bundle"),
                              ("remove bundle", "remove_bundle"),
                              ("tool result", "tool/result"),
                              ("tool-result", "tool/result"),
                              ("command run", "command/run"),
                              ("command done", "command/done")):
            if spoken in g["text"]:
                g["text"] = g["text"].replace(spoken, shown)
                for w in g["words"]:
                    w["text"] = w["text"].replace(spoken, shown)

    for i, g in enumerate(groups):
        if i + 1 < len(groups):
            g["end"] = max(g["start"] + 0.4, groups[i + 1]["start"])
        else:
            g["end"] = g["words"][-1]["end"] + 0.35
    return groups


def key_spans(text: str) -> list[tuple[int, int]]:
    """在整行文本里找术语出现的位置（中英文都按子串匹配）。"""
    spans = []
    low = text.lower()
    for kw in KEYWORDS:
        needle = kw.lower()
        pos = low.find(needle)
        while pos >= 0:
            spans.append((pos, pos + len(needle)))
            pos = low.find(needle, pos + 1)
    return spans


def make_group(groups: list[dict], frame: int, base: float, chunk: list[dict], display: str | None = None) -> dict:
    n = len(groups)
    text = "".join(w["text"] for w in chunk)
    if MODE == "line":
        # 整行模式不需要逐词切片：一整行带标点上屏，读起来才像句子
        display = (display or text).strip()
        return {
            "id": f"caption-group-{n}", "frame": frame,
            "start": round(base + chunk[0]["start"], 3),
            "end": round(base + chunk[-1]["end"], 3),
            "text": display,
            "words": [{"id": f"caption-word-{n}-0", "text": display,
                       "start": round(base + chunk[0]["start"], 3),
                       "end": round(base + chunk[-1]["end"], 3), "key": False}],
        }
    spans = key_spans(text)
    offsets, pos = [], 0
    for w in chunk:
        offsets.append((pos, pos + len(w["text"])))
        pos += len(w["text"])
    marks = [any(a < e and b > st for a, b in spans) for st, e in offsets]
    return {
        "id": f"caption-group-{n}",
        "frame": frame,
        "start": round(base + chunk[0]["start"], 3),
        "end": round(base + chunk[-1]["end"], 3),
        "text": text,
        "words": [{
            "id": f"caption-word-{n}-{i}",
            "text": w["text"],
            "key": marks[i],
            "start": round(base + w["start"], 3),
            "end": round(base + w["end"], 3),
        } for i, w in enumerate(chunk)],
    }


HTML = """<template id="captions-template" data-composition-id="captions" data-width="1920" data-height="1080">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  @font-face{{font-family:'Inter';src:url('assets/fonts/Inter-Variable.woff2') format('woff2');font-weight:100 900;font-display:block}}
  #captions-root{{position:absolute;inset:0;pointer-events:none}}
  .caption-stage{{position:absolute;left:0;right:0;top:900px;height:180px;display:flex;align-items:center;justify-content:center}}
  .caption-group{{position:absolute;left:0;right:0;top:0;height:100%;display:flex;align-items:center;justify-content:center;opacity:0}}
  .caption-line{{font-family:'Inter',sans-serif;font-weight:500;font-size:31px;line-height:1.2;letter-spacing:.005em;
    color:#E9E4D8;display:flex;flex-wrap:nowrap;gap:.02em;white-space:nowrap;max-width:92%}}
  .caption-word{{display:inline-block;color:#6E747F;will-change:transform}}
  #captions-root[data-mode="line"] .caption-word,
  #captions-root[data-mode="keyword"] .caption-word,
  #captions-root[data-mode="reveal"] .caption-word{{color:#E9E4D8}}
  .caption-word.is-active{{color:#5C78FF}}
  .caption-word.is-spoken{{color:#E9E4D8;box-shadow:none}}
  #captions-root[data-mode="keyword"] .caption-word.cap-key{{color:#6F86FF}}
</style>
<div id="captions-root" data-mode="{mode}" data-composition-id="captions" data-timeline-locked data-start="0" data-duration="{duration}" data-fps="30" data-width="1920" data-height="1080">
  <div class="caption-layer" aria-hidden="true"><div id="caption-stage" class="caption-stage"></div></div>
</div>
<script>
  var GROUPS = {groups};
  var DURATION = {duration};
  var MODE = "{mode}";
  (function () {{
    var stage = document.getElementById("caption-stage");
    GROUPS.forEach(function (group, g) {{
      var groupEl = document.createElement("div");
      groupEl.className = "caption-group";
      groupEl.id = "caption-group-" + g;
      var line = document.createElement("div");
      line.className = "caption-line";
      (group.words || []).forEach(function (w, i) {{
        var span = document.createElement("span");
        span.className = "caption-word" + (w.key ? " cap-key" : "");
        span.id = "caption-word-" + g + "-" + i;
        span.textContent = String(w.text);
        line.appendChild(span);
      }});
      groupEl.appendChild(line);
      stage.appendChild(groupEl);
    }});

    window.__timelines = window.__timelines || {{}};
    var tl = gsap.timeline({{ paused: true }});

    GROUPS.forEach(function (group, g) {{
      var groupEl = document.getElementById("caption-group-" + g);
      var words = group.words || [];
      var start = Math.max(0, Number(group.start));
      var end = Math.max(start + 0.1, Number(group.end));

      tl.set(groupEl, {{ opacity: 1 }}, start);
      tl.set(groupEl, {{ opacity: 0 }}, end);

      if (MODE === "line" || MODE === "keyword") {{
        tl.fromTo(groupEl, {{ opacity: 0, y: 8 }}, {{ opacity: 1, y: 0, duration: .24, ease: "power2.out" }}, start);
        tl.to(groupEl, {{ opacity: 0, duration: .2 }}, end);
      }} else if (MODE === "reveal") {{
        tl.set(groupEl, {{ opacity: 1 }}, start);
        tl.set(groupEl, {{ opacity: 0 }}, end);
        words.forEach(function (w, i) {{
          var el = document.getElementById("caption-word-" + g + "-" + i);
          tl.fromTo(el, {{ opacity: 0, y: 6 }}, {{ opacity: 1, y: 0, duration: .18, ease: "power2.out" }},
            Math.max(start, Number(w.start)));
        }});
      }} else {{
        words.forEach(function (w, i) {{
          var el = document.getElementById("caption-word-" + g + "-" + i);
          var at = Math.max(start, Number(w.start));
          tl.set(el, {{ className: "caption-word" }}, start);
          tl.set(el, {{ className: "caption-word is-active" }}, at);
          if (i + 1 < words.length) {{
            tl.set(el, {{ className: "caption-word is-spoken" }}, Math.max(at, Number(words[i + 1].start)));
          }}
        }});
        var lastEl = document.getElementById("caption-word-" + g + "-" + (words.length - 1));
        tl.set(lastEl, {{ className: "caption-word is-spoken" }}, Math.min(end, Number(words[words.length - 1].end) + 0.12));
      }}
    }});

    tl.to({{}}, {{ duration: DURATION }}, 0);
    window.__timelines["captions"] = tl;
  }})();
</script>
</template>
"""


MODE = "word"


def check_freshness() -> None:
    """audio_meta 比 voice_takes 旧，说明改了文案却漏跑 timing.py —— 字幕会整体错位。"""
    takes = ROOT / "voice_takes.json"
    if not takes.exists() or not META.exists():
        return
    if META.stat().st_mtime < takes.stat().st_mtime:
        print("✗ audio_meta.json 比 voice_takes.json 旧：先跑 python3 tools/timing.py 再生成字幕",
              file=sys.stderr)
        raise SystemExit(1)


def main() -> int:
    global MODE
    if "--mode" in sys.argv:
        MODE = sys.argv[sys.argv.index("--mode") + 1]
    check_freshness()
    groups = build()
    duration = max(g["end"] for g in groups) + 0.2
    OUT_HTML.write_text(HTML.format(
        duration=round(duration, 3),
        mode=MODE,
        groups=json.dumps(groups, ensure_ascii=False, separators=(",", ":")),
    ))
    OUT_JSON.write_text(json.dumps(groups, ensure_ascii=False, indent=2))
    (ROOT / "caption-overrides.json").write_text("[]")
    print(f"✓ {len(groups)} 行字幕，覆盖 {duration:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
