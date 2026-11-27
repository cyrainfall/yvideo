#!/usr/bin/env python3
"""Build s1-baseline.json from the two raw captures (_public_raw.json, _member_raw.json)."""
import json
import statistics
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

S1 = ["BV1PHyVzrEcn", "BV1YwyVzsEdL", "BV18uyVzSEzJ",
      "BV1zSyGzYE6Z", "BV11yyjzpEXS", "BV11yyjzpEsU"]
S1_AID = ["117658867468437", "117659018529104", "117659270186344",
          "117659421182333", "117660947909141", "117660947909748"]

pub = json.loads((HERE / "_public_raw.json").read_text())
mem = json.loads((HERE / "_member_raw.json").read_text())

rows = []
for i, (bvid, aid) in enumerate(zip(S1, S1_AID)):
    p = pub["videos"][bvid]
    m = mem["videos"][aid]
    st = p["stat_full"]
    pl = (m.get("raw") or {}).get("play") or {}
    mstat = (m.get("raw") or {}).get("stat") or {}
    view = st.get("view")
    fav = st.get("favorite")
    rows.append({
        "ep": f"EP{i + 1:02d}",
        "bvid": bvid,
        "aid": int(aid),
        "title": p["title"],
        "pubdate": p["pubdate"],
        "pubdate_iso": time.strftime("%Y-%m-%d %H:%M", time.localtime(p["pubdate"])),
        "duration_s": p["duration"],
        "duration_mmss": f"{p['duration'] // 60}:{p['duration'] % 60:02d}",
        "view": view,
        "favorite": fav,
        "like": st.get("like"),
        "coin": st.get("coin"),
        "share": st.get("share"),
        "reply": st.get("reply"),
        "danmaku": st.get("danmaku"),
        "favorite_per_view": round(fav / view, 4) if view else None,
        "backend_stat_play": mstat.get("play"),
        "backend_play_view": pl.get("view"),
        "backend_play_ratio_bp": pl.get("rate"),
        "completion_rate": round(pl["rate"] / 10000, 4) if pl.get("rate") is not None else None,
        "avg_watch_s": pl.get("avg_duration"),
        "backend_duration_s": pl.get("duration"),
        "avg_progress_derived": round(pl["avg_duration"] / pl["duration"], 4)
        if pl.get("avg_duration") and pl.get("duration") else None,
        "view_backend_minus_public": (mstat.get("play") or 0) - (view or 0),
        "sources": {
            "view/favorite/like/coin/share/reply/danmaku": "public GET /x/web-interface/view?bvid=",
            "backend_stat_play/backend_play_view/backend_play_ratio_bp/avg_watch_s":
                "member GET /x/web/data/archive?aid=",
        },
    })

ctx = []
for bvid, rec in pub["videos"].items():
    if bvid in S1:
        continue
    st = rec["stat_full"]
    mrec = None
    for v in mem["videos"].values():
        if v.get("aid") == rec.get("aid"):
            mrec = v
    pl = ((mrec or {}).get("raw") or {}).get("play") or {}
    ctx.append({
        "bvid": bvid, "aid": rec.get("aid"), "title": rec["title"],
        "duration_s": rec["duration"], "view": st.get("view"),
        "favorite": st.get("favorite"), "like": st.get("like"),
        "favorite_per_view": round(st["favorite"] / st["view"], 4) if st.get("view") else None,
        "completion_rate": round(pl["rate"] / 10000, 4) if pl.get("rate") is not None else None,
        "avg_watch_s": pl.get("avg_duration"),
        "note": "非 S1，仅作口径参照",
    })


