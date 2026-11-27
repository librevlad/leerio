/**
 * Scans device storage for audiobook folders (Capacitor native only).
 *
 * Convention: each subfolder = one book. Folder name = book title.
 * Audio files inside (including nested "CD1/", "Part 2/" folders) = tracks, sorted by path.
 *
 * Scans: /Audiobooks/, /Download/, /Music/ (ExternalStorage).
 * On web: no-op (returns empty).
 *
 * Persistent storage: localStorage "leerio_fs_books" (Record<string, FsBookMeta>).
 */
import { ref } from 'vue'
import { Capacitor, registerPlugin } from '@capacitor/core'
import { Filesystem, Directory } from '@capacitor/filesystem'
import { STORAGE } from '../constants/storage'
import { fetchCoversForBooks } from './useBookCovers'
import type { FsBookMeta, FsTrack } from '../types'

const SCAN_DIRS = ['Audiobooks', 'Download', 'Music']
// "mp3" without the dot: long names truncated by some downloaders ("…где мы гmp3")
const AUDIO_EXT = /(\.(m4a|m4b|ogg|opus|flac|wav)|mp3)$/i
const MAX_DEPTH = 3 // book folder → nested part folders
const NOT_BOOK_KEYWORDS = /podcast|music|ringtone|notification|alarm|recording/i

// Native (android/.../AudioPermissionPlugin.java): READ_MEDIA_AUDIO on Android 13+
const AudioPermission = registerPlugin<{ request(): Promise<{ granted: boolean }> }>('AudioPermission')

// ── Singleton state ────────────────────────────────────────────────────

