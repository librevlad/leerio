import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, computed, nextTick, effectScope, type EffectScope } from 'vue'

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function flushPromises() {
  return new Promise<void>((r) => setTimeout(r, 0))
}

/* ------------------------------------------------------------------ */
/*  Mocks                                                             */
/* ------------------------------------------------------------------ */

// Auth — real Vue reactivity so watch() inside useSync fires properly
const mockUser = ref<{ id: string } | null>(null)
const mockIsLoggedIn = computed(() => !!mockUser.value)

vi.mock('./useAuth', () => ({
  useAuth: vi.fn(() => ({ isLoggedIn: mockIsLoggedIn })),
}))

const mockLocal = {
  getAllBookStatuses: vi.fn().mockResolvedValue({}),
  importStatuses: vi.fn().mockResolvedValue(undefined),
  getAllProgress: vi.fn().mockResolvedValue({}),
  importProgress: vi.fn().mockResolvedValue(undefined),
  setSettings: vi.fn().mockResolvedValue(undefined),
  getQuotes: vi.fn().mockResolvedValue([]),
  addQuote: vi.fn().mockResolvedValue(undefined),
  importBookmarks: vi.fn().mockResolvedValue(undefined),
  getCollections: vi.fn().mockResolvedValue([]),
  saveCollection: vi.fn().mockResolvedValue(undefined),
  importNotes: vi.fn().mockResolvedValue(undefined),
  importTags: vi.fn().mockResolvedValue(undefined),
}

vi.mock('./useLocalData', () => ({
  useLocalData: vi.fn(() => mockLocal),
}))

const mockOnReconnectPermanent = vi.fn()
vi.mock('./useNetwork', () => ({
  onReconnectPermanent: (...args: unknown[]) => mockOnReconnectPermanent(...args),
}))

const mockApi = {
  getAllBookStatuses: vi.fn().mockResolvedValue({}),
  setBookStatus: vi.fn().mockResolvedValue({ ok: true }),
  getAllProgress: vi.fn().mockResolvedValue({}),
  setProgress: vi.fn().mockResolvedValue({ ok: true }),
  getUserSettings: vi.fn().mockResolvedValue({ yearly_goal: 24, playback_speed: 1 }),
  getQuotes: vi.fn().mockResolvedValue([]),
  getAllBookmarksMap: vi.fn().mockResolvedValue({}),
  getCollections: vi.fn().mockResolvedValue([]),
  getAllNotesMap: vi.fn().mockResolvedValue({}),
  getAllTagsMap: vi.fn().mockResolvedValue({}),
}

vi.mock('../api', () => ({
  api: mockApi,
}))

/* ------------------------------------------------------------------ */
/*  Reset between tests                                               */
/* ------------------------------------------------------------------ */

let scope: EffectScope

beforeEach(() => {
  vi.resetModules()

  // Reset reactive user state
  mockUser.value = null

  // Reset all mock call counts
  Object.values(mockLocal).forEach((fn) => fn.mockClear())
  mockOnReconnectPermanent.mockClear()

  mockApi.getAllBookStatuses.mockClear().mockResolvedValue({})
  mockApi.setBookStatus.mockClear().mockResolvedValue({ ok: true })
  mockApi.getAllProgress.mockClear().mockResolvedValue({})
  mockApi.setProgress.mockClear().mockResolvedValue({ ok: true })
  mockApi.getUserSettings.mockClear().mockResolvedValue({ yearly_goal: 24, playback_speed: 1 })
  mockApi.getQuotes.mockClear().mockResolvedValue([])
  mockApi.getAllBookmarksMap.mockClear().mockResolvedValue({})
  mockApi.getCollections.mockClear().mockResolvedValue([])
  mockApi.getAllNotesMap.mockClear().mockResolvedValue({})
  mockApi.getAllTagsMap.mockClear().mockResolvedValue({})

  // Create a new effect scope so watchers from useSync are contained
  scope = effectScope()
})

afterEach(() => {
  // Stop all watchers created in this test so they don't leak into the next
  scope.stop()
})

/* ------------------------------------------------------------------ */
/*  Tests                                                             */
/* ------------------------------------------------------------------ */

