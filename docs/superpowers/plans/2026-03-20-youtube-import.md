# YouTube Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Users can paste a YouTube URL, download audio, split into chapters, and save as a local audiobook with optional cloud upload.

**Architecture:** Server resolves YouTube metadata via yt-dlp and streams audio on demand. Client downloads through server proxy, splits with ffmpeg.wasm (single-threaded), saves to IndexedDB via useLocalBooks. Cloud upload reuses existing uploadBook flow.

**Tech Stack:** Python (yt-dlp, FastAPI), Vue 3 + TypeScript, ffmpeg.wasm (single-threaded), IndexedDB

**Spec:** `docs/superpowers/specs/2026-03-20-youtube-import-design.md`

---

## File Structure

### Create:
- `server/youtube_api.py` — FastAPI router: `/api/youtube/resolve` + `/api/youtube/stream/{video_id}`
- `server/tests/test_youtube_api.py` — backend endpoint tests
- `app/src/composables/useYouTubeImport.ts` — download + split + save composable
- `app/src/composables/useYouTubeImport.test.ts` — unit tests

### Modify:
- `server/api.py` — import and include youtube router
- `app/src/api.ts` — add `youtubeResolve()` API method
- `app/src/views/UploadView.vue` — add YouTube tab
- `app/src/views/MyLibraryView.vue` — add "В облако" button for `lb:` books
- `app/src/composables/useLocalBooks.ts` — fix blob URL revocation bug
- `app/src/composables/useLocalBooks.test.ts` — update tests for fix
- `app/src/i18n/locales/ru.ts` — YouTube translations
- `app/src/i18n/locales/en.ts` — YouTube translations
- `app/src/i18n/locales/uk.ts` — YouTube translations
- `app/package.json` — add `@ffmpeg/ffmpeg`, `@ffmpeg/util`

---

## Task 0: Prerequisite — Fix useLocalBooks blob URL revocation

**Files:**
- Modify: `app/src/composables/useLocalBooks.ts:11,161-170`
- Modify: `app/src/composables/useLocalBooks.test.ts`

- [ ] **Step 1: Write failing test**

In `useLocalBooks.test.ts`, add test that verifies getting audio URL for track B does NOT revoke track A's URL:

```typescript
it('does not revoke current track URL when preloading next', async () => {
  // Setup: add a book with 2 tracks
  // Get audio URL for track 0
  // Get audio URL for track 1
  // Verify URL.revokeObjectURL was NOT called for track 0's URL
})
```

- [ ] **Step 2: Run test — verify fail**

Run: `cd app && npx vitest run src/composables/useLocalBooks.test.ts`

- [ ] **Step 3: Implement fix**

In `useLocalBooks.ts`, replace single `previousAudioUrl` with a `Map`:

```typescript
// Replace line 11:
// let previousAudioUrl: string | null = null
const activeBlobUrls = new Map<string, string>()

// Replace getLocalAudioUrl (lines 161-170):
async function getLocalAudioUrl(bookId: string, trackIndex: number): Promise<string | null> {
  const key = `${bookId}/${trackIndex}`
  const existing = activeBlobUrls.get(key)
  if (existing) return existing

  const blob = await getBlob(key)
  if (!blob) return null

  const url = URL.createObjectURL(blob)
  activeBlobUrls.set(key, url)
  return url
}

function revokeAudioUrls(keepKeys?: Set<string>) {
  for (const [key, url] of activeBlobUrls) {
    if (!keepKeys || !keepKeys.has(key)) {
      URL.revokeObjectURL(url)
      activeBlobUrls.delete(key)
    }
  }
}
```

Export `revokeAudioUrls` from `useLocalBooks()` return object.

- [ ] **Step 4: Run test — verify pass**

Run: `cd app && npx vitest run src/composables/useLocalBooks.test.ts`

- [ ] **Step 5: Run all tests + type check**

Run: `cd app && npx vitest run && npx vue-tsc --noEmit`

- [ ] **Step 6: Commit**

```bash
git add app/src/composables/useLocalBooks.ts app/src/composables/useLocalBooks.test.ts
git commit -m "fix: prevent blob URL revocation of playing track in useLocalBooks"
```

---

## Task 1: Backend — YouTube resolve endpoint

**Files:**
- Create: `server/youtube_api.py`
- Modify: `server/api.py:59-63,391-394`

- [ ] **Step 1: Create `server/youtube_api.py`**