const fsBooks = ref<Record<string, FsBookMeta>>(loadFromStorage())
const scanning = ref(false)
const scanProgress = ref('')
let scanAborted = false

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
  // Re-sync from localStorage on each call (handles tests that set localStorage after module load)
  const stored = loadFromStorage()
  for (const [id, book] of Object.entries(stored)) {
    if (!fsBooks.value[id]) {
      fsBooks.value[id] = book
    }
  }

  const isNative = Capacitor.isNativePlatform()

  async function requestPermissions(): Promise<boolean> {
    try {
      const status = await Filesystem.requestPermissions()
      if (status.publicStorage !== 'granted') return false
      // Filesystem says "granted" on Android 13+ without asking — other apps' audio stays hidden
      const audio = await AudioPermission.request()
      return audio.granted
    } catch {
      return false
    }
  }

  async function scan(): Promise<FsBookMeta[]> {
    if (!isNative) return []

    const granted = await requestPermissions()
    if (!granted) return []

    scanAborted = false
    scanning.value = true
    scanProgress.value = ''

    const found: FsBookMeta[] = []

    try {
      for (const dir of SCAN_DIRS) {
        if (scanAborted) break
        scanProgress.value = dir
        try {
          const result = await Filesystem.readdir({
            path: dir,
            directory: Directory.ExternalStorage,
          })

          let processed = 0
          for (const entry of result.files) {
            if (scanAborted) break
            if (entry.type !== 'directory') continue

            const bookPath = `${dir}/${entry.name}`
            const { tracks, sizeBytes } = await scanFolder(bookPath)

            if (tracks.length > 0) {
              const id = `fs:${entry.name}`
              // Skip duplicates already in persistent store
              if (fsBooks.value[id]) continue

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

  function abortScan() {
    scanAborted = true
  }

  async function validateFsBooks(): Promise<void> {
    if (!isNative) return
    const toRemove: string[] = []
    for (const [id, book] of Object.entries(fsBooks.value)) {
      try {
        await Filesystem.stat({
          path: book.folderPath,
          directory: Directory.ExternalStorage,
        })
      } catch {
        // Folder no longer exists
        toRemove.push(id)
      }
    }
    for (const id of toRemove) {
      delete fsBooks.value[id]
    }
    if (toRemove.length > 0) persist()
  }

  async function scanFolder(path: string): Promise<{ tracks: FsTrack[]; sizeBytes: number }> {
    const files: { rel: string; name: string; size: number }[] = []
    await collectAudio(path, '', 0, files)
    files.sort((a, b) => a.rel.localeCompare(b.rel, undefined, { numeric: true }))

    return {
      tracks: files.map((f, i) => ({
        index: i,
        filename: f.name,
        path: `${path}/${f.rel}`,
        duration: 0,
      })),
      sizeBytes: files.reduce((sum, f) => sum + f.size, 0),
    }
  }

  async function collectAudio(
    root: string,
    rel: string,
    depth: number,
    out: { rel: string; name: string; size: number }[],
  ): Promise<void> {
    let entries
    try {
      const result = await Filesystem.readdir({
        path: rel ? `${root}/${rel}` : root,
        directory: Directory.ExternalStorage,
      })
      entries = result.files
    } catch {
      return
    }
    for (const entry of entries) {
      const childRel = rel ? `${rel}/${entry.name}` : entry.name
      if (entry.type === 'directory') {
        if (depth < MAX_DEPTH) await collectAudio(root, childRel, depth + 1, out)
      } else if (AUDIO_EXT.test(entry.name)) {
        out.push({ rel: childRel, name: entry.name, size: entry.size || 0 })
      }
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

  /** Fetch covers from Open Library for fs books that don't have one yet. Background, non-blocking. */
  async function fetchMissingCovers(): Promise<void> {
    const booksWithoutCover = Object.values(fsBooks.value).filter((b) => !b.coverUrl)
    if (!booksWithoutCover.length) return

    const titles = booksWithoutCover.map((b) => b.title)
    const coverMap = await fetchCoversForBooks(titles)

    let updated = false
    for (const book of booksWithoutCover) {
      const url = coverMap[book.title]
      if (url) {
        book.coverUrl = url
        updated = true
      }
    }
    if (updated) persist()
  }

  return {
    fsBooks,
    scanning,
    scanProgress,
    scan,
    abortScan,
    validateFsBooks,
    addFsBooks,
    removeFsBook,
    markSynced,
    getFsBook,
    fetchMissingCovers,
    cleanTitle,
    extractAuthor,
    isLikelyNotBook,
  }
}

// ── Helpers (exported for testing) ──────────────────────────────────────

const AUTHOR_SEP = / [-–—] /

/** "Author_-_Title_(Reader)" → "Author - Title": underscores, trailing [Reader]/(Reader), stray ".mp3" */
function normalizeFolderName(folderName: string): string {
  return folderName
    .replace(/_/g, ' ')
    .replace(/\.mp3$/i, '')
    .replace(/\s*[[(][^\])]*[\])]?\s*$/, '')
    .replace(/\s+/g, ' ')
    .trim()
}

/** "Author - Title [Reader]" / "Author «Title» [Reader]" → "Title" */
export function cleanTitle(folderName: string): string {
  const name = normalizeFolderName(folderName)
  const parts = name.split(AUTHOR_SEP)
  if (parts.length > 1) return parts.slice(1).join(' - ').trim() || folderName
  const quoted = name.match(/«(.+?)»/)
  if (quoted?.[1]) return quoted[1].trim()
  return name || folderName
}

/** "Author - Title [Reader]" / "Author «Title» [Reader]" → "Author" */
export function extractAuthor(folderName: string): string {
  const name = normalizeFolderName(folderName)
  const parts = name.split(AUTHOR_SEP)
  if (parts.length > 1) return parts[0]?.trim() ?? ''
  const quoteStart = name.indexOf('«')
  if (quoteStart > 0) return name.slice(0, quoteStart).trim()
  return ''
}

/** Heuristic: folder is probably not an audiobook. Pass the full path ("Music/Scorpions") — Music/ means music */
export function isLikelyNotBook(folderPath: string, trackCount: number): boolean {
  if (trackCount < 2) return true
  if (NOT_BOOK_KEYWORDS.test(folderPath)) return true
  return false
}
