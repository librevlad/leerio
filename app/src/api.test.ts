import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

/* ------------------------------------------------------------------ */
/*  Mocks                                                             */
/* ------------------------------------------------------------------ */

vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => false },
}))

const mockIsOnline = { value: true }

vi.mock('./composables/useNetwork', () => ({
  useNetwork: vi.fn(() => ({ isOnline: mockIsOnline })),
}))

const mockCache = {
  get: vi.fn().mockReturnValue(null),
  set: vi.fn(),
}

vi.mock('./composables/useOfflineCache', () => ({
  useOfflineCache: vi.fn(() => mockCache),
}))

const mockQueue = {
  enqueue: vi.fn(),
}

vi.mock('./composables/useOfflineQueue', () => ({
  useOfflineQueue: vi.fn(() => mockQueue),
}))

/* ------------------------------------------------------------------ */
/*  Imports (after mocks)                                             */
/* ------------------------------------------------------------------ */

import { audioUrl, coverUrl, userBookCoverUrl, apiUrl, api } from './api'

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function mockFetchOk(data: unknown) {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  })
}

function mockFetch401() {
  return vi.fn().mockResolvedValue({
    ok: false,
    status: 401,
    statusText: 'Unauthorized',
    json: () => Promise.resolve({ detail: 'Not authenticated' }),
    text: () => Promise.resolve('Not authenticated'),
  })
}

function mockFetchError(status: number, body: string) {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    statusText: 'Error',
    json: () => Promise.reject(new Error('not json')),
    text: () => Promise.resolve(body),
  })
}

/* ------------------------------------------------------------------ */
/*  Setup / teardown                                                  */
/* ------------------------------------------------------------------ */

const originalFetch = globalThis.fetch

beforeEach(() => {
  mockIsOnline.value = true
  mockCache.get.mockReset().mockReturnValue(null)
  mockCache.set.mockReset()
  mockQueue.enqueue.mockReset()
})

afterEach(() => {
  globalThis.fetch = originalFetch
})

/* ------------------------------------------------------------------ */
/*  URL helpers                                                       */
/* ------------------------------------------------------------------ */

describe('audioUrl', () => {
  it('uses relative path', () => {
    expect(audioUrl('book-1', 2)).toBe('/api/audio/book-1/2')
  })
})

describe('coverUrl', () => {
  it('uses relative path', () => {
    expect(coverUrl('book-1')).toBe('/api/books/book-1/cover')
  })
})

describe('userBookCoverUrl', () => {
  it('uses relative path with slug', () => {
    expect(userBookCoverUrl('my-book')).toBe('/api/user/books/my-book/cover')
  })
})

describe('apiUrl', () => {
  it('prefixes path with /api', () => {
    expect(apiUrl('/books')).toBe('/api/books')
  })

  it('works with nested paths', () => {
    expect(apiUrl('/books/123/cover')).toBe('/api/books/123/cover')
  })
})

/* ------------------------------------------------------------------ */
/*  request() (tested via api methods)                                */
/* ------------------------------------------------------------------ */

describe('request (via api methods)', () => {
  it('returns parsed JSON on success', async () => {
    globalThis.fetch = mockFetchOk({ id: '1', title: 'Test Book' })

    const result = await api.getBook('1')
    expect(result).toEqual({ id: '1', title: 'Test Book' })
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/books/1',
      expect.objectContaining({
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
      }),
    )
  })

  it('throws "Not authenticated" on 401', async () => {
    globalThis.fetch = mockFetch401()

    await expect(api.getBook('1')).rejects.toThrow('Not authenticated')
  })

  it('throws with status and body text on other errors', async () => {
    globalThis.fetch = mockFetchError(500, 'Internal Server Error')

    await expect(api.getBook('1')).rejects.toThrow('500: Internal Server Error')
  })
})

/* ------------------------------------------------------------------ */
/*  get() — online + caching                                         */
/* ------------------------------------------------------------------ */

describe('get() — online', () => {
  it('fetches and caches data for cacheable paths', async () => {
    const books = [{ id: '1', title: 'Book A' }]
    globalThis.fetch = mockFetchOk(books)

    const result = await api.getBooks()

    expect(result).toEqual(books)
    // /books is in CACHEABLE list — cache.set should be called
    expect(mockCache.set).toHaveBeenCalledWith(expect.any(String), books)
  })

  it('does not cache non-cacheable paths', async () => {
    globalThis.fetch = mockFetchOk([])

    await api.getHistory()

    // /history is NOT in CACHEABLE list
    expect(mockCache.set).not.toHaveBeenCalled()
  })
})

