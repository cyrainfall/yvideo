# yvideo — 全系列工作区（一集一工程）
#
# 层级：仓库根 = 全系列共享（tools/、templates/、doc/、SERIES 大纲）
#        projects/<epNN-标题>/ = 一集的全套内容
#
# 别在这里加"重建一条链"——那在每一集自己的 Makefile 里。这里只管跨集的事。

SHELL := /bin/bash
EP    ?=
TITLE ?=

.PHONY: help new-episode verify-all list

help:
	@echo "make new-episode EP=08 TITLE=接缝   从模板生成一集新工程"
	@echo "make verify-all                     跑所有活跃工程的闸门（无 Makefile 的自动跳过）"
	@echo "make list                           列出工程与状态"

new-episode:
	@test -n "$(EP)"    || { echo "用法：make new-episode EP=08 TITLE=接缝"; exit 1; }
	@test -n "$(TITLE)" || { echo "缺 TITLE：make new-episode EP=08 TITLE=接缝"; exit 1; }
	@python3 tools/new_episode.py --ep "$(EP)" --title "$(TITLE)"

verify-all:
	@fail=0; for d in projects/*/; do \
	  if [ -f "$$d/Makefile" ]; then \
	    echo "── $$d"; \
	    ( cd "$$d" && make verify ) || fail=1; \
	  else \
	    echo "── $$d （无 Makefile，跳过）"; \
	  fi; \
	done; \
	if [ $$fail -ne 0 ]; then echo "✗ 有工程未通过"; exit 1; fi; \
	echo "✓ 所有活跃工程通过"

list:
	@for d in projects/*/; do \
	  if [ -f "$$d/Makefile" ]; then st="活跃"; else st="冻结/归档"; fi; \
	  printf "  %-42s %s\n" "$$d" "$$st"; \
	done
