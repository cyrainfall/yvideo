# yvideo — 全系列工作区（一集一工程）
#
# 层级：仓库根 = 全系列共享（tools/、templates/、doc/、SERIES 大纲）
#        projects/<epNN-标题>/ = 一集的全套内容
#
# 别在这里加"重建一条链"——那在每一集自己的 Makefile 里。这里只管跨集的事。

SHELL := /bin/bash
EP    ?=
TITLE ?=
APPLY ?=

.PHONY: help new-episode verify-all check-docs list gc

help:
	@echo "make new-episode EP=08 TITLE=接缝   从模板生成一集新工程"
	@echo "make check-docs                     文档里抄的代码常量是否与代码一致（TTS 端点等）"
	@echo "make verify-all                     跑所有活跃工程的闸门（无 Makefile 的自动跳过）"
	@echo "make list                           列出工程与状态"
	@echo "make gc                             体检：各类可重建物的大小与重建代价（默认只报告）"
	@echo "make gc APPLY=safe                  真删（safe / safe,cache / safe,derived）"

new-episode:
	@test -n "$(EP)"    || { echo "用法：make new-episode EP=08 TITLE=接缝"; exit 1; }
	@test -n "$(TITLE)" || { echo "缺 TITLE：make new-episode EP=08 TITLE=接缝"; exit 1; }
	@python3 tools/new_episode.py --ep "$(EP)" --title "$(TITLE)"

# 文档与代码的分歧不会自己消失：文档写一个世界，代码跑另一个世界，只有新人会被骗。
# 2026-11-28 定：冲突时以代码为准；这里让机器盯着那几处"文档抄了代码常量"的地方。
check-docs:
	@python3 tools/doc_facts.py

verify-all: check-docs
	@fail=0; for d in projects/*/; do \
	  if [ -f "$$d/Makefile" ]; then \
	    echo "── $$d"; \
	    ( cd "$$d" && make verify ) || fail=1; \
	    ( cd "$$d" && make review-check ) || fail=1; \
	  else \
	    echo "── $$d （无 Makefile，跳过）"; \
	  fi; \
	done; \
	if [ $$fail -ne 0 ]; then echo "✗ 有工程未通过"; exit 1; fi; \
	echo "✓ 所有活跃工程通过（含验收包未过期、文档常量与代码一致）"

list:
	@for d in projects/*/; do \
	  if [ -f "$$d/Makefile" ]; then st="活跃"; else st="冻结/归档"; fi; \
	  printf "  %-42s %s\n" "$$d" "$$st"; \
	done

# 体检与清理。默认只报告——"可重建"不等于"该删"，删掉 .takes 要重配 53 句音，
# 删掉 renders 要重渲 10 分钟。工具会把代价一起打出来，再让你决定。
gc:
	@python3 tools/gc.py $(if $(APPLY),--apply $(APPLY),)