describe('useSync', () => {
  async function callUseSync() {
    const mod = await import('./useSync')
    scope.run(() => mod.useSync())
  }

  it('does not sync when not logged in', async () => {
    mockUser.value = null
    await callUseSync()

    await nextTick()
    await flushPromises()

    expect(mockApi.getAllBookStatuses).not.toHaveBeenCalled()
    expect(mockApi.getAllProgress).not.toHaveBeenCalled()
    expect(mockLocal.importStatuses).not.toHaveBeenCalled()
  })

  it('syncs all data types when logged in', async () => {
    mockUser.value = null
    await callUseSync()

    // Log in
    mockUser.value = { id: '1' }
    await nextTick()
    await flushPromises()

    expect(mockApi.getAllBookStatuses).toHaveBeenCalledTimes(2) // push compare + pull fresh
    expect(mockApi.getAllProgress).toHaveBeenCalledTimes(2) // push compare + pull fresh
    expect(mockApi.getUserSettings).toHaveBeenCalledTimes(1)
    expect(mockApi.getQuotes).toHaveBeenCalledTimes(1)
    expect(mockApi.getAllBookmarksMap).toHaveBeenCalledTimes(1)
    expect(mockApi.getCollections).toHaveBeenCalledTimes(1)
    expect(mockApi.getAllNotesMap).toHaveBeenCalledTimes(1)
    expect(mockApi.getAllTagsMap).toHaveBeenCalledTimes(1)

    expect(mockLocal.importStatuses).toHaveBeenCalledTimes(1)
    expect(mockLocal.importProgress).toHaveBeenCalledTimes(1)
    expect(mockLocal.setSettings).toHaveBeenCalledWith({ yearly_goal: 24, playback_speed: 1 })
  })

  it('does not re-sync if already synced', async () => {
    mockUser.value = { id: '1' }
    await callUseSync()

    // First sync fires immediately via { immediate: true }
    await nextTick()
    await flushPromises()
    expect(mockApi.getAllBookStatuses).toHaveBeenCalledTimes(2) // push compare + pull fresh

    // Calling useSync again — the synced flag is still true, so the second
    // watch fires with immediate:true but hits the `if (synced) return` guard
    await callUseSync()
    await nextTick()
    await flushPromises()
    expect(mockApi.getAllBookStatuses).toHaveBeenCalledTimes(2)
  })

  it('resets synced flag on logout and re-syncs on next login', async () => {
    mockUser.value = { id: '1' }
    await callUseSync()

    await nextTick()
    await flushPromises()
    expect(mockApi.getAllBookStatuses).toHaveBeenCalledTimes(2) // push compare + pull fresh

    // Logout
    mockUser.value = null
    await nextTick()
    await flushPromises()

    // Login again — should re-sync because synced was reset to false
    mockUser.value = { id: '2' }
    await nextTick()
    await flushPromises()
    expect(mockApi.getAllBookStatuses).toHaveBeenCalledTimes(4) // 2 more calls for second sync
  })

  it('registers reconnect callback', async () => {
    await callUseSync()

    expect(mockOnReconnectPermanent).toHaveBeenCalledTimes(1)
    expect(typeof mockOnReconnectPermanent.mock.calls[0][0]).toBe('function')
  })

  it('registers reconnect callback only once', async () => {
    await callUseSync()
    await callUseSync()

    // reconnectRegistered flag prevents double registration
    expect(mockOnReconnectPermanent).toHaveBeenCalledTimes(1)
  })

  it('reconnect callback re-syncs when logged in', async () => {
    mockUser.value = { id: '1' }
    await callUseSync()

    await nextTick()
    await flushPromises()
    expect(mockApi.getAllBookStatuses).toHaveBeenCalledTimes(2) // push compare + pull fresh

    // Simulate reconnect — call the registered callback
    const reconnectCb = mockOnReconnectPermanent.mock.calls[0][0]
    await reconnectCb()
    await flushPromises()

    expect(mockApi.getAllBookStatuses).toHaveBeenCalledTimes(4) // 2 more calls for reconnect sync
  })

  it('reconnect callback does not sync when logged out', async () => {
    mockUser.value = null
    await callUseSync()

    await nextTick()
    await flushPromises()

    const reconnectCb = mockOnReconnectPermanent.mock.calls[0][0]
    await reconnectCb()
    await flushPromises()

    expect(mockApi.getAllBookStatuses).not.toHaveBeenCalled()
  })

  it('handles individual sync failures gracefully (Promise.allSettled)', async () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    // Make two sync tasks fail — pick ones without internal try/catch
    // (syncStatuses and syncProgress have no try/catch, so rejection propagates)
    mockApi.getAllBookStatuses.mockRejectedValue(new Error('network'))
    mockApi.getAllProgress.mockRejectedValue(new Error('timeout'))

    mockUser.value = { id: '1' }
    await callUseSync()

    await nextTick()
    await flushPromises()

    // syncAll should not throw — Promise.allSettled handles partial failures
    // The remaining 6 sync tasks should still complete
    expect(mockApi.getUserSettings).toHaveBeenCalledTimes(1)
    expect(mockApi.getQuotes).toHaveBeenCalledTimes(1)
    expect(mockLocal.setSettings).toHaveBeenCalledTimes(1)

    // Warning about 2 failures out of 8
    expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining('2/8'))

    consoleSpy.mockRestore()
  })

  it('maps server statuses correctly into importStatuses', async () => {
    mockApi.getAllBookStatuses.mockResolvedValue({
      'book-1': { status: 'reading', updated: '2025-01-01T00:00:00Z' },
      'book-2': { status: 'finished', updated: undefined },
      'book-3': { status: '', updated: '2025-02-01T00:00:00Z' }, // falsy status — skipped
    })

    mockUser.value = { id: '1' }
    await callUseSync()

    await nextTick()
    await flushPromises()

    const call = mockLocal.importStatuses.mock.calls[0][0]
    expect(call['book-1']).toEqual({ status: 'reading', updated: '2025-01-01T00:00:00Z' })
    // book-2 should have a generated timestamp (since updated was undefined)
    expect(call['book-2'].status).toBe('finished')
    expect(call['book-2'].updated).toBeDefined()
    // book-3 has empty status — should be excluded
    expect(call['book-3']).toBeUndefined()
  })

  it('maps server progress into importProgress', async () => {
    mockApi.getAllProgress.mockResolvedValue({
      'book-1': { pct: 50 },
      'book-2': { pct: 100 },
    })

    mockUser.value = { id: '1' }
    await callUseSync()

    await nextTick()
    await flushPromises()

    expect(mockLocal.importProgress).toHaveBeenCalledWith({ 'book-1': 50, 'book-2': 100 })
  })

  it('deduplicates quotes by text::book key', async () => {
    mockApi.getQuotes.mockResolvedValue([
      { text: 'hello', book: 'b1', author: 'a1', ts: '2025-01-01' },
      { text: 'world', book: 'b2', author: 'a2', ts: '2025-01-02' },
    ])

    // Local already has one of them
    mockLocal.getQuotes.mockResolvedValue([
      { text: 'hello', book: 'b1', author: 'a1', ts: '2025-01-01' },
    ])

    mockUser.value = { id: '1' }
    await callUseSync()

    await nextTick()
    await flushPromises()

    // Only the new quote should be added
    expect(mockLocal.addQuote).toHaveBeenCalledTimes(1)
    expect(mockLocal.addQuote).toHaveBeenCalledWith({
      text: 'world',
      book: 'b2',
      author: 'a2',
      ts: '2025-01-02',
    })
  })

  it('deduplicates collections by id', async () => {
    mockApi.getCollections.mockResolvedValue([
      { id: 1, name: 'Col A', books: [], description: '' },
      { id: 2, name: 'Col B', books: [], description: '' },
    ])

    // Local already has collection 1
    mockLocal.getCollections.mockResolvedValue([
      { id: 1, name: 'Col A', books: [], description: '' },
    ])

    mockUser.value = { id: '1' }
    await callUseSync()

    await nextTick()
    await flushPromises()

    // Only new collection (id=2) should be saved
    expect(mockLocal.saveCollection).toHaveBeenCalledTimes(1)
    expect(mockLocal.saveCollection).toHaveBeenCalledWith(
      expect.objectContaining({ id: 2, name: 'Col B' }),
    )
  })
})
