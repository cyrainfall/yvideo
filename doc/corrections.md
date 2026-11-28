# 纠正账本

> 这张表是整个工作区唯一会"自我进化"的地方。
> 机制来自《把 slop 炼成黄金》：**每次纠正 agent，先问能不能变成一次确定性检查；不能，才允许写进散文。**

## 怎么用

每踩一次坑，当场记一行。每集收尾扫一遍：**「固化形态」还空着的，就是下一个闸门。**

这条规则现在有闸门了——`make check-ledger`（`tools/corrections_ledger.py`）：

| 它判 | 它判不了 |
|---|---|
| 每行必须有「固化形态」，且标签认得 | **有没有漏记一整条纠正**（只有当时在场的人知道） |
| 不许留 `待办`：要么固化成检查，要么降级成 `文档` 并写清理由 | 一条规则写得对不对（判据本身要有红绿回归，见 `en_check --selftest`） |
| 行里点名的 `tools/*.py` 必须存在（防止"闸门记了、脚本改名了"的假固化） | 散文类（`文档`）写得够不够清楚 |

翻译：它保证**记了就得交代清楚**，不保证**一定会记**。

| 固化形态 | 含义 |
|---|---|
| `G-R*` | 已变成 `tools/en_check.py` 的规则（读法） |
| `G-♪` | 已变成 `tools/polyphone_check.py` 的复听档 |
| `架构` | 已改成结构（依赖图、目录契约），不再需要人记 |
| `待办` | 还没固化——**这是技术债，不是已经解决**；`make check-ledger` 会红 |
| `文档` | 只能写进散文（判断力/审美，无法自动化） |

---

## 账本

| 日期 | 症状 | 根因 | 固化形态 |
|---|---|---|---|
| 2026-11-28 | 旁白里 `ctx` → "cats"、`PENDING` → "pinned in ding ding"、`browserUse` → "berber use" | 读法规则只活在 `voice/读法规则.md` 的表格里，靠人/agent 记性执行 | `G-R2/R3/R4/R5`：`voice/lexicon.json` + `en_check.py` 强制，selftest 兜底 |
| 2026-11-28 | 「接缝」「重写」「重名」读错，但 ASR 完全听不出（只回写规范汉字） | TTS 无拼音门控；声调差异 ASR 不可见 | `G-♪`：polyphone 三档（`!` 阻断 / `·` 提示 / `♪` 复听），`make listen` 直接给时间点 + 试听命令 |
| 2026-11-28 | 改一句文案要"从 1 重跑到 3"，README 反复写「必须」「否则错位」 | 流程顺序靠记性，不在结构里 | `架构`：Makefile 依赖图 `captions → timing → narrate`、`render → verify` |
| 2026-11-28 | 两个工程的 `tools/` 已分叉（`voice_build.py` 两份 DIFF） | 工具没有单一实现，复制即漂移 | `架构`：仓库根 `tools/` 单一实现（ROOT 跟随 cwd），`dsh-anatomy` 已切过来；`dsh-ydesk-explainer` 冻结为旧副本 |
| 2026-11-28 | README 交付表曾停在 EP06，而 EP07 已发布 | 人工回填表格 | `G`：`tools/delivery_table.py` 对账（已发布没列 / bvid 不符 / 成片或归档不见了 → 红），接进 `make readonly`。**不代笔**：标题与括号注释是人的判断，机器只指出缺口 |
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
| 2026-11-28 | 「已交付」表 EP06 写 4:06.3，`renders/` 里那份是 4:09.0；平台回执 247s | 成片在**发布之后**被重渲过（文件 mtime 00:29 晚于发布 00:08），仓库里的渲染物和上线的那一版不再是一回事 | `文档`：表写发布那一版（发布事实），本地文件不改名不覆盖；`delivery_table.py` 把「本地成片与表内时长不同」报为提示而不是错误 |
| 2026-11-28 | 源和生成物平铺在工程根：`voice_takes.json`、`audio_meta.json`、`caption_groups.json` 与 `SCRIPT.md` 并排 | 「禁止手改」只是表格里的一句话；最近的编辑动作永远是改那个长得像数据的文件 | `架构`：生成物移到 `generated/`（`tools/paths.py` 成为布局的唯一答案），G7 检查根上有没有旧残留，`tools/migrate_layout.py` 幂等迁移。`index.html` 与 `compositions/captions.html` 因 HyperFrames 契约必须留原位，那两个仍只由 G6 兜 |
| 2026-11-28 | 新脚手架里 `make captions` 直接 FileNotFoundError：`generated/voice_takes.json` 写不进去 | 布局改了，但"那个目录还不存在"这件事没人管——老工程有目录，新工程没有 | `G`：`paths.py` 在 import 时 `GEN.mkdir(exist_ok=True)`。踩坑方式值得记：**改布局只在已有工程的路径上验证，新工程第一次跑就崩**，是 EP99 脚手架冒烟测试抓到的 |
| 2026-11-28 | `captions_build.check_freshness()` 还在用 mtime 判新旧，和当天早些时候修掉的 `en_check.stale()`、G2 是同一个误报源 | 修误报时只改了看到的两个副本，没 grep 全仓同类判据 | `G`：改成内容投影（帧号 / 路径 / 时长）。教训：**同一个错误在这个仓库里通常有 3 个副本**——修一处必须 grep 全仓 |
| 2026-11-28 | `frame-04/05.html` 里 8 条时间码注释与旁白起点差 0.24–0.69s（注释写 8.50s，那句旁白其实在 7.97s），tween 也跟着旧时点走 | 注释是人的备忘，改文案后整帧平移，没有任何东西会因为它过期而报警；`hyperframes check` 只查布局与动效，G1–G7 只查数据一致性 | `G8`：`tools/frame_anchors.py` 拿注释文字逐字对旁白（44 条可判锚点），偏 0.06s 即红；`--fix` 只改注释数字。已发布的 EP07 不改，8 条记进 `frame-anchors-allowlist.json` 明写理由 |
| 2026-11-28 | `doc/配音指导.md` 说「服务地址与 key 走 `TTS_URL` / `TTS_KEY`」，而 `tools/voice_build.py` 早就是硬编码 `127.0.0.1:8010`、无鉴权、用 `ref_audio` 克隆；`templates/episode` 里还写着 VoiceStudio `d38028e2` | 文档写一个世界、代码跑另一个世界，两边各自自洽，只有新来的人会被骗；这类分歧不会自己消失（挂了至少两轮没人定） | `G`：定规则**文档与代码冲突以代码为准**，按代码事实重写 §3.1/§6.1 与两份模板；`tools/doc_facts.py` 抓出文档里的端点与 `voice_build.ENDPOINT` 对账（`make check-docs`，进 `verify-all`） |
| 2026-11-28 | 纠正账本是整个工作区唯一自我进化的地方，但它自己没人管：可以漏记、可以记了不填「固化形态」、可以填 `待办` 永远不动，而没有任何东西会报警 | 「每次纠正变成一条检查」这个机制，唯一没被检查的就是它自己的产出 | `G`：`tools/corrections_ledger.py`（`make check-ledger`，进 `verify-all`）——每行必须有固化形态、不许 `待办`、点名的 `tools/*.py` 必须存在。它明写判不了「漏记」，只保证「记了就得交代清楚」 |
