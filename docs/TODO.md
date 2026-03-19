# TODO

## Открытые

- [ ] [ОТЛОЖЕНО] Paddle: настроить credentials на VPS + webhook URL
- [x] [2026-03-18] Upload: серверная поддержка M4A/M4B/OGG/FLAC/WAV (сделано 2026-03-19)
- [x] [2026-03-18] Upload: ZIP распаковка на бэкенде (сделано 2026-03-19)
- [x] [2026-03-18] Telemetry: resume_clicked, upload_started/completed, book_played (сделано 2026-03-19)
- [ ] [2026-03-19] Иконка APK покорёженная (SVG в nav лендинга)
- [ ] [2026-03-19] Онбординг: выбор папки с книгами на устройстве в APK + кнопка заливки в облако (масштабная фича)
- [ ] [2026-03-19] E2E: покрытие offline flow, payment paywall
- [x] [2026-03-19] User stories E2E: 7 критических потоков (browse→play, status, bookmark, settings, notes, nav, guest)
- [x] [2026-03-19] PWA banner убран, APK prompt оставлен на странице книги
- [x] [2026-03-19] Python рефакторинг: SQL injection guard, N+1 fix, constants, metadata bug, upload formats
- [x] [2026-03-19] "4/1 годовая цель" — теперь показывает done/goal, label "Прослушано / цель"
- [x] [2026-03-19] Кнопка загрузки + пометка в каталоге — уже реализовано (BookDetailView + BookCard, native-only)
- [x] [2026-03-19] Пагинация: infinite scroll с IntersectionObserver вместо кнопки
- [x] [2026-03-19] Описания книг заполнены на проде (343 книги, fallback по категориям)
- [x] [2026-03-19] BUG: "Цель 3" — TTS job записал 45-байтный пустой MP3 (TTS pipeline баг, не player)
- [x] [2026-03-19] Иконки ±сек заменены на Material Design Icons (rewind-15, fast-forward-30)
- [x] [2026-03-19] Закладки: подключены в fullscreen player — загрузка, отображение, seek, удаление
- [x] [2026-03-19] Loading spinner на play кнопке при загрузке трека (FullscreenPlayer + MiniPlayer)
- [x] [2026-03-19] "Хочу прочесть" — пункт в меню (/library?status=want_to_read), фильтр работает
- [x] [2026-03-19] Sidebar: последняя прослушанная книга всегда видна (localStorage persistence)
- [x] [2026-03-19] Полировка бордюров/разделителей в правой панели fullscreen player

## Завершённые

- [x] [2026-03-19] Редизайн desktop fullscreen player — Split Layout с прогресс-кольцом
- [x] [2026-03-19] SVG иконки skip -15/+30 вместо текста (все плееры)
- [x] [2026-03-19] trackDisplayName: "0101.mp3" → "Глава 1" (shared util)
- [x] [2026-03-19] Security: user book access bypass fix (audio streaming)
- [x] [2026-03-19] Security: Paddle webhook reject без secret
- [x] [2026-03-19] Security: password hash crash protection
- [x] [2026-03-19] Stability: offline queue res.ok check
- [x] [2026-03-19] Stability: app error boundary с recovery UI
- [x] [2026-03-19] Stability: logout graceful network error handling
- [x] [2026-03-19] i18n: login email placeholder
- [x] [2026-03-19] Оптимизация logo.png (183KB → 143KB)
- [x] [2026-03-19] Caddyfile: security headers для app.leerio.app
- [x] [2026-03-19] PWA: NetworkFirst caching для /api/audio/* (офлайн-воспроизведение)
- [x] [2026-03-19] useSync: полная синхронизация (bookmarks, collections, notes, tags)
- [x] [2026-03-19] E2E: тесты для collections + sync
- [x] [2026-03-19] db.py: sqlite3.OperationalError вместо bare Exception

- [x] [2026-03-18] Починить логин race condition (useAuth AbortController)
- [x] [2026-03-18] Редизайн SettingsView (iOS-style)
- [x] [2026-03-18] Ripple feedback на кнопках/карточках
- [x] [2026-03-18] Stagger анимации списков
- [x] [2026-03-18] Count-up числа + ProgressBar от 0
- [x] [2026-03-18] Микро-интеракции (tab transitions, now-playing pulse, bookmark pop, error shake)
- [x] [2026-03-18] Починить i18n ключ player.nowPlaying → nav.nowPlaying
- [x] [2026-03-18] APK install prompt на странице книги (веб)
- [x] [2026-03-18] IndexedDB data layer (useLocalData) + optional auth
- [x] [2026-03-18] E2E interaction tests + /verify-interactions скилл
- [x] [2026-03-18] Улучшить /redesign скилл
- [x] [2026-03-18] Guest-friendly UI (dashboard, settings, book detail)
- [x] [2026-03-18] Local-first: notes, tags, status, bookmarks, quotes, collections → IndexedDB
- [x] [2026-03-18] Sync engine + файловый сканер
- [x] [2026-03-18] Onboarding wizard (3 экрана)
- [x] [2026-03-18] Upload: drag & drop + расширенные форматы + auto-fill metadata + progress bar
- [x] [2026-03-18] Free plan limit 10 книг + paywall modal + Paddle integration
- [x] [2026-03-18] Settings: plan badge + X/10 counter + upgrade button
- [x] [2026-03-18] Telemetry composable + backend endpoint
- [x] [2026-03-18] Dashboard: "Recently Added" shelf + sort=recent API
- [x] [2026-03-18] Library: "By author" grouped view
- [x] [2026-03-18] CLAUDE.md обновлён