```python
"""YouTube metadata resolution and audio streaming."""
import re
import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .auth import get_current_user

router = APIRouter(prefix="/api/youtube", tags=["youtube"])

_YT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
_YT_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})"
)
_MAX_DURATION = 24 * 3600  # 24 hours


class ResolveRequest(BaseModel):
    url: str


class Chapter(BaseModel):
    title: str
    start: float
    end: float


class ResolveResponse(BaseModel):
    video_id: str
    title: str
    author: str
    duration: float
    thumbnail: str
    chapters: list[Chapter]


def _parse_author(title: str) -> tuple[str, str]:
    """Try to extract author from 'Author — Title' or 'Author - Title'."""
    for sep in (" — ", " – ", " - "):
        if sep in title:
            parts = title.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return "", title


def _extract_video_id(url: str) -> str | None:
    m = _YT_URL_RE.search(url)
    return m.group(1) if m else None


async def _yt_dlp_json(video_id: str) -> dict:
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp", "--dump-json", "--no-download", "--no-warnings",
        f"https://www.youtube.com/watch?v={video_id}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        if "Private video" in err or "Video unavailable" in err:
            raise HTTPException(404, "Video not found or private")
        raise HTTPException(400, f"yt-dlp error: {err[:200]}")
    return json.loads(stdout)


@router.post("/resolve", response_model=ResolveResponse)
async def resolve(body: ResolveRequest, _user=Depends(get_current_user)):
    video_id = _extract_video_id(body.url)
    if not video_id:
        raise HTTPException(400, "Invalid YouTube URL")

    info = await _yt_dlp_json(video_id)

    duration = info.get("duration") or 0
    if duration > _MAX_DURATION:
        raise HTTPException(413, f"Video too long ({duration}s > {_MAX_DURATION}s)")

    raw_title = info.get("title", "")
    author, title = _parse_author(raw_title)

    chapters: list[Chapter] = []
    for ch in info.get("chapters") or []:
        start = ch.get("start_time", 0)
        end = ch.get("end_time", 0)
        if end > start:
            chapters.append(Chapter(title=ch.get("title", ""), start=start, end=end))

    thumbnail = info.get("thumbnail", "")

    return ResolveResponse(
        video_id=video_id,
        title=title,
        author=author,
        duration=duration,
        thumbnail=thumbnail,
        chapters=chapters,
    )


@router.get("/stream/{video_id}")
async def stream_audio(video_id: str, _user=Depends(get_current_user)):
    if not _YT_ID_RE.match(video_id):
        raise HTTPException(400, "Invalid video ID")

    proc = await asyncio.create_subprocess_exec(
        "yt-dlp", "-f", "bestaudio", "-o", "-",
        f"https://www.youtube.com/watch?v={video_id}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def generate():
        try:
            while True:
                chunk = await proc.stdout.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            if proc.returncode is None:
                proc.kill()

    return StreamingResponse(
        generate(),
        media_type="audio/webm",
        headers={"Cache-Control": "no-store"},
    )
```

- [ ] **Step 2: Register router in `server/api.py`**

Add import (around line 63):
```python
from .youtube_api import router as youtube_router
```

Add include (around line 394):
```python
app.include_router(youtube_router)
```

- [ ] **Step 3: Test manually**

```bash
LEERIO_DEV=1 python -m uvicorn server.api:app --port 8000
# In another terminal:
curl -X POST http://localhost:8000/api/youtube/resolve \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}' \
  -b "session=..."
```

- [ ] **Step 4: Commit**

```bash
git add server/youtube_api.py server/api.py
git commit -m "feat: add YouTube resolve and stream endpoints"
```

---

## Task 2: Frontend — API methods + types

**Files:**
- Modify: `app/src/api.ts:142-251`
- Modify: `app/src/types.ts`

- [ ] **Step 1: Add types to `types.ts`**

```typescript
// ── YouTube types ────────────────────────────────────────────────────
export interface YouTubeChapter {
  title: string
  start: number
  end: number
}

export interface YouTubeResolveResult {
  video_id: string
  title: string
  author: string
  duration: number
  thumbnail: string
  chapters: YouTubeChapter[]
}
```

- [ ] **Step 2: Add API methods to `api.ts`**

In the `api` object (around line 250), add:

```typescript
  // YouTube
  youtubeResolve: (url: string) => post<YouTubeResolveResult>('/youtube/resolve', { url }),
  youtubeStreamUrl: (videoId: string) => apiUrl(`/youtube/stream/${videoId}`),
```

Note: `youtubeStreamUrl` returns a URL string (not a fetch), because the client will `fetch()` it with ReadableStream for progress tracking.

- [ ] **Step 3: Type check**

