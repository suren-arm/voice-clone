# Convenience targets. Everything here is a plain command you can also run by
# hand -- see README.md for the unabbreviated versions.

.PHONY: help install backend frontend test test-backend test-frontend e2e lint format \
        download-model benchmark docker docker-gpu clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install backend (dev) and frontend dependencies
	cd backend && python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd frontend && npm install

backend: ## Run the API with hot reload on :8000
	cd backend && uvicorn app.main:app --reload --port 8000

frontend: ## Run the web app on :3000
	cd frontend && npm run dev

test: test-backend test-frontend ## Run every fast test

test-backend: ## pytest (mock engine, no weights)
	cd backend && VOICE_ENGINE=mock pytest

test-ai: ## pytest against the real model (downloads weights, needs a GPU)
	cd backend && pytest -m ai tests/ai

test-frontend: ## vitest unit tests
	cd frontend && npm run test:run

e2e: ## Playwright end-to-end tests
	cd frontend && npm run test:e2e

lint: ## ruff + eslint + tsc
	cd backend && ruff check . && ruff format --check .
	cd frontend && npm run lint && npm run typecheck

format: ## Auto-fix formatting
	cd backend && ruff format . && ruff check --fix .
	cd frontend && npm run lint -- --fix

download-model: ## Pre-fetch Chatterbox weights into the HF cache
	python scripts/download_model.py

benchmark: ## Measure load time, conditioning time and RTF
	python scripts/benchmark.py --engine chatterbox --variant multilingual

docker: ## Build and run the CPU stack
	docker compose up --build

docker-gpu: ## Build and run the GPU stack
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build

clean: ## Remove caches and build output (keeps storage/ and model weights)
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf backend/.pytest_cache backend/.ruff_cache .benchmark
	rm -rf frontend/.next frontend/coverage frontend/playwright-report frontend/test-results
