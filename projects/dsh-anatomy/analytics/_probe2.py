#!/usr/bin/env python3
"""Second probe round: hunt for explicit 完播率 / 展开播放 fields."""
import json
import sys

sys.path.insert(0, "/Users/cyx/repo/yvideo/.agents/skills/bilibili-skills/scripts")

from bilibili.api import BilibiliAPI  # noqa: E402

MEMBER = "https://member.bilibili.com"
ACCEPT = (200, 400, 401, 403, 404, 412, 429, 500, 502)
AID = 117658867468437

CANDIDATES = [
    "/x/web/data/archive?aid={aid}&type=1",
    "/x/web/data/archive/trend?aid={aid}",
    "/x/web/data/v2/archive/trend?aid={aid}",
    "/x/web/data/archive/play?aid={aid}",
    "/x/web/data/archive/base?aid={aid}",
    "/x/web/data/v2/archive/base?aid={aid}&type=2",
    "/x/web/data/pandora?type=2&aid={aid}&period=0",
    "/x/web/data/v2/pandora?type=2&aid={aid}&period=0",
    "/x/web/data/pandora?type=2&aid={aid}&date=0",
    "/x/web/data/archive/retention?aid={aid}&type=1",
    "/x/web/data/v2/retention?aid={aid}",
    "/x/web/data/retention?aid={aid}",
    "/x/web/data/v2/archive/detail?aid={aid}",
    "/x/web/data/archive/detail?aid={aid}",
    "/x/web/data/detail?aid={aid}",
    "/x/web/data/v2/detail?aid={aid}",
    "/x/web/data/archive/v2?aid={aid}",
    "/x/web/data/full?aid={aid}",
    "/x/web/data/archive/full?aid={aid}",
    "/x/web/data/v2/archive/full?aid={aid}",
    "/x/archive/data?aid={aid}",
    "/x/web/archive/data?aid={aid}",
    "/x/web/data/uparchive?aid={aid}",
    "/x/web/data/v2/uparchive?aid={aid}",
]


def collect(obj, path="", out=None, depth=0):
    if out is None:
        out = {}
    if depth > 6 or len(out) > 200:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            if isinstance(v, (dict, list)):
                collect(v, p, out, depth + 1)
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                out[p] = v
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:4]):
            collect(v, f"{path}[{i}]", out, depth + 1)
    return out


def main() -> None:
    api = BilibiliAPI()
    rows = []
    for tpl in CANDIDATES:
        url = MEMBER + tpl.format(aid=AID)
        rec = {"endpoint": tpl}
        try:
            resp = api.session.get(url, accept_status=ACCEPT)
            rec["http_status"] = resp.status
            try:
                body = resp.json()
            except Exception as e:  # noqa: BLE001
                rec["json_error"] = type(e).__name__
                print(f"[{resp.status}] {tpl} -> non-JSON ({type(e).__name__})")
                rows.append(rec)
                continue
            if isinstance(body, dict):
                rec["code"] = body.get("code")
                rec["message"] = body.get("message")
                d = body.get("data")
                rec["data_keys"] = list(d.keys()) if isinstance(d, dict) else type(d).__name__
                nums = collect(d)
                rec["numbers"] = nums
                hits = [k for k in nums if any(t in k.lower() for t in
                        ("ratio", "full", "finish", "complete", "rate", "avg", "expand", "explay"))]
                print(f"[{resp.status}] {tpl} code={rec['code']} msg={rec['message']!r} keys={rec['data_keys']}")
                if hits:
                    print("    HITS:", json.dumps({k: nums[k] for k in hits}, ensure_ascii=False)[:600])
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}"
            print(f"[ERR] {tpl} -> {type(e).__name__}: {str(e)[:120]}")
        rows.append(rec)

    with open("/Users/cyx/repo/yvideo/projects/dsh-anatomy/analytics/_probe2-results.json", "w") as f:
        json.dump({"aid": AID, "results": rows}, f, ensure_ascii=False, indent=2)
    print("\nwrote _probe2-results.json")


if __name__ == "__main__":
    main()
