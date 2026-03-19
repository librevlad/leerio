# Leerio — Audiobook Library Manager

SaaS audiobook library with Google OAuth, per-user data, web UI, and TUI.

## Project Structure

```
server/          Python backend (FastAPI)
  core.py        Business logic, data persistence, UserData class
  api.py         REST API endpoints (auth-protected)
  auth.py        Google OAuth token verification, JWT cookie management
  db.py          SQLite users database (users table, seed admin)
  metadata.py    Cover art and ID3 tag management
  migrate_to_multitenancy.py  One-time data migration script
  Dockerfile     Production container
  requirements.txt

app/             Vue 3 frontend (TypeScript + Tailwind)
  src/           Components, views, composables
  src/composables/useAuth.ts  Auth state, Google login, logout
  src/views/LoginView.vue     Google Sign-In page
  Dockerfile     Multi-stage build (node + nginx), accepts VITE_GOOGLE_CLIENT_ID build arg
  nginx.conf     SPA routing + API proxy + Google CSP

landing/         Static landing page (served by Caddy at leerio.app)
  index.html     Landing page with APK download + web app links
  style.css      Dark theme styles

data/            Runtime data files (gitignored, volume-mounted)
  config.json    App configuration
  leerio.db      SQLite users database
  users/         Per-user data directories
    {user_id}/   Each user's JSON files
      history.json, notes.json, tags.json, collections.json,
      progress.json, playback.json, quotes.json, sessions.json,
      book_status.json, bookmarks.json

books/           Audiobook files (gitignored, volume-mounted, shared read-only)
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

**Note:** Backend requires S3 credentials to complete startup (`sync_books()`). Without `S3_*` env vars, uvicorn hangs after "S3 not configured" warning. Test UI changes by deploying to production.

### Frontend
```bash
cd app && npm install && npm run dev
# or: make app-dev
```

Vite dev server must run from `app/` directory (`cd app && npx vite`), not project root.

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
- `GOOGLE_CLIENT_ID` — Google OAuth 2.0 Web Client ID (required for login)
- `JWT_SECRET` — random 64-char string for signing JWT tokens (required)
- `LEERIO_DEV` — set to `1` for local dev (disables secure cookie flag)
- `VITE_GOOGLE_CLIENT_ID` — frontend build arg (passed via docker-compose from `GOOGLE_CLIENT_ID`)
- `TTS_OPENAI_BASE_URL` — OpenAI-compatible TTS endpoint (e.g. `http://openedai-speech:8000/v1` or `https://api.openai.com/v1`). Engine selector appears when set.
- `TTS_OPENAI_API_KEY` — API key for OpenAI-compatible TTS (can be dummy for openedai-speech)
- `TTS_OPENAI_MODEL` — model name for OpenAI-compatible TTS (default: `tts-1`)
- `PADDLE_API_KEY` — Paddle API key for payment verification
- `PADDLE_PRICE_ID` — Paddle price ID for checkout ($4/month subscription)
- `PADDLE_WEBHOOK_SECRET` — HMAC secret for Paddle webhook signature verification
- `PADDLE_CLIENT_TOKEN` — Paddle client-side token for SDK initialization (used in PaywallModal)

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
- `v-ripple` directive registered globally in `main.ts` — use on buttons, cards, clickable rows
- `.stagger-item` CSS class + inline `animationDelay` for list entrance animations
- `useCountUp` composable for animated number transitions
- Design tokens in `app/src/style.css` — always use CSS variables (`--bg`, `--accent`, `--t1`/`--t2`/`--t3`), never hardcode colors
- `useLocalData` composable: IndexedDB primary store for all user data (idb-keyval)
- Auth is optional: router never blocks guests, API 401 doesn't redirect to login
- Never use `.catch(() => {})` on API calls — silently swallows 403 paywall and other meaningful errors. Use try/catch with explicit error handling.
- Range inputs: use `-webkit-slider-runnable-track` (not `-webkit-slider-track`) for cross-browser consistency
- db.py schema: all columns defined in CREATE TABLE — no ALTER TABLE migrations (collapsed for pre-production)
- App-level error boundary (`onErrorCaptured` in App.vue) catches uncaught component errors with recovery UI

## Local-First Architecture

- **Primary data store**: IndexedDB via `useLocalData` composable
- All user data (notes, tags, statuses, bookmarks, quotes, collections) writes to IndexedDB first, syncs to server if logged in
- `useSync` composable: syncs 8 data types on login + reconnect (statuses, progress, settings, quotes, bookmarks, collections, notes, tags)
- Bulk sync endpoints: `GET /api/user/{bookmarks,notes,tags}/all` — return `Record<bookId, data>` maps
- `trackDisplayName()` in `utils/format.ts` — converts numeric filenames ("0101.mp3") to "Глава N"
- `useFileScanner`: Capacitor-native device scanner for `/Audiobooks/` folder
- `isGuest` computed in `useAuth` — true when no user logged in
- Guest views: DashboardView shows welcome card, SettingsView shows "Guest" profile

## Monetization

- **Free plan**: max 10 uploaded books (enforced in `server/upload.py`, `FREE_BOOK_LIMIT`, env-configurable)
- **Premium**: unlimited books, $4/month via Paddle
- Paywall triggers on upload at limit (403 `limit_reached` → `PaywallModal`)
- `server/payments.py`: Paddle webhook handler (subscription.activated/canceled)
- User model: `plan` (free/premium), `stripe_customer_id` (Paddle customer ID)
- Settings: plan badge + X/20 counter + upgrade button
- Onboarding: `/welcome` route, 3 screens, triggered on first visit (`localStorage: leerio_onboarded`)

## Authentication & Multi-Tenancy

