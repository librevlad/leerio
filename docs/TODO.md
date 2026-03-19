# TODO

## Открытые

- [ ] [2026-03-18] Paddle: настроить credentials на VPS (PADDLE_API_KEY, PADDLE_PRICE_ID, PADDLE_WEBHOOK_SECRET)
- [ ] [2026-03-18] Paddle: добавить webhook URL в Paddle Dashboard → app.leerio.app/api/payments/paddle-webhook
- [x] [2026-03-18] Upload: серверная поддержка M4A/M4B/OGG/FLAC/WAV (сделано 2026-03-19)
- [ ] [2026-03-18] Upload: ZIP распаковка на бэкенде
- [x] [2026-03-18] Telemetry: resume_clicked, upload_started/completed, book_played (сделано 2026-03-19)
- [ ] [2026-03-19] E2E: покрытие offline flow, payment paywall
- [ ] [2026-03-19] Написать user stories для всех сценариев и покрыть браузерными E2E тестами
- [x] [2026-03-19] PWA banner убран, APK prompt оставлен на странице книги
- [ ] [2026-03-19] Глобальный рефакторинг всего Python кода
- [ ] [2026-03-19] Разобраться что такое "4/1 годовая цель" в настройках — UX непонятен
- [ ] [2026-03-19] Кнопка загрузки на странице книги + пометка загруженных книг в каталоге
- [ ] [2026-03-19] Редизайн пагинации в каталоге
- [ ] [2026-03-19] Найти и заполнить описания ко всем книгам каталога через Claude Code
- [ ] [2026-03-19] BUG: загруженная книга "Цель 3" не играет
- [ ] [2026-03-19] Заменить кривые иконки ±сек на нормальные готовые иконки во всех местах
- [ ] [2026-03-19] BUG: кнопка "Закладка" ничего полезного не делает — разобраться и предотвратить
- [ ] [2026-03-19] Фидбэк при слабом интернете: анимация загрузки на кнопках переключения треков — проработать и покрыть E2E
- [ ] [2026-03-19] "Хочу прочесть" как "Смотреть позже" — фильтр в каталоге, пункт в меню, случайная книга на дашборде

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