Run: `cd app && npx vue-tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add app/src/types.ts app/src/api.ts
git commit -m "feat: add YouTube API types and methods"
```

---

## Task 3: Install ffmpeg.wasm

**Files:**
- Modify: `app/package.json`

- [ ] **Step 1: Install**

```bash
cd app && npm install @ffmpeg/ffmpeg @ffmpeg/util
```

- [ ] **Step 2: Verify build**

```bash
cd app && npx vite build 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
git add app/package.json app/package-lock.json
git commit -m "chore: add @ffmpeg/ffmpeg and @ffmpeg/util"
```

---

## Task 4: Frontend — useYouTubeImport composable

**Files:**
- Create: `app/src/composables/useYouTubeImport.ts`
- Create: `app/src/composables/useYouTubeImport.test.ts`

- [ ] **Step 1: Write tests first**

Create `app/src/composables/useYouTubeImport.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api', () => ({
  api: {
    youtubeResolve: vi.fn(),
    youtubeStreamUrl: vi.fn((id: string) => `/api/youtube/stream/${id}`),
  },
}))

vi.mock('./useLocalBooks', () => ({
  useLocalBooks: () => ({
    addLocalBook: vi.fn().mockResolvedValue({ id: 'lb:test', title: 'Test', author: 'A', tracks: [], addedAt: '' }),
  }),
}))

import { useYouTubeImport } from './useYouTubeImport'
import { api } from '../api'

describe('useYouTubeImport', () => {
  beforeEach(() => {
    vi.mocked(api.youtubeResolve).mockReset()
  })

  it('starts in idle state', () => {
    const yt = useYouTubeImport()
    expect(yt.step.value).toBe('idle')
    expect(yt.progress.value).toBe(0)
  })

  it('resolve sets metadata from API', async () => {
    vi.mocked(api.youtubeResolve).mockResolvedValue({
      video_id: 'abc12345678',
      title: 'Test Book',
      author: 'Author',
      duration: 3600,
      thumbnail: 'https://img.youtube.com/thumb.jpg',
      chapters: [{ title: 'Ch 1', start: 0, end: 1800 }],
    })

    const yt = useYouTubeImport()
    await yt.resolve('https://youtube.com/watch?v=abc12345678')

    expect(yt.step.value).toBe('resolved')
    expect(yt.title.value).toBe('Test Book')
    expect(yt.author.value).toBe('Author')
    expect(yt.chapters.value).toHaveLength(1)
  })

  it('resolve handles errors', async () => {
    vi.mocked(api.youtubeResolve).mockRejectedValue(new Error('400: Invalid URL'))

    const yt = useYouTubeImport()
    await yt.resolve('invalid')

    expect(yt.step.value).toBe('error')
    expect(yt.errorMessage.value).toContain('Invalid URL')
  })

  it('reset clears all state', async () => {
    const yt = useYouTubeImport()
    yt.title.value = 'Something'
    yt.step.value = 'error'
    yt.reset()
    expect(yt.step.value).toBe('idle')
    expect(yt.title.value).toBe('')
  })

  it('generates chapters for unchaptered audio', () => {
    const yt = useYouTubeImport()
    const chapters = yt.generateChapters(3600, 600) // 1h, 10min chunks
    expect(chapters).toHaveLength(6)
    expect(chapters[0]).toEqual({ title: 'Глава 1', start: 0, end: 600 })
    expect(chapters[5]).toEqual({ title: 'Глава 6', start: 3000, end: 3600 })
  })
})
```

- [ ] **Step 2: Run tests — verify fail**

Run: `cd app && npx vitest run src/composables/useYouTubeImport.test.ts`

- [ ] **Step 3: Implement composable**

Create `app/src/composables/useYouTubeImport.ts`:

