#!/usr/bin/env python3
"""Throwaway probe: which creator-backend endpoints expose per-video metrics?

Uses the bilibili-skills authenticated session (read-only cookie reuse). Never
prints cookie/token values: only HTTP status, top-level keys, and numeric fields.
"""
import json
import sys

sys.path.insert(0, "/Users/cyx/repo/yvideo/.agents/skills/bilibili-skills/scripts")

from bilibili.api import BilibiliAPI  # noqa: E402

MEMBER = "https://member.bilibili.com"
ACCEPT = (200, 400, 401, 403, 404, 405, 412, 429, 500, 502)

# key targets: EP01..EP06 aids (from publish/ep0*/result.json)
AIDS = [117658867468437, 117659018529104, 117659270186344,
        117659421182333, 117660947909141, 117660947909748]

# endpoint templates: {aid} substituted
CANDIDATES = [
    "/x/web/data/v2/archive/base?aid={aid}",
    "/x/web/data/pandora?aid={aid}",
    "/x/web/data/v2/pandora?type=2&aid={aid}",
    "/x/web/data/archive?aid={aid}",
    "/x/web/data/v2/archive/retention?aid={aid}",
    "/x/web/data/archive/retention?aid={aid}",
    "/x/web/data/v2/base?aid={aid}",
    "/x/web/data/base?aid={aid}",
    "/x/web/data/v2/playanalysis?aid={aid}",
    "/x/web/data/playanalysis?aid={aid}&type=1",
    "/x/web/data/archive/analysis?aid={aid}",
    "/x/web/data/v2/archive/analysis?aid={aid}",
    "/x/web/data/overview?aid={aid}",
    "/x/web/data/v2/overview?aid={aid}",
    "/x/web/data/pandora/full?aid={aid}",
    "/x/web/data/v2/pandora/full?type=2&aid={aid}",
    "/x/web/data/v2/archive/pandora?aid={aid}",
    "/x/web/data/v2/archive/base/v2?aid={aid}",
]

INTERESTING = (
    "ratio", "rate", "duration", "time", "full", "ret", "avg",
    "average", "play", "view", "fav", "finish", "complete",
)


def collect_numbers(obj, path="", out=None, depth=0):
    """Recursively gather scalars whose key looks metric-ish (values only)."""
    if out is None:
        out = {}
    if depth > 6 or len(out) > 120:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            if isinstance(v, (dict, list)):
                collect_numbers(v, p, out, depth + 1)
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                if any(t in str(k).lower() for t in INTERESTING):
                    out[p] = v
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:6]):
            collect_numbers(v, f"{path}[{i}]", out, depth + 1)
    return out


def main() -> None:
    api = BilibiliAPI()
    results = []
    aid = AIDS[0]
    for tpl in CANDIDATES:
        url = MEMBER + tpl.format(aid=aid)
        rec = {"url": url, "endpoint": tpl}
        try:
            resp = api.session.get(url, accept_status=ACCEPT)
            rec["http_status"] = resp.status
            try:
                payload = resp.json()
            except Exception as e:  # noqa: BLE001
                rec["json_error"] = f"{type(e).__name__}"
                rec["body_snippet"] = str(getattr(resp, "text", ""))[:160]
                results.append(rec)
                print(f"[{rec['http_status']}] {tpl} -> not JSON ({type(e).__name__})")
                continue
            if isinstance(payload, dict):
                rec["code"] = payload.get("code")
                rec["message"] = payload.get("message") or payload.get("msg")
                rec["top_keys"] = list(payload.keys())
                d = payload.get("data")
                rec["data_keys"] = list(d.keys()) if isinstance(d, dict) else (
                    f"list[{len(d)}]" if isinstance(d, list) else type(d).__name__
                )
                rec["numbers"] = collect_numbers(d)
            print(f"[{rec['http_status']}] {tpl}")
            print(f"    envelope keys={rec.get('top_keys')} code={rec.get('code')} msg={rec.get('message')!r}")
            print(f"    data_keys={rec.get('data_keys')}")
            if rec.get("numbers"):
                print(f"    numbers={json.dumps(rec['numbers'], ensure_ascii=False)[:900]}")
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"
            print(f"[ERR] {tpl} -> {type(e).__name__}: {str(e)[:200]}")
        results.append(rec)

    with open("/Users/cyx/repo/yvideo/projects/dsh-anatomy/analytics/_probe-results.json", "w") as f:
        json.dump({"aid_probed": aid, "results": results}, f, ensure_ascii=False, indent=2)
    print("\nwrote _probe-results.json")


if __name__ == "__main__":
    main()
