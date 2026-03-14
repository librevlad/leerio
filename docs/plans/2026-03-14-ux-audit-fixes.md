# UX Audit Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all business/user/marketing issues found in the UX audit — from test data cleanup to dashboard redesign to landing page fixes.

**Architecture:** Frontend-first changes across Vue components, landing HTML, and i18n locales. One backend change for dashboard API. No new dependencies.

**Tech Stack:** Vue 3 + TypeScript, Tailwind CSS, static HTML (landing), FastAPI (one endpoint change)

---

## Task 1: Remove test data from production

**Files:**
- Modify: `server/db.py` — add filter to exclude "Личные" from public category lists
- Modify: `server/api.py` — filter personal books from shelves/catalog for non-owners

- [ ] **Step 1:** In `server/api.py`, find the `get_shelves` endpoint. Add a filter to exclude categories with count <= 1 that contain only user-uploaded books (category "Личные"). Alternatively, simply exclude the category name "Личные" from shelves since it's a per-user concept.

- [ ] **Step 2:** Delete the test book "Искусство войні" (slug: ololo-iskusstvo-voyn) from the VPS data directory after deploy (manual step, not code).

- [ ] **Step 3:** Verify catalog no longer shows "Личные 1" pill.

- [ ] **Step 4:** Commit.

---

## Task 2: Slim down dashboard — remove category shelves

The dashboard currently duplicates the entire catalog. Remove category shelves, keep only personal sections.

**Files:**
- Modify: `app/src/views/DashboardView.vue`

- [ ] **Step 1:** Remove the `BookShelf` import (line 9) and `ShelfData` type import.

- [ ] **Step 2:** Remove `shelves` ref (line 21) and `api.getShelves()` call from `loadData()` (line 44).

- [ ] **Step 3:** Remove the category shelves template block (lines 203-210):
```vue
<!-- DELETE THIS BLOCK -->
<BookShelf
  v-for="shelf in shelves"
  :key="shelf.category"
  :category="shelf.category"
  :count="shelf.count"
  :books="shelf.books"
/>
```

- [ ] **Step 4:** Verify dashboard now shows: greeting → stats → continue listening → recommendations → heatmap + goal → recent activity.

- [ ] **Step 5:** Commit: `fix: remove category shelves from dashboard to reduce clutter`

---

## Task 3: Fix "дней дней" pluralization bug

**Files:**
- Modify: `app/src/views/SettingsView.vue:264`

- [ ] **Step 1:** Change line 264 from:
```vue
{{ t('plural.day', streak.current) }} {{ t('book.streakDays', streak.current) }}
```
to:
```vue
{{ t('plural.day', streak.current) }}
```

- [ ] **Step 2:** Verify settings page shows "0 дней" / "1 день" / "5 дней" (not doubled).

- [ ] **Step 3:** Commit: `fix: remove duplicate pluralization in streak display`

---

## Task 4: Filter "Продолжить слушать" — only books with real progress

**Files:**
- Modify: `app/src/components/dashboard/ContinueListening.vue`

- [ ] **Step 1:** Add a computed that filters to books with progress > 0:
```ts
const activeBooks = computed(() => props.books.filter(b => b.progress > 0))
```

- [ ] **Step 2:** Update template to use `activeBooks` instead of `books`:
- Line 41: `v-if="activeBooks.length"` (was `books.length`)
- Line 46: `v-for="book in activeBooks"` (was `books`)

- [ ] **Step 3:** If all books have 0 progress, show a gentle prompt instead: "Начните слушать книгу из каталога". Add i18n key `dashboard.startListening` to all 3 locales.

- [ ] **Step 4:** Verify dashboard hides 0% books from "Продолжить слушать".

- [ ] **Step 5:** Commit: `fix: only show books with actual progress in continue listening`

---

## Task 5: Add proper 404 page

**Files:**
- Create: `app/src/views/NotFoundView.vue`
- Modify: `app/src/router.ts`
- Modify: `app/src/i18n/locales/ru.ts`, `en.ts`, `uk.ts`

- [ ] **Step 1:** Create `NotFoundView.vue` — centered layout with:
- Large "404" text
- Message: "Страница не найдена"
- Button: "На главную" → router.push('/')
- Use existing dark theme styles, keep it simple

- [ ] **Step 2:** Update router catch-all (currently redirects to `/`) to render NotFoundView:
```ts
{ path: '/:pathMatch(.*)*', component: () => import('../views/NotFoundView.vue'), meta: { public: true } }
```

- [ ] **Step 3:** Add i18n keys: `common.notFoundTitle`, `common.notFoundDesc`, `common.goHome` to all 3 locales.

- [ ] **Step 4:** Verify `/nonexistent-page` shows 404 page.

- [ ] **Step 5:** Commit: `feat: add proper 404 page`

---

## Task 6: Landing page fixes

**Files:**
- Modify: `landing/index.html`

- [ ] **Step 1:** Update book count stat from "195+" to "270+" (line ~97 in stats section).

- [ ] **Step 2:** Add language auto-detect + switcher. Add a small RU|UA toggle in the nav bar. Use JS to swap text content based on `navigator.language`. Default: Ukrainian. Fallback texts in a simple JS object at the bottom of the file.

Simpler alternative: just add both languages inline with `<span lang="ru">` and `<span lang="uk">` toggled by a single button. Keep it lightweight — no framework.

- [ ] **Step 3:** Reduce the massive empty space between hero screenshot and features section. The screenshot `mockup` div likely has excessive bottom margin/padding. Inspect and tighten.

- [ ] **Step 4:** Add APK rename note: change the download link text from pointing to `app-debug.apk` — rename in the GitHub release action to `leerio.apk` (modify `.github/workflows/ci.yml` APK build job, `files:` field).

