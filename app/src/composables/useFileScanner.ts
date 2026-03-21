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
      return status.publicStorage === 'granted'
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
                } catch {
                  /* stat can fail on some devices */
                }
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
    cleanTitle,
    extractAuthor,
    isLikelyNotBook,
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
