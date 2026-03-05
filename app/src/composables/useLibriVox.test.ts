import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api', () => ({
  api: {
    librivoxSearch: vi.fn(),
  },
}))

import { useLibriVox } from './useLibriVox'
import { api } from '../api'

function makeRawBook(overrides: Record<string, unknown> = {}) {
  return {
    librivox_id: '123',
    title: 'Test Book',
    author: 'Author',
    description: 'A book',
    language: 'English',
    copyright_year: '1900',
    num_sections: 10,
    total_time: '05:30:00',
    total_time_secs: 19800,
    url_librivox: 'https://librivox.org/test',
    ...overrides,
  }
}

describe('useLibriVox', () => {
  beforeEach(() => {
    vi.mocked(api.librivoxSearch).mockReset()
    // Reset singleton state
    const lv = useLibriVox()
    lv.books.value = []
    lv.hasMore.value = false
  })

  it('search() populates books from API', async () => {
    vi.mocked(api.librivoxSearch).mockResolvedValue({
      books: [makeRawBook()],
    } as never)

    const lv = useLibriVox()
    await lv.search('test', 'English')
    expect(lv.books.value).toHaveLength(1)
    expect(lv.books.value[0].id).toBe('lv:123')
    expect(lv.books.value[0].title).toBe('Test Book')
    expect(lv.loading.value).toBe(false)
  })

  it('mapBook handles missing fields with defaults', async () => {
    vi.mocked(api.librivoxSearch).mockResolvedValue({
      books: [{ librivox_id: '1' }], // minimal raw data
    } as never)

    const lv = useLibriVox()
    await lv.search('', '')
    const book = lv.books.value[0]
    expect(book.title).toBe('')
    expect(book.author).toBe('')
    expect(book.num_sections).toBe(0)
    expect(book.total_time_secs).toBe(0)
  })

  it('hasMore is true when results === PAGE_SIZE', async () => {
    const books = Array.from({ length: 20 }, (_, i) => makeRawBook({ librivox_id: String(i) }))
    vi.mocked(api.librivoxSearch).mockResolvedValue({ books } as never)

    const lv = useLibriVox()
    await lv.search('test', '')
    expect(lv.hasMore.value).toBe(true)
  })

  it('hasMore is false when results < PAGE_SIZE', async () => {
    vi.mocked(api.librivoxSearch).mockResolvedValue({
      books: [makeRawBook()],
    } as never)

    const lv = useLibriVox()
    await lv.search('test', '')
    expect(lv.hasMore.value).toBe(false)
  })

  it('loadMore() appends to existing books', async () => {
    // First page
    vi.mocked(api.librivoxSearch).mockResolvedValue({
      books: [makeRawBook({ librivox_id: '1' })],
    } as never)
    const lv = useLibriVox()
    await lv.search('test', '')
    expect(lv.books.value).toHaveLength(1)

    // Load more
    vi.mocked(api.librivoxSearch).mockResolvedValue({
      books: [makeRawBook({ librivox_id: '2' })],
    } as never)
    await lv.loadMore('test', '')
    expect(lv.books.value).toHaveLength(2)
    expect(lv.books.value[1].librivox_id).toBe('2')
  })

  it('search with reset clears previous results', async () => {
    vi.mocked(api.librivoxSearch).mockResolvedValue({
      books: [makeRawBook({ librivox_id: '1' })],
    } as never)
    const lv = useLibriVox()
    await lv.search('first', '')

    vi.mocked(api.librivoxSearch).mockResolvedValue({
      books: [makeRawBook({ librivox_id: '2' })],
    } as never)
    await lv.search('second', '', true)
    expect(lv.books.value).toHaveLength(1)
    expect(lv.books.value[0].librivox_id).toBe('2')
  })
})
