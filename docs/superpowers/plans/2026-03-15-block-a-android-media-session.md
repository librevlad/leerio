# Block A — Android Media Session Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add artwork, seek handlers, and position state to the existing Media Session integration so Android shows a full media notification with cover, controls, and progress bar.

**Architecture:** All changes in a single file (`usePlayer.ts`). Add a `loadCoverBlobUrl()` helper to fetch cover art and create a blob URL, an `updatePositionState()` helper for position reporting, and extend `updateMediaSession()` with artwork and two new action handlers.

**Tech Stack:** Vue 3 composables, Media Session API, Blob/URL APIs

**Spec:** `docs/superpowers/specs/2026-03-15-block-a-android-media-session-design.md`

---

## Chunk 1: Implementation

### Task 1: Add cover blob URL helper and state

**Files:**
- Modify: `app/src/composables/usePlayer.ts:1-2` (imports)
- Modify: `app/src/composables/usePlayer.ts:40-41` (new refs after `isFullscreen`)
- Modify: `app/src/composables/usePlayer.ts:190-208` (updateMediaSession)
- Test: `app/src/composables/usePlayer.test.ts`

- [ ] **Step 0: Update API mock and add global stubs**

First, update the API mock at the top of `usePlayer.test.ts` to include the new imports. Add `coverUrl` and `userBookCoverUrl` to the mock factory (alongside `api` and `audioUrl`):

