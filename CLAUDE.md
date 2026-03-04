# Leerio — Audiobook Library Manager

Personal audiobook library with Trello integration, web UI, and TUI.

## Project Structure

```
server/          Python backend (FastAPI)
  core.py        Business logic, data persistence, Trello client
  api.py         REST API endpoints
  metadata.py    Cover art and ID3 tag management
  Dockerfile     Production container
  requirements.txt

app/             Vue 3 frontend (TypeScript + Tailwind)
  src/           Components, views, composables
  Dockerfile     Multi-stage build (node + nginx)
  nginx.conf     SPA routing + API proxy

landing/         Static coming-soon page (served by Caddy at leerio.app)
  index.html     Landing page with email waitlist
  style.css      Dark theme styles

data/            Runtime data files (gitignored, volume-mounted)
  config.json    Trello API keys
  history.json   Action log
  tracker.csv    Book catalog from Trello
  ...            Other JSON data files

books/           Audiobook files (gitignored, volume-mounted)
  Бизнес/
  Отношения/
  Саморазвитие/
  Художественная/
  Языки/

_library.py      Local TUI wrapper (imports from server.core)
```

## Running Locally

### Backend
```bash
pip install -r server/requirements.txt
uvicorn server.api:app --reload
# or: make server-dev
```

### Frontend
```bash
cd app && npm install && npm run dev
# or: make app-dev
```

### TUI
```bash
pip install rich InquirerPy requests
python _library.py          # interactive menu
python _library.py status   # quick status
```

### Docker
```bash
docker compose up --build
# or: make docker-up
```

## Environment Variables

- `LEERIO_BASE` — project root (default: auto-detected)
- `LEERIO_DATA` — data directory (default: `$BASE/data`)
- `LEERIO_BOOKS` — books directory (default: `$BASE/books`)
- `LEERIO_LOG_LEVEL` — Python logging level (default: `INFO`)
- `CORS_ORIGINS` — comma-separated allowed origins (default: `http://localhost:5173,http://localhost:80`)

## Key Conventions

- All data paths are in `server/core.py`, resolved via env vars
- Book folder format: `Author - Title [Reader]`
- Cyrillic names throughout (UI labels, categories, statuses)
- Data files use atomic writes (`_safe_json_write`) to prevent corruption
- API prefix: `/api/` — all endpoints under this path
- Frontend proxies `/api/` to backend in both dev (vite proxy) and prod (nginx)
- Path alias `@/` maps to `src/` in frontend (tsconfig + vite)
- Backend uses Python `logging` module (logger name: `leerio`), not `print()` — including `metadata.py` (`leerio.metadata`)
- CORS: env-based origins via `CORS_ORIGINS`; global exception handler logs unhandled errors
- Root `.dockerignore` excludes `.git`, tests, caches from server build context
- Node version pinned: `app/.nvmrc` (20) + `engines.node` in `package.json`

## Dev Workflow

### First-time setup
```bash
make setup   # installs deps, enables pre-commit hooks
```

### Linting & formatting
```bash
make lint      # ruff check + eslint (both projects)
make format    # ruff format + prettier (auto-fix)
make test      # pytest + vitest
make check     # full suite: lint + test + vue-tsc type check
```

### Individual targets
```bash
make server-lint    # ruff check + format check
make server-format  # ruff fix + format
make app-lint       # eslint src/
make app-format     # prettier --write src/
```

### Testing
```bash
make test          # run all tests with coverage (pytest + vitest)
make server-test   # pytest --cov=server
make app-test      # vitest --coverage
```

- **Python tests**: `server/tests/` — run with `pytest` (pytest-cov for coverage)
  - `test_core.py` — pure function smoke tests
  - `test_api.py` — API endpoint tests via TestClient (uses temp dirs via conftest.py)
- **Frontend tests**: `app/src/**/*.test.ts` — run with `vitest` (@vitest/coverage-v8)
- Dev dependencies: `server/requirements-dev.txt` (extends requirements.txt)
- Coverage config: `pyproject.toml` (Python), `app/vite.config.ts` (frontend)
- Coverage thresholds enforced: Python 30% (`fail_under`), frontend 3% lines (`thresholds`) — raise as coverage improves

### Git hooks
Runs automatically on `git commit` (after `make setup`):
1. **pre-commit**: staged-file-only checks — `ruff check` + `ruff format --check` (Python), `eslint` + `prettier --check` + `vue-tsc --noEmit` (frontend); skips languages with no staged files
2. **commit-msg**: commitlint — enforces [Conventional Commits](https://www.conventionalcommits.org/) format (e.g. `feat: add search`, `fix: handle null`)

### Config files
- `pyproject.toml` — ruff config (Python linting/formatting)
- `app/eslint.config.js` — ESLint flat config (Vue 3 / TypeScript)
- `app/.prettierrc` — Prettier config (formatting)
- `app/commitlint.config.js` — commit message linting (conventional commits)
- `app/.nvmrc` — Node version for `nvm use`

## Deployment

Push to `main` triggers GitHub Actions (single `ci.yml` workflow):
1. CI: lint (ruff + eslint + prettier), test (pytest + vitest), type-check + build (vue-tsc + vite)
2. Deploy: gated on CI success (`needs: [server-lint, app-build]`), SSH to VPS, git pull, docker compose up --build, health check via `https://app.leerio.app` with retry (3 attempts), auto-rollback on failure

### Production Architecture

```
Internet -> Caddy (:80/:443)
              |
              ├── leerio.app       -> static landing page (/srv/landing)
              └── app.leerio.app   -> nginx/app (:80) -> FastAPI/server (:8000)
                                      SPA + /api/ proxy    Business logic
```

- **Domain split**: `leerio.app` serves a static coming-soon landing page; `app.leerio.app` serves the Vue SPA + API
- **Caddy** handles HTTPS automatically (Let's Encrypt auto-cert/renew, HTTP->HTTPS redirect)
- Only Caddy exposes host ports (80, 443); server/app are internal-only
- `Caddyfile` at project root — two site blocks: `leerio.app` (file_server) + `app.leerio.app` (reverse_proxy)
- `landing/` directory mounted read-only into Caddy container at `/srv/landing`
- `env_file: .env` on server service loads Trello keys + `CORS_ORIGINS`
- Caddy data/config persisted via named Docker volumes (`caddy_data`, `caddy_config`)

### Dev vs Production

- `docker-compose.override.yml` re-exposes dev ports (8000, 5173) and disables Caddy via `profiles: ["production"]`
- Local `docker compose up` = dev mode (no Caddy, direct port access)
- Production VPS has no override file — Caddy runs by default

### Docker
- Server service has a healthcheck (`curl /api/config/constants`, 30s interval)
- App (nginx) service has a healthcheck (`wget localhost:80`, 30s interval)
- App depends on server via `condition: service_healthy`; Caddy depends on app
- Nginx serves gzip-compressed static assets (CSS, JS, JSON, SVG)
- Nginx has HSTS, Content-Security-Policy, and other security headers
- Nginx trusts Docker network IPs for `X-Forwarded-For` (real client IP from Caddy)
- App Dockerfile runs `vue-tsc --noEmit` before build (catches type errors in Docker builds)
- Root `.dockerignore` keeps build context lean (excludes `.git`, tests, `node_modules`, data)
- CI uses concurrency groups — new pushes cancel stale in-progress runs
- Python `requires-python = ">=3.12"` in `pyproject.toml`
