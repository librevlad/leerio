# Session Dump — 2026-03-21

## Что сделано за сессию

### APK Folder Onboarding (масштабная фича)
- **Spec + Plan**: design doc + 12-task implementation plan
- **useFileScanner v2**: persistent localStorage, multi-dir scan (Audiobooks/Download/Music), size calc, heuristics ("not a book"), async yielding, runtime permissions
- **ScanResultsView**: fullscreen view с чекбоксами, select all/deselect, "Add N books" button
- **WelcomeView step 2**: 3 кнопки (Scan/Files/Folder) с platform detection (Scan hidden on web)
- **AddBookFab**: FAB "+" в библиотеке, popup-меню (5 пунктов APK / 3 web), Teleport, scale-up animation
- **BookDetailView**: бейдж "На устройстве"/"В облаке", кнопка "Загрузить в облако", paywall для free users
- **YouTubeImportView**: отдельный fullscreen view (из вкладки в UploadView)
- **useYouTubeImport**: save to filesystem на APK (chunked base64), web fallback IndexedDB
- **usePlayer fs: branch**: resolveAudioSrc (Filesystem.getUri + convertFileSrc), loadBook с position restore
- **Backend**: POST /api/user/books/cloud-sync (premium only)
- **Android**: permissions READ_EXTERNAL_STORAGE, READ_MEDIA_AUDIO, WRITE_EXTERNAL_STORAGE
- **Router**: /scan-results, /youtube-import
- **i18n**: scan, fab, book sections (ru/en/uk)
- **Types**: FsBookMeta, FsTrack interfaces

### Player Hardening (7 фиксов по ревью)
1. `playerState` computed — derived state (idle/loading/playing/paused/error)
2. `autoplay` параметр в loadBook — контроль над auto-play
3. `restorePosition()` — одна функция вместо 3 копий
4. `retryAudio` + opId — не replay stale треки
5. `preloadNextTrack` guard — preloadInProgress flag
6. Player telemetry — player_play, player_pause, player_error, player_load_book
7. FAB → `isPlayerVisible` вместо `currentBook`

### Code Quality
- Дедуплицирование cloud-sync endpoint: `_extract_audio_files()` + `_save_book()` shared helpers
- preloadNextTrack для fs: книг
- E2E login tests fixed (onboarding redirect, updated locators)
- Strict type errors in tests fixed (build step)
- Prettier + eslint formatting across all files
- Multiline inline handlers extracted to functions (Vite prod build)

### Landing Page Fix
- CSS/img paths: убран `/landing/` prefix (Caddy root уже `/srv/landing`)
- Copyright 2025 → 2026
- CI paths-ignore: убран `landing/**` чтобы deploy триггерился
- Deploy verified — стили работают

### E2E Tests: 42 теста
**folder-onboarding.spec.ts (30 тестов):**
- Онбординг step 2: web/APK platform detection, skip, back, primary button
- FAB: open/close, overlay, rotate, menu items, navigation
- ScanResults: empty state, back
- fs: books: inject → MyLibrary, filter, BookDetail, badge, cloud upload paywall, synced, not found, play
- YouTube: input, Find enable, back
- Persistence: survive reload, correct structure
- Cloud API: 403 free user
- Edge cases: empty data, corrupted JSON, onboarding redirect

**folder-onboarding-advanced.spec.ts (12 тестов):**
- Real MP3 upload via API + library verify
- Catalog book → play → player opens
- Position persistence in localStorage
- Continue Listening LAST_PLAYED
- FAB bottom offset (80px vs 130px with MiniPlayer)
- Scan heuristics runtime check
- Paywall close button
- Cloud sync API with real MP3 (403 + valid upload)

### APK Testing
- Android emulator (Medium_Phone_API_36.1) launched and tested
- APK installed via ADB, WebView connected via CDP
- Screenshots verified: onboarding step 2 shows all 3 buttons, FAB shows all 5 items

## Архитектура

### fs: books data flow
```
Scan: useFileScanner.scan() → Filesystem.readdir → FsBookMeta[] → localStorage
Play: resolveAudioSrc("fs:") → Filesystem.getUri(ExternalStorage) → convertFileSrc → audio.src
Save position: localStorage (instant) + IndexedDB (async)
Cloud upload: Filesystem.readFile → Blob → FormData POST /api/user/books/cloud-sync
```

### Player state model
```
playerState = computed:
  audioError → 'error'
  isLoading → 'loading'
  isPlaying → 'playing'
  currentBook → 'paused'
  else → 'idle'
```

## Статистика
- 367 unit tests (all pass)
- 42 E2E tests (desktop + mobile)
- ~25 commits
- CI: lint ✅, format ✅, test ✅, type check ✅, build ✅, deploy ✅
