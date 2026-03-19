/**
 * Scans device storage for audiobook folders (Capacitor native only).
 *
 * Convention: each subfolder in the scan directory = one book.
 * Folder name = book title. MP3 files inside = tracks (sorted by name).
 *
 * Scan directory: /storage/emulated/0/Audiobooks/ (configurable)
 *
 * On web: no-op (returns empty).
 */
import { ref } from 'vue'
import { Capacitor } from '@capacitor/core'
import { Filesystem, Directory } from '@capacitor/filesystem'
import type { LocalBook, LocalTrack } from '../types'

const SCAN_DIR = 'Audiobooks'
const scannedBooks = ref<LocalBook[]>([])
const scanning = ref(false)

export function useFileScanner() {
  const isNative = Capacitor.isNativePlatform()

  async function scan(): Promise<LocalBook[]> {
    if (!isNative) return []
    scanning.value = true

    try {
      // List folders in Audiobooks directory
      const result = await Filesystem.readdir({
        path: SCAN_DIR,
        directory: Directory.ExternalStorage,
      })

      const books: LocalBook[] = []

      for (const entry of result.files) {
        if (entry.type !== 'directory') continue

        // Each folder = one book
        const bookPath = `${SCAN_DIR}/${entry.name}`
        const tracks = await scanFolder(bookPath)

        if (tracks.length > 0) {
          books.push({
            id: `fs:${entry.name}`,
            title: cleanTitle(entry.name),
            author: extractAuthor(entry.name),
            tracks,
            addedAt: new Date().toISOString(),
          })
        }
      }

      scannedBooks.value = books
      return books
    } catch (e) {
      console.warn('[scanner] scan failed:', e)
      return []
    } finally {
      scanning.value = false
    }
  }

  async function scanFolder(path: string): Promise<LocalTrack[]> {
    try {
      const result = await Filesystem.readdir({
        path,
        directory: Directory.ExternalStorage,
      })

      const audioFiles = result.files
        .filter((f) => f.type === 'file' && /\.(mp3|m4a|m4b|ogg|opus|flac|wav)$/i.test(f.name))
        .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))

      return audioFiles.map((f, i) => ({
        index: i,
        filename: f.name,
        path: `${path}/${f.name}`,
        duration: 0, // unknown until played
      }))
    } catch {
      return []
    }
  }

  return { scannedBooks, scanning, scan }
}

// ── Helpers ──────────────────────────────────────────────────────────────

/** "Author - Title [Reader]" → "Title" */
function cleanTitle(folderName: string): string {
  let name = folderName
  // Remove [Reader] suffix
  name = name.replace(/\s*\[.*?\]\s*$/, '')
  // If "Author - Title", take Title
  if (name.includes(' - ')) {
    name = name.split(' - ').slice(1).join(' - ')
  }
  return name.trim() || folderName
}

/** "Author - Title [Reader]" → "Author" */
function extractAuthor(folderName: string): string {
  const clean = folderName.replace(/\s*\[.*?\]\s*$/, '')
  if (clean.includes(' - ')) {
    return clean.split(' - ')[0]?.trim() ?? ''
  }
  return ''
}