```typescript
import { ref } from 'vue'
import { api } from '../api'
import { useLocalBooks } from './useLocalBooks'
import type { YouTubeChapter, YouTubeResolveResult } from '../types'

type Step = 'idle' | 'resolving' | 'resolved' | 'downloading' | 'splitting' | 'saving' | 'done' | 'error'

export function useYouTubeImport() {
  const step = ref<Step>('idle')
  const progress = ref(0)
  const title = ref('')
  const author = ref('')
  const duration = ref(0)
  const thumbnail = ref('')
  const chapters = ref<YouTubeChapter[]>([])
  const videoId = ref('')
  const errorMessage = ref('')

  let abortController: AbortController | null = null

  async function resolve(url: string) {
    step.value = 'resolving'
    progress.value = 0
    errorMessage.value = ''
    try {
      const result: YouTubeResolveResult = await api.youtubeResolve(url)
      videoId.value = result.video_id
      title.value = result.title
      author.value = result.author
      duration.value = result.duration
      thumbnail.value = result.thumbnail
      chapters.value = result.chapters
      step.value = 'resolved'
    } catch (e) {
      step.value = 'error'
      errorMessage.value = e instanceof Error ? e.message : 'Unknown error'
    }
  }

  async function download(): Promise<Blob | null> {
    if (!videoId.value) return null
    step.value = 'downloading'
    progress.value = 0
    abortController = new AbortController()

    try {
      const url = api.youtubeStreamUrl(videoId.value)
      const res = await fetch(url, {
        credentials: 'include',
        signal: abortController.signal,
      })
      if (!res.ok) throw new Error(`Download failed: ${res.status}`)
      if (!res.body) throw new Error('No response body')

      const contentLength = Number(res.headers.get('content-length')) || 0
      const reader = res.body.getReader()
      const chunks: Uint8Array[] = []
      let received = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        chunks.push(value)
        received += value.length
        if (contentLength > 0) {
          progress.value = Math.round((received / contentLength) * 100)
        }
      }

      return new Blob(chunks)
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        step.value = 'idle'
        return null
      }
      step.value = 'error'
      errorMessage.value = e instanceof Error ? e.message : 'Download failed'
      return null
    }
  }

  async function splitAudio(blob: Blob, chapterList: YouTubeChapter[]): Promise<File[]> {
    step.value = 'splitting'
    progress.value = 0

    const { FFmpeg } = await import('@ffmpeg/ffmpeg')
    const { fetchFile } = await import('@ffmpeg/util')

    const ffmpeg = new FFmpeg()
    await ffmpeg.load()

    const inputName = 'input.webm'
    const inputData = await fetchFile(blob)
    await ffmpeg.writeFile(inputName, inputData)

    const files: File[] = []

    for (let i = 0; i < chapterList.length; i++) {
      const ch = chapterList[i]
      const outputName = `chapter-${String(i + 1).padStart(3, '0')}.mp3`
      await ffmpeg.exec([
        '-i', inputName,
        '-ss', String(ch.start),
        '-to', String(ch.end),
        '-c', 'copy',
        '-y', outputName,
      ])
      const data = await ffmpeg.readFile(outputName)
      const fileBlob = new Blob([data], { type: 'audio/mpeg' })
      files.push(new File([fileBlob], outputName, { type: 'audio/mpeg' }))
      progress.value = Math.round(((i + 1) / chapterList.length) * 100)
    }

    ffmpeg.terminate()
    return files
  }

  function generateChapters(totalDuration: number, chunkSeconds: number): YouTubeChapter[] {
    const result: YouTubeChapter[] = []
    let start = 0
    let i = 1
    while (start < totalDuration) {
      const end = Math.min(start + chunkSeconds, totalDuration)
      result.push({ title: `Глава ${i}`, start, end })
      start = end
      i++
    }
    return result
  }

  async function importFromYouTube(chunkMinutes?: number) {
    try {
      const blob = await download()
      if (!blob) return

      let chapterList = chapters.value
      if (!chapterList.length) {
        chapterList = generateChapters(duration.value, (chunkMinutes ?? 10) * 60)
      }

      const files = await splitAudio(blob, chapterList)
      if (!files.length) {
        step.value = 'error'
        errorMessage.value = 'No chapters produced'
        return
      }

      step.value = 'saving'
      progress.value = 0

      const { addLocalBook } = useLocalBooks()
      await addLocalBook(files, {
        title: title.value,
        author: author.value,
      })

      step.value = 'done'
      progress.value = 100
    } catch (e) {
      step.value = 'error'
      errorMessage.value = e instanceof Error ? e.message : 'Import failed'
    }
  }

  function cancel() {
    abortController?.abort()
    abortController = null
    step.value = 'idle'
    progress.value = 0
  }

  function reset() {
    cancel()
    title.value = ''
    author.value = ''
    duration.value = 0
    thumbnail.value = ''
    chapters.value = []
    videoId.value = ''
    errorMessage.value = ''
  }

  return {
    step, progress, title, author, duration, thumbnail,
    chapters, videoId, errorMessage,
    resolve, importFromYouTube, cancel, reset, generateChapters,
  }
}
```

- [ ] **Step 4: Run tests — verify pass**

Run: `cd app && npx vitest run src/composables/useYouTubeImport.test.ts`

- [ ] **Step 5: Type check**

Run: `cd app && npx vue-tsc --noEmit`

- [ ] **Step 6: Commit**

