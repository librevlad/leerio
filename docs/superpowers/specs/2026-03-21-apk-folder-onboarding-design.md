# APK Folder Onboarding + Cloud Upload — Design Spec

**Date:** 2026-03-21
**Status:** Draft

---

## Summary

Пользователь устанавливает APK → онбординг предлагает сканировать устройство на аудиокниги → найденные книги добавляются в библиотеку → опционально загружаются в облако (premium). В библиотеке FAB "+" с popup-меню объединяет все способы добавления книг.

## Goals

- Автоматически находить аудиокниги на устройстве
- 1 клик до начала прослушивания найденной книги
- Библиотека = главный хаб, каталог вторичен
- Локальные книги бесплатны без лимита
- Облачная синхронизация = premium
- YouTube скачивает на устройство как локальную книгу
- Юридическая чистота: сервер не хранит и не проксирует аудиоконтент YouTube

## Non-goals

- Фоновое автосканирование при каждом запуске
- Глобальный поиск (только поиск в библиотеке)
- Извлечение обложек из ID3-тегов (placeholder для fs: книг)

---

## 1. Онбординг — шаг 2 (редизайн)

### Было
Drop zone для файлов (drag & drop + file input).

### Стало
Три кнопки + ссылка "Пропустить":

1. **📱 Сканировать устройство** (primary, accent gradient) — только APK
   - Сканирует `/Audiobooks/`, `/Download/`, `/Music/`
   - Переходит к ScanResultsView
2. **📄 Выбрать файлы** — file input (MP3, M4A, M4B, OGG, OPUS, FLAC, WAV, ZIP)
   - На вебе становится primary кнопкой
3. **📂 Указать папку** — APK: Android SAF picker. Web: `<input webkitdirectory>`

**Пропустить →** — текстовая ссылка внизу (не кнопка)

### Платформенная адаптация
- **APK:** все 3 кнопки видны, "Сканировать" = primary
- **Web:** "Сканировать" скрыт, "Выбрать файлы" = primary

---

## 2. Результаты сканирования (ScanResultsView)

Полноэкранный view с роутом `/scan-results`. Используется и в онбординге (router.push), и по FAB.

### UI
- Заголовок: "Найдено N книг"
- Ссылка "Выбрать все" / "Снять все"
- Подзаголовок: "Уберите галочку с книг, которые не нужны"
- Прогресс скана: spinner + "Сканируем /Download/..." пока идёт скан (async, yielding)
- Список карточек с чекбоксами:
  - Checkbox (accent, rounded) слева
  - Название книги (из имени папки, `cleanTitle()`)
  - Автор · N треков · размер
  - Некниги (podcast_episodes и т.п.) отображаются unchecked + opacity 0.6
- Кнопка: "Добавить N книг" (dynamic count)
- Подпись: "Книги останутся на устройстве"

### Поведение
- Все книги выбраны по умолчанию
- Пользователь снимает галочки с ненужного
- Кнопка disabled если ничего не выбрано
- После "Добавить": книги сохраняются в `useFileScanner` persistent store → навигация в `/library`
- В онбординге: пропускает шаг 3 (done), сразу `/library`

### Эвристика "не книга"
- Менее 2 треков → unchecked по умолчанию
- Имя папки содержит "podcast", "music", "ringtone" → unchecked

### Скан больших директорий
- `/Download/` может содержать тысячи файлов
- Скан async с `requestAnimationFrame` yielding каждые 50 записей
- UI показывает прогресс: "Сканируем... (найдено N книг)"
- Максимальная глубина: 2 уровня (папка → файлы, не рекурсивно)

---

## 3. FAB + Popup в библиотеке

### FAB
- Круглая кнопка "+" (52×52px), accent gradient, bottom-right
- Позиция: динамическая, выше BottomNav + MiniPlayer (если виден)
  - MiniPlayer виден: `bottom: 130px`
  - MiniPlayer скрыт: `bottom: 80px`
  - Реактивно через `usePlayer().currentBook` — если есть, MiniPlayer виден
- Shadow: `0 4px 12px rgba(249,115,22,0.4)`
- При раскрытии: rotate(45deg) → визуально "✕"

### Popup меню
- Появляется над FAB, справа
- Background: `--card-solid`, border-radius: 14px
- Shadow: `0 8px 32px rgba(0,0,0,0.5)`
- Анимация: scale-up от FAB + fade
- Overlay: полупрозрачный чёрный, тап закрывает
- Если popup выходит за верхний край экрана — открывается вниз (маленькие экраны)

### Пункты меню

| Иконка | Название | Подпись | Платформа | Действие |
|--------|----------|---------|-----------|----------|
| 📱 | Сканировать | Найти книги на устройстве | APK only | → /scan-results |
| 📄 | Файлы | MP3, M4A, M4B, ZIP | Все | file input |
| 📂 | Папка | Указать папку вручную | Все | SAF/webkitdirectory |
| --- | --- | --- | --- | разделитель |
| 🎥 | YouTube | Скачать аудиокнигу | APK only | → /youtube-import |
| 🗣 | Озвучить текст | TTS из текста | Все | → /upload (TTS tab) |

