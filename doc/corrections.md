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
| 2026-11-28 | 两个工程的 `tools/` 已分叉（`voice_build.py` 两份 DIFF） | 工具没有单一实现，复制即漂移 | `待办`：合并为仓库级 `tools/`，各项目引用同一份 |
| 2026-11-28 | README 交付表曾停在 EP06，而 EP07 已发布 | 人工回填表格 | `待办`：以 `publish/epNN/result.json` 为权威，表格自动生成 |
| 2026-11-28 | 连续跑两次 `hyperframes check` 出现一次 `Check failed`，紧接着两次都 passed | 疑似 `.hyperframes` 状态并发写 | `待办`：确认是否可复现；必要时给 check 加锁或串行化 |
