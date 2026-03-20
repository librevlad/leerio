import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api', () => ({
  api: {
    getBooks: vi.fn(),
  },
}))

import { useBooks } from './useBooks'
import { api } from '../api'

describe('useBooks', () => {
  beforeEach(() => {
    vi.mocked(api.getBooks).mockReset()
    // Reset singleton state
    const b = useBooks()
    b.books.value = []
  })

  it('categories extracts unique sorted categories', () => {
    const b = useBooks()
    b.books.value = [
      {
        id: '1',
        folder: '',
        category: 'Бизнес',
        author: '',
        title: '',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      },
      {
        id: '2',
        folder: '',
        category: 'Языки',
        author: '',
        title: '',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      },
      {
        id: '3',
        folder: '',
        category: 'Бизнес',
        author: '',
        title: '',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      },
    ]
    expect(b.categories.value).toEqual(['Бизнес', 'Языки'])
  })

  it('categories returns empty array when no books', () => {
    const b = useBooks()
    b.books.value = []
    expect(b.categories.value).toEqual([])
  })

  it('load() calls API and populates books', async () => {
    const mockBooks = [
      {
        id: '1',
        folder: '',
        category: 'A',
        author: '',
        title: '',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      },
    ]
    vi.mocked(api.getBooks).mockResolvedValue(mockBooks as never)

    const b = useBooks()
    await b.load()
    expect(api.getBooks).toHaveBeenCalled()
    expect(b.books.value).toEqual(mockBooks)
    expect(b.loading.value).toBe(false)
  })

  it('load() preserves existing books on error', async () => {
    vi.mocked(api.getBooks).mockRejectedValue(new Error('fail'))
    const b = useBooks()
    const existing = [
      {
        id: '1',
        folder: '',
        category: '',
        author: '',
        title: '',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      },
    ]
    b.books.value = existing
    await b.load()
    // Books should be preserved on error, not wiped
    expect(b.books.value).toEqual(existing)
  })

  it('load() keeps empty array if no prior data on error', async () => {
    vi.mocked(api.getBooks).mockRejectedValue(new Error('fail'))
    const b = useBooks()
    b.books.value = []
    await b.load()
    expect(b.books.value).toEqual([])
  })
})
