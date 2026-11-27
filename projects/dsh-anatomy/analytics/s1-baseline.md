# 拆开 DSH · Season-1 基线数据

> 抓取时间：**2026-11-26 22:41 (+08:00)** ｜ 账号：`perfectH`（mid 13839021，已登录，只读）
> 原始数据：`s1-baseline.json`（含每集原始 payload 摘录）｜ 采集脚本：`_fetch_public.py`、`_fetch_member.py`、`_build_baseline.py`
> 本文只报数，不含解读；S2 的阈值判断在 `SERIES-S2-PLAN.md` §9 由 lead 合并。

## 1 · S1 六集

| EP | BV | 时长 | 播放 | 收藏 | 收藏率 | 完播率\* | 平均观看时长 | 数据来源 |
|---|---|---|---|---|---|---|---|---|
| EP01 | BV1PHyVzrEcn | 2:05 | 20 | 1 | 5.00% | 18.66% | 23s | view 公开接口 + archive 后端接口 |
| EP02 | BV1YwyVzsEdL | 2:13 | 17 | 1 | 5.88% | 21.27% | 28s | 同上 |
| EP03 | BV18uyVzSEzJ | 1:53 | 12 | 2 | 16.67% | 13.27% | 15s | 同上 |
| EP04 | BV1zSyGzYE6Z | 2:21 | 16 | 2 | 12.50% | 32.36% | 45s | 同上 |
| EP05 | BV11yyjzpEXS | 3:44 | 16 | 0 | 0.00% | 18.08% | 40s | 同上 |
| EP06 | BV11yyjzpEsU | 4:07 | 25 | 1 | 4.00% | 20.14% | 49s | 同上 |

\* 见 §3「完播率口径」——这个数不是页面上的「完播率」列，是先能拿到的最接近口径，务必按口径读。

## 2 · 汇总（n=6）

| 指标 | 均值 | 中位数 | 最小 | 最大 |
|---|---|---|---|---|
| 播放 | 17.67 | 16.5 | 12 | 25 |
| 收藏 | 1.17 | 1.0 | 0 | 2 |
| 收藏率（集均） | 7.34% | 5.44% | 0.00% | 16.67% |
| 收藏率（合并 7/106） | 6.60% | — | — | — |
| 完播率（rate 口径） | 20.63% | 19.40% | 13.27% | 32.36% |
| 平均观看时长 | 33.3s | 34.0s | 15s | 49s |
| 时长 | 163.8s | 137s | 113s | 247s |

合计：播放 **106**，收藏 **7**，点赞 **8**，投币 **0**，分享 **0**，评论 **3**（EP04 两条 + EP05 一条），弹幕 **0**。

## 3 · 口径与缺失

### 每个数字的来源

| 数字 | 来源 | 说明 |
|---|---|---|
| 时长、播放、收藏、点赞、投币、分享、评论、弹幕 | `GET https://api.bilibili.com/x/web-interface/view?bvid=<BV>` → `data.duration` / `data.stat.*` | 公开接口，**不用 Cookie**，仅普通浏览器 UA。`data.stat.view` 即平台公开展示的播放数。 |
| 收藏率 | 计算：`data.stat.favorite / data.stat.view` | 分母统一用公开播放数（`view`），不用后端 `play.view`。 |
| 平均观看时长 | `GET https://member.bilibili.com/x/web/data/archive?aid=<aid>` → `data.play.avg_duration`（秒） | 创作中心后端接口，经 bilibili-skills 的只读 Cookie 会话请求；cookie 值从未读取/打印/落盘。 |
| 完播率（近似） | 同一接口 → `data.play.rate`（**万分比**，1866 → 18.66%） | 口径见下。 |

### 完播率口径：为什么标了星号

后端只给一个 `play.rate`（万分比）。把它和「平均观看时长 ÷ 时长」逐集对照：

| EP | rate | avg/duration | 差 |
|---|---|---|---|
| EP01 | 18.66% | 23/125 = 18.40% | +0.26pp |
| EP02 | 21.27% | 28/133 = 21.05% | +0.22pp |
| EP03 | 13.27% | 15/113 = 13.27% | 0.00pp |
| EP04 | 32.36% | 45/141 = 31.91% | +0.45pp |
| EP05 | 18.08% | 40/224 = 17.86% | +0.22pp |
| EP06 | 20.14% | 49/247 = 19.84% | +0.30pp |