```bash
git add app/src/composables/useYouTubeImport.ts app/src/composables/useYouTubeImport.test.ts
git commit -m "feat: add useYouTubeImport composable with tests"
```

---

## Task 5: i18n translations

**Files:**
- Modify: `app/src/i18n/locales/ru.ts`
- Modify: `app/src/i18n/locales/en.ts`
- Modify: `app/src/i18n/locales/uk.ts`

- [ ] **Step 1: Add Russian translations**

In `ru.ts` upload section (around line 189), add:

```typescript
tabYouTube: 'YouTube',
youtubeUrl: 'Ссылка на YouTube',
youtubeUrlPlaceholder: 'https://youtube.com/watch?v=...',
youtubeFind: 'Найти',
youtubeDownload: 'Скачать и сохранить',
youtubeResolving: 'Получение данных...',
youtubeDownloading: 'Скачивание',
youtubeSplitting: 'Нарезка на главы...',
youtubeSaving: 'Сохранение...',
youtubeDone: 'Книга сохранена!',
youtubeNoChapters: 'Без глав — будет разбито по {n} мин',
youtubeChunkLength: 'Длина главы (мин)',
youtubeCancel: 'Отмена',
```

- [ ] **Step 2: Add English and Ukrainian translations**

Same keys with translated values in `en.ts` and `uk.ts`.

- [ ] **Step 3: Commit**

```bash
git add app/src/i18n/locales/
git commit -m "feat: add YouTube import translations"
```

---

## Task 6: UI — YouTube tab in UploadView

**Files:**
- Modify: `app/src/views/UploadView.vue:13,25,313-317`

- [ ] **Step 1: Add YouTube tab type and definition**

Line 25 — add `'youtube'` to type:
```typescript
const activeTab = ref<'upload' | 'youtube' | 'tts' | 'local'>('upload')
```

Lines 313-317 — add YouTube tab to `tabDefs`:
```typescript
{ key: 'youtube' as const, label: t('upload.tabYouTube'), icon: IconPlay },
```

- [ ] **Step 2: Add YouTube tab content section**

After the existing tab content sections, add a new `v-else-if="activeTab === 'youtube'"` block with:
- URL input + "Найти" button
- Resolve result card (thumbnail, editable title/author, chapters list)
- Chunk length slider (when no chapters)
- "Скачать и сохранить" button
- Progress bar with step text
- Cancel button

Use `useYouTubeImport()` composable for all logic.

- [ ] **Step 3: Test visually**

Open `http://localhost:5173/upload`, verify YouTube tab appears and UI renders correctly.

- [ ] **Step 4: Commit**

```bash
git add app/src/views/UploadView.vue
git commit -m "feat: add YouTube tab to upload view"
```

---

## Task 7: UI — "В облако" button in MyLibraryView

**Files:**
- Modify: `app/src/views/MyLibraryView.vue:334-340`

- [ ] **Step 1: Add cloud upload button for local books**

In the book card footer (lines 334-340), add a cloud upload button that only shows for items where `item.id.startsWith('lb:')`:

```html
<button
  v-if="item.id.startsWith('lb:')"
  class="..."
  @click.prevent="uploadToCloud(item)"
>
  <IconUpload :size="14" />
</button>
```

- [ ] **Step 2: Implement `uploadToCloud` function**

```typescript
async function uploadToCloud(item: UnifiedItem) {
  // 1. Get all track blobs from IndexedDB via useLocalBooks
  // 2. Wrap each as File with proper filename
  // 3. Create FormData with title, author, files
  // 4. Call api.uploadBook(formData) with XHR for progress
  // 5. On success: remove local book, reload user books
}
```

- [ ] **Step 3: Test visually**

Navigate to My Library, verify cloud button appears on local books.

- [ ] **Step 4: Commit**

```bash
git add app/src/views/MyLibraryView.vue
git commit -m "feat: add upload-to-cloud button for local books"
```

---

## Task 8: Integration test

- [ ] **Step 1: Run full test suite**

```bash
cd app && npx vitest run && npx vue-tsc --noEmit && npx eslint src/
```

- [ ] **Step 2: Run coverage**

```bash
cd app && npx vitest run --coverage
```

- [ ] **Step 3: Manual E2E test**

1. Open `/upload` → YouTube tab
2. Paste a YouTube URL → verify resolve shows metadata
3. Click "Скачать и сохранить" → verify download + split progress
4. Check "Моя библиотека" → book appears
5. Play the book → verify audio plays correctly
6. Click cloud upload button → verify upload works

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: YouTube audio import — complete implementation"
```
