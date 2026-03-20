import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { LocalBook } from '../types'

// --- In-memory IDB mock ---
let mockStore: Map<string, unknown>

function createMockObjectStore() {
  return {
    put: vi.fn((value: unknown, key: string) => {
      mockStore.set(key, value)
      return { onsuccess: null, onerror: null }
    }),
    get: vi.fn((key: string) => {
      const req = { result: mockStore.get(key), onsuccess: null as (() => void) | null, onerror: null }
      Promise.resolve().then(() => req.onsuccess?.())
      return req
    }),
    delete: vi.fn((key: string) => {
      mockStore.delete(key)
    }),
    getAllKeys: vi.fn(() => {
      const req = { result: [...mockStore.keys()] as IDBValidKey[], onsuccess: null as (() => void) | null, onerror: null }
      Promise.resolve().then(() => req.onsuccess?.())
      return req
    }),
  }
}

function setupIndexedDBMock() {
  const objectStore = createMockObjectStore()
  vi.stubGlobal('indexedDB', {
    open: vi.fn(() => {
      const req = {
        result: {
          transaction: vi.fn(() => {
            const tx = {
              objectStore: vi.fn(() => objectStore),
              oncomplete: null as (() => void) | null,
              onerror: null as (() => void) | null,
            }
            Promise.resolve().then(() => tx.oncomplete?.())
            return tx
          }),
          createObjectStore: vi.fn(),
        },
        onsuccess: null as (() => void) | null,
        onerror: null as (() => void) | null,
        onupgradeneeded: null as (() => void) | null,
      }
      Promise.resolve().then(() => req.onsuccess?.())
      return req
    }),
  })
  return objectStore
}

// Mock crypto.randomUUID
let uuidCounter = 0
vi.stubGlobal('crypto', {
  ...globalThis.crypto,
  randomUUID: () => `test-uuid-${++uuidCounter}`,
})

// Mock URL.createObjectURL / revokeObjectURL on the existing URL class
let blobUrlCounter = 0
globalThis.URL.createObjectURL = vi.fn((_blob: Blob) => `blob:mock-url-${++blobUrlCounter}`)
globalThis.URL.revokeObjectURL = vi.fn()

// Mock Audio constructor for getAudioDuration
class MockAudio {
  src = ''
  duration = 0
  private listeners: Record<string, (() => void)[]> = {}

  addEventListener(event: string, cb: () => void) {
    if (!this.listeners[event]) this.listeners[event] = []
    this.listeners[event]!.push(cb)
    if (event === 'loadedmetadata') {
      this.duration = 120
      Promise.resolve().then(() => cb())
    }
  }
}
vi.stubGlobal('Audio', MockAudio)

const STORAGE_KEY = 'leerio_local_books'

function makeBook(id: string, trackCount = 2): LocalBook {
  const tracks = Array.from({ length: trackCount }, (_, i) => ({
    index: i,
    filename: `track${i}.mp3`,
    path: `${id}/${i}`,
    duration: 300,
  }))
  return {
    id,
    title: `Book ${id}`,
    author: 'Test Author',
    tracks,
    addedAt: '2025-01-01T00:00:00.000Z',
  }
}

