# 拆开 DSH — 单集重建链
#
# 设计原则：散文里能写成命令的，就别留在 README 里。
# 一切"别忘了"都应该是依赖或闸门，而不是一句提醒。

SHELL := /bin/bash
EP    ?= ep07
HF    := node $(HOME)/.agents/skills/hyperframes/scripts/plugin-cli.mjs
MODE  ?= line
# 仓库级共享工具：一集一工程，tools/ 只有一份（在仓库根）
TOOLS ?= ../../tools

.PHONY: help verify readonly chain narrate timing captions listen asr check preview render

help:
	@echo "make verify    全部闸门：读法 + 多音字 + 生成物新鲜度 + hyperframes check"
	@echo "make readonly  只跑静态闸门（秒级，改稿时反复用）"
	@echo "make chain     链路一致性 G1–G5（旁白覆盖/新鲜度/音轨/帧时长/时间轴）"
	@echo "make narrate   合成旁白（按句缓存，改一句只重配一句）"
	@echo "make timing    重算词级时间（改了文案必须跑）"
	@echo "make captions  重建字幕（内含 audio_meta 新鲜度保护）"
	@echo "make listen    交付前复听清单（多音字无法自动判定，只能靠耳朵）"
	@echo "make check     hyperframes lint + runtime + layout + motion + contrast"
	@echo "make preview   起后台预览（Studio 交接用）"
	@echo "make render    渲染成片（前置 verify 必须通过）  EP=ep07"
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

chain:
	@echo "── 链路一致性（G1–G5）"
	@python3 $(TOOLS)/gate_chain.py --strict

## ── 重建链 ────────────────────────────────────────────
narrate:
	python3 $(TOOLS)/voice_build.py

timing: narrate
	python3 $(TOOLS)/timing.py

captions: timing
	python3 $(TOOLS)/captions_build.py --mode $(MODE)

## ── 交付 ──────────────────────────────────────────────
listen:
	@python3 $(TOOLS)/polyphone_check.py
	@echo ""
	@python3 $(TOOLS)/en_check.py --list

asr:
	@python3 $(TOOLS)/en_check.py --asr

check:
	@$(HF) check

preview:
	@$(HF) preview --background
	@$(HF) preview --status

render: verify
	@$(HF) render --quality high --output renders/$(EP).mp4