def agg(key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return {
        "mean": round(statistics.mean(vals), 4),
        "median": round(statistics.median(vals), 4),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "n": len(vals),
    }


total_view = sum(r["view"] for r in rows)
total_fav = sum(r["favorite"] for r in rows)

out = {
    "dataset": "拆开 DSH Season-1 baseline",
    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "account": {"mid": 13839021, "nickname": "perfectH"},
    "method": {
        "public_stats": {
            "endpoint": "https://api.bilibili.com/x/web-interface/view?bvid=<BV>",
            "auth": "none (public web API; browser User-Agent only, no cookies)",
            "fields_used": ["data.title", "data.pubdate", "data.duration",
                            "data.stat.view", "data.stat.favorite", "data.stat.like",
                            "data.stat.coin", "data.stat.share", "data.stat.reply",
                            "data.stat.danmaku"],
        },
        "backend_stats": {
            "endpoint": "https://member.bilibili.com/x/web/data/archive?aid=<aid>",
            "auth": "bilibili-skills Browserless session (read-only reuse of the "
                    "already-logged-in browser cookie; no cookie value read, printed or stored)",
            "fields_used": ["data.stat.play", "data.play.view",
                            "data.play.rate (万分比)", "data.play.duration",
                            "data.play.avg_duration (秒)"],
            "note": "唯一可用的后端逐视频接口；其余候选全部 404（见 missing.failed_endpoints）",
        },
        "completion_rate": {
            "value": "data.play.rate / 10000",
            "caveat": "rate 与 avg_duration/duration 逐集吻合（±0.5pp，见 "
                      "per_episode[].avg_progress_derived），因此其口径是「平均播放进度」；"
                      "平台页面上「完播率」列未读取核对（未连浏览器扩展），"
                      "故完成率标为 page_verified=false。",
            "page_verified": False,
        },
        "expand_play": {
            "status": "unavailable",
            "detail": "无任何探测到的接口返回「展开播放」字段；"
                      "后端 data.play.view 略小于 data.stat.play，差值是否为展开播放未验证。",
        },
    },
    "per_episode": rows,
    "aggregates_s1": {
        "n_episodes": len(rows),
        "view": agg("view"),
        "favorite": agg("favorite"),
        "favorite_per_view": agg("favorite_per_view"),
        "favorite_per_view_pooled": round(total_fav / total_view, 4),
        "completion_rate": agg("completion_rate"),
        "avg_watch_s": agg("avg_watch_s"),
        "duration_s": agg("duration_s"),
        "totals": {"view": total_view, "favorite": total_fav},
    },
    "context_non_s1": ctx,
    "missing": {
        "platform_completion_rate_page": {
            "status": "not_verified",
            "reason": "B站创作中心「视频数据」页面需已加载扩展的浏览器会话；本次仅走协议层。",
            "url_would_be": "https://member.bilibili.com/platform/analytics/video",
        },
        "expand_play": {
            "status": "unavailable",
            "reason": "无接口返回该字段（逐个探测见 failed_endpoints）。",
        },
        "retention_curve": {
            "status": "unavailable",
            "reason": "完播/留存曲线接口探测全 404。",
        },
        "failed_endpoints": [
            {"url": "https://member.bilibili.com/x/web/data/v2/archive/base?aid=<aid>", "http": 404},
            {"url": "https://member.bilibili.com/x/web/data/pandora?aid=<aid>", "http": 404},
            {"url": "https://member.bilibili.com/x/web/data/v2/pandora?type=2&aid=<aid>", "http": 404},
            {"url": "https://member.bilibili.com/x/web/data/v2/archive/retention?aid=<aid>", "http": 404},
            {"url": "https://member.bilibili.com/x/web/data/archive/retention?aid=<aid>", "http": 404},
            {"url": "https://member.bilibili.com/x/web/data/v2/archive/trend?aid=<aid>", "http": 404},
            {"url": "https://member.bilibili.com/x/web/data/archive/analysis?aid=<aid>", "http": 404},
            {"url": "https://member.bilibili.com/x/web/data/archive/detail?aid=<aid>", "http": 404},
            {"url": "https://member.bilibili.com/x/web/data/v2/archive/base/v2?aid=<aid>", "http": 404},
            {"url": "https://member.bilibili.com/x/web/data/playanalysis?aid=<aid>&type=1",
             "http": 200, "code": -400, "message": "请求错误"},
            {"url": "https://member.bilibili.com/x/web/data/base?aid=<aid>",
             "http": 200, "note": "返回 period/viewer_area/viewer_base，无单视频指标"},
        ],
    },
    "raw_excerpts": {},
}

# trimmed raw payloads for provenance
for bvid, aid in zip(S1, S1_AID):
    p = pub["videos"][bvid]
    m = mem["videos"][aid]
    out["raw_excerpts"][f"{bvid}"] = {
        "public": {
            "http": p["http_status"], "code": p["code"],
            "title": p["title"], "pubdate": p["pubdate"], "duration": p["duration"],
            "stat": p["stat_full"], "desc_head": (p.get("desc") or "")[:120],
        },
        "member": {
            "http": m.get("http_status"), "code": m.get("code"),
            "data": m.get("raw"),
        },
    }

(HERE / "s1-baseline.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(out["aggregates_s1"], ensure_ascii=False, indent=2))
print("\nwrote s1-baseline.json")
