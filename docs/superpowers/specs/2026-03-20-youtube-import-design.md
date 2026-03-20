# YouTube Import — Design Spec

## Summary

Пользователь вставляет YouTube URL → сервер извлекает метаданные (yt-dlp) → пользователь подтверждает → клиент скачивает аудио через серверный stream-proxy → ffmpeg.wasm (single-threaded) нарезает на главы → сохраняет локально (IndexedDB) → опционально загружает в облако.

## Constraints

- Скачивание контента инициируется клиентом (легальность)
- Сервер не хранит контент, только проксирует поток и извлекает метаданные
- Offline-first: книга сразу доступна локально после импорта
- Облако по запросу пользователя
- Торренты — отложены на v2

---

## Backend

### Требует аутентификации

Оба эндпоинта требуют `Depends(get_current_user)`. Без авторизации — 401.

### `POST /api/youtube/resolve`

**Request:** `{ "url": "https://www.youtube.com/watch?v=..." }`

**Response:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "Война и мир — Лев Толстой",
  "author": "",
  "duration": 36240,
  "thumbnail": "https://i.ytimg.com/vi/.../maxresdefault.jpg",
  "chapters": [
    { "title": "Глава 1", "start": 0, "end": 1823 },
    { "title": "Глава 2", "start": 1823, "end": 3601 }
  ]
}
```

**Примечание:** `audio_url` НЕ возвращается клиенту. URL googlevideo истекает через ~6 часов. Вместо этого клиент скачивает через proxy (см. ниже).

**Logic:**
- `yt-dlp --dump-json --no-download` — только метаданные
- Chapters из YouTube metadata (или пустой массив)
- Author: парсинг из title по паттерну "Author — Title" / "Author - Title"
- Валидация: URL = youtube.com / youtu.be, длительность ≤ 24 часа
- Rate limit: 5 req/min на пользователя

**Errors:** 400 (невалидный URL), 404 (видео не найдено), 413 (> 24 часов), 429 (rate limit)

### `GET /api/youtube/stream/{video_id}`

Stream-proxy: сервер запускает `yt-dlp -o -` для конкретного video_id и стримит аудио клиенту. Свежий URL извлекается на каждый запрос — нет проблемы с expiry.

**Безопасность:**
- `video_id` валидируется regex: `^[a-zA-Z0-9_-]{11}$` (ровно 11 символов)
- Нет произвольных URL — только YouTube video ID → нет SSRF
- Range headers поддержаны (HTTP 206)
- Content-Type: `audio/webm` или `audio/mp4` (зависит от формата)
- Не кэширует и не сохраняет контент на диск

---

## Frontend: `useYouTubeImport` composable

### State

```typescript
step: 'idle' | 'resolving' | 'downloading' | 'splitting' | 'saving' | 'done' | 'error'
progress: number        // 0-100 текущего этапа
title: string           // редактируемый
author: string          // редактируемый
chapters: Chapter[]     // из resolve или сгенерированные
duration: number
thumbnail: string
errorMessage: string
```

### Flow

1. **resolve(url)** — POST `/api/youtube/resolve`. Показывает карточку: обложка, title, chapters. Пользователь может редактировать title/author.

2. **download()** — `fetch(/api/youtube/stream/{video_id})` с ReadableStream для progress. Результат: Blob. Нет CORS проблем (same-origin).

3. **split(blob, chapters)** — ffmpeg.wasm single-threaded (`@ffmpeg/ffmpeg` без SharedArrayBuffer, без COOP/COEP). Если chapters есть — нарезка по таймкодам (`-ss -to -c copy`). Если нет — равные куски (настраиваемая длина: 5/10/15/20 мин). Без перекодирования.

4. **save(files, meta)** — `useLocalBooks.addLocalBook(files, meta)`. Книга сразу в "Моя библиотека".

### ffmpeg.wasm — single-threaded mode

Используем `@ffmpeg/ffmpeg` в single-threaded режиме:
- **НЕ требует** `SharedArrayBuffer`, COOP, COEP
- Не ломает Google OAuth popup flow
- Не ломает cross-origin img/audio (S3 covers)
- Достаточно быстр для `-c copy` (нет перекодирования)
- ~25MB WASM, кэшируется Service Worker

### Cancellation

AbortController на каждом этапе. Кнопка "Отмена" доступна всегда.

### Edge Cases

- ffmpeg.wasm не загрузился → ошибка + retry
- Закрытие вкладки во время download → данные теряются (повтор)
- Видео без аудио дорожки → ошибка на этапе resolve
- Chapters с нулевой длительностью → фильтруются
- Очень длинное аудио (20+ часов) → предупреждение о времени
- Сервер перезагрузился во время stream → download прерывается, retry

---

## Prerequisite fix: useLocalBooks blob URL revocation

**Проблема:** `getLocalAudioUrl()` ревокает `previousAudioUrl` при каждом вызове. Когда player preloads следующий трек → ревокается URL текущего играющего трека → playback ломается.

**Фикс (до начала YouTube import):**
- Заменить `previousAudioUrl: string | null` на `activeUrls: Map<string, string>` (key = `${bookId}/${trackIndex}`)
- Ревокать только URL которые не являются текущим или preloaded треком
- Очистка всех URL при `closePlayer()`

---

## UI

### UploadView — вкладка "YouTube"

Порядок вкладок: Загрузить | **YouTube** | TTS | Локальные

**Ввод URL:**
- Поле ввода с placeholder "Вставьте ссылку на YouTube"
- Кнопка "Найти"

**Результат resolve:**
- Карточка: thumbnail, title (editable input), author (editable input)
- Список chapters (если есть) или текст "Без глав — будет разбито по N мин"
- Слайдер длины куска (5/10/15/20 мин) — только если нет chapters
- Длительность, формат

**Процесс:**
- Кнопка "Скачать и сохранить"
- Прогресс-бар с текстом этапа: "Получение данных..." → "Скачивание 34%" → "Нарезка на главы..." → "Сохранение..."
- Кнопка "Отмена"

### MyLibraryView — кнопка "В облако"

- Локальные книги (`lb:` prefix) показывают иконку upload
- Клик → загружает все главы через `api.uploadBook(formData)`
- Каждый Blob оборачивается в `new File([blob], 'chapter-{i+1}.mp3', { type: 'audio/mpeg' })` (сервер требует filename)
- Прогресс на карточке
- После успеха: книга = `ub:` (серверная), локальная копия удаляется

---

## What We Don't Change

- usePlayer — уже поддерживает локальные книги
- Существующие вкладки Upload / TTS — без изменений
- Серверный upload flow — используется as-is для "В облако"
- Audio engine, position saving, offline — всё работает с `lb:` книгами

## What We Fix First

- `useLocalBooks.getLocalAudioUrl` — blob URL revocation bug (prerequisite)

---

## Testing

- Unit: `useYouTubeImport` — resolve mock, download mock, split mock
- Unit: `/api/youtube/resolve` — valid/invalid URLs, chapters parsing, author extraction
- Unit: `/api/youtube/stream/{video_id}` — video_id validation (regex), 401 without auth
- Edge case: abort, NaN duration, empty chapters, expired stream
- E2E: вставить URL → увидеть карточку → (mock download) → книга в библиотеке
- Security: video_id injection attempts, non-YouTube URLs blocked
