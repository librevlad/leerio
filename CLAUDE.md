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

## Key Conventions

- All data paths are in `server/core.py`, resolved via env vars
- Book folder format: `Author - Title [Reader]`
- Cyrillic names throughout (UI labels, categories, statuses)
- Data files use atomic writes (`_safe_json_write`) to prevent corruption
- API prefix: `/api/` — all endpoints under this path
- Frontend proxies `/api/` to backend in both dev (vite proxy) and prod (nginx)

## Dev Workflow

### First-time setup
```bash
make setup   # installs deps, enables pre-commit hooks
```

### Linting & formatting
```bash
make lint      # ruff check + eslint (both projects)
make format    # ruff format + prettier (auto-fix)
make check     # full suite: lint + vue-tsc type check
```

### Individual targets
```bash
make server-lint    # ruff check + format check
make server-format  # ruff fix + format
make app-lint       # eslint src/
make app-format     # prettier --write src/
```

### Pre-commit hook
Runs automatically on `git commit` (after `make setup`):
1. `ruff check server/` + `ruff format --check server/`
2. `vue-tsc --noEmit` (TypeScript type check)

### Config files
- `pyproject.toml` — ruff config (Python linting/formatting)
- `app/eslint.config.js` — ESLint flat config (Vue 3 / TypeScript)
- `app/.prettierrc` — Prettier config (formatting)

## Deployment

Push to `main` triggers GitHub Actions:
1. CI: lint server (ruff check + format), lint app (eslint), type-check + build app (vue-tsc + vite)
2. Deploy: SSH to VPS, git pull, docker compose up --build
