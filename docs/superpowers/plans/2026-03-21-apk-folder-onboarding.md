# APK Folder Onboarding + Cloud Upload — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let APK users scan their device for audiobooks in onboarding and library, play them from the filesystem, and optionally sync to cloud (premium).

**Architecture:** Extend `useFileScanner` with persistent localStorage storage (`leerio_fs_books`). Add `fs:` branch to `resolveAudioSrc` using `Filesystem.getUri(ExternalStorage)` + `convertFileSrc`. FAB in library opens popup with all add-book options. YouTube downloads to filesystem via Capacitor HTTP, keeping server as a stream proxy (no storage).

**Tech Stack:** Vue 3, Capacitor 8 (Filesystem, HTTP), TypeScript, Tailwind, Python/FastAPI backend

**Spec:** `docs/superpowers/specs/2026-03-21-apk-folder-onboarding-design.md`

---

## File Map

### New files
| File | Responsibility |
|------|---------------|
| `app/src/views/ScanResultsView.vue` | Fullscreen scan results with checkboxes |
| `app/src/components/library/AddBookFab.vue` | FAB "+" button + popup menu |
| `app/src/views/YouTubeImportView.vue` | Fullscreen YouTube import (extracted from YouTubeTab) |

### Modified files
| File | Changes |
|------|---------|
| `app/src/types.ts` | Add `FsBookMeta`, `FsTrack` interfaces |
| `app/src/constants/storage.ts` | Add `FS_BOOKS` key |
| `app/src/composables/useFileScanner.ts` | Persistent storage, multi-dir scan, size calc, heuristics, async yielding |
| `app/src/composables/usePlayer.ts` | `resolveAudioSrc()` — add `fs:` branch |
| `app/src/views/WelcomeView.vue` | Step 2: three buttons instead of drop zone |
| `app/src/views/LibraryView.vue` | Mount AddBookFab |
| `app/src/views/BookDetailView.vue` | "On device" badge + "Upload to cloud" button |
| `app/src/composables/useYouTubeImport.ts` | Download to filesystem via Capacitor HTTP |
| `app/src/router.ts` | Routes `/scan-results`, `/youtube-import` |
| `app/android/app/src/main/AndroidManifest.xml` | Add storage permissions |
| `server/youtube_api.py` | No changes needed (keep stream proxy as-is) |

---

## Task 1: Types & Storage Keys

**Files:**
- Modify: `app/src/types.ts:265-281`
- Modify: `app/src/constants/storage.ts`

- [ ] **Step 1: Add FsTrack and FsBookMeta interfaces to types.ts**

After the existing `LocalBook` interface (line 281), add:

```typescript
// ── Filesystem Book types (scanned from device) ─────────────────────────

export interface FsTrack {
  index: number
  filename: string
  path: string // relative to ExternalStorage, e.g. "Audiobooks/Author - Title/01.mp3"
  duration: number
}

export interface FsBookMeta {
  id: string // "fs:{folderName}"
  title: string
  author: string
  folderPath: string // relative to ExternalStorage, e.g. "Audiobooks/Author - Title"
  tracks: FsTrack[]
  sizeBytes: number
  synced: boolean
  addedAt: string
}
```

- [ ] **Step 2: Add FS_BOOKS storage key**

In `app/src/constants/storage.ts`, add to the STORAGE object:

```typescript
FS_BOOKS: 'leerio_fs_books',
```

- [ ] **Step 3: Run type check**

Run: `cd app && npx vue-tsc --noEmit`
Expected: PASS (no errors)

- [ ] **Step 4: Commit**

```bash
git add app/src/types.ts app/src/constants/storage.ts
git commit -m "feat: add FsBookMeta/FsTrack types and FS_BOOKS storage key"
```

---

## Task 2: useFileScanner — Persistent Multi-Directory Scanner

**Files:**
- Modify: `app/src/composables/useFileScanner.ts`
- Create: `app/src/__tests__/useFileScanner.test.ts`

- [ ] **Step 1: Write tests for useFileScanner**

Create `app/src/__tests__/useFileScanner.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock Capacitor
vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => false },
}))
vi.mock('@capacitor/filesystem', () => ({
  Filesystem: {
    readdir: vi.fn(),
    stat: vi.fn(),
    getUri: vi.fn(),
    mkdir: vi.fn(),
  },
  Directory: { ExternalStorage: 'EXTERNAL_STORAGE' },
}))

import { useFileScanner } from '../composables/useFileScanner'

describe('useFileScanner', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns empty on web (not native)', async () => {
    const { scan } = useFileScanner()
    const result = await scan()
    expect(result).toEqual([])
  })

  it('loads persisted books from localStorage', () => {
    const books = { 'fs:test': { id: 'fs:test', title: 'Test', author: '', folderPath: 'Audiobooks/test', tracks: [], sizeBytes: 0, synced: false, addedAt: '2026-01-01' } }
    localStorage.setItem('leerio_fs_books', JSON.stringify(books))
    const { fsBooks } = useFileScanner()
    expect(fsBooks.value['fs:test']?.title).toBe('Test')
  })

  it('cleanTitle extracts title from "Author - Title [Reader]"', () => {
    const { cleanTitle } = useFileScanner()
    expect(cleanTitle('Толстой - Война и мир [Иванов]')).toBe('Война и мир')
    expect(cleanTitle('Simple Book')).toBe('Simple Book')
  })

  it('extractAuthor extracts author from "Author - Title"', () => {
    const { extractAuthor } = useFileScanner()
    expect(extractAuthor('Толстой - Война и мир')).toBe('Толстой')
    expect(extractAuthor('NoAuthor')).toBe('')
  })

  it('isLikelyNotBook returns true for short or keyword folders', () => {
    const { isLikelyNotBook } = useFileScanner()
    expect(isLikelyNotBook('podcast_episodes', 1)).toBe(true)
    expect(isLikelyNotBook('My Audiobook', 10)).toBe(false)
    expect(isLikelyNotBook('music_collection', 5)).toBe(true)
    expect(isLikelyNotBook('book', 1)).toBe(true) // < 2 tracks
  })

  it('addFsBooks persists to localStorage', () => {
    const { addFsBooks, fsBooks } = useFileScanner()
    addFsBooks([{
      id: 'fs:mybook',
      title: 'My Book',
      author: 'Author',
      folderPath: 'Audiobooks/mybook',
      tracks: [{ index: 0, filename: '01.mp3', path: 'Audiobooks/mybook/01.mp3', duration: 0 }],
      sizeBytes: 1000,
      synced: false,
      addedAt: '2026-01-01',
    }])
    expect(fsBooks.value['fs:mybook']).toBeDefined()
    const stored = JSON.parse(localStorage.getItem('leerio_fs_books') || '{}')
    expect(stored['fs:mybook']).toBeDefined()
  })

  it('removeFsBook removes from localStorage', () => {
    const { addFsBooks, removeFsBook, fsBooks } = useFileScanner()
    addFsBooks([{ id: 'fs:x', title: 'X', author: '', folderPath: 'Audiobooks/x', tracks: [], sizeBytes: 0, synced: false, addedAt: '' }])
    removeFsBook('fs:x')
    expect(fsBooks.value['fs:x']).toBeUndefined()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd app && npx vitest run src/__tests__/useFileScanner.test.ts`