describe('useLocalBooks', () => {
  let mockObjectStore: ReturnType<typeof createMockObjectStore>

  beforeEach(async () => {
    // Clear all state
    localStorage.clear()
    mockStore = new Map()
    uuidCounter = 0
    blobUrlCounter = 0
    vi.mocked(URL.createObjectURL).mockClear()
    vi.mocked(URL.revokeObjectURL).mockClear()

    mockObjectStore = setupIndexedDBMock()

    // Reset module-level singleton state (localBooks ref, dbPromise, activeBlobUrls)
    vi.resetModules()
  })

  async function getComposable() {
    const mod = await import('./useLocalBooks')
    return mod.useLocalBooks()
  }

  // --- loadMeta / init ---
  it('loads books from localStorage on init', async () => {
    const books = [makeBook('lb:1'), makeBook('lb:2')]
    localStorage.setItem(STORAGE_KEY, JSON.stringify(books))

    const { localBooks } = await getComposable()
    expect(localBooks.value).toHaveLength(2)
    expect(localBooks.value[0]!.id).toBe('lb:1')
    expect(localBooks.value[1]!.id).toBe('lb:2')
  })

  it('returns empty array when localStorage is empty', async () => {
    const { localBooks } = await getComposable()
    expect(localBooks.value).toEqual([])
  })

  it('returns empty array on corrupted localStorage', async () => {
    localStorage.setItem(STORAGE_KEY, '{not valid json!!!')

    const { localBooks } = await getComposable()
    expect(localBooks.value).toEqual([])
  })

  // --- getLocalBook ---
  it('getLocalBook finds book by id', async () => {
    const books = [makeBook('lb:a'), makeBook('lb:b')]
    localStorage.setItem(STORAGE_KEY, JSON.stringify(books))

    const { getLocalBook } = await getComposable()
    const found = getLocalBook('lb:b')
    expect(found).toBeDefined()
    expect(found!.id).toBe('lb:b')
    expect(found!.title).toBe('Book lb:b')
  })

  it('getLocalBook returns undefined for unknown id', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([makeBook('lb:x')]))

    const { getLocalBook } = await getComposable()
    expect(getLocalBook('lb:unknown')).toBeUndefined()
  })

  // --- totalSize ---
  it('totalSize computes from tracks duration', async () => {
    const books = [makeBook('lb:1', 2)] // 2 tracks, 300s each
    localStorage.setItem(STORAGE_KEY, JSON.stringify(books))

    const { totalSize } = await getComposable()
    // 2 tracks * 300 duration * 16000 = 9_600_000
    expect(totalSize()).toBe(9_600_000)
  })

  it('totalSize returns 0 with no books', async () => {
    const { totalSize } = await getComposable()
    expect(totalSize()).toBe(0)
  })

  it('totalSize sums across multiple books', async () => {
    const books = [makeBook('lb:1', 1), makeBook('lb:2', 3)]
    localStorage.setItem(STORAGE_KEY, JSON.stringify(books))

    const { totalSize } = await getComposable()
    // book1: 1 * 300 * 16000 = 4_800_000
    // book2: 3 * 300 * 16000 = 14_400_000
    expect(totalSize()).toBe(19_200_000)
  })

  // --- addLocalBook ---
  it('addLocalBook stores book metadata and updates localStorage', async () => {
    const { addLocalBook, localBooks } = await getComposable()

    const file = new File(['audio-data'], 'chapter1.mp3', { type: 'audio/mpeg' })
    const book = await addLocalBook([file], { title: 'My Book', author: 'Me' })

    expect(book.id).toBe('lb:test-uuid-1')
    expect(book.title).toBe('My Book')
    expect(book.author).toBe('Me')
    expect(book.tracks).toHaveLength(1)
    expect(book.tracks[0]!.filename).toBe('chapter1.mp3')
    expect(book.tracks[0]!.index).toBe(0)
    expect(book.addedAt).toBeTruthy()

    // localStorage updated
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    expect(stored).toHaveLength(1)
    expect(stored[0].id).toBe('lb:test-uuid-1')

    // Ref updated
    expect(localBooks.value).toHaveLength(1)
  })

  it('addLocalBook stores blob in IDB', async () => {
    const { addLocalBook } = await getComposable()

    const file = new File(['data'], 'ch.mp3', { type: 'audio/mpeg' })
    await addLocalBook([file], { title: 'T', author: 'A' })

    expect(mockObjectStore.put).toHaveBeenCalledWith(file, 'lb:test-uuid-1/0')
  })

  it('addLocalBook preserves coverDataUrl', async () => {
    const { addLocalBook } = await getComposable()

    const file = new File(['d'], 'c.mp3', { type: 'audio/mpeg' })
    const book = await addLocalBook([file], {
      title: 'T',
      author: 'A',
      coverDataUrl: 'data:image/png;base64,abc',
    })

    expect(book.coverDataUrl).toBe('data:image/png;base64,abc')
  })

  // --- removeLocalBook ---
  it('removeLocalBook removes from localStorage and ref', async () => {
    const books = [makeBook('lb:keep'), makeBook('lb:remove')]
    localStorage.setItem(STORAGE_KEY, JSON.stringify(books))

    const { removeLocalBook, localBooks } = await getComposable()
    await removeLocalBook('lb:remove')

    expect(localBooks.value).toHaveLength(1)
    expect(localBooks.value[0]!.id).toBe('lb:keep')

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    expect(stored).toHaveLength(1)
    expect(stored[0].id).toBe('lb:keep')
  })

  it('removeLocalBook deletes blobs with matching prefix from IDB', async () => {
    mockStore.set('lb:del/0', new Blob(['a']))
    mockStore.set('lb:del/1', new Blob(['b']))
    mockStore.set('lb:other/0', new Blob(['c']))

    localStorage.setItem(STORAGE_KEY, JSON.stringify([makeBook('lb:del'), makeBook('lb:other')]))

    const { removeLocalBook } = await getComposable()
    await removeLocalBook('lb:del')

    expect(mockObjectStore.delete).toHaveBeenCalledWith('lb:del/0')
    expect(mockObjectStore.delete).toHaveBeenCalledWith('lb:del/1')
    // 'lb:other/0' should not be deleted
    expect(mockStore.has('lb:other/0')).toBe(true)
  })

  // --- getLocalAudioUrl ---
  it('getLocalAudioUrl returns blob URL when blob exists', async () => {
    const blob = new Blob(['audio'], { type: 'audio/mpeg' })
    mockStore.set('lb:book/0', blob)

    const { getLocalAudioUrl } = await getComposable()
    const url = await getLocalAudioUrl('lb:book', 0)

    expect(url).toContain('blob:mock-url-')
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob)
  })

  it('getLocalAudioUrl returns null when blob not found', async () => {
    const { getLocalAudioUrl } = await getComposable()
    const url = await getLocalAudioUrl('lb:missing', 0)
    expect(url).toBeNull()
  })

  it('returns same URL for same track (cached)', async () => {
    mockStore.set('lb:book/0', new Blob(['a']))

    const { getLocalAudioUrl } = await getComposable()

    const url1 = await getLocalAudioUrl('lb:book', 0)
    const url2 = await getLocalAudioUrl('lb:book', 0)

    expect(url1).toBe(url2)
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
  })

  it('does not revoke other tracks URLs when getting new track', async () => {
    mockStore.set('lb:b/0', new Blob(['a']))
    mockStore.set('lb:b/1', new Blob(['b']))

    const { getLocalAudioUrl } = await getComposable()

    await getLocalAudioUrl('lb:b', 0)
    await getLocalAudioUrl('lb:b', 1)

    expect(URL.revokeObjectURL).not.toHaveBeenCalled()
  })

  it('revokeAudioUrls cleans up all URLs', async () => {
    mockStore.set('lb:b/0', new Blob(['a']))
    mockStore.set('lb:b/1', new Blob(['b']))

    const { getLocalAudioUrl, revokeAudioUrls } = await getComposable()

    const url0 = await getLocalAudioUrl('lb:b', 0)
    const url1 = await getLocalAudioUrl('lb:b', 1)

    revokeAudioUrls()

    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith(url0)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith(url1)
  })

  it('revokeAudioUrls keeps specified keys', async () => {
    mockStore.set('lb:b/0', new Blob(['a']))
    mockStore.set('lb:b/1', new Blob(['b']))

    const { getLocalAudioUrl, revokeAudioUrls } = await getComposable()

    const url0 = await getLocalAudioUrl('lb:b', 0)
    const url1 = await getLocalAudioUrl('lb:b', 1)

    revokeAudioUrls(new Set(['lb:b/0']))

    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith(url1)
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(url0)
  })
})