```ts
vi.mock('../api', () => ({
  api: {
    getBookTracks: vi.fn(),
    getPlaybackPosition: vi.fn(),
    setPlaybackPosition: vi.fn().mockResolvedValue(undefined),
    setProgress: vi.fn().mockResolvedValue(undefined),
    startSession: vi.fn().mockResolvedValue(undefined),
    stopSession: vi.fn().mockResolvedValue(undefined),
    getUserBookTracks: vi.fn(),
  },
  audioUrl: vi.fn((_id: string, _idx: number) => 'http://test/audio.mp3'),
  coverUrl: vi.fn((id: string) => `http://test/books/${id}/cover`),
  userBookCoverUrl: vi.fn((slug: string) => `http://test/user/books/${slug}/cover`),
}))
```

Then add a `MediaMetadata` global stub after all `vi.mock()` calls and before the `createMockAudio()` function:

```ts
// Stub MediaMetadata (not available in JSDOM)
vi.stubGlobal(
  'MediaMetadata',
  class MediaMetadata {
    title?: string
    artist?: string
    album?: string
    artwork?: MediaImage[]
    constructor(init: Record<string, unknown>) {
      Object.assign(this, init)
    }
  },
)
```

- [ ] **Step 1: Write the failing test for loadCoverBlobUrl**

In `app/src/composables/usePlayer.test.ts`, add at the end (before the closing `})`):

```ts
// ── Media Session ─────────────────────────────────────────────────────
describe('media session', () => {
  const mockMetadata = vi.fn()
  const mockSetActionHandler = vi.fn()
  const mockSetPositionState = vi.fn()

  let origCreateObjectURL: typeof URL.createObjectURL
  let origRevokeObjectURL: typeof URL.revokeObjectURL

  beforeEach(() => {
    // Save originals for cleanup
    origCreateObjectURL = URL.createObjectURL
    origRevokeObjectURL = URL.revokeObjectURL

    // Mock navigator.mediaSession
    Object.defineProperty(navigator, 'mediaSession', {
      value: {
        _metadata: null,
        get metadata() {
          return this._metadata
        },
        set metadata(v: MediaMetadata) {
          this._metadata = v
          mockMetadata(v)
        },
        setActionHandler: mockSetActionHandler,
        setPositionState: mockSetPositionState,
      },
      writable: true,
      configurable: true,
    })
    mockMetadata.mockClear()
    mockSetActionHandler.mockClear()
    mockSetPositionState.mockClear()
  })

  afterEach(() => {
    // Restore URL methods
    URL.createObjectURL = origCreateObjectURL
    URL.revokeObjectURL = origRevokeObjectURL
    // Restore fetch
    vi.unstubAllGlobals()
  })

  it('fetches cover and creates blob URL on loadBook', async () => {
    const { api } = await import('../api')
    vi.mocked(api.getBookTracks).mockResolvedValue({
      book_id: '1',
      count: 1,
      tracks: [{ index: 0, filename: '01.mp3', path: '', duration: 60 }],
    })
    vi.mocked(api.getPlaybackPosition).mockResolvedValue({
      track_index: 0,
      position: 0,
    })

    // Mock fetch for cover
    const mockBlob = new Blob(['fake-image'], { type: 'image/jpeg' })
    const mockResponse = {
      ok: true,
      blob: () => Promise.resolve(mockBlob),
      headers: new Headers({ 'Content-Type': 'image/jpeg' }),
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse))

    const mockBlobUrl = 'blob:http://localhost/fake-cover'
    URL.createObjectURL = vi.fn(() => mockBlobUrl)
    URL.revokeObjectURL = vi.fn()

    const p = usePlayer()
    await p.loadBook({
      id: '1',
      folder: 'test',
      category: 'test',
      author: 'Author',
      title: 'Title',
      reader: '',
      path: '',
      progress: 0,
      tags: [],
      note: '',
    })

    // Verify MediaMetadata was created with artwork
    expect(mockMetadata).toHaveBeenCalled()
    const metadata = mockMetadata.mock.calls[0][0]
    expect(metadata.artwork).toEqual([
      { src: mockBlobUrl, sizes: '512x512', type: 'image/jpeg' },
    ])
  })

  it('skips artwork when cover is SVG placeholder', async () => {
    const { api } = await import('../api')
    vi.mocked(api.getBookTracks).mockResolvedValue({
      book_id: '2',
      count: 1,
      tracks: [{ index: 0, filename: '01.mp3', path: '', duration: 60 }],
    })
    vi.mocked(api.getPlaybackPosition).mockResolvedValue({
      track_index: 0,
      position: 0,
    })

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(['<svg></svg>'], { type: 'image/svg+xml' })),
      headers: new Headers({ 'Content-Type': 'image/svg+xml' }),
    }))

    const p = usePlayer()
    await p.loadBook({
      id: '2',
      folder: 'test',
      category: 'test',
      author: 'Author',
      title: 'Title',
      reader: '',
      path: '',
      progress: 0,
      tags: [],
      note: '',
    })

    expect(mockMetadata).toHaveBeenCalled()
    const metadata = mockMetadata.mock.calls[0][0]
    expect(metadata.artwork).toBeUndefined()
  })

  it('omits artwork when cover fetch fails', async () => {
    const { api } = await import('../api')
    vi.mocked(api.getBookTracks).mockResolvedValue({
      book_id: '3',
      count: 1,
      tracks: [{ index: 0, filename: '01.mp3', path: '', duration: 60 }],
    })
    vi.mocked(api.getPlaybackPosition).mockResolvedValue({
      track_index: 0,
      position: 0,
    })

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network error')))

    const p = usePlayer()
    await p.loadBook({
      id: '3',
      folder: 'test',
      category: 'test',
      author: 'Author',
      title: 'Title',
      reader: '',
      path: '',
      progress: 0,
      tags: [],
      note: '',
    })

    expect(mockMetadata).toHaveBeenCalled()
    const metadata = mockMetadata.mock.calls[0][0]
    expect(metadata.artwork).toBeUndefined()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && npx vitest run src/composables/usePlayer.test.ts --reporter=verbose`
Expected: FAIL — artwork tests fail because `updateMediaSession()` doesn't set artwork yet.

- [ ] **Step 3: Add imports and state refs**

In `app/src/composables/usePlayer.ts`, add `coverUrl` and `userBookCoverUrl` to the api import (line 2):

```ts
import { api, audioUrl, coverUrl, userBookCoverUrl } from '../api'
```

Add new refs after `isFullscreen` (after line 40):

```ts
let coverBlobUrl: string | null = null
let coverMimeType: string | null = null
```

- [ ] **Step 4: Add loadCoverBlobUrl helper**

Insert before `updateMediaSession()` (before line 192):

```ts
async function loadCoverBlobUrl(book: Book): Promise<void> {
  // Revoke previous blob URL
  if (coverBlobUrl) {
    URL.revokeObjectURL(coverBlobUrl)
    coverBlobUrl = null
    coverMimeType = null
  }

  try {
    let url: string
    if (book.id.startsWith('lb:')) {
      // Local books: cover stored in IndexedDB — skip for now
      // (IndexedDB blobs need separate handling via useLocalBooks)
      return
    } else if (book.id.startsWith('ub:')) {
      const slug = book.id.split(':')[2] ?? ''
      url = userBookCoverUrl(slug)
    } else {
      url = coverUrl(book.id)
    }

    const response = await fetch(url, { credentials: 'include', redirect: 'follow' })
    if (!response.ok) return

    const contentType = response.headers.get('Content-Type') || 'image/jpeg'
    // Skip SVG placeholders — Android Chrome can't render them in notifications
    if (contentType.includes('svg')) return

    const blob = await response.blob()
    coverBlobUrl = URL.createObjectURL(blob)
    coverMimeType = contentType
  } catch {
    // Cover fetch failed (network, CORS on S3 redirect, etc.) — skip artwork
  }
}
```

- [ ] **Step 5: Update updateMediaSession to include artwork**

Replace the `updateMediaSession()` function (lines 192-208):

```ts
function updateMediaSession() {
  if (!('mediaSession' in navigator) || !currentBook.value) return

  const artwork: MediaImage[] | undefined =
    coverBlobUrl && coverMimeType
      ? [{ src: coverBlobUrl, sizes: '512x512', type: coverMimeType }]
      : undefined

  navigator.mediaSession.metadata = new MediaMetadata({
    title: currentTrack.value?.filename ?? 'Unknown',
    artist: currentBook.value.author,
    album: currentBook.value.title,
    ...(artwork && { artwork }),
  })

  navigator.mediaSession.setActionHandler('play', () => togglePlay())
  navigator.mediaSession.setActionHandler('pause', () => togglePlay())
  navigator.mediaSession.setActionHandler('previoustrack', () => prevTrack())
  navigator.mediaSession.setActionHandler('nexttrack', () => nextTrack())
  navigator.mediaSession.setActionHandler('seekto', (details) => {
    if (details.seekTime != null) seek(details.seekTime)
  })
  navigator.mediaSession.setActionHandler('seekbackward', (details) => {
    skipBackward(details.seekOffset ?? 10)
  })
  navigator.mediaSession.setActionHandler('seekforward', (details) => {
    skipForward(details.seekOffset ?? 30)
  })
}
```

- [ ] **Step 6: Call loadCoverBlobUrl in loadBook**

In `loadBook()`, add `await loadCoverBlobUrl(book)` before each `updateMediaSession()` call.

For the local book path (before line 293 `updateMediaSession()`):
```ts
      await loadCoverBlobUrl(book)
      updateMediaSession()
```

For the main path (before line 344 `updateMediaSession()`):
```ts
    await loadCoverBlobUrl(book)
    updateMediaSession()
```

- [ ] **Step 7: Revoke blob URL in closePlayer**

In `closePlayer()` (line 488), add cleanup before the existing code:

```ts
  if (coverBlobUrl) {
    URL.revokeObjectURL(coverBlobUrl)
    coverBlobUrl = null
    coverMimeType = null
  }
```

- [ ] **Step 8: Run tests**

Run: `cd app && npx vitest run src/composables/usePlayer.test.ts --reporter=verbose`
Expected: All tests PASS including the new artwork tests.

- [ ] **Step 9: Commit**

```bash
git add app/src/composables/usePlayer.ts app/src/composables/usePlayer.test.ts
git commit -m "feat: add artwork to Media Session notification"
```

---

### Task 2: Add seekbackward / seekforward handlers

Tests for these are implicitly covered by Task 1 (the action handlers are set in `updateMediaSession`). Add explicit tests.

**Files:**
- Modify: `app/src/composables/usePlayer.test.ts`

- [ ] **Step 1: Write tests for seek handlers**

Add to the `media session artwork` describe block:

```ts
  it('registers seekbackward handler with 10s default', async () => {
    const { api } = await import('../api')
    vi.mocked(api.getBookTracks).mockResolvedValue({
      book_id: '4',
      count: 1,
      tracks: [{ index: 0, filename: '01.mp3', path: '', duration: 120 }],
    })
    vi.mocked(api.getPlaybackPosition).mockResolvedValue({ track_index: 0, position: 50 })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('no cover')))

    const p = usePlayer()
    await p.loadBook({
      id: '4', folder: '', category: '', author: '', title: '',
      reader: '', path: '', progress: 0, tags: [], note: '',
    })

    // Find the seekbackward handler
    const seekbackwardCall = mockSetActionHandler.mock.calls.find(
      (c: unknown[]) => c[0] === 'seekbackward'
    )
    expect(seekbackwardCall).toBeTruthy()

    // Call handler with no seekOffset — should use 10s default
    mockAudio._setDuration(120)
    p.currentTime.value = 50
    seekbackwardCall![1]({})
    expect(p.currentTime.value).toBe(40)
  })

  it('registers seekforward handler with 30s default', async () => {
    const { api } = await import('../api')
    vi.mocked(api.getBookTracks).mockResolvedValue({
      book_id: '5',
      count: 1,
      tracks: [{ index: 0, filename: '01.mp3', path: '', duration: 120 }],
    })
    vi.mocked(api.getPlaybackPosition).mockResolvedValue({ track_index: 0, position: 20 })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('no cover')))

    const p = usePlayer()
    await p.loadBook({
      id: '5', folder: '', category: '', author: '', title: '',
      reader: '', path: '', progress: 0, tags: [], note: '',
    })

    const seekforwardCall = mockSetActionHandler.mock.calls.find(
      (c: unknown[]) => c[0] === 'seekforward'
    )
    expect(seekforwardCall).toBeTruthy()

    mockAudio._setDuration(120)
    p.currentTime.value = 20
    seekforwardCall![1]({})
    expect(p.currentTime.value).toBe(50)
  })
