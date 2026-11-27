#!/usr/bin/env python3
"""Fetch public per-video stats from Bilibili web-interface/view.

No cookies are used or read here: this is the public web API, browser UA only.
Writes raw payloads to _public_raw.json (full stat block + trimmed fields).
"""
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
API = "https://api.bilibili.com/x/web-interface/view?bvid="

S1 = [
    ("EP01", "BV1PHyVzrEcn"),
    ("EP02", "BV1YwyVzsEdL"),
    ("EP03", "BV18uyVzSEzJ"),
    ("EP04", "BV1zSyGzYE6Z"),
    ("EP05", "BV11yyjzpEXS"),
    ("EP06", "BV11yyjzpEsU"),
]
CONTEXT = [
    ("CTX-ydesk", "BV1z6sU6iEDX"),
    ("CTX-ping-tcp", "BV1nZsP6jEds"),
    ("CTX-jev", "BV1Pth66NEs3"),
    ("CTX-2021", "BV1Ui4y1X7CW"),
    ("CTX-2020", "BV2H5411H7hU"),  # placeholder, corrected from archive list below
]


def fetch(bvid: str) -> dict:
    req = urllib.request.Request(
        API + bvid,
        headers={
            "User-Agent": UA,
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return {"http_status": r.status, "body": json.loads(r.read().decode("utf-8"))}


def main() -> None:
    listing = json.loads((HERE / "_list-archives.json").read_text())
    archived = {it["bvid"]: it for it in listing["archives"]}
    s1_bvids = {b for _, b in S1}

    targets = list(S1) + [
        ("CTX", b) for b in archived if b not in s1_bvids
    ]

    out = {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "endpoint": API, "videos": {}}
    for label, bvid in targets:
        try:
            got = fetch(bvid)
        except Exception as e:  # noqa: BLE001
            out["videos"][bvid] = {"label": label, "error": f"{type(e).__name__}: {e}"}
            print(f"{label:12s} {bvid} ERROR {type(e).__name__}: {e}")
            continue
        body = got["body"]
        data = body.get("data") or {}
        stat = data.get("stat") or {}
        rec = {
            "label": label,
            "http_status": got["http_status"],
            "code": body.get("code"),
            "message": body.get("message"),
            "aid": data.get("aid"),
            "bvid": data.get("bvid"),
            "title": data.get("title"),
            "pubdate": data.get("pubdate"),
            "duration": data.get("duration"),
            "tname": data.get("tname"),
            "desc": (data.get("desc") or "")[:200],
            "stat_full": stat,
        }
        out["videos"][bvid] = rec
        print(
            f"{label:12s} {bvid} http={got['http_status']} code={body.get('code')} "
            f"dur={data.get('duration')} view={stat.get('view')} fav={stat.get('favorite')} "
            f"like={stat.get('like')} coin={stat.get('coin')} share={stat.get('share')} "
            f"reply={stat.get('reply')} dm={stat.get('danmaku')}"
        )
        time.sleep(0.6)

    (HERE / "_public_raw.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nwrote {HERE / '_public_raw.json'}")


if __name__ == "__main__":
    main()
