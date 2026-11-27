#!/usr/bin/env python3
"""Fetch per-video creator-backend metrics for all published videos.

Endpoint: GET https://member.bilibili.com/x/web/data/archive?aid=<aid>
Auth: bilibili-skills Browserless session (read-only cookie reuse; nothing printed).
Payload of interest (data.play): view, rate, duration, avg_duration.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Users/cyx/repo/yvideo/.agents/skills/bilibili-skills/scripts")

from bilibili.api import BilibiliAPI  # noqa: E402

HERE = Path(__file__).resolve().parent
URL = "https://member.bilibili.com/x/web/data/archive?aid={aid}"

S1 = ["117658867468437", "117659018529104", "117659270186344",
      "117659421182333", "117660947909141", "117660947909748"]


def main() -> None:
    listing = json.loads((HERE / "_list-archives.json").read_text())
    all_aids = [str(it["aid"]) for it in listing["archives"]]
    labels = {a: (f"EP{i + 1:02d}" if a in S1 else "CTX") for i, a in enumerate(S1)}
    for a in all_aids:
        labels.setdefault(a, "CTX")

    api = BilibiliAPI()
    out = {"endpoint": URL, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "videos": {}}
    for aid in all_aids:
        rec = {"aid": int(aid), "label": labels.get(aid, "CTX")}
        try:
            resp = api.session.get(URL.format(aid=aid), accept_status=(200, 403, 404, 412))
            rec["http_status"] = resp.status
            body = resp.json()
            rec["code"] = body.get("code")
            rec["message"] = body.get("message")
            data = body.get("data") or {}
            rec["raw"] = data
            pl = data.get("play") or {}
            st = data.get("stat") or {}
            rec["normalized"] = {
                "play_total": st.get("play"),
                "play_view": pl.get("view"),
                "rate_raw": pl.get("rate"),
                "duration": pl.get("duration"),
                "avg_duration": pl.get("avg_duration"),
                "group": data.get("group"),
            }
            print(f"{rec['label']:5s} aid={aid} http={resp.status} code={rec['code']} "
                  f"stat.play={st.get('play')} play.view={pl.get('view')} rate={pl.get('rate')} "
                  f"dur={pl.get('duration')} avg={pl.get('avg_duration')} group={data.get('group')}")
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"
            print(f"{rec['label']:5s} aid={aid} ERROR {type(e).__name__}: {str(e)[:160]}")
        out["videos"][aid] = rec
        time.sleep(0.5)

    (HERE / "_member_raw.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nwrote {HERE / '_member_raw.json'}")


if __name__ == "__main__":
    main()