### Компонент: AddBookFab.vue
- Props: нет (singleton)
- Emits: нет (навигация через router)
- State: `isOpen` ref
- Подключается в LibraryView.vue

---

## 4. Облачный upload (premium)

### UI в BookDetailView
- Для локальных книг (`fs:` или `lb:`) показывается:
  - Бейдж: "📱 На устройстве"
  - Кнопка: "☁️ Загрузить в облако" (secondary style)
  - Подпись: "Sync между устройствами · Premium"

### Поведение
- **Free user** → тап → paywall modal:
  - Иконка ☁️, заголовок "Облачная синхронизация"
  - Преимущества: ∞ облачных книг / Sync устройств / Бэкап
  - CTA: "Попробовать Premium"
  - "Не сейчас" закрывает
- **Premium user** → тап → upload с прогрессом:
  - Читаем файлы через `Filesystem.readFile()` → Blob
  - `FormData POST /api/user/books/cloud-sync` (отдельный endpoint, без free-tier лимита)
  - Progress bar
  - После upload: бейдж → "☁️ В облаке"
  - `synced = true` в fs: metadata
- Локальная копия НЕ удаляется после upload

### API endpoint
- **Новый** `POST /api/user/books/cloud-sync` — для premium cloud sync
- Не использует `POST /api/user/books` (у него free-tier лимит 10 книг)
- Backend проверяет `is_premium` перед принятием upload
- Помечает книгу `source='cloud-sync'`

### Лимиты
- Локальные книги (fs:, lb:) — бесплатно, без лимита
- Облачный upload — premium only (отдельный endpoint)
- YouTube → всегда локальная книга (бесплатно)

---

## 5. YouTube Import (редизайн)

### Новый flow
```
URL → POST /api/youtube/resolve → {metadata, audio_url}
→ APK: Capacitor HTTP download audio_url → temp file на filesystem
→ ffmpeg split (Capacitor → native temp file, не в память)
→ сохранить в /Audiobooks/{title}/ (fs:)
```

**Важно**: yt-dlp `--get-url` возвращает URL привязанный к IP сервера. Если клиент на другом IP — URL не сработает. Поэтому:
- **Оставить** `GET /api/youtube/stream/{video_id}` как server-side proxy (StreamingResponse, без записи на диск)
- Сервер = pipe, не хранилище. yt-dlp stdout → StreamingResponse → клиент
- Юридически: сервер не хранит контент, только проксирует по запросу пользователя
- **YouTube = APK only** (Capacitor HTTP скачивает через наш сервер, без CORS проблем)

### Отличие от текущего flow
- **Хранение**: вместо IndexedDB (`lb:`) → filesystem `/Audiobooks/{title}/` (`fs:`)
- **View**: отдельный `/youtube-import` вместо вкладки в UploadView
- **Splitting**: скачать во temp file → ffmpeg split → записать главы на filesystem
- **Память**: не загружать весь blob в RAM, скачивать на диск через Capacitor HTTP `downloadFile()`

### Отдельный view: `/youtube-import`
- Полноэкранный YouTubeImportView.vue
- Открывается из FAB popup
- UI: тот же (URL input → metadata → download → progress)

### Оптимизация памяти (Android WebView)
- Скачивание: `Capacitor HTTP downloadFile()` → temp file на диск (не blob в RAM)
- Splitting: ffmpeg.wasm читает из temp file, пишет главы по одной
- Если файл > 200MB: предупреждение "Большой файл, может занять время"
- При OOM: catch ошибка, предложить скачать без split (один файл = один трек)

---

## 6. Архитектура

### Persistence для fs: книг

**Проблема**: `useFileScanner` хранит результаты в ephemeral `ref` — теряется при перезагрузке.

**Решение**: `useFileScanner` получает persistent storage по аналогии с `useDownloads`:

```
localStorage key: "leerio_fs_books"
Формат: Record<string, FsBookMeta>

FsBookMeta = {
  id: string              // "fs:{folderName}"
  title: string
  author: string
  folderPath: string      // "Audiobooks/Author - Title"
  tracks: FsTrack[]       // { index, filename, path, duration }
  sizeBytes: number       // сумма размеров файлов (Filesystem.stat)
  synced: boolean         // загружена в облако
  addedAt: string         // ISO timestamp
}
```

- **При скане**: `Filesystem.stat()` на каждый файл → `sizeBytes` (работает на всех Android версиях)
- **Загружаем при старте**: `JSON.parse(localStorage.getItem('leerio_fs_books'))`
- **Continue Listening**: Dashboard проверяет `leerio_fs_books` наряду с API progress
- **loadBook**: если `book.id.startsWith('fs:')` → track list из localStorage, не из API

### resolveAudioSrc для fs: книг

Вставить **перед** проверкой `lb:` в `usePlayer.ts:resolveAudioSrc()`:

```typescript
// Filesystem book (scanned from device storage)
if (bookId.startsWith('fs:')) {
  const track = tracks.value[trackIndex]
  if (!track?.path) return ''
  // ExternalStorage paths → native URI → web-accessible URL
  const uri = await Filesystem.getUri({
    path: track.path,
    directory: Directory.ExternalStorage,
  })
  playingOffline.value = true
  return Capacitor.convertFileSrc(uri.uri)
}
```

