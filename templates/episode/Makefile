# 拆开 DSH — 单集重建链（__EP__《__TITLE__》）
#
# 一集一工程：本目录是这一集的全部内容；生成物在 .gitignore 里，源文件入库。
# 共享工具在仓库根 tools/，由 TOOLS 指向。
#
# 设计原则：散文里能写成命令的，就别留在 README 里。
# 一切"别忘了"都应该是依赖或闸门，而不是一句提醒。

SHELL := /bin/bash
EP    ?= __EP__
HF    := node $(HOME)/.agents/skills/hyperframes/scripts/plugin-cli.mjs
MODE  ?= line
# 仓库级共享工具：一集一工程，tools/ 只有一份（在仓库根）
TOOLS ?= ../../tools

.PHONY: help verify readonly chain narrate timing index frames captions listen asr check check-full preview render review review-check delivery

help:
	@echo "make verify    全部闸门：读法 + 多音字 + 链路 G1–G6 + hyperframes check"
	@echo "make readonly  只跑静态闸门（秒级，改稿时反复用）"
	@echo "make chain     链路一致性 G1–G6（旁白/新鲜度/音轨/帧时长/时间轴/生成物指纹）"
	@echo "make narrate   合成旁白（按句缓存，改一句只重配一句）"
	@echo "make timing    重算词级时间（改了文案必须跑）"
	@echo "make index     重建 index.html 时间轴（依赖 timing）"
	@echo "make frames    按旁白帧数铺 frame-NN.html 骨架，并校准每帧 DUR"
	@echo "make captions  重建字幕（依赖 index，含 audio_meta 新鲜度保护）"
	@echo "make listen    交付前复听清单（多音字无法自动判定，只能靠耳朵）"
	@echo "make check     hyperframes lint + runtime + layout + motion + contrast（增量，秒级）"
	@echo "make check-full 同上但 --no-cache 全量分析（慢，交付前跑一次）"
	@echo "make preview   起后台预览（Studio 交接用）"
	@echo "make render    渲染成片（前置 verify 必须通过）  EP=ep07"
	@echo "make review    验收包：画面/时长/字幕/波形/复听 → renders/$(EP)-review/（给人判）"
	@echo "make review-check  验收包是否还描述着当前这一版（改稿或重渲后过期）"
	@echo "make delivery  交付表对账全表（含「本地成片与表内时长不同」这类提示）"
	@echo ""
	@echo "改一句文案的正确顺序：make narrate && make timing && make captions && make verify"

## ── 闸门 ──────────────────────────────────────────────
verify: readonly chain check
	@echo "✓ 全部闸门通过"

readonly:
	@echo "── 读法闸门（英文标识符 / 缩写 / 驼峰 / 点号）"
	@python3 $(TOOLS)/en_check.py --strict
	@echo "── 多音字闸门（需改写项阻断，必用词进复听清单）"
	@python3 $(TOOLS)/polyphone_check.py --strict
	@echo "── 规则自检（改了 lexicon.json 就跑这个）"
	@python3 $(TOOLS)/en_check.py --selftest
	@echo "── 交付表对账（README「已交付」 vs publish/epNN/result.json）"
	@python3 $(TOOLS)/delivery_table.py

chain:
	@echo "── 链路一致性（G1–G6）"
	@python3 $(TOOLS)/gate_chain.py --strict

## ── 重建链 ────────────────────────────────────────────
narrate:
	python3 $(TOOLS)/voice_build.py

timing: narrate
	python3 $(TOOLS)/timing.py

# index.html 是 G5 的检查对象，必须由它自己的身体生成，不能手改。
index: timing
	python3 $(TOOLS)/index_build.py

# 按旁白帧数铺 frame-NN.html（不覆盖已有画面，只校准每帧 DUR）
frames: index
	python3 $(TOOLS)/frames_scaffold.py

captions: index
	python3 $(TOOLS)/captions_build.py --mode $(MODE)

## ── 交付 ──────────────────────────────────────────────
listen:
	@python3 $(TOOLS)/polyphone_check.py
	@echo ""
	@python3 $(TOOLS)/en_check.py --list

asr:
	@python3 $(TOOLS)/en_check.py --asr

# hyperframes check 已知非确定性（约 5 次红 1 次，疑与负载下的时间轴采样有关）：
# 首次红就复跑一次并**明确打印**，避免 agent 把偶发红灯当成噪音而无视。
check:
	@$(HF) check || { \
	  echo "⚠ check 首次失败：已知 flaky（见 doc/corrections.md），复跑一次以区分偶发与真失败"; \
	  $(HF) check; \
	}

# 全量分析：不走缓存。慢（负载抖动时 10 分钟以上），交付/发布前跑一次。
check-full:
	@$(HF) check --no-cache

preview:
	@$(HF) preview --background
	@$(HF) preview --status

# 验收包：把「这一集能不能发」压成一个人 3 分钟能判完的目录（画面 / 时长 / 字幕 / 波形 / 复听）。
# 为何不进 make verify：改稿循环里每改一句就逼你重建 40s 的包，人一定会绕过它。它属于交付动作。
review: verify
	@python3 $(TOOLS)/review_build.py --ep $(EP)

# 验收包是否还描述着当前这一版（改了文案、或重渲了成片，就会过期）。
review-check:
	@python3 $(TOOLS)/review_build.py --check --ep $(EP)

# 「已交付」表只读对账：谁发布了、bvid 对不对、成片和归档还在不在。只报不改。
delivery:
	@python3 $(TOOLS)/delivery_table.py --report

render: verify
	@$(HF) render --quality high --output renders/$(EP).mp4
