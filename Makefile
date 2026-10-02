.PHONY: run run-local build selfcheck eval test lint stop logs clean dev
run run-local build selfcheck eval test lint stop logs clean dev:
	$(MAKE) -C track_2a $@