- [ ] **Step 5:** Verify landing loads with updated stats, less whitespace, and proper APK name.

- [ ] **Step 6:** Commit: `fix: landing page — update stats, reduce whitespace, rename APK`

---

## Task 7: Login page improvements

**Files:**
- Modify: `app/src/views/LoginView.vue`
- Modify: `app/src/i18n/locales/ru.ts`, `en.ts`, `uk.ts`

- [ ] **Step 1:** Add registration hint below the Google button:
```vue
<p class="mt-4 text-center text-[12px] text-[--t3]">
  {{ t('login.noAccount') }}
</p>
```
i18n keys:
- ru: "Нет аккаунта? Войдите через Google для регистрации"
- en: "No account? Sign in with Google to register"
- uk: "Немає акаунту? Увійдіть через Google для реєстрації"

- [ ] **Step 2:** Change "Войдите, чтобы продолжить" to something more motivating:
- ru: "Войдите, чтобы начать слушать"
- en: "Sign in to start listening"
- uk: "Увійдіть, щоб почати слухати"
Update the i18n key `login.subtitle`.

- [ ] **Step 3:** Verify login page shows new hint and subtitle.

- [ ] **Step 4:** Commit: `fix: improve login page copy and add registration hint`

---

## Task 8: Empty states and onboarding hints

**Files:**
- Modify: `app/src/views/MyLibraryView.vue`
- Modify: `app/src/i18n/locales/ru.ts`, `en.ts`, `uk.ts`

- [ ] **Step 1:** In MyLibraryView, find the empty state (when user has no books). Add a clear onboarding message:
- Title: "Ваша библиотека пуста"
- Description: "Добавьте книги из каталога или загрузите свои аудиокниги"
- Two CTAs: "Перейти в каталог" → /library, "Загрузить книгу" → /upload

- [ ] **Step 2:** Add explanatory subtitles to the filter tabs "Скачанные / Локальные / Загруженные" as tooltips or small descriptions:
- Скачанные: books downloaded from catalog for offline
- Локальные: books on device storage (Capacitor)
- Загруженные: user-uploaded MP3s

Add a small `title` attribute or info icon with tooltip.

- [ ] **Step 3:** Add i18n keys for the new empty state messages.

- [ ] **Step 4:** Verify empty library shows helpful onboarding hints.

- [ ] **Step 5:** Commit: `feat: add onboarding hints to empty library state`

---

## Task 9: Content curation — hide low-quality "Другое" entries

**Files:**
- Modify: `server/api.py` — shelves endpoint
- Modify: `app/src/views/DashboardView.vue` — recommendations

- [ ] **Step 1:** In the dashboard recommendations API (`/api/dashboard/recommendations`), exclude books that have no cover AND no author (low-quality LibriVox entries). Add filter in the query:
```python
# Only recommend books with covers or known authors
books = [b for b in books if b.get("has_cover") or b.get("author")]
```

- [ ] **Step 2:** In the catalog (`/api/books`), keep all books visible (don't hide from search), but sort books without covers to the end of the list within their category.

- [ ] **Step 3:** Verify recommendations no longer show coverless/authorless books; catalog still shows everything but better sorted.

- [ ] **Step 4:** Commit: `fix: exclude low-quality books from recommendations`

---

## Task 10: Add Plausible analytics

**Files:**
- Modify: `landing/index.html` — add Plausible script
- Modify: `app/index.html` — add Plausible script
- Modify: `app/nginx.conf` — allow Plausible domain in CSP

- [ ] **Step 1:** Sign up for Plausible Cloud (plausible.io) or self-host. Get the script tag for domain `leerio.app`.

- [ ] **Step 2:** Add Plausible script to `landing/index.html` in `<head>`:
```html
<script defer data-domain="leerio.app" src="https://plausible.io/js/script.js"></script>
```

- [ ] **Step 3:** Add the same script to `app/index.html` for the SPA (use `data-domain="app.leerio.app"`).

- [ ] **Step 4:** Update CSP in `app/nginx.conf` to allow `https://plausible.io` in `script-src` and `connect-src`:
```
script-src 'self' https://accounts.google.com https://plausible.io;
connect-src 'self' https://accounts.google.com https://*.vultrobjects.com https://plausible.io;
```

- [ ] **Step 5:** Verify no CSP errors in browser console, analytics events appear in Plausible dashboard.

- [ ] **Step 6:** Commit: `feat: add Plausible analytics to landing and app`

---

## Task 11: Add OG meta tags to SPA for social sharing

**Files:**
- Modify: `app/index.html`

- [ ] **Step 1:** Add Open Graph meta tags to `app/index.html` `<head>`:
```html
<meta property="og:type" content="website" />
<meta property="og:title" content="Leerio — Audiobook Library" />
<meta property="og:description" content="Listen to audiobooks, track progress, manage your library." />
<meta property="og:image" content="https://leerio.app/img/desktop-dashboard.png" />
<meta property="og:url" content="https://app.leerio.app" />
<meta name="twitter:card" content="summary_large_image" />
```

- [ ] **Step 2:** Commit: `feat: add OG meta tags to SPA for social sharing`

---

## Execution Order

1. **Task 1** — Remove test data (quick, reduces noise)
2. **Task 3** — Fix pluralization bug (one-line fix)
3. **Task 4** — Filter continue listening (small component change)
4. **Task 2** — Slim dashboard (biggest visual impact)
5. **Task 5** — 404 page (new file, independent)
6. **Task 7** — Login improvements (copy changes)
7. **Task 8** — Empty states (onboarding)
8. **Task 9** — Content curation (backend filter)
9. **Task 6** — Landing page fixes (HTML + CI)
10. **Task 11** — OG tags (one file)
11. **Task 10** — Analytics (needs Plausible account — last, may need user input)
