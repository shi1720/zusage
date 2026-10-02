# Zusage — Apertus-powered interview coach for Swiss apprenticeship seekers.
#
#   make run         build + start the app in Docker, then prove it works end to end
#                    (scripted interview over HTTP: start → answers → report → budget check)
#   make run-local   same, plus a local Apertus 1.5 8B (llama.cpp) — no external calls at runtime
#   make eval        evaluation harness (calibration, consistency, judge) inside the container
#   make test        backend + frontend tests (local toolchain)
#   make stop / logs / clean
#
# Configure the model in .env (copied from .env.example on first run):
#   LLM_NAME, LLM_BASE_URL, LLM_API_KEY   — empty LLM_BASE_URL = offline demo coach

SHELL := /bin/bash
PORT ?= 8080
URL := http://localhost:$(PORT)
IMAGE := zusage:latest
NAME := zusage
# `make run` uses plain `docker` only (no compose plugin needed) for maximum portability.
COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

.PHONY: run run-local stop logs selfcheck eval test lint dev clean build

.env:
	@cp .env.example .env
	@echo "→ created .env from .env.example (add LLM_BASE_URL / LLM_API_KEY for Apertus)"

build:
	docker build -t $(IMAGE) .

run: .env build
	-@docker rm -f $(NAME) >/dev/null 2>&1
	docker run -d --name $(NAME) --env-file .env -p $(PORT):8080 -v zusage-data:/app/var $(IMAGE)
	@echo "→ waiting for Zusage to become healthy…"
	@for i in $$(seq 1 60); do curl -fs $(URL)/api/health >/dev/null 2>&1 && break; sleep 2; done
	docker exec $(NAME) zusage selfcheck --url http://127.0.0.1:8080
	@echo ""
	@echo "  ✓ Zusage is running →  $(URL)"
	@echo "    One-click demo: 'Try as student' (Lea) or 'Try as teacher' (Frau Meier, class code CHUR26)"
	@echo "    Logs: make logs   ·   Stop: make stop"

run-local: .env
	LLM_BASE_URL=http://apertus:8000/v1 LLM_API_KEY=local $(COMPOSE) --profile local-llm up --build -d
	@echo "→ first start downloads the Apertus GGUF (~5 GB) — this can take a while"
	@for i in $$(seq 1 600); do curl -fs http://localhost:8000/health >/dev/null 2>&1 && break; sleep 3; done
	@for i in $$(seq 1 60); do curl -fs $(URL)/api/health >/dev/null 2>&1 && break; sleep 2; done
	$(COMPOSE) exec -T zusage zusage selfcheck --url http://127.0.0.1:8080
	@echo "  ✓ Zusage + local Apertus running →  $(URL)"

selfcheck:
	docker exec $(NAME) zusage selfcheck --url http://127.0.0.1:8080

eval: .env build
	mkdir -p data/eval/results-latest
	docker run --rm --env-file .env -v "$(CURDIR)/data/eval/results-latest:/out" $(IMAGE) zusage eval --out /out

stop:
	-docker rm -f $(NAME)
	-$(COMPOSE) --profile local-llm down 2>/dev/null

logs:
	docker logs -f --tail=100 $(NAME)

clean: stop
	-docker volume rm zusage-data

# --- local development (needs Python 3.11+ with uv, Node 22) ---------------
test:
	cd src/backend && uv run --extra dev pytest -q
	cd src/frontend && npm test

lint:
	cd src/backend && uv run --extra dev ruff check zusage tests
	cd src/frontend && npx tsc --noEmit

dev:
	cd src/backend && uv run uvicorn zusage.main:create_app --factory --reload --port 8000 & \
	cd src/frontend && npm run dev