Expected: FAIL (missing exports)

- [ ] **Step 3: Rewrite useFileScanner.ts**

Replace `app/src/composables/useFileScanner.ts` entirely:

```typescript
/**
 * Scans device storage for audiobook folders (Capacitor native only).
 *
 * Convention: each subfolder = one book. Folder name = book title.
 * Audio files inside = tracks (sorted by name).
 *
 * Scans: /Audiobooks/, /Download/, /Music/ (ExternalStorage).
 * On web: no-op (returns empty).
 *
 * Persistent storage: localStorage "leerio_fs_books" (Record<string, FsBookMeta>).
 */
import { ref } from 'vue'
import { Capacitor } from '@capacitor/core'
import { Filesystem, Directory } from '@capacitor/filesystem'
import { STORAGE } from '../constants/storage'
import type { FsBookMeta, FsTrack } from '../types'

const SCAN_DIRS = ['Audiobooks', 'Download', 'Music']
const AUDIO_EXT = /\.(mp3|m4a|m4b|ogg|opus|flac|wav)$/i
const NOT_BOOK_KEYWORDS = /podcast|music|ringtone|notification|alarm|recording/i
const MAX_DEPTH = 2

// ── Singleton state ────────────────────────────────────────────────────

const fsBooks = ref<Record<string, FsBookMeta>>(loadFromStorage())
const scanning = ref(false)
const scanProgress = ref('')

function loadFromStorage(): Record<string, FsBookMeta> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE.FS_BOOKS) || '{}')
  } catch {
    return {}
  }
}

function persist() {
  localStorage.setItem(STORAGE.FS_BOOKS, JSON.stringify(fsBooks.value))
}

// ── Public API ─────────────────────────────────────────────────────────

export function useFileScanner() {
  const isNative = Capacitor.isNativePlatform()

  async function scan(): Promise<FsBookMeta[]> {
    if (!isNative) return []
    scanning.value = true
    scanProgress.value = ''

    const found: FsBookMeta[] = []

    try {
      for (const dir of SCAN_DIRS) {
        scanProgress.value = dir
        try {
          const result = await Filesystem.readdir({
            path: dir,
            directory: Directory.ExternalStorage,
          })

          let processed = 0
          for (const entry of result.files) {
            if (entry.type !== 'directory') continue

            const bookPath = `${dir}/${entry.name}`
            const tracks = await scanFolder(bookPath)

            if (tracks.length > 0) {
              const id = `fs:${entry.name}`
              // Skip duplicates already in persistent store
              if (fsBooks.value[id]) continue

              let sizeBytes = 0
              for (const track of tracks) {
                try {
                  const stat = await Filesystem.stat({
                    path: track.path,
                    directory: Directory.ExternalStorage,
                  })
                  sizeBytes += stat.size || 0
                } catch { /* stat can fail on some devices */ }
              }

              found.push({
                id,
                title: cleanTitle(entry.name),
                author: extractAuthor(entry.name),
                folderPath: bookPath,
                tracks,
                sizeBytes,
                synced: false,
                addedAt: new Date().toISOString(),
              })
            }

            // Yield to UI every 50 entries
            processed++
            if (processed % 50 === 0) {
              await new Promise((r) => requestAnimationFrame(r))
            }
          }
        } catch {
          // Directory doesn't exist — skip
        }
      }

      return found
    } finally {
      scanning.value = false
      scanProgress.value = ''
    }
  }

  async function scanFolder(path: string): Promise<FsTrack[]> {
    try {
      const result = await Filesystem.readdir({
        path,
        directory: Directory.ExternalStorage,
      })

      const audioFiles = result.files
        .filter((f) => f.type === 'file' && AUDIO_EXT.test(f.name))
        .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))

      return audioFiles.map((f, i) => ({
        index: i,
        filename: f.name,
        path: `${path}/${f.name}`,
        duration: 0,
      }))
    } catch {
      return []
    }
  }

  function addFsBooks(books: FsBookMeta[]) {
    for (const book of books) {
      fsBooks.value[book.id] = book
    }
    persist()
  }

  function removeFsBook(id: string) {
    delete fsBooks.value[id]
    persist()
  }

  function markSynced(id: string) {
    if (fsBooks.value[id]) {
      fsBooks.value[id]!.synced = true
      persist()
    }
  }

  function getFsBook(id: string): FsBookMeta | undefined {
    return fsBooks.value[id]
  }

  return {
    fsBooks, scanning, scanProgress,
    scan, addFsBooks, removeFsBook, markSynced, getFsBook,
    cleanTitle, extractAuthor, isLikelyNotBook,
  }
}

// ── Helpers (exported for testing) ──────────────────────────────────────

/** "Author - Title [Reader]" → "Title" */
export function cleanTitle(folderName: string): string {
  let name = folderName.replace(/\s*\[.*?\]\s*$/, '')
  if (name.includes(' - ')) {
    name = name.split(' - ').slice(1).join(' - ')
  }
  return name.trim() || folderName
}

/** "Author - Title [Reader]" → "Author" */
export function extractAuthor(folderName: string): string {
  const clean = folderName.replace(/\s*\[.*?\]\s*$/, '')
  if (clean.includes(' - ')) {
    return clean.split(' - ')[0]?.trim() ?? ''
  }
  return ''
}

/** Heuristic: folder is probably not an audiobook */
export function isLikelyNotBook(folderName: string, trackCount: number): boolean {
  if (trackCount < 2) return true
  if (NOT_BOOK_KEYWORDS.test(folderName)) return true
  return false
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd app && npx vitest run src/__tests__/useFileScanner.test.ts`
Expected: PASS

- [ ] **Step 5: Run full type check**

Run: `cd app && npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/src/composables/useFileScanner.ts app/src/__tests__/useFileScanner.test.ts
git commit -m "feat: useFileScanner persistent storage, multi-dir scan, heuristics"
```