六集全部在 ±0.5pp 内吻合（差异来自 avg_duration 取整到秒）。所以 `rate` 的实际口径是**平均播放进度**，不是「看到结尾的人数比例」那种完播率。
若 S2 要拿它当 §9 的「完播率」基线，请沿用同一字段 + 同一口径；换成页面上的「完播率」列后**不可与本表直接相减**。

### 明确拿不到的

1. **创作中心页面的「完播率」列（未核对）** — 需要已加载扩展的浏览器会话读 `https://member.bilibili.com/platform/analytics/video`；本次只走协议层（`mode: api`），没有开浏览器，所以页面口径的数字**不可得**。要拿就补一次浏览器路径。
2. **「展开播放」** — 没有任何探测到的接口返回该字段。后端 `data.play.view` 略小于 `data.stat.play`（EP01 19/20、EP03 11/12、EP04 14/16、EP06 23/25），差值是不是「展开播放」未验证，因此不报。`s1-baseline.json` 里两个数都留了原值。
3. **留存/完播曲线、单集流量来源** — 探测的曲线类接口全部 404。

### 探测过的接口（全部失败项，供下一个人别再试）

`https://member.bilibili.com` 下，除 `/x/web/data/archive?aid=` 外全部不可用：

| 路径 | 结果 |
|---|---|
| `/x/web/data/v2/archive/base?aid=` | 404 |
| `/x/web/data/pandora?aid=` | 404 |
| `/x/web/data/v2/pandora?type=2&aid=` | 404 |
| `/x/web/data/v2/archive/retention?aid=` | 404 |
| `/x/web/data/archive/retention?aid=` | 404 |
| `/x/web/data/v2/archive/trend?aid=` | 404 |
| `/x/web/data/archive/analysis?aid=` | 404 |
| `/x/web/data/archive/detail?aid=` | 404 |
| `/x/web/data/v2/archive/base/v2?aid=` | 404 |
| `/x/web/data/playanalysis?aid=&type=1` | 200 / `code=-400 请求错误` |
| `/x/web/data/base?aid=` | 200，但只返回 `period`/`viewer_area`/`viewer_base`，无单集指标 |

## 4 · 非 S1 对照（不参与均值，仅作量级参照）

同账号另外 5 条已发布视频，说明 S1 的播放/收藏量级不是接口问题，是内容早期状态：

| BV | 视频 | 时长 | 播放 | 收藏 | 收藏率 | rate 口径 | 平均观看 |
|---|---|---|---|---|---|---|---|
| BV1z6sU6iEDX | dsh-ydesk 原理拆解 | 1:08 | 87 | 0 | 0.00% | 40.04% | 27s |
| BV1nZsP6jEds | 把 TCP 塞进 ping 里 | 1:06 | 38 | 0 | 0.00% | 45.84% | 30s |
| BV1Pth66NEs3 | 不会聊天的模型 Jev | 1:14 | 22 | 1 | 4.55% | 31.55% | 23s |
| BV1Ui4y1X7CW | 我的 2021 奇幻冒险 | 0:34 | 2 | 0 | 0.00% | 60.29% | 20s |
| BV1H5411H7hU | 2020 时光机 | 0:57 | 2 | 0 | 0.00% | 30.70% | 17s |

带 `rate` 口径的短对照（1:06–1:14）明显高于 S1 六集（1:53–4:07）——与「越短越容易留人」一致，但样本仅 5 条，不足以当结论用。

## 5 · 复现

```bash
cd /Users/cyx/repo/yvideo/projects/dsh-anatomy/analytics
python3 _fetch_public.py    # 公开指标（无 Cookie）→ _public_raw.json
python3 _fetch_member.py    # 后端指标（只读复用登录态）→ _member_raw.json
python3 _build_baseline.py  # 合并算聚合 → s1-baseline.json
```

`_probe.py` / `_probe2.py` 是当初找接口的一次性探针，留着供复核，正常流程不用跑。