### Auth Flow
```
Google Sign-In (frontend) → POST /api/auth/google { id_token }
→ backend verifies with google-auth → creates/finds user in SQLite
→ sets httpOnly JWT cookie → frontend redirects to dashboard
```

### Roles
- **admin** (`librevlad@gmail.com`): Full access
- **user**: Book library, personal book statuses, notes, tags, progress, analytics

### Data Isolation
- **Shared**: `books/` (filesystem, read-only), `config.json`
- **Per-user**: `data/users/{user_id}/*.json` — history, notes, tags, progress, playback, quotes, sessions, collections, book_status
- **Users DB**: `data/leerio.db` (SQLite — users table only)

### Auth Endpoints
- `POST /api/auth/google` — verify Google ID token, set cookie, return user
- `GET /api/auth/me` — return current user from cookie (401 if not authenticated)
- `POST /api/auth/logout` — clear cookie

### Book Status System
- Statuses: `want_to_read`, `reading`, `paused`, `done`, `rejected`
- Endpoints: `GET/PUT/DELETE /api/user/book-status/{book_id}`

### Public Endpoints (no auth)
- `GET /api/config/constants` — healthcheck + app constants
- `GET /api/books/{id}/cover` — cover images (base64 IDs are unguessable)
- `GET /api/audio/{id}/{track}` — audio streaming (same-origin cookies sent automatically)

### Protected Endpoints
- All user-data endpoints require `Depends(get_current_user)` — returns per-user `UserData`

### Test Auth
- `conftest.py` overrides `get_current_user` dependency with `TEST_USER` (admin role)
- Tests use `app.dependency_overrides` pattern for FastAPI

### Migration
- Run `python -m server.migrate_to_multitenancy` once to copy `data/*.json` → `data/users/{admin-id}/`

## Interaction Verification Rule

**Every interactive UI element MUST be verified end-to-end before considering work complete.**

When creating or modifying any `@click`, `@submit`, `v-on` handler, or interactive element:

1. **Trace the full chain**: `@click` → handler function → API call / store mutation → backend endpoint → DB effect
2. **If ANY link is missing** — implement it. Never leave stubs, no-ops, or TODO handlers.
3. **Add E2E test**: Every new interactive feature needs a Playwright test in `app/e2e/tests/` that:
   - Clicks the element
   - Verifies the **result** (not just that the element exists)
   - Example: click bookmark → verify toast appears AND bookmark shows in list
4. **Run `make e2e`** after creating interactive features to catch wiring issues

### What counts as verified
- Button click → visible state change (toast, list update, navigation, class toggle)
- Form submit → API call succeeds → data persists (reload page → still there)
- Toggle → both states work (on→off, off→on)

### What does NOT count
- Element `toBeVisible()` — only proves rendering, not functionality
- Mocked unit test — proves function exists, not that it's wired to UI
- "It compiles" — TypeScript won't catch a `@click` pointing to a no-op function

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
- **E2E tests**: `app/e2e/tests/` — run with `make e2e` (Playwright)
  - `interactions.spec.ts` — smoke tests that click buttons and verify results (not just visibility)
  - Tag `@needs-books` for tests requiring book data (skipped in CI without S3 books)
  - Auth setup: `e2e/auth.setup.ts` (local email/password login, not Google OAuth)
  - Telemetry: `POST /api/telemetry` logs events (fire-and-forget, no DB)

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
2. APK build: debug APK built on push to main (after app-build), uploaded as artifact + GitHub release
3. Deploy: gated on CI success (`needs: [server-lint, app-build]`), SSH to VPS, git pull, docker compose up --build, health check via `https://app.leerio.app` with retry (3 attempts), auto-rollback on failure

### Production Architecture

```
Internet -> Caddy (:80/:443)
              |
              ├── leerio.app       -> static landing page (/srv/landing)
              └── app.leerio.app   -> nginx/app (:80) -> FastAPI/server (:8000)
                                      SPA + /api/ proxy    Business logic
                                                              |
                                                              └── openedai-speech (:8000)
                                                                   Piper TTS (CPU)
```

- **Domain split**: `leerio.app` serves a static landing page (APK download + web app links); `app.leerio.app` serves the Vue SPA + API
- **Caddy** handles HTTPS automatically (Let's Encrypt auto-cert/renew, HTTP->HTTPS redirect)
- Only Caddy exposes host ports (80, 443); server/app are internal-only
- `Caddyfile` at project root — two site blocks: `leerio.app` (file_server) + `app.leerio.app` (reverse_proxy)
- `landing/` directory mounted read-only into Caddy container at `/srv/landing`
- `env_file: .env` on server service loads `CORS_ORIGINS` and other config
- Caddy data/config persisted via named Docker volumes (`caddy_data`, `caddy_config`)

### OpenAI-Compatible TTS (openedai-speech)

- `openedai-speech` service runs alongside the app, provides OpenAI-compatible `/v1/audio/speech` API
- Uses **Piper** (CPU-only) for `tts-1` model — no GPU required
- Default voices: alloy, echo, fable, onyx, nova, shimmer (English; maps to Piper ONNX models)
- Voice models are downloaded on first use and cached in `tts_voices` Docker volume
- Server connects via `TTS_OPENAI_BASE_URL=http://openedai-speech:8000/v1`
- Dev override exposes port 8001 for direct access (`localhost:8001`)

### Dev vs Production

- `docker-compose.override.yml` re-exposes dev ports (8000, 5173, 8001) and disables Caddy via `profiles: ["production"]` — gitignored, dev-only
- Local `docker compose up` = dev mode (no Caddy, direct port access)
- Production VPS: deploy script removes override file; Caddy runs by default

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