---

## Task 3: resolveAudioSrc — fs: Branch

**Files:**
- Modify: `app/src/composables/usePlayer.ts:332-363`
- Modify: `app/src/__tests__/usePlayer.test.ts`

- [ ] **Step 1: Add fs: branch to resolveAudioSrc**

In `app/src/composables/usePlayer.ts`, find `resolveAudioSrc` (line 332). Add before the `lb:` check:

```typescript
async function resolveAudioSrc(bookId: string, trackIndex: number): Promise<string> {
  // Filesystem book (scanned from device, ExternalStorage)
  if (bookId.startsWith('fs:')) {
    const track = tracks.value[trackIndex]
    if (!track?.path) return ''
    try {
      const uri = await Filesystem.getUri({
        path: track.path,
        directory: Directory.ExternalStorage,
      })
      playingOffline.value = true
      return Capacitor.convertFileSrc(uri.uri)
    } catch {
      return ''
    }
  }
  // Local book (device-only, stored in IndexedDB)
  if (bookId.startsWith('lb:')) {
```

- [ ] **Step 2: Add Filesystem import if not present**

At the top of `usePlayer.ts`, ensure these imports exist:

```typescript
import { Filesystem, Directory } from '@capacitor/filesystem'
import { Capacitor } from '@capacitor/core'
```

Check if already imported (they may be from useDownloads — usePlayer may not have them directly). Add if missing.

- [ ] **Step 3: Add loadBook support for fs: books**

In `usePlayer.ts`, find `loadBook` function (line 367). Insert `fs:` branch after the `isLocalBook` check block (after line 449 `return`), following the exact same pattern as the `lb:` branch:

```typescript
    const isFsBook = book.id.startsWith('fs:')
    const isLocalBook = book.id.startsWith('lb:')
    const isUserBook = book.id.startsWith('ub:')
    const { isOnline } = useNetwork()

    if (isFsBook) {
      // Filesystem book: load from persistent scanner storage
      const { getFsBook } = useFileScanner()
      const fsMeta = getFsBook(book.id)
      if (!fsMeta) throw new Error('Filesystem book not found')
      tracks.value = fsMeta.tracks.map((t) => ({
        index: t.index,
        filename: t.filename,
        path: t.path,
        duration: t.duration,
      }))
      playingOffline.value = true
      currentTrackIndex.value = 0

      // Restore position (same pattern as lb:)
      let pos = { track_index: startTrackIndex ?? 0, position: 0 }
      if (startTrackIndex === undefined) {
        try {
          const savedPos = localStorage.getItem(`${STORAGE.POSITION_PREFIX}${book.id}`)
          if (savedPos) pos = JSON.parse(savedPos)
        } catch { /* corrupted localStorage */ }
      }
      const idx = pos.track_index >= 0 && pos.track_index < tracks.value.length ? pos.track_index : 0
      const seekPos = isFinite(pos.position) && pos.position >= 0 ? pos.position : 0
      currentTrackIndex.value = idx

      const a = ensureAudio()
      const fsUrl = await resolveAudioSrc(book.id, idx)
      if (loadOpId !== opId) return
      a.src = fsUrl || ''
      a.load()

      if (seekPos > 0) {
        const onLoaded = () => {
          a.removeEventListener('loadedmetadata', onLoaded)
          if (loadOpId !== opId) return
          a.currentTime = seekPos
          currentTime.value = seekPos
          a.play().catch((e) => console.warn('Auto-play blocked:', e))
        }
        a.addEventListener('loadedmetadata', onLoaded)
      } else {
        a.play().catch((e) => console.warn('Auto-play blocked:', e))
      }

      updateMediaSession()
      return
    }

    if (isLocalBook) {
```

This mirrors the existing `lb:` branch exactly (position restore, loadedmetadata seek, opId staleness checks, media session update) but uses `resolveAudioSrc` for the `fs:` URL resolution instead of `getLocalAudioUrl`.

- [ ] **Step 4: Add useFileScanner import to usePlayer.ts**

```typescript
import { useFileScanner } from './useFileScanner'
```

- [ ] **Step 5: Run type check**

Run: `cd app && npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/src/composables/usePlayer.ts
git commit -m "feat: resolveAudioSrc + loadBook support for fs: books"
```

---

## Task 4: Router — New Routes

**Files:**
- Modify: `app/src/router.ts`

- [ ] **Step 1: Add /scan-results and /youtube-import routes**

In `app/src/router.ts`, add before the catch-all 404 route:

```typescript
    {
      path: '/scan-results',
      name: 'scan-results',
      component: () => import('./views/ScanResultsView.vue'),
      meta: { title: 'Scan Results', public: true },
    },
    {
      path: '/youtube-import',
      name: 'youtube-import',
      component: () => import('./views/YouTubeImportView.vue'),
      meta: { title: 'YouTube Import' },
    },
```

- [ ] **Step 2: Commit**

```bash
git add app/src/router.ts
git commit -m "feat: add /scan-results and /youtube-import routes"
```

---

## Task 5: ScanResultsView

**Files:**
- Create: `app/src/views/ScanResultsView.vue`

- [ ] **Step 1: Create ScanResultsView.vue**

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useFileScanner, isLikelyNotBook } from '../composables/useFileScanner'
import { useToast } from '../composables/useToast'
import { useTracking } from '../composables/useTelemetry'
import { formatSize } from '../utils/format'
import { IconCheck, IconArrowLeft } from '../components/shared/icons'
import type { FsBookMeta } from '../types'

const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const { track } = useTracking()
const scanner = useFileScanner()

const scannedBooks = ref<FsBookMeta[]>([])
const selected = ref<Set<string>>(new Set())
const hasScanned = ref(false)

const selectedCount = computed(() => selected.value.size)

onMounted(async () => {
  const found = await scanner.scan()
  scannedBooks.value = found
  hasScanned.value = true

  // Select all except "not a book" heuristic
  for (const book of found) {
    if (!isLikelyNotBook(book.title, book.tracks.length)) {
      selected.value.add(book.id)
    }
  }

  track('scan_completed', { found: found.length })
})

function toggle(id: string) {
  if (selected.value.has(id)) {
    selected.value.delete(id)
  } else {
    selected.value.add(id)
  }
  // Force reactivity
  selected.value = new Set(selected.value)
}

function selectAll() {
  for (const b of scannedBooks.value) selected.value.add(b.id)
  selected.value = new Set(selected.value)
}

function deselectAll() {
  selected.value = new Set()
}

