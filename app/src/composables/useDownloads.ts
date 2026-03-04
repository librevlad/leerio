import { ref, computed } from 'vue'
import { Capacitor } from '@capacitor/core'
import { Filesystem, Directory } from '@capacitor/filesystem'
import { audioUrl } from '../api'
import type { Book, Track } from '../types'

// ── Types ──────────────────────────────────────────────────────────────────

interface DownloadedTrack {
  index: number
  filename: string
  size: number
}

interface BookMeta {
  bookId: string
  title: string
  author: string
  category: string
  tracks: DownloadedTrack[]
  totalSize: number
  downloadedAt: string
}

interface DownloadsMeta {
  books: Record<string, BookMeta>
}

interface DownloadProgress {
  currentTrack: number
  totalTracks: number
  bytesDownloaded: number
  bytesTotal: number
}

// ── Constants ──────────────────────────────────────────────────────────────

const META_PATH = 'leerio/downloads.json'
const BOOKS_DIR = 'leerio/books'

// ── Singleton state ────────────────────────────────────────────────────────

const isNative = ref(false)
const meta = ref<DownloadsMeta>({ books: {} })
const downloading = ref<Record<string, DownloadProgress>>({})
const abortControllers = new Map<string, AbortController>()

// ── Helpers ────────────────────────────────────────────────────────────────

function trackFileName(index: number): string {
  return `track_${String(index).padStart(3, '0')}.mp3`
}

async function saveMeta(): Promise<void> {
  await Filesystem.writeFile({
    path: META_PATH,
    data: JSON.stringify(meta.value, null, 2),
    directory: Directory.Data,
    encoding: 'utf8' as any,
  })
}

async function loadMeta(): Promise<void> {
  try {
    const result = await Filesystem.readFile({
      path: META_PATH,
      directory: Directory.Data,
      encoding: 'utf8' as any,
    })
    const data = typeof result.data === 'string' ? result.data : ''
    meta.value = JSON.parse(data) as DownloadsMeta
  } catch {
    meta.value = { books: {} }
  }
}

// ── Init ───────────────────────────────────────────────────────────────────

async function init(): Promise<void> {
  isNative.value = Capacitor.isNativePlatform()
  if (!isNative.value) return

  await loadMeta()

  // Reset any stale "downloading" states from interrupted downloads
  // (downloading map is ephemeral, so nothing to clean there)
}

// ── Download book ──────────────────────────────────────────────────────────

async function downloadBook(book: Book, trackList: Track[]): Promise<void> {
  if (!isNative.value) return
  if (downloading.value[book.id]) return // already in progress

  let cancelled = false
  abortControllers.set(book.id, { abort: () => { cancelled = true } } as any)

  const totalBytes = trackList.reduce((s, t) => s + (t.size_bytes || 0), 0)
  downloading.value[book.id] = {
    currentTrack: 0,
    totalTracks: trackList.length,
    bytesDownloaded: 0,
    bytesTotal: totalBytes,
  }

  const downloadedTracks: DownloadedTrack[] = []
  let bytesDownloaded = 0

  try {
    // Ensure book directory exists
    try {
      await Filesystem.mkdir({
        path: `${BOOKS_DIR}/${book.id}`,
        directory: Directory.Data,
        recursive: true,
      })
    } catch {
      // directory may already exist
    }

    for (let i = 0; i < trackList.length; i++) {
      if (cancelled) break

      const track = trackList[i]!
      downloading.value[book.id] = {
        currentTrack: i,
        totalTracks: trackList.length,
        bytesDownloaded,
        bytesTotal: totalBytes,
      }

      const url = audioUrl(book.id, track.index)

      // Download directly to disk — no JS memory pressure
      await Filesystem.downloadFile({
        url,
        path: `${BOOKS_DIR}/${book.id}/${trackFileName(track.index)}`,
        directory: Directory.Data,
      })

      if (cancelled) break

      const trackSize = track.size_bytes || 0
      bytesDownloaded += trackSize
      downloadedTracks.push({
        index: track.index,
        filename: track.filename,
        size: trackSize,
      })
    }

    if (!cancelled) {
      // Save meta
      meta.value.books[book.id] = {
        bookId: book.id,
        title: book.title,
        author: book.author,
        category: book.category,
        tracks: downloadedTracks,
        totalSize: bytesDownloaded,
        downloadedAt: new Date().toISOString(),
      }
      await saveMeta()
    } else {
      // Cancelled — clean up partial download
      try {
        await Filesystem.rmdir({
          path: `${BOOKS_DIR}/${book.id}`,
          directory: Directory.Data,
          recursive: true,
        })
      } catch { /* ignore */ }
    }
  } catch {
    // Download error — clean up partial files
    try {
      await Filesystem.rmdir({
        path: `${BOOKS_DIR}/${book.id}`,
        directory: Directory.Data,
        recursive: true,
      })
    } catch { /* ignore */ }
  } finally {
    delete downloading.value[book.id]
    abortControllers.delete(book.id)
  }
}

