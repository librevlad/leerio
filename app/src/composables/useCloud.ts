/**
 * Books from the owner's own bucket (Cloudflare R2 / any S3). The list is the bucket's library.json;
 * a book downloads into Audiobooks/<folder>/ and joins My Library as an fs: book — offline from then on.
 *
 * The bucket's read key sits in the app's own folder on the device, Android/data/<app>/files/cloud.json
 * ({ endpoint, bucket, accessKey, secretKey }, put there over adb). No file — no cloud: the menu item
 * stays hidden. APK only.
 *
 * Downloads go one book at a time; a file already on the device at its full size is not fetched again,
 * so a retry after a dropped connection picks up where it stopped.
 */
import { ref, computed } from 'vue'
import { Capacitor, CapacitorHttp } from '@capacitor/core'
import { Filesystem, Directory, Encoding } from '@capacitor/filesystem'
import { presignGet, type S3Config } from '../utils/s3'
import { useFileScanner, cleanTitle, extractAuthor } from './useFileScanner'
import { STORAGE } from '../constants/storage'
import type { FsBookMeta } from '../types'

export interface CloudFile {
  /** Object key in the bucket */
  key: string
  /** Path inside the book folder: "01.mp3", "CD1/01.mp3" */
  name: string
  size: number
}

export interface CloudBook {
  folder: string
  files: CloudFile[]
  bytes: number
}

export interface CloudJob {
  state: 'queued' | 'downloading' | 'failed'
  /** Bytes of this book already on the device */
  done: number
}

const CONFIG_FILE = 'cloud.json'
const LIBRARY_KEY = 'library.json'
const BOOKS_DIR = 'Audiobooks'

// ── Singleton state ────────────────────────────────────────────────────

const config = ref<S3Config | null>(null)
let configLoad: Promise<void> | null = null
const books = ref<CloudBook[]>(parseLibrary(readCache()))
const loading = ref(false)
const listError = ref(false)
const jobs = ref<Record<string, CloudJob>>({})
const pending = new Map<string, CloudBook>()
let running = false

function readCache(): unknown {
  try {
    return { books: JSON.parse(localStorage.getItem(STORAGE.CLOUD_BOOKS) || '[]') }
  } catch {
    return null
  }
}

/** A relative path that stays inside the book folder */
function isSafePath(p: unknown): p is string {
  return typeof p === 'string' && p !== '' && !p.split('/').some((s) => s === '' || s === '.' || s === '..')
}

/** library.json → books; anything malformed or pointing outside its folder is dropped */
export function parseLibrary(data: unknown): CloudBook[] {
  const list = (data as { books?: unknown } | null)?.books
  if (!Array.isArray(list)) return []
  return list
    .filter(
      (b) =>
        isSafePath(b?.folder) &&
        !b.folder.includes('/') &&
        Array.isArray(b.files) &&
        b.files.length > 0 &&
        b.files.every((f: CloudFile) => typeof f?.key === 'string' && isSafePath(f.name) && Number.isFinite(f.size)),
    )
    .map((b) => ({
      folder: b.folder as string,
      files: (b.files as CloudFile[]).map(({ key, name, size }) => ({ key, name, size })),
      bytes: (b.files as CloudFile[]).reduce((sum, f) => sum + f.size, 0),
    }))
}

/** A downloaded book, as the device scanner would see it: tracks in natural file order */
export function toFsBook(book: CloudBook): FsBookMeta {
  const folderPath = `${BOOKS_DIR}/${book.folder}`
  const files = [...book.files].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
  return {
    id: `fs:${book.folder}`,
    title: cleanTitle(book.folder),
    author: extractAuthor(book.folder),
    folderPath,
    tracks: files.map((f, i) => ({
      index: i,
      filename: f.name.split('/').pop() || f.name,
      path: `${folderPath}/${f.name}`,
      duration: 0,
    })),
    sizeBytes: book.bytes,
    synced: false,
    addedAt: new Date().toISOString(),
  }
}

async function readConfig(): Promise<S3Config | null> {
  if (!Capacitor.isNativePlatform()) return null
  try {
    const { data } = await Filesystem.readFile({
      path: CONFIG_FILE,
      directory: Directory.External,
      encoding: Encoding.UTF8,
    })
    // trim(): a BOM from a Windows editor is whitespace too
    const c = JSON.parse(typeof data === 'string' ? data.trim() : '') as Partial<S3Config>
    if (!c.endpoint || !c.bucket || !c.accessKey || !c.secretKey) return null
    return { endpoint: c.endpoint, bucket: c.bucket, accessKey: c.accessKey, secretKey: c.secretKey, region: c.region }
  } catch {
    return null
  }
}

function init(): Promise<void> {
  configLoad ??= readConfig().then((c) => {
    config.value = c
  })
  return configLoad
}

/** Fresh list from the bucket. Offline: the last list stays, `listError` says so */
async function refresh(): Promise<void> {
  const cfg = config.value
  if (!cfg || loading.value) return
  loading.value = true
  try {
    const res = await CapacitorHttp.get({ url: await presignGet(cfg, LIBRARY_KEY), responseType: 'json' })
    if (res.status !== 200) throw new Error(`library.json: ${res.status}`)
    books.value = parseLibrary(typeof res.data === 'string' ? JSON.parse(res.data) : res.data)
    listError.value = false
    localStorage.setItem(STORAGE.CLOUD_BOOKS, JSON.stringify(books.value))
  } catch {
    listError.value = true
  } finally {
    loading.value = false
  }
}

async function sizeOf(path: string): Promise<number> {
  try {
    return (await Filesystem.stat({ path, directory: Directory.ExternalStorage })).size
  } catch {
    return -1
  }
}

async function fetchBook(cfg: S3Config, book: CloudBook, job: CloudJob): Promise<void> {
  const dir = `${BOOKS_DIR}/${book.folder}`
  const dirs = new Set(book.files.map((f) => `${dir}/${f.name}`.replace(/\/[^/]+$/, '')))
  for (const path of dirs) {
    // Throws when the folder is already there; a real failure shows up in the download below
    await Filesystem.mkdir({ path, directory: Directory.ExternalStorage, recursive: true }).catch(() => {})
  }
  job.done = 0
  for (const f of book.files) {
    const path = `${dir}/${f.name}`
    if ((await sizeOf(path)) !== f.size) {
      await Filesystem.downloadFile({ url: await presignGet(cfg, f.key), path, directory: Directory.ExternalStorage })
      if ((await sizeOf(path)) !== f.size) throw new Error(`incomplete: ${f.name}`)
    }
    job.done += f.size
  }
  useFileScanner().addFsBooks([toFsBook(book)])
}

async function runQueue(): Promise<void> {
  if (running) return
  running = true
  try {
    for (const [folder, book] of pending) {
      pending.delete(folder)
      const job = jobs.value[folder]
      const cfg = config.value
      if (!job || !cfg) continue
      job.state = 'downloading'
      try {
        await fetchBook(cfg, book, job)
        delete jobs.value[folder]
      } catch {
        job.state = 'failed'
      }
    }
  } finally {
    running = false
  }
}

/** Queue a book (or retry a failed one); a book already queued or downloading is left alone */
function download(book: CloudBook): void {
  const job = jobs.value[book.folder]
  if (job && job.state !== 'failed') return
  jobs.value[book.folder] = { state: 'queued', done: job?.done ?? 0 }
  pending.set(book.folder, book)
  void runQueue()
}

const available = computed(() => config.value !== null)

export function useCloud() {
  return { available, books, loading, listError, jobs, init, refresh, download }
}