function addSelected() {
  const books = scannedBooks.value.filter((b) => selected.value.has(b.id))
  if (!books.length) return

  scanner.addFsBooks(books)
  toast.success(t('scan.added', { n: books.length }))
  track('scan_books_added', { count: books.length })
  router.push('/library')
}

function fmtSize(bytes: number): string {
  return formatSize(bytes, t)
}
</script>

<template>
  <div class="min-h-dvh min-h-screen px-4 py-6" style="background: var(--bg)">
    <!-- Header -->
    <div class="mb-6 flex items-center gap-3">
      <button class="flex items-center text-[--t3] hover:text-[--t1]" @click="router.back()">
        <IconArrowLeft :size="20" />
      </button>
      <div class="flex-1">
        <h1 v-if="hasScanned" class="text-[18px] font-bold text-[--t1]">
          {{ t('scan.found', { n: scannedBooks.length }) }}
        </h1>
        <h1 v-else class="text-[18px] font-bold text-[--t1]">{{ t('scan.scanning') }}</h1>
      </div>
      <button
        v-if="scannedBooks.length"
        class="text-[12px] font-semibold text-[--accent]"
        @click="selectedCount === scannedBooks.length ? deselectAll() : selectAll()"
      >
        {{ selectedCount === scannedBooks.length ? t('scan.deselectAll') : t('scan.selectAll') }}
      </button>
    </div>

    <!-- Scanning progress -->
    <div v-if="scanner.scanning.value" class="mb-6 flex flex-col items-center gap-3 py-8">
      <div class="h-8 w-8 animate-spin rounded-full border-2 border-[--accent] border-t-transparent" />
      <p class="text-[13px] text-[--t3]">{{ t('scan.scanningDir', { dir: scanner.scanProgress.value }) }}</p>
    </div>

    <!-- No results -->
    <div v-else-if="hasScanned && !scannedBooks.length" class="py-12 text-center">
      <div class="mb-4 text-[40px]">📂</div>
      <p class="text-[14px] text-[--t2]">{{ t('scan.nothingFound') }}</p>
      <p class="mt-2 text-[12px] text-[--t3]">{{ t('scan.tryFolder') }}</p>
    </div>

    <!-- Book list -->
    <div v-else class="space-y-2">
      <p v-if="scannedBooks.length" class="mb-4 text-[12px] text-[--t3]">{{ t('scan.uncheckHint') }}</p>

      <div
        v-for="book in scannedBooks"
        :key="book.id"
        class="flex cursor-pointer items-center gap-3 rounded-xl px-3 py-3 transition-all"
        :class="selected.has(book.id)
          ? 'border border-[--accent]/30 bg-white/[0.05]'
          : 'border border-white/[0.06] bg-white/[0.03] opacity-60'"
        @click="toggle(book.id)"
      >
        <!-- Checkbox -->
        <div
          class="flex h-5 w-5 shrink-0 items-center justify-center rounded-md transition-colors"
          :class="selected.has(book.id) ? 'bg-[--accent]' : 'border-2 border-[--border]'"
        >
          <IconCheck v-if="selected.has(book.id)" :size="12" class="text-white" />
        </div>

        <!-- Info -->
        <div class="min-w-0 flex-1">
          <div class="truncate text-[13px] font-semibold text-[--t1]">{{ book.title }}</div>
          <div class="mt-0.5 text-[11px] text-[--t3]">
            <span v-if="book.author">{{ book.author }} · </span>
            {{ book.tracks.length }} {{ t('scan.tracks', { n: book.tracks.length }) }}
            <span v-if="book.sizeBytes"> · {{ fmtSize(book.sizeBytes) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Add button (sticky bottom) -->
    <div
      v-if="scannedBooks.length"
      class="fixed bottom-0 left-0 right-0 px-4 pb-6 pt-3"
      style="background: linear-gradient(transparent, var(--bg) 20%)"
    >
      <button
        v-ripple
        class="btn btn-primary w-full justify-center py-3.5 text-[15px]"
        :disabled="!selectedCount"
        @click="addSelected"
      >
        {{ t('scan.addN', { n: selectedCount }) }}
      </button>
      <p class="mt-2 text-center text-[11px] text-[--t3]">{{ t('scan.stayOnDevice') }}</p>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Add i18n keys**

Add scan-related keys to the i18n files (Russian primary). Find the locale file and add under a `scan` namespace:

```json
{
  "scan": {
    "found": "Найдено {n} книг",
    "scanning": "Сканируем...",
    "scanningDir": "Сканируем {dir}...",
    "nothingFound": "Аудиокниги не найдены",
    "tryFolder": "Попробуйте указать папку вручную",
    "uncheckHint": "Уберите галочку с книг, которые не нужны",
    "selectAll": "Выбрать все",
    "deselectAll": "Снять все",
    "tracks": "{n} треков",
    "addN": "Добавить {n} книг",
    "stayOnDevice": "Книги останутся на устройстве",
    "added": "Добавлено {n} книг"
  }
}
```

- [ ] **Step 3: Run type check**

Run: `cd app && npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/src/views/ScanResultsView.vue
git commit -m "feat: ScanResultsView — scan results with checkboxes"
```

---

## Task 6: WelcomeView Step 2 Redesign

**Files:**
- Modify: `app/src/views/WelcomeView.vue:142-201`

- [ ] **Step 1: Replace step 2 content**

In `WelcomeView.vue`, replace the step 2 block (`v-else-if="step === 2"`, lines 143-201) with:

```vue
        <!-- Step 2: Add books -->
        <div v-else-if="step === 2" key="step2">
          <h1 class="mb-1 text-center text-[20px] font-extrabold tracking-tight text-[--t1]">
            {{ t('welcome.addBooksTitle') }}
          </h1>
          <p class="mb-6 text-center text-[13px] text-[--t3]">{{ t('welcome.addBooksSubtitle') }}</p>

          <!-- Scan device (APK only) -->
          <button
            v-if="isNative"
            v-ripple
            class="mb-2.5 flex w-full items-center gap-3 rounded-xl px-4 py-3.5 text-left text-white"
            style="background: var(--gradient-accent)"
            @click="$router.push('/scan-results')"
          >
            <span class="text-[22px]">📱</span>
            <div>
              <div class="text-[14px] font-semibold">{{ t('welcome.scanDevice') }}</div>
              <div class="mt-0.5 text-[11px] opacity-80">{{ t('welcome.scanDeviceHint') }}</div>
            </div>
          </button>

          <!-- Choose files -->
          <button
            v-ripple
            class="mb-2.5 flex w-full items-center gap-3 rounded-xl border px-4 py-3.5 text-left"
            :class="isNative ? 'border-white/[0.08] bg-white/[0.05]' : ''"
            :style="!isNative ? 'background: var(--gradient-accent); color: white' : ''"
            @click="($refs.fileInput as HTMLInputElement)?.click()"
          >
            <input
              ref="fileInput"
              type="file"
              accept=".mp3,.m4a,.m4b,.ogg,.opus,.flac,.wav,.zip"
              multiple
              hidden
              @change="handleFileInput"
            />
            <span class="text-[22px]">📄</span>
            <div>
              <div class="text-[14px] font-semibold" :class="isNative ? 'text-[--t1]' : ''">{{ t('welcome.chooseFiles') }}</div>
              <div class="mt-0.5 text-[11px]" :class="isNative ? 'text-[--t3]' : 'opacity-80'">MP3, M4A, M4B, OGG, FLAC, ZIP</div>
            </div>
          </button>

          <!-- Choose folder -->
          <button
            v-ripple
            class="mb-4 flex w-full items-center gap-3 rounded-xl border border-white/[0.08] bg-white/[0.05] px-4 py-3.5 text-left"
            @click="pickFolder"
          >
            <span class="text-[22px]">📂</span>
            <div>
              <div class="text-[14px] font-semibold text-[--t1]">{{ t('welcome.chooseFolder') }}</div>
              <div class="mt-0.5 text-[11px] text-[--t3]">{{ t('welcome.chooseFolderHint') }}</div>
            </div>
          </button>

          <!-- File list (if files selected) -->
          <div v-if="files.length" class="mb-4 max-h-[160px] space-y-1.5 overflow-y-auto">
            <div
              v-for="(f, i) in files"
              :key="f.name"
              class="stagger-item flex items-center gap-2 rounded-lg px-3 py-2 text-[12px]"
              style="background: var(--card)"
              :style="{ animationDelay: `${i * 40}ms` }"
            >
              <span class="text-[14px]">🎵</span>
              <span class="min-w-0 flex-1 truncate text-[--t2]">{{ f.name }}</span>
              <span class="shrink-0 text-[--t3]">{{ fmtSize(f.size) }}</span>
              <button class="shrink-0 text-[--t3] hover:text-red-400" @click.stop="removeFile(i)">✕</button>
            </div>
          </div>

          <button
            v-if="files.length"
            v-ripple
            class="btn btn-primary mt-2 w-full justify-center py-3 text-[15px]"
            @click="next"
          >
            {{ t('welcome.continue') }}
          </button>

          <div class="mt-3 flex justify-center gap-4">
            <button class="py-2 text-[12px] text-[--t3] hover:text-[--t2]" @click="prev">
              {{ t('common.back') }}
            </button>
            <button class="py-2 text-[12px] text-[--t3] hover:text-[--t2]" @click="next">
              {{ t('welcome.skip') }} →
            </button>
          </div>
        </div>
```

- [ ] **Step 2: Add isNative and pickFolder to script**

In the `<script setup>` section, add:

```typescript
import { Capacitor } from '@capacitor/core'

const isNative = Capacitor.isNativePlatform()

function pickFolder() {
  // Web: use webkitdirectory input
  const input = document.createElement('input')
  input.type = 'file'
  input.setAttribute('webkitdirectory', '')
  input.setAttribute('directory', '')
  input.multiple = true
  input.accept = '.mp3,.m4a,.m4b,.ogg,.opus,.flac,.wav'
  input.onchange = () => {
    if (input.files) addFiles(input.files)
  }
  input.click()
}
```

- [ ] **Step 3: Add i18n keys for new strings**

```json
{
  "welcome": {
    "addBooksTitle": "Добавь свои книги",
    "addBooksSubtitle": "Мы найдём аудиокниги на устройстве",
    "scanDevice": "Сканировать устройство",
    "scanDeviceHint": "Найдём папки с аудиокнигами",
    "chooseFiles": "Выбрать файлы",
    "chooseFolder": "Указать папку",
    "chooseFolderHint": "Выберите папку с книгами вручную"
  }
}
```

- [ ] **Step 4: Run type check**

Run: `cd app && npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/src/views/WelcomeView.vue
git commit -m "feat: onboarding step 2 — scan/files/folder buttons"
```

---

## Task 7: AddBookFab Component

**Files:**
- Create: `app/src/components/library/AddBookFab.vue`
- Modify: `app/src/views/LibraryView.vue`

- [ ] **Step 1: Create AddBookFab.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Capacitor } from '@capacitor/core'
import { usePlayer } from '../../composables/usePlayer'
import { IconPlus } from '../shared/icons'

const router = useRouter()
const { t } = useI18n()
const { currentBook } = usePlayer()

const isOpen = ref(false)
const isNative = Capacitor.isNativePlatform()

const bottomOffset = () => currentBook.value ? '130px' : '80px'

function toggle() {
  isOpen.value = !isOpen.value
}

function close() {
  isOpen.value = false
}

function scanDevice() {
  close()
  router.push('/scan-results')
}

function pickFiles() {
  close()
  router.push('/upload')
}

function pickFolder() {
  close()
  router.push('/upload')
}

function openYouTube() {
  close()
  router.push('/youtube-import')
}

function openTTS() {
  close()
  router.push('/upload?tab=tts')
}
</script>

<template>
  <!-- Overlay -->
  <Teleport to="body">
    <transition name="fade">
      <div
        v-if="isOpen"
        class="fixed inset-0 z-40 bg-black/50"
        @click="close"
      />
    </transition>

    <!-- Popup menu -->
    <transition name="scale-up">
      <div
        v-if="isOpen"
        class="fixed right-4 z-50 w-[220px] rounded-2xl p-1.5 shadow-2xl"
        :style="{ bottom: `calc(${bottomOffset()} + 60px)` }"
        style="background: var(--card-solid)"
      >
        <!-- Scan (APK only) -->
        <button
          v-if="isNative"
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="scanDevice"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg text-[16px]" style="background: rgba(249,115,22,0.15)">📱</div>
          <div>
            <div class="text-[13px] font-semibold text-[--t1]">{{ t('fab.scan') }}</div>
            <div class="text-[10px] text-[--t3]">{{ t('fab.scanHint') }}</div>
          </div>
        </button>

        <!-- Files -->
        <button
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="pickFiles"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-[16px]">📄</div>
          <div>
            <div class="text-[13px] font-semibold text-[--t1]">{{ t('fab.files') }}</div>
            <div class="text-[10px] text-[--t3]">MP3, M4A, M4B, ZIP</div>
          </div>
        </button>

        <!-- Folder -->
        <button
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="pickFolder"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-[16px]">📂</div>
          <div>
            <div class="text-[13px] font-semibold text-[--t1]">{{ t('fab.folder') }}</div>
            <div class="text-[10px] text-[--t3]">{{ t('fab.folderHint') }}</div>
          </div>
        </button>

        <!-- Divider -->
        <div class="mx-3 my-1 h-px bg-white/[0.06]" />

        <!-- YouTube (APK only) -->
        <button
          v-if="isNative"
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="openYouTube"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg text-[16px]" style="background: rgba(255,0,0,0.1)">🎥</div>
          <div>
            <div class="text-[13px] font-semibold text-[--t1]">YouTube</div>
            <div class="text-[10px] text-[--t3]">{{ t('fab.youtube') }}</div>
          </div>
        </button>

        <!-- TTS -->
        <button
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="openTTS"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-[16px]">🗣</div>
          <div>
            <div class="text-[13px] font-semibold text-[--t1]">{{ t('fab.tts') }}</div>
            <div class="text-[10px] text-[--t3]">{{ t('fab.ttsHint') }}</div>
          </div>
        </button>
      </div>
    </transition>

    <!-- FAB button -->
    <button
      class="fixed right-4 z-50 flex h-[52px] w-[52px] items-center justify-center rounded-full text-white shadow-lg transition-transform duration-200"
      :class="isOpen ? 'rotate-45' : ''"
      :style="{ bottom: bottomOffset(), background: 'var(--gradient-accent)', boxShadow: '0 4px 12px rgba(249,115,22,0.4)' }"
      @click="toggle"
    >
      <IconPlus :size="24" />
    </button>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.scale-up-enter-active { transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1); }