// ── Cancel download ────────────────────────────────────────────────────────

function cancelDownload(bookId: string): void {
  const handle = abortControllers.get(bookId)
  if (handle) handle.abort()
}

// ── Delete book ────────────────────────────────────────────────────────────

async function deleteBook(bookId: string): Promise<void> {
  try {
    await Filesystem.rmdir({
      path: `${BOOKS_DIR}/${bookId}`,
      directory: Directory.Data,
      recursive: true,
    })
  } catch { /* ignore */ }
  delete meta.value.books[bookId]
  await saveMeta()
}

async function deleteAllBooks(): Promise<void> {
  for (const bookId of Object.keys(meta.value.books)) {
    try {
      await Filesystem.rmdir({
        path: `${BOOKS_DIR}/${bookId}`,
        directory: Directory.Data,
        recursive: true,
      })
    } catch { /* ignore */ }
  }
  meta.value = { books: {} }
  await saveMeta()
}

// ── Get local audio URL ────────────────────────────────────────────────────

async function getLocalAudioUrl(bookId: string, trackIndex: number): Promise<string | null> {
  if (!isNative.value) return null
  if (!meta.value.books[bookId]) return null

  try {
    const result = await Filesystem.getUri({
      path: `${BOOKS_DIR}/${bookId}/${trackFileName(trackIndex)}`,
      directory: Directory.Data,
    })
    return Capacitor.convertFileSrc(result.uri)
  } catch {
    return null
  }
}

// ── Query helpers ──────────────────────────────────────────────────────────

function isBookDownloaded(bookId: string): boolean {
  return !!meta.value.books[bookId]
}

function isBookDownloading(bookId: string): boolean {
  return !!downloading.value[bookId]
}

function bookDownloadProgress(bookId: string): DownloadProgress | null {
  return downloading.value[bookId] ?? null
}

function isTrackDownloaded(bookId: string, trackIndex: number): boolean {
  const book = meta.value.books[bookId]
  if (!book) return false
  return book.tracks.some(t => t.index === trackIndex)
}

// ── Computed ───────────────────────────────────────────────────────────────

const downloadedBooks = computed(() => Object.values(meta.value.books))

const totalDownloadedSize = computed(() =>
  downloadedBooks.value.reduce((sum, b) => sum + b.totalSize, 0)
)

// ── Export ──────────────────────────────────────────────────────────────────

export function useDownloads() {
  return {
    isNative,
    meta,
    downloading,

    init,
    downloadBook,
    cancelDownload,
    deleteBook,
    deleteAllBooks,
    getLocalAudioUrl,

    isBookDownloaded,
    isBookDownloading,
    bookDownloadProgress,
    isTrackDownloaded,

    downloadedBooks,
    totalDownloadedSize,
  }
}