describe('get() — offline', () => {
  beforeEach(() => {
    mockIsOnline.value = false
  })

  it('returns cached data for cacheable paths when offline', async () => {
    const cachedBooks = [{ id: '1', title: 'Cached' }]
    mockCache.get.mockReturnValue(cachedBooks)

    const result = await api.getBooks()

    expect(result).toEqual(cachedBooks)
    expect(mockCache.get).toHaveBeenCalled()
    // Should NOT call fetch when returning cached data
    globalThis.fetch = vi.fn()
    // (fetch was not set, so if it were called it would fail)
  })

  it('falls through to fetch for cacheable paths with no cache', async () => {
    mockCache.get.mockReturnValue(null)
    globalThis.fetch = mockFetchOk([])

    // Cache miss — falls through to network request
    const result = await api.getBooks()
    expect(result).toEqual([])
  })

  it('calls fetch for non-cacheable paths (no cache lookup)', async () => {
    globalThis.fetch = mockFetchOk([])

    // /history is not cacheable — goes straight to fetch even offline
    await api.getHistory()
    expect(globalThis.fetch).toHaveBeenCalled()
  })
})

/* ------------------------------------------------------------------ */
/*  post() — online / offline                                        */
/* ------------------------------------------------------------------ */

describe('post() — online', () => {
  it('sends POST request with JSON body', async () => {
    globalThis.fetch = mockFetchOk({ ok: true })

    await api.addQuote('Hello', 'book1', 'Author')

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/quotes',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ text: 'Hello', book: 'book1', author: 'Author' }),
        credentials: 'include',
      }),
    )
  })
})

describe('post() — offline', () => {
  beforeEach(() => {
    mockIsOnline.value = false
  })

  it('enqueues to offline queue instead of fetching', async () => {
    globalThis.fetch = vi.fn()

    const result = await api.addQuote('Hello', 'book1', 'Author')

    expect(result).toEqual({ ok: true })
    expect(mockQueue.enqueue).toHaveBeenCalledWith('POST', '/api/quotes', {
      text: 'Hello',
      book: 'book1',
      author: 'Author',
    })
    // fetch should NOT be called
    expect(globalThis.fetch).not.toHaveBeenCalled()
  })
})

/* ------------------------------------------------------------------ */
/*  put() — online / offline                                         */
/* ------------------------------------------------------------------ */

describe('put() — online', () => {
  it('sends PUT request with JSON body', async () => {
    globalThis.fetch = mockFetchOk({ ok: true })

    await api.setProgress('book-1', 75)

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/books/book-1/progress',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ pct: 75 }),
        credentials: 'include',
      }),
    )
  })
})

describe('put() — offline', () => {
  beforeEach(() => {
    mockIsOnline.value = false
  })

  it('enqueues to offline queue instead of fetching', async () => {
    globalThis.fetch = vi.fn()

    const result = await api.setProgress('book-1', 75)

    expect(result).toEqual({ ok: true })
    expect(mockQueue.enqueue).toHaveBeenCalledWith('PUT', '/api/books/book-1/progress', { pct: 75 })
    expect(globalThis.fetch).not.toHaveBeenCalled()
  })
})

/* ------------------------------------------------------------------ */
/*  del() — online / offline                                         */
/* ------------------------------------------------------------------ */

describe('del() — online', () => {
  it('sends DELETE request', async () => {
    globalThis.fetch = mockFetchOk({ ok: true })

    await api.deleteQuote(42)

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/quotes/42',
      expect.objectContaining({
        method: 'DELETE',
        credentials: 'include',
      }),
    )
  })
})

describe('del() — offline', () => {
  beforeEach(() => {
    mockIsOnline.value = false
  })

  it('enqueues to offline queue instead of fetching', async () => {
    globalThis.fetch = vi.fn()

    const result = await api.deleteQuote(42)

    expect(result).toEqual({ ok: true })
    expect(mockQueue.enqueue).toHaveBeenCalledWith('DELETE', '/api/quotes/42')
    expect(globalThis.fetch).not.toHaveBeenCalled()
  })
})