```

- [ ] **Step 2: Run tests**

Run: `cd app && npx vitest run src/composables/usePlayer.test.ts --reporter=verbose`
Expected: All PASS — handlers were already added in Task 1 Step 5.

- [ ] **Step 3: Commit**

```bash
git add app/src/composables/usePlayer.test.ts
git commit -m "test: add seekbackward/seekforward handler tests"
```

---

### Task 3: Add position state reporting

**Files:**
- Modify: `app/src/composables/usePlayer.ts:71-147` (ensureAudio event listeners)
- Test: `app/src/composables/usePlayer.test.ts`

- [ ] **Step 1: Write failing test for updatePositionState**

Add to the `media session artwork` describe block:

```ts
  it('calls setPositionState on play event', async () => {
    const { api } = await import('../api')
    vi.mocked(api.getBookTracks).mockResolvedValue({
      book_id: '6',
      count: 1,
      tracks: [{ index: 0, filename: '01.mp3', path: '', duration: 60 }],
    })
    vi.mocked(api.getPlaybackPosition).mockResolvedValue({ track_index: 0, position: 0 })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('no cover')))

    const p = usePlayer()
    await p.loadBook({
      id: '6', folder: '', category: '', author: '', title: '',
      reader: '', path: '', progress: 0, tags: [], note: '',
    })

    mockSetPositionState.mockClear()
    mockAudio._setDuration(60)
    mockAudio._emit('play')

    expect(mockSetPositionState).toHaveBeenCalledWith({
      duration: 60,
      position: expect.any(Number),
      playbackRate: expect.any(Number),
    })
  })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && npx vitest run src/composables/usePlayer.test.ts --reporter=verbose`
Expected: FAIL — `setPositionState` is not called on play event yet.

- [ ] **Step 3: Add updatePositionState helper**

Insert after `updateMediaSession()` function in `usePlayer.ts`:

```ts
function updatePositionState() {
  if (!('mediaSession' in navigator) || !audio) return
  try {
    navigator.mediaSession.setPositionState({
      duration: audio.duration || 0,
      position: audio.currentTime || 0,
      playbackRate: audio.playbackRate || 1,
    })
  } catch {
    // setPositionState can throw if duration is NaN or 0
  }
}
```

- [ ] **Step 4: Hook updatePositionState into audio events**

In `ensureAudio()`, add `updatePositionState()` calls:

After the `loadedmetadata` listener (after line 86):
```ts
    audio.addEventListener('loadedmetadata', () => {
      duration.value = audio!.duration
      isLoading.value = false
      updatePositionState()
    })