.scale-up-leave-active { transition: all 0.15s ease-in; }
.scale-up-enter-from { opacity: 0; transform: scale(0.8) translateY(10px); }
.scale-up-leave-to { opacity: 0; transform: scale(0.9); }
</style>
```

- [ ] **Step 2: Add i18n keys**

```json
{
  "fab": {
    "scan": "Сканировать",
    "scanHint": "Найти книги на устройстве",
    "files": "Файлы",
    "folder": "Папка",
    "folderHint": "Указать папку вручную",
    "youtube": "Скачать аудиокнигу",
    "tts": "Озвучить текст",
    "ttsHint": "TTS из текста в аудиокнигу"
  }
}
```

- [ ] **Step 3: Mount in LibraryView.vue**

In `app/src/views/LibraryView.vue`, add import and component:

```typescript
import AddBookFab from '../components/library/AddBookFab.vue'
```

Add `<AddBookFab />` at the end of the template (inside the root element, after the book grid).

- [ ] **Step 4: Run type check**

Run: `cd app && npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/src/components/library/AddBookFab.vue app/src/views/LibraryView.vue
git commit -m "feat: AddBookFab — FAB + popup menu in library"
```

---

## Task 8: BookDetailView — Cloud Upload Badge + Button

**Files:**
- Modify: `app/src/views/BookDetailView.vue`

- [ ] **Step 1: Add computed properties for fs/lb detection**

In BookDetailView's `<script setup>`, add:

```typescript
import { useFileScanner } from '../composables/useFileScanner'
import PaywallModal from '../components/shared/PaywallModal.vue'

