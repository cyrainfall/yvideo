# 纠正账本

> 这张表是整个工作区唯一会"自我进化"的地方。
> 机制来自《把 slop 炼成黄金》：**每次纠正 agent，先问能不能变成一次确定性检查；不能，才允许写进散文。**

## 怎么用

每踩一次坑，当场记一行。每集收尾扫一遍：**「固化形态」还空着的，就是下一个闸门。**

| 固化形态 | 含义 |
|---|---|
| `G-R*` | 已变成 `tools/en_check.py` 的规则（读法） |
| `G-♪` | 已变成 `tools/polyphone_check.py` 的复听档 |
| `架构` | 已改成结构（依赖图、目录契约），不再需要人记 |
| `待办` | 还没固化——**这是技术债，不是已经解决** |
| `文档` | 只能写进散文（判断力/审美，无法自动化） |

---

## 账本

| 日期 | 症状 | 根因 | 固化形态 |
|---|---|---|---|
| 2026-11-28 | 旁白里 `ctx` → "cats"、`PENDING` → "pinned in ding ding"、`browserUse` → "berber use" | 读法规则只活在 `voice/读法规则.md` 的表格里，靠人/agent 记性执行 | `G-R2/R3/R4/R5`：`voice/lexicon.json` + `en_check.py` 强制，selftest 兜底 |
| 2026-11-28 | 「接缝」「重写」「重名」读错，但 ASR 完全听不出（只回写规范汉字） | TTS 无拼音门控；声调差异 ASR 不可见 | `G-♪`：polyphone 三档（`!` 阻断 / `·` 提示 / `♪` 复听），`make listen` 直接给时间点 + 试听命令 |
| 2026-11-28 | 改一句文案要"从 1 重跑到 3"，README 反复写「必须」「否则错位」 | 流程顺序靠记性，不在结构里 | `架构`：Makefile 依赖图 `captions → timing → narrate`、`render → verify` |
| 2026-11-28 | 两个工程的 `tools/` 已分叉（`voice_build.py` 两份 DIFF） | 工具没有单一实现，复制即漂移 | `架构`：仓库根 `tools/` 单一实现（ROOT 跟随 cwd），`dsh-anatomy` 已切过来；`dsh-ydesk-explainer` 冻结为旧副本 |
| 2026-11-28 | README 交付表曾停在 EP06，而 EP07 已发布 | 人工回填表格 | `待办`：以 `publish/epNN/result.json` 为权威，表格自动生成 |
| 2026-11-28 | 改稿后漏跑 `timing.py`、或手改 `index.html` 的 `data-duration`，字幕与时间轴静默错位（成片才发现） | 五条不变量只写在 README 散文里，漏跑不报错 | `G1–G5`：`tools/gate_chain.py`，`make chain` 已接进 `make verify` |
| 2026-11-28 | `hyperframes check` 约 5 次红 1 次：报 7 条 `dead_stretch`，时间区间正好覆盖**每一帧的整段**（0.00–30.10、30.54–68.17…），同批 `runtime` 也多出 2 条 | **不是画面真静止**。分析器在该会话里没看到子组合时间线（动画未注册/未加载），于是把每帧判成全程静止；重跑即恢复 | `架构`：`make check` 首次红自动复跑并打印告警；`make check-full`（`--no-cache`）拿准信。**判别特征：全帧均匀报警＝分析失败，单帧静置＝真内容问题** |
| 2026-11-28 | 两个工程的工具已分叉，且「一集一工程」需要共享 tools | 工具锚在工程目录 | `架构`：tools 上移 + 模板化（`templates/episode/` + `make new-episode`） |
| 2026-11-28 | EP07 已发布后仍被 `dead_stretch` 报警，是否要改已上线成片 | 报警本身是分析失败（见上一行） | `文档`：决定 B —— **不动已发布成片**；把判别特征写进模板，EP08 起在 verify 阶段处理真静置 |
| 2026-11-28 | 新脚手架被自己的多音字闸门判红：`polyphone_check` 把帧外的说明文字当旁白扫 | 与 `en_check` 的"只扫帧内叙事行"口径不一致 | `G`：`polyphone_check` 加 `frame == 0` 跳过，两边口径统一 |
| 2026-11-28 | `make verify-all` 输出的中文出现乱码、`$$d` 变量为空 | Makefile 里 `$$变量` 紧跟全角括号时，make 吞掉多字节首字节 | `文档`：写成 `$$d （无`（留空格）；已记入 MAP 已知坑 |
| 2026-11-28 | `caption-overrides.json` 只写不读，且每次 `make captions` 都会把它重置成 `[]`——手填的覆盖会被静默清掉 | 占位实现忘了接消费方 | `架构`：删除该写入与文件；要真做覆盖，先实现读取再开放入口 |
| 2026-11-28 | 「生成物禁止手改」只写在 AGENTS 的一行表格里；G1–G5 查的是一致性，人改完只要自洽就全绿，改错层完全不可见 | 只有约定，没有强制 | `G6`：`tools/gen_manifest.py` 边车指纹（自身内容 / 上游 / 生成器），接进 `make chain`；手改与漏跑分别报错并指名下一步 |
| 2026-11-28 | `make listen` 无端报「voice_takes.json 比 SCRIPT.md 旧」并退出 3，而两个文件内容一个字都没变 | 新鲜度用 **mtime** 判：`git checkout` / `cp` 恢复文件会把时间戳改新；反过来 `cp -p` 保留旧时间戳时，真落后又能蒙过去 | `G`：`en_check.stale()` 与 `gate_chain` G2 改成**内容判据**（逐帧旁白 / (帧号, 路径, 时长) 投影）；「生成器改了没重跑」交给 G6 的 `tool_sha` 提示，时钟不再参与判据 |
| 2026-11-28 | 字幕语速把 `bash-local` 记成 10 个字，于是正常的一行被标成「8.3 字/秒 读不完」 | 度量口径错：按字符数算，拉丁词按字母膨胀 | `架构`：`review_build.py` 改用**音节当量/秒**（汉字 1、一个拉丁词 1），阈值 6；错的是度量不是字幕 |
| 2026-11-28 | 「这一集能不能发」只有 `make verify` 的绿灯，画面/语速/读音仍要人去翻终端和记忆 | 机器能判的都进了闸门，人才能判的没有落点 | `架构`：`make review` → `renders/epNN-review/`（REVIEW.md + 抽帧 + 切点条 + 波形 + 时长账 + 复听表 + checks.txt + manifest 指纹），`make review-check` 判过期，接进 `make verify-all` |
| 2026-11-28 | G6 上线后，两份 Makefile 的 help 与 README 仍写「链路 G1–G5」，`START-EPISODE` 仍写「5 条链路不变量」 | 加闸门时只改了代码和自己的说明，没扫全仓引用 | `文档`：加闸门时必须 `grep` 旧编号；已全仓校正为 G1–G6 |