```

After the `play` listener (inside the play handler, after `startSaveTimer()`):
```ts
    audio.addEventListener('play', () => {
      isPlaying.value = true
      startSaveTimer()
      updatePositionState()
      // ... rest of session code
    })
```

After the `pause` listener (inside the pause handler, after `isPlaying.value = false`):
```ts
    audio.addEventListener('pause', () => {
      isPlaying.value = false
      updatePositionState()
      stopSaveTimer()
      // ... rest
    })
```

Add a `seeked` listener (after the `error` listener, ~line 127):
```ts
    audio.addEventListener('seeked', () => {
      updatePositionState()
    })
```

- [ ] **Step 5: Call updatePositionState when playback rate changes**

In `setPlaybackRate()` function, add at the end:

```ts
function setPlaybackRate(rate: number) {
  playbackRate.value = rate
  if (audio) audio.playbackRate = rate
  localStorage.setItem('leerio_playback_rate', String(rate))
  updatePositionState()
}
```

- [ ] **Step 6: Run tests**

Run: `cd app && npx vitest run src/composables/usePlayer.test.ts --reporter=verbose`
Expected: All PASS.

- [ ] **Step 7: Run full lint + type check**

Run: `cd app && npx vue-tsc --noEmit && npx eslint src/composables/usePlayer.ts`
Expected: No errors.

- [ ] **Step 8: Commit**

```bash
git add app/src/composables/usePlayer.ts app/src/composables/usePlayer.test.ts
git commit -m "feat: add position state to Media Session for notification progress bar"
```

---

### Task 4: Final verification

- [ ] **Step 1: Run full test suite**

Run: `cd app && npx vitest run --reporter=verbose`
Expected: All tests PASS.

- [ ] **Step 2: Run full lint**

Run: `cd app && npx eslint src/ && npx prettier --check src/ && npx vue-tsc --noEmit`
Expected: No errors.

- [ ] **Step 3: Commit any fixes if needed**

---

## Summary of all changes to `usePlayer.ts`

| Location | Change |
|----------|--------|
| Line 2 | Add `coverUrl, userBookCoverUrl` to imports |
| After line 40 | Add `coverBlobUrl`, `coverMimeType` variables |
| Before `updateMediaSession` | Add `loadCoverBlobUrl()` helper |
| `updateMediaSession()` | Add artwork to MediaMetadata, add seekbackward/seekforward handlers |
| After `updateMediaSession` | Add `updatePositionState()` helper |
| `ensureAudio()` listeners | Add `updatePositionState()` to loadedmetadata, play, pause; add seeked listener |
| `setPlaybackRate()` | Add `updatePositionState()` call |
| `loadBook()` (2 places) | Add `await loadCoverBlobUrl(book)` before `updateMediaSession()` |
| `closePlayer()` | Add `URL.revokeObjectURL()` cleanup |