const { getFsBook, markSynced } = useFileScanner()

const isLocalBook = computed(() => {
  const id = book.value?.id
  return id?.startsWith('fs:') || id?.startsWith('lb:')
})

const isSynced = computed(() => {
  const id = book.value?.id
  if (!id?.startsWith('fs:')) return false
  return getFsBook(id)?.synced ?? false
})

const isPremium = computed(() => user.value?.plan === 'premium')

const showPaywall = ref(false)
const cloudUploading = ref(false)
const cloudProgress = ref(0)
```

- [ ] **Step 2: Add cloudUpload function**

```typescript
async function cloudUpload() {
  if (!isPremium.value) {
    showPaywall.value = true
    return
  }
  if (!book.value || cloudUploading.value) return

  const fsBook = getFsBook(book.value.id)
  if (!fsBook) return

  cloudUploading.value = true
  cloudProgress.value = 0

  try {
    const formData = new FormData()
    formData.append('title', fsBook.title)
    formData.append('author', fsBook.author)

    for (let i = 0; i < fsBook.tracks.length; i++) {
      const track = fsBook.tracks[i]!
      const result = await Filesystem.readFile({
        path: track.path,
        directory: Directory.ExternalStorage,
      })
      const blob = typeof result.data === 'string'
        ? new Blob([Uint8Array.from(atob(result.data), c => c.charCodeAt(0))])
        : new Blob([result.data])
      formData.append('files', new File([blob], track.filename, { type: 'audio/mpeg' }))
      cloudProgress.value = Math.round(((i + 1) / fsBook.tracks.length) * 50)
    }

    await api.cloudSyncBook(formData)
    markSynced(book.value.id)
    cloudProgress.value = 100
    toast.success(t('book.cloudUploadDone'))
  } catch (e) {
    toast.error(t('book.cloudUploadFailed'))
  } finally {
    cloudUploading.value = false
  }
}
```

- [ ] **Step 3: Add template elements**

After the play button in the template, add:

```vue
        <!-- Device badge + Cloud upload -->
        <div v-if="isLocalBook" class="mt-3 space-y-2">
          <div class="inline-flex items-center gap-1.5 rounded-md bg-white/[0.06] px-2.5 py-1 text-[11px] text-[--t3]">
            <IconSmartphone :size="12" />
            {{ isSynced ? t('book.inCloud') : t('book.onDevice') }}
          </div>

          <button
            v-if="!isSynced"
            v-ripple
            class="flex w-full items-center justify-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.05] px-4 py-3 text-[13px] font-semibold text-[--t1]"
            :disabled="cloudUploading"
            @click="cloudUpload"
          >
            <template v-if="cloudUploading">
              <div class="h-4 w-4 animate-spin rounded-full border-2 border-[--accent] border-t-transparent" />
              {{ cloudProgress }}%
            </template>
            <template v-else>
              <IconCloud :size="16" />
              {{ t('book.uploadToCloud') }}
            </template>
          </button>
          <p v-if="!isSynced" class="text-center text-[10px] text-[--t3]">{{ t('book.cloudHint') }}</p>
        </div>

        <PaywallModal :open="showPaywall" @close="showPaywall = false" />
