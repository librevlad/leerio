.PHONY: dev server-dev app-dev docker-up docker-down lint format check build setup \
       server-lint server-format app-lint app-format

# ── Development ──────────────────────────────────────────────────────────────

dev: server-dev

server-dev:
	uvicorn server.api:app --reload --host 0.0.0.0 --port 8000

app-dev:
	cd app && npm run dev

# ── Docker ───────────────────────────────────────────────────────────────────

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

# ── Linting ──────────────────────────────────────────────────────────────────

lint: server-lint app-lint

server-lint:
	ruff check server/
	ruff format --check server/

app-lint:
	cd app && npx eslint src/

# ── Formatting ───────────────────────────────────────────────────────────────

format: server-format app-format

server-format:
	ruff check --fix server/
	ruff format server/

app-format:
	cd app && npx prettier --write src/

# ── Full check (same as pre-commit) ─────────────────────────────────────────

check: lint
	cd app && npx vue-tsc --noEmit

# ── Build ────────────────────────────────────────────────────────────────────

build:
	cd app && npm run build

# ── Setup ────────────────────────────────────────────────────────────────────

setup:
	git config core.hooksPath .githooks
	pip install -r server/requirements.txt
	pip install ruff
	cd app && npm install
	@echo "Done. Pre-commit hooks enabled."
