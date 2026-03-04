.PHONY: help dev server-dev app-dev docker-up docker-down docker-logs lint format check build setup \
       server-lint server-format app-lint app-format test server-test app-test type-check clean

.DEFAULT_GOAL := help

# ── Help ────────────────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ── Development ──────────────────────────────────────────────────────────────

dev: server-dev ## Start backend dev server

server-dev: ## Backend dev server (uvicorn --reload)
	uvicorn server.api:app --reload --host 0.0.0.0 --port 8000

app-dev: ## Frontend dev server (vite)
	cd app && npm run dev

# ── Docker ───────────────────────────────────────────────────────────────────

docker-up: ## Build and start containers
	docker compose up --build -d

docker-down: ## Stop containers
	docker compose down

docker-logs: ## Tail container logs
	docker compose logs -f

# ── Linting ──────────────────────────────────────────────────────────────────

lint: server-lint app-lint ## Lint both projects

server-lint: ## Ruff check + format check
	ruff check server/
	ruff format --check server/

app-lint: ## ESLint + Prettier check
	cd app && npx eslint src/
	cd app && npx prettier --check src/

# ── Formatting ───────────────────────────────────────────────────────────────

format: server-format app-format ## Auto-fix formatting

server-format: ## Ruff fix + format
	ruff check --fix server/
	ruff format server/

app-format: ## Prettier write
	cd app && npx prettier --write src/

# ── Testing ──────────────────────────────────────────────────────────────────

test: server-test app-test ## Run all tests with coverage

server-test: ## Pytest with coverage
	pytest --cov=server

app-test: ## Vitest with coverage
	cd app && npx vitest run --coverage

# ── Full check (same as pre-commit) ─────────────────────────────────────────

type-check: ## Vue TypeScript type check
	cd app && npx vue-tsc --noEmit

check: lint test type-check ## Full suite: lint + test + type check

# ── Build ────────────────────────────────────────────────────────────────────

build: ## Production build (frontend)
	cd app && npm run build

# ── Setup ────────────────────────────────────────────────────────────────────

setup: ## First-time setup: deps + git hooks
	git config core.hooksPath .githooks
	pip install -r server/requirements-dev.txt
	cd app && npm install
	@echo "Done. Pre-commit and commit-msg hooks enabled."

# ── Cleanup ──────────────────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
	rm -rf app/dist app/coverage