```

- [ ] **Step 4: Add i18n keys**

```json
{
  "book": {
    "onDevice": "На устройстве",
    "inCloud": "В облаке",
    "uploadToCloud": "Загрузить в облако",
    "cloudHint": "Sync между устройствами · Premium",
    "cloudUploadDone": "Книга загружена в облако",
    "cloudUploadFailed": "Ошибка загрузки в облако"
  }
}
```

- [ ] **Step 5: Add api.cloudSyncBook to api.ts**

```typescript
cloudSyncBook: (formData: FormData) => {
  return fetch(apiUrl('/user/books/cloud-sync'), {
    method: 'POST',
    credentials: 'include',
    body: formData,
  }).then((r) => {
    if (!r.ok) throw new Error(`Upload failed: ${r.status}`)
    return r.json()
  })
},
```

- [ ] **Step 6: Run type check**

Run: `cd app && npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/src/views/BookDetailView.vue app/src/api.ts
git commit -m "feat: BookDetailView — device badge + cloud upload button"
```

---

## Task 9: Backend — Cloud Sync Endpoint

**Files:**
- Modify: `server/upload.py`

- [ ] **Step 1: Add cloud-sync endpoint**

In `server/upload.py`, add a new endpoint after the existing upload endpoint:

```python
@router.post("/user/books/cloud-sync")
async def cloud_sync_book(
    request: Request,
    title: str = Form(...),
    author: str = Form(""),
    files: list[UploadFile] = File(...),
    cover: UploadFile | None = File(None),
):
    """Upload a local book to cloud for sync. Premium only."""
    user = _require_auth(request)

    if user.get("plan", "free") != "premium":
        raise HTTPException(403, {"error": "premium_required"})

    # Reuse existing book creation logic
    return await _create_user_book(user, title, author, files, cover, source="cloud-sync")
```

Extract the existing book creation logic from the upload endpoint into a shared `_create_user_book` helper if not already extracted. The cloud-sync endpoint differs only in: no free-tier limit check, `source='cloud-sync'`.

- [ ] **Step 2: Test the endpoint**

```bash
# Test 403 for free users
curl -X POST https://app.leerio.app/api/user/books/cloud-sync \
  -H "Cookie: session=..." \
  -F "title=Test" -F "files=@test.mp3"
# Expected: 403 {"error": "premium_required"}
```

- [ ] **Step 3: Commit**

```bash
git add server/upload.py
git commit -m "feat: POST /api/user/books/cloud-sync — premium cloud sync endpoint"
```

---

## Task 10: YouTubeImportView

**Files:**
- Create: `app/src/views/YouTubeImportView.vue`
- Modify: `app/src/composables/useYouTubeImport.ts`

- [ ] **Step 1: Create YouTubeImportView.vue**

Extract the content from `app/src/components/upload/YouTubeTab.vue` into a new fullscreen view:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useYouTubeImport } from '@/composables/useYouTubeImport'
import { IconCheck, IconArrowLeft } from '@/components/shared/icons'

const { t } = useI18n()
const router = useRouter()
const yt = useYouTubeImport()
const youtubeUrl = ref('')
const chunkMinutes = ref(10)
</script>

<template>
  <div class="min-h-dvh min-h-screen px-4 py-6" style="background: var(--bg)">
    <!-- Header -->
    <div class="mb-6 flex items-center gap-3">
      <button class="flex items-center text-[--t3] hover:text-[--t1]" @click="router.back()">
        <IconArrowLeft :size="20" />
      </button>
      <h1 class="text-[18px] font-bold text-[--t1]">YouTube</h1>
    </div>

    <div class="mx-auto max-w-xl space-y-5">
      <!-- URL Input -->
      <div class="card space-y-4 px-5 py-5">
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">{{ t('upload.youtubeUrl') }}</label>
          <div class="flex gap-2">
            <input
              v-model="youtubeUrl"
              type="url"
              :placeholder="t('upload.youtubeUrlPlaceholder')"
              class="input-field min-w-0 flex-1 px-3.5 py-2.5"
              :disabled="yt.step.value !== 'idle' && yt.step.value !== 'resolved' && yt.step.value !== 'error'"
              @keydown.enter="yt.resolve(youtubeUrl)"
            />
            <button
              class="btn-primary shrink-0 px-5"
              :disabled="!youtubeUrl.trim() || yt.step.value === 'resolving'"
              @click="yt.resolve(youtubeUrl)"
            >
              {{ yt.step.value === 'resolving' ? '...' : t('upload.youtubeFind') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Resolve Result -->
      <div v-if="yt.step.value === 'resolved' || yt.step.value === 'downloading' || yt.step.value === 'splitting' || yt.step.value === 'saving'" class="card space-y-4 px-5 py-5">
        <div class="flex gap-4">
          <img v-if="yt.thumbnail.value" :src="yt.thumbnail.value" :alt="yt.title.value" class="h-24 w-24 shrink-0 rounded-lg object-cover" />
          <div class="min-w-0 flex-1 space-y-3">
            <div>
              <label class="mb-1 block text-[11px] font-semibold text-[--t3]">{{ t('upload.labelTitle') }}</label>
              <input v-model="yt.title.value" type="text" class="input-field w-full px-3 py-2 text-[13px]" :disabled="yt.step.value !== 'resolved'" />
            </div>
            <div>
              <label class="mb-1 block text-[11px] font-semibold text-[--t3]">{{ t('upload.labelAuthor') }}</label>
              <input v-model="yt.author.value" type="text" class="input-field w-full px-3 py-2 text-[13px]" :disabled="yt.step.value !== 'resolved'" />
            </div>
          </div>
        </div>

        <div class="text-[12px] text-[--t3]">
          <span v-if="yt.chapters.value.length">{{ yt.chapters.value.length }} {{ t('upload.youtubeChapters', { n: yt.chapters.value.length }) }}</span>
          <span v-else>{{ t('upload.youtubeNoChapters', { n: chunkMinutes }) }}</span>
          <span class="ml-2">&middot;</span>
          <span class="ml-2">{{ Math.round(yt.duration.value / 60) }} {{ t('upload.youtubeDuration', { m: Math.round(yt.duration.value / 60) }) }}</span>
        </div>

        <div v-if="!yt.chapters.value.length && yt.step.value === 'resolved'" class="flex items-center gap-3">
          <label class="text-[12px] text-[--t2]">{{ t('upload.youtubeChunkLength') }}</label>
          <input v-model.number="chunkMinutes" type="range" min="5" max="30" step="5" class="flex-1" />
          <span class="w-10 text-right text-[12px] font-semibold text-[--t1]">{{ chunkMinutes }}</span>
        </div>

        <button v-if="yt.step.value === 'resolved'" class="btn-primary w-full py-3" @click="yt.importFromYouTube(chunkMinutes)">
          {{ t('upload.youtubeDownload') }}
        </button>

        <div v-if="yt.step.value === 'downloading' || yt.step.value === 'splitting' || yt.step.value === 'saving'">
          <div class="mb-2 flex items-center justify-between text-[12px]">
            <span class="text-[--t2]">
              <template v-if="yt.step.value === 'downloading'">{{ t('upload.youtubeDownloading', { progress: yt.progress.value }) }}</template>
              <template v-else-if="yt.step.value === 'splitting'">{{ t('upload.youtubeSplitting') }} {{ yt.progress.value }}%</template>
              <template v-else>{{ t('upload.youtubeSaving') }}</template>
            </span>
            <button class="cursor-pointer border-0 bg-transparent text-[--t3] hover:text-[--t1]" @click="yt.cancel()">{{ t('upload.youtubeCancel') }}</button>
          </div>
          <div class="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
            <div class="h-full rounded-full transition-all duration-300" style="background: var(--gradient-accent)" :style="{ width: yt.progress.value + '%' }" />
          </div>
        </div>
      </div>

      <!-- Done -->
      <div v-if="yt.step.value === 'done'" class="card flex items-center gap-3 px-5 py-4">
        <IconCheck :size="20" class="text-green-400" />
        <span class="text-[13px] font-medium text-[--t1]">{{ t('upload.youtubeDone') }}</span>
        <router-link to="/my-library" class="ml-auto text-[12px] font-semibold text-[--accent] no-underline">{{ t('nav.myLibrary') }}</router-link>
      </div>

      <!-- Error -->
      <div v-if="yt.step.value === 'error'" class="card flex items-center gap-3 px-5 py-4 border-red-500/20">
        <span class="text-[13px] text-red-400">{{ yt.errorMessage.value }}</span>
        <button class="ml-auto cursor-pointer border-0 bg-transparent text-[12px] font-semibold text-[--accent]" @click="yt.reset(); youtubeUrl = ''">{{ t('upload.youtubeRetry') }}</button>
      </div>
    </div>
  </div>
</template>
```

