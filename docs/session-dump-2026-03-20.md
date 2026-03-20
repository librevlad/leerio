# Session Dump — 2026-03-20

## Что сделано за сессию

### Тесты: 83 → 360 (покрытие 28% → 70%)
- 12 новых тестовых файлов: plural, useNetwork, useAuth, useCategories, useConstants, useAnalytics, useTelemetry, useLocalData, useSync, useCountUp, usePullToRefresh, useLocalBooks
- Расширен api.test.ts (2 → 19 тестов), usePlayer.test.ts (36 → 65 тестов)
- useYouTubeImport.test.ts — 25 тестов (resolve, download, split, edge cases)
- Edge case тесты: NaN, Infinity, negative, empty arrays, concurrent operations

### Player stability (AIMP-level)
- Race conditions: loadedmetadata listener leak fix, preloadNextTrack opId check, cover blob URL race
- AbortError filter в togglePlay, playTrack, retryAudio
- Skip guards: skipForward/skipBackward blocked during isLoading
- No overlap: audio.pause() before src change in playTrack and loadBook
- Position never lost: beforeunload + visibilitychange + IndexedDB + localStorage + API (3 layers)
- Pause handler: only save/stopSession on user-initiated pause, not programmatic
- API debounce: savePosition debounces API calls by 1s
- closePlayer: cancels all async ops (loadOpId++, playOpId++), clears all state
- ended event: blocked during isLoading to prevent race with playTrack
- devicechange: null audio guard + catch on enumerateDevices
- NaN guards: seek(), setVolume(), setPlaybackRate(), setSleepTimer(), formatTime() all reject NaN/Infinity/negative
- seekPercent clamped to 0-100% in FullscreenPlayer

### Offline-first (6/10 → 10/10)
- Position/Progress → IndexedDB (primary) + localStorage (instant) + API (sync)
- Book status → IndexedDB first, then API queue
- Sync push: local changes pushed to server before pull (timestamp-based for statuses, higher-wins for progress)
- Track metadata: cached in IndexedDB, offline fallback when SW cache expires
- Books catalog: cached in IndexedDB, offline search/browse works
- Offline indicator: red banner "Офлайн — доступны только скачанные книги"
- Offline queue: navigator.onLine guard, merge failed + new items after replay
- Auto-resume: clears LAST_PLAYED if book unavailable

### Security fixes
- Path traversal: .resolve() check in _resolve_user_book_path
- TTS error sanitization: type(e).__name__ instead of str(e) in user-visible errors
- S3 timeout: connect_timeout=10, read_timeout=30
- YouTube API: video_id regex validation, no SSRF, subprocess timeout 30s

### YouTube Import (new feature)
- Backend: POST /api/youtube/resolve + GET /api/youtube/stream/{video_id}
- Frontend: useYouTubeImport composable (resolve → download → split → save)
- ffmpeg.wasm single-threaded (no SharedArrayBuffer needed, no COOP/COEP)
- UI: YouTube tab in UploadView with progress tracking
- Cloud upload: "В облако" button for local books in MyLibraryView
- Edge cases: yt-dlp not found (503), subprocess timeout, ffmpeg OOM, empty chapters, NaN duration

### Auth Redesign
- Backend: 4 new endpoints (register, verify-email, forgot-password, reset-password)
- Email: Resend API module (dev mode = console log)
- DB: verification_codes table, register_user(), activate_user(), verify_code()
- Frontend: LoginView rewrite with tabs (Login/Register), password strength indicator, forgot password 3-step flow, email verification with resend cooldown
- Google OAuth preserved

### UX fixes
- Volume persistence: localStorage + applied on init
- MiniPlayer duration fallback: audio.duration when totalDuration=0
- "Моя" link added to sidebar + BottomNav
- /upload route registered in router
- Duplicate books removed (149 dupes, filesystem sync now deduplicates by s3_prefix)
- Global search removed (redundant with library search)
- Guest flow: onboarding saves local books, play button shows toast before redirect, mobile nav hides protected tabs for guests
- BookDetailView: toast on API error for status changes
- LibraryView: IntersectionObserver null guard
- HistoryView: mounted flag prevents stale setTimeout
- App.vue: auto-resume route check

### Refactoring
- UploadView: 904 lines → ~50 lines parent + 4 tab components
- NotFoundView: redesigned with personality and navigation
- useLocalBooks: Map-based blob URL management (no revocation of playing track)
- format.ts: NaN/negative/Infinity guards on formatSize, formatSizeMB, formatRemaining
- plural.ts: NaN/Infinity guard
- useBooks: preserves existing books on error (doesn't wipe library)

## Архитектура

### Data flow (offline-first)
```
User action → IndexedDB (immediate) → localStorage (instant recovery) → API queue (when online)
Server sync → push local changes → pull fresh data → merge into IndexedDB
```

### Player position persistence
```
savePosition() called every 5s + on pause + on beforeunload + on visibilitychange:
  1. IndexedDB: localData.setPosition(bookId, {track_index, position})
  2. localStorage: leerio_pos_{bookId} (instant recovery)
  3. API: debounced 1s, setPlaybackPosition + setProgress

loadBook() position restore:
  1. Try API: api.getPlaybackPosition(bookId)
  2. Fallback: IndexedDB → localData.getPosition(bookId)
  3. Fallback: localStorage → leerio_pos_{bookId}
```

### YouTube Import flow
```
User pastes URL → POST /api/youtube/resolve (yt-dlp metadata)
  → User confirms title/author/chapters
  → GET /api/youtube/stream/{video_id} (yt-dlp audio stream)
  → ffmpeg.wasm splits into chapters (client-side, single-threaded)
  → useLocalBooks.addLocalBook(files, meta)
  → Book appears in "Моя библиотека"
  → Optional: "В облако" button uploads to server
```

### Auth flow
```
Register: POST /register → send verification code → POST /verify-email → set cookie → redirect
Login: POST /login → set cookie → redirect
Forgot: POST /forgot-password → send reset code → POST /reset-password → set cookie → redirect
Google: GSI SDK → POST /auth/google → set cookie → redirect
```

## Файлы затронуты (ключевые)

### Created
- server/youtube_api.py, server/email.py
- app/src/composables/useYouTubeImport.ts + test
- app/src/components/upload/{UploadTab,YouTubeTab,TTSTab,LocalTab}.vue
- 12 new test files (useAuth, useNetwork, useLocalData, etc.)
- docs/superpowers/specs/ and plans/ for YouTube and Auth

### Modified (major)
- server/db.py — verification_codes, register_user, sync dedup fix
- server/api.py — 4 auth endpoints, YouTube router
- app/src/composables/usePlayer.ts — 20+ stability/offline fixes
- app/src/views/LoginView.vue — complete rewrite
- app/src/views/UploadView.vue — split into 4 components
- app/src/views/NotFoundView.vue — redesigned
- app/src/App.vue — offline indicator, global search removed
- app/src/composables/useSync.ts — push local changes
- app/src/composables/useBooks.ts — IndexedDB cache
- app/src/composables/useLocalBooks.ts — Map-based blob URLs
- app/src/composables/useLocalData.ts — getTrackMeta, getBooks
- All 3 i18n locale files

## Известные ограничения
- YouTube Import: ffmpeg.wasm ~25MB download (cached by SW)
- Email verification: requires RESEND_API_KEY for production (dev mode logs to console)
- Торренты: отложены на v2 (WebTorrent ограничения)
- E2E тесты: не обновлены под новые изменения (unit тесты покрывают)
