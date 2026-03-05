import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('@/api', () => ({
  api: {
    getUserBooks: vi.fn(),
    deleteUserBook: vi.fn(),
    getTTSJob: vi.fn(),
    getTTSJobs: vi.fn(),
  },
}))

import { useUserBooks } from './useUserBooks'
import { api } from '@/api'

const mockUserBook = (slug: string) => ({
  id: `ub:user:${slug}`,
  slug,
  title: `Book ${slug}`,
  author: 'Author',
  reader: 'TTS',
  source: 'tts' as const,
  created_at: '2025-01-01',
  is_personal: true as const,
  has_cover: false,
  mp3_count: 3,
})

describe('useUserBooks', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(api.getUserBooks).mockReset()
    vi.mocked(api.deleteUserBook).mockReset()
    vi.mocked(api.getTTSJob).mockReset()
    // Reset singleton state
    const ub = useUserBooks()
    ub.userBooks.value = []
    ub.loading.value = false
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('loadUserBooks() fetches and populates ref', async () => {
    const books = [mockUserBook('a'), mockUserBook('b')]
    vi.mocked(api.getUserBooks).mockResolvedValue(books as never)

    const ub = useUserBooks()
    await ub.loadUserBooks()
    expect(ub.userBooks.value).toEqual(books)
    expect(ub.loading.value).toBe(false)
  })

  it('deleteBook() filters out by slug and calls API', async () => {
    vi.mocked(api.deleteUserBook).mockResolvedValue(undefined as never)
    const ub = useUserBooks()
    ub.userBooks.value = [mockUserBook('a'), mockUserBook('b')] as never

    await ub.deleteBook('a')
    expect(api.deleteUserBook).toHaveBeenCalledWith('a')
    expect(ub.userBooks.value).toHaveLength(1)
    expect(ub.userBooks.value[0].slug).toBe('b')
  })

  it('pollJob() calls API at interval, stops on done', async () => {
    const callback = vi.fn()
    vi.mocked(api.getTTSJob).mockResolvedValue({
      id: 'j1',
      status: 'processing',
      progress: 50,
    } as never)

    const ub = useUserBooks()
    ub.pollJob('j1', callback, 1000)

    await vi.advanceTimersByTimeAsync(1000)
    expect(callback).toHaveBeenCalledTimes(1)

    // Now return done
    vi.mocked(api.getTTSJob).mockResolvedValue({
      id: 'j1',
      status: 'done',
      progress: 100,
    } as never)
    await vi.advanceTimersByTimeAsync(1000)
    expect(callback).toHaveBeenCalledTimes(2)

    // Should not poll again
    await vi.advanceTimersByTimeAsync(1000)
    expect(callback).toHaveBeenCalledTimes(2)
  })

  it('pollJob() stops on error status', async () => {
    const callback = vi.fn()
    vi.mocked(api.getTTSJob).mockResolvedValue({
      id: 'j1',
      status: 'error',
      progress: 0,
    } as never)

    const ub = useUserBooks()
    ub.pollJob('j1', callback, 1000)

    await vi.advanceTimersByTimeAsync(1000)
    expect(callback).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1000)
    expect(callback).toHaveBeenCalledTimes(1)
  })

  it('pollJob() returns cleanup function that clears interval', async () => {
    const callback = vi.fn()
    vi.mocked(api.getTTSJob).mockResolvedValue({
      id: 'j1',
      status: 'processing',
      progress: 50,
    } as never)

    const ub = useUserBooks()
    const cleanup = ub.pollJob('j1', callback, 1000)

    await vi.advanceTimersByTimeAsync(1000)
    expect(callback).toHaveBeenCalledTimes(1)

    cleanup()
    await vi.advanceTimersByTimeAsync(5000)
    expect(callback).toHaveBeenCalledTimes(1)
  })
})
