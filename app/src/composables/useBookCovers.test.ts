import { describe, it, expect, vi, beforeEach } from 'vitest'

// Reset module state between tests
beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
  vi.resetModules()
})

async function getModule() {
  const mod = await import('./useBookCovers')
  mod._resetCache()
  return mod
}

describe('useBookCovers', () => {
  // --- fetchCover ---

  it('fetches cover from Open Library and caches it', async () => {
    const { fetchCover } = await getModule()

    const mockResponse = {
      docs: [{ cover_i: 12345, title: 'Test Book', author_name: ['Author'] }],
    }
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response)

    const url = await fetchCover('Test Book')
    expect(url).toBe('https://covers.openlibrary.org/b/id/12345-M.jpg')

    // Verify it was cached
    const cached = JSON.parse(localStorage.getItem('leerio_cover_cache') || '{}')
    expect(cached['Test Book']).toBe('https://covers.openlibrary.org/b/id/12345-M.jpg')
  })

  it('returns cached result without fetching', async () => {
    localStorage.setItem(
      'leerio_cover_cache',
      JSON.stringify({ 'Cached Book': 'https://covers.openlibrary.org/b/id/999-M.jpg' }),
    )
    const { fetchCover } = await getModule()

    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const url = await fetchCover('Cached Book')

    expect(url).toBe('https://covers.openlibrary.org/b/id/999-M.jpg')
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('caches null when no cover found', async () => {
    const { fetchCover } = await getModule()

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => ({ docs: [] }),
    } as Response)

    const url = await fetchCover('Unknown Book')
    expect(url).toBeNull()

    // Verify null is cached
    const cached = JSON.parse(localStorage.getItem('leerio_cover_cache') || '{}')
    expect(cached['Unknown Book']).toBeNull()
  })

  it('returns cached null without fetching', async () => {
    localStorage.setItem('leerio_cover_cache', JSON.stringify({ 'No Cover': null }))
    const { fetchCover } = await getModule()

    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const url = await fetchCover('No Cover')

    expect(url).toBeNull()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('returns null on network error without caching', async () => {
    const { fetchCover } = await getModule()

    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('Network error'))

    const url = await fetchCover('Error Book')
    expect(url).toBeNull()

    // Should NOT be cached (allow retry)
    const cached = JSON.parse(localStorage.getItem('leerio_cover_cache') || '{}')
    expect('Error Book' in cached).toBe(false)
  })

  it('returns null on non-ok response', async () => {
    const { fetchCover } = await getModule()

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 429,
    } as Response)

    const url = await fetchCover('Rate Limited')
    expect(url).toBeNull()
  })

  it('handles response with docs but no cover_i', async () => {
    const { fetchCover } = await getModule()

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => ({ docs: [{ title: 'No Cover', author_name: ['A'] }] }),
    } as Response)

    const url = await fetchCover('No Cover ID')
    expect(url).toBeNull()

    const cached = JSON.parse(localStorage.getItem('leerio_cover_cache') || '{}')
    expect(cached['No Cover ID']).toBeNull()
  })

  // --- getCachedCover ---

  it('getCachedCover returns cached url', async () => {
    localStorage.setItem(
      'leerio_cover_cache',
      JSON.stringify({ 'My Book': 'https://covers.openlibrary.org/b/id/1-M.jpg' }),
    )
    const { getCachedCover } = await getModule()

    expect(getCachedCover('My Book')).toBe('https://covers.openlibrary.org/b/id/1-M.jpg')
  })

  it('getCachedCover returns null for unknown title', async () => {
    const { getCachedCover } = await getModule()
    expect(getCachedCover('Unknown')).toBeNull()
  })

  // --- fetchCoversForBooks ---

  it('fetchCoversForBooks fetches multiple titles', async () => {
    const { fetchCoversForBooks } = await getModule()

    let callCount = 0
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      callCount++
      return {
        ok: true,
        json: async () => ({ docs: [{ cover_i: callCount * 100 }] }),
      } as Response
    })

    const results = await fetchCoversForBooks(['Book A', 'Book B'])

    expect(results['Book A']).toBe('https://covers.openlibrary.org/b/id/100-M.jpg')
    expect(results['Book B']).toBe('https://covers.openlibrary.org/b/id/200-M.jpg')
  })

  it('fetchCoversForBooks skips already-cached titles', async () => {
    localStorage.setItem(
      'leerio_cover_cache',
      JSON.stringify({ 'Cached': 'https://covers.openlibrary.org/b/id/50-M.jpg' }),
    )
    const { fetchCoversForBooks } = await getModule()

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => ({ docs: [{ cover_i: 200 }] }),
    } as Response)

    const results = await fetchCoversForBooks(['Cached', 'New Book'])

    expect(results['Cached']).toBe('https://covers.openlibrary.org/b/id/50-M.jpg')
    expect(results['New Book']).toBe('https://covers.openlibrary.org/b/id/200-M.jpg')
    // Only one actual fetch (for 'New Book')
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  // --- _resetCache ---

  it('_resetCache clears in-memory cache', async () => {
    const { fetchCover, getCachedCover, _resetCache } = await getModule()

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => ({ docs: [{ cover_i: 1 }] }),
    } as Response)

    await fetchCover('A')
    expect(getCachedCover('A')).toBeTruthy()

    // Clear localStorage and reset in-memory cache
    localStorage.clear()
    _resetCache()

    expect(getCachedCover('A')).toBeNull()
  })
})
