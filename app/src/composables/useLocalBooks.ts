import { ref } from 'vue'
import type { LocalBook, LocalTrack } from '../types'
import { STORAGE } from '../constants/storage'

const STORAGE_KEY = STORAGE.LOCAL_BOOKS
const DB_NAME = 'leerio_local_audio'
const DB_STORE = 'tracks'

const localBooks = ref<LocalBook[]>([])
let dbPromise: Promise<IDBDatabase> | null = null
const activeBlobUrls = new Map<string, string>()

function loadMeta(): LocalBook[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

function saveMeta(books: LocalBook[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(books))
  localBooks.value = books
}

function openDB(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      req.result.createObjectStore(DB_STORE)
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
  return dbPromise
}

async function storeBlob(key: string, blob: Blob) {
  const db = await openDB()
  return new Promise<void>((resolve, reject) => {
    const tx = db.transaction(DB_STORE, 'readwrite')
    tx.objectStore(DB_STORE).put(blob, key)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

async function getBlob(key: string): Promise<Blob | undefined> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(DB_STORE, 'readonly')
    const req = tx.objectStore(DB_STORE).get(key)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function deleteBlobs(prefix: string) {
  const db = await openDB()
  return new Promise<void>((resolve, reject) => {
    const tx = db.transaction(DB_STORE, 'readwrite')
    const store = tx.objectStore(DB_STORE)
    const req = store.getAllKeys()
    req.onsuccess = () => {
      for (const key of req.result) {
        if (String(key).startsWith(prefix)) store.delete(key)
      }
    }
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

function generateId(): string {
  return `lb:${crypto.randomUUID()}`
}

function getAudioDuration(file: File): Promise<number> {
  return new Promise((resolve) => {
    const audio = new Audio()
    const url = URL.createObjectURL(file)
    // Timeout — never hang indefinitely on corrupt/unsupported files
    const timeout = setTimeout(() => {
      resolve(0)
      URL.revokeObjectURL(url)
    }, 10_000)
    audio.src = url
    audio.addEventListener(
      'loadedmetadata',
      () => {
        clearTimeout(timeout)
        resolve(isFinite(audio.duration) ? audio.duration : 0)
        URL.revokeObjectURL(url)
      },
      { once: true },
    )
    audio.addEventListener(
      'error',
      () => {
        clearTimeout(timeout)
        resolve(0)
        URL.revokeObjectURL(url)
      },
      { once: true },
    )
  })
}

export function useLocalBooks() {
  // Init on first call
  if (!localBooks.value.length) {
    localBooks.value = loadMeta()
  }

  async function addLocalBook(
    files: File[],
    meta: { title: string; author: string; coverDataUrl?: string },
  ): Promise<LocalBook> {
    const id = generateId()
    const tracks: LocalTrack[] = []

    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      if (!file) continue
      const blobKey = `${id}/${i}`
      await storeBlob(blobKey, file)
      const duration = await getAudioDuration(file)
      tracks.push({
        index: i,
        filename: file.name,
        path: blobKey,
        duration,
      })
    }

    const book: LocalBook = {
      id,
      title: meta.title,
      author: meta.author,
      tracks,
      coverDataUrl: meta.coverDataUrl,
      addedAt: new Date().toISOString(),
    }

    const all = [...loadMeta(), book]
    saveMeta(all)
    return book
  }

  async function removeLocalBook(id: string) {
    await deleteBlobs(`${id}/`)
    const all = loadMeta().filter((b) => b.id !== id)
    saveMeta(all)
  }

  function getLocalBook(id: string): LocalBook | undefined {
    return loadMeta().find((b) => b.id === id)
  }

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

  function totalSize(): number {
    // rough estimate from metadata
    return localBooks.value.reduce(
      (sum, b) => sum + b.tracks.reduce((s, t) => s + t.duration * 16000, 0), // ~128kbps estimate
      0,
    )
  }

  return {
    localBooks,
    addLocalBook,
    removeLocalBook,
    getLocalBook,
    getLocalAudioUrl,
    revokeAudioUrls,
    totalSize,
  }
}