Copy the template content from `YouTubeTab.vue` into this view. The only difference: add back button header and fullscreen layout wrapper.

- [ ] **Step 2: Update useYouTubeImport to save to filesystem on APK**

In `useYouTubeImport.ts`, modify `importFromYouTube` to save to filesystem when native:

```typescript
import { Capacitor } from '@capacitor/core'
import { Filesystem, Directory } from '@capacitor/filesystem'
import { useFileScanner } from './useFileScanner'

// In importFromYouTube, after splitAudio produces files:
if (Capacitor.isNativePlatform()) {
  const { addFsBooks } = useFileScanner()
  const folderPath = `Audiobooks/${title.value}`

  // Create folder
  try {
    await Filesystem.mkdir({
      path: folderPath,
      directory: Directory.ExternalStorage,
      recursive: true,
    })
  } catch { /* already exists */ }

  // Write chapter files (chunked base64 to avoid stack overflow)
  const fsTracks = []
  for (let i = 0; i < files.length; i++) {
    const file = files[i]!
    const arrayBuf = await file.arrayBuffer()
    const bytes = new Uint8Array(arrayBuf)
    // Chunked base64 encoding — spread operator crashes on large arrays
    let binary = ''
    const chunkSize = 8192
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      const chunk = bytes.subarray(offset, offset + chunkSize)
      binary += String.fromCharCode.apply(null, chunk as unknown as number[])
    }
    const base64 = btoa(binary)
    await Filesystem.writeFile({
      path: `${folderPath}/${file.name}`,
      data: base64,
      directory: Directory.ExternalStorage,
    })
    fsTracks.push({
      index: i,
      filename: file.name,
      path: `${folderPath}/${file.name}`,
      duration: 0,
    })
  }

  addFsBooks([{
    id: `fs:${title.value}`,
    title: title.value,
    author: author.value,
    folderPath,
    tracks: fsTracks,
    sizeBytes: files.reduce((sum, f) => sum + f.size, 0),
    synced: false,
    addedAt: new Date().toISOString(),
  }])
} else {
  // Web fallback: save to IndexedDB as before
  await addLocalBook(files, { title: title.value, author: author.value })
}
```

- [ ] **Step 3: Run type check**

Run: `cd app && npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/src/views/YouTubeImportView.vue app/src/composables/useYouTubeImport.ts
git commit -m "feat: YouTubeImportView + save to filesystem on APK"
```

---

## Task 11: Android Permissions

**Files:**
- Modify: `app/android/app/src/main/AndroidManifest.xml`

- [ ] **Step 1: Add storage permissions**

In `AndroidManifest.xml`, add inside `<manifest>` before `<application>`:

```xml
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"
                 android:maxSdkVersion="32" />
<uses-permission android:name="android.permission.READ_MEDIA_AUDIO" />
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"
                 android:maxSdkVersion="29" />
```

- [ ] **Step 2: Add runtime permission request to useFileScanner**

In `useFileScanner.ts`, add permission check before scan:

```typescript
async function requestPermissions(): Promise<boolean> {
  try {
    // Capacitor Filesystem plugin handles permission requests
    const status = await Filesystem.requestPermissions()
    return status.publicStorage === 'granted'
  } catch {
    return false
  }
}

// In scan(), before readdir:
const granted = await requestPermissions()
if (!granted) {
  scanning.value = false
  return []
}
```

- [ ] **Step 3: Commit**

```bash
git add app/android/app/src/main/AndroidManifest.xml app/src/composables/useFileScanner.ts
git commit -m "feat: Android storage permissions for file scanning"
```

---

## Task 12: Integration Smoke Test

- [ ] **Step 1: Run full test suite**

Run: `cd app && npx vitest run`
Expected: All existing tests PASS + new useFileScanner tests PASS

- [ ] **Step 2: Run type check**

Run: `cd app && npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Run lint**

Run: `cd app && npx eslint src/ --ext .ts,.vue`
Expected: PASS (or only pre-existing warnings)

- [ ] **Step 4: Manual verification checklist**

- [ ] Onboarding step 2 shows 3 buttons (web: 2 buttons + folder)
- [ ] FAB visible in library, opens popup
- [ ] Popup shows correct items (Scan hidden on web)
- [ ] ScanResultsView loads with spinner, shows empty state
- [ ] BookDetailView shows "On device" badge for lb:/fs: books
- [ ] "Upload to cloud" button triggers paywall for free users
- [ ] YouTube import route accessible at /youtube-import

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: APK folder onboarding + cloud upload + FAB library menu"
```