**Ключевое отличие от downloads**: downloads используют `Directory.Data`, fs: книги — `Directory.ExternalStorage`. Нужен `Filesystem.getUri()` + `Capacitor.convertFileSrc()`.

### Data flow

```
Сканирование:
  useFileScanner.scan()
  → Filesystem.readdir(/Audiobooks/, /Download/, /Music/)
  → scanFolder() для каждой поддиректории (async, yielding)
  → FsBookMeta[] с id "fs:{name}"
  → ScanResultsView (чекбоксы)
  → выбранные → localStorage "leerio_fs_books"
  → navigate → /library

Воспроизведение fs: книг:
  usePlayer.resolveAudioSrc()
  → prefix "fs:" → Filesystem.getUri(track.path, ExternalStorage)
  → Capacitor.convertFileSrc(uri) → audio.src

Continue Listening:
  Dashboard: LAST_PLAYED из localStorage
  → если id начинается с "fs:" → загрузить meta из leerio_fs_books
  → показать в Continue Listening карточке

Облачный upload:
  BookDetailView → "В облако"
  → проверить isPremium
  → Filesystem.readFile(track.path, ExternalStorage) → Blob для каждого трека
  → FormData POST /api/user/books/cloud-sync
  → meta.synced = true → обновить localStorage

YouTube import:
  POST /api/youtube/resolve → metadata
  → Capacitor HTTP downloadFile(GET /api/youtube/stream/{video_id}) → temp file
  → ffmpeg.wasm split → chapter files
  → Filesystem.writeFile() → /Audiobooks/{title}/
  → регистрируем в leerio_fs_books как fs: книгу
```

### Новые файлы

| Файл | Назначение |
|------|-----------|
| `views/ScanResultsView.vue` | Результаты сканирования с чекбоксами |
| `components/library/AddBookFab.vue` | FAB + popup-меню |
| `views/YouTubeImportView.vue` | Полноэкранный YouTube import |

### Изменяемые файлы

| Файл | Изменения |
|------|-----------|
| `useFileScanner.ts` | Persistent storage, несколько директорий, подсчёт размера, эвристика "не книга", async yielding |
| `WelcomeView.vue` | Шаг 2: три кнопки вместо drop zone |
| `LibraryView.vue` | Подключить AddBookFab |
| `usePlayer.ts` | `resolveAudioSrc()`: ветка `fs:` с `Filesystem.getUri` + `convertFileSrc` |
| `BookDetailView.vue` | Бейдж "На устройстве" + кнопка "В облако" + paywall |
| `useYouTubeImport.ts` | Download через Capacitor HTTP `downloadFile`, сохранение в filesystem |
| `types.ts` | `FsBookMeta` interface, `FsTrack` interface |
| `router.ts` | Роуты `/scan-results`, `/youtube-import` |
| `android/app/src/main/AndroidManifest.xml` | Добавить permissions READ_EXTERNAL_STORAGE, READ_MEDIA_AUDIO |

### Не меняем
- `useLocalBooks.ts` — для `lb:` книг (IndexedDB blobs), `fs:` отдельно
- `useDownloads.ts` — для скачивания каталожных книг
- Player core logic — только `resolveAudioSrc` расширяем
- Collections, notes, analytics

### Android permissions

Добавить в `android/app/src/main/AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"
                 android:maxSdkVersion="32" />
<uses-permission android:name="android.permission.READ_MEDIA_AUDIO" />
```

Runtime permission request через Capacitor Permissions API перед первым сканом. Если denied — показать объяснение + кнопку "Разрешить" (откроет системные настройки).

---

## 7. Edge cases

- **Нет папки /Audiobooks/**: создать при первом скане, показать "Ничего не найдено, попробуйте указать папку"
- **Нет permissions**: показать объяснение зачем + retry кнопку. Если permanently denied → ссылка на системные настройки
- **Пустые папки**: пропускать (0 аудиофайлов)
- **Дубликаты**: если `fs:{name}` уже существует в localStorage → пропустить, не дублировать
- **Большой /Download/**: async yielding scan, макс. глубина 2, UI с прогрессом
- **Большие файлы YouTube (ffmpeg OOM)**: скачивать на диск через `downloadFile()`, не в RAM. При OOM → fallback: один файл = один трек
- **YouTube URL протухший**: скачивать сразу после resolve, не хранить URL
- **SD-карта**: ExternalStorage может быть SD — проверить оба location через `Filesystem.readdir`
- **Offline**: сканирование работает offline, YouTube — нет (нужен сервер)
- **fs: книга удалена с устройства**: при `Filesystem.getUri` → catch → показать "Файл не найден" + предложить пересканировать
- **Обложки fs: книг**: placeholder по умолчанию (без ID3 extraction, слишком сложно для v1)
- **Post-scan навигация**: после "Добавить N книг" → `/library`. В онбординге — сразу `/library` (пропускаем шаг 3)
