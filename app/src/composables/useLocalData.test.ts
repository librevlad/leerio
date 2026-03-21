import { describe, it, expect, vi, beforeEach } from 'vitest'

// vi.hoisted runs before vi.mock hoisting, so `stores` is available in the factory
const stores = vi.hoisted(() => new Map<object, Map<string, unknown>>())

vi.mock('idb-keyval', () => ({
  createStore: vi.fn(() => {
    const store = {}
    stores.set(store, new Map())
    return store
  }),
  get: vi.fn(async (key: string, store: object) => {
    return stores.get(store)?.get(key)
  }),
  set: vi.fn(async (key: string, value: unknown, store: object) => {
    stores.get(store)?.set(key, value)
  }),
  setMany: vi.fn(async (entries: [string, unknown][], store: object) => {
    const map = stores.get(store)!
    for (const [k, v] of entries) map.set(k, v)
  }),
  del: vi.fn(async (key: string, store: object) => {
    stores.get(store)?.delete(key)
  }),
  keys: vi.fn(async (store: object) => {
    return [...(stores.get(store)?.keys() ?? [])]
  }),
  entries: vi.fn(async (store: object) => {
    return [...(stores.get(store)?.entries() ?? [])]
  }),
}))

import { useLocalData } from './useLocalData'
import type { PlaybackPosition, Collection } from '../types'

beforeEach(() => {
  for (const map of stores.values()) map.clear()
})

describe('useLocalData', () => {
  // ── Book Status ────────────────────────────────────────────

  describe('book status', () => {
    it('returns undefined for unknown bookId', async () => {
      const local = useLocalData()
      expect(await local.getBookStatus('unknown')).toBeUndefined()
    })

    it('set and get a status', async () => {
      const local = useLocalData()
      await local.setBookStatus('b1', 'reading')
      const result = await local.getBookStatus('b1')
      expect(result).toBeDefined()
      expect(result!.status).toBe('reading')
      expect(result!.updated).toBeTruthy()
    })

    it('remove a status', async () => {
      const local = useLocalData()
      await local.setBookStatus('b1', 'done')
      await local.removeBookStatus('b1')
      expect(await local.getBookStatus('b1')).toBeUndefined()
    })

    it('getAllBookStatuses returns all entries', async () => {
      const local = useLocalData()
      await local.setBookStatus('b1', 'reading')
      await local.setBookStatus('b2', 'done')
      const all = await local.getAllBookStatuses()
      expect(Object.keys(all)).toHaveLength(2)
      expect(all['b1'].status).toBe('reading')
      expect(all['b2'].status).toBe('done')
    })
  })

  // ── Progress ───────────────────────────────────────────────

  describe('progress', () => {
    it('returns undefined for unknown bookId', async () => {
      const local = useLocalData()
      expect(await local.getProgress('unknown')).toBeUndefined()
    })

    it('set and get progress', async () => {
      const local = useLocalData()
      await local.setProgress('b1', 42)
      expect(await local.getProgress('b1')).toBe(42)
    })

    it('getAllProgress returns all entries', async () => {
      const local = useLocalData()
      await local.setProgress('b1', 10)
      await local.setProgress('b2', 90)
      const all = await local.getAllProgress()
      expect(all).toEqual({ b1: 10, b2: 90 })
    })
  })

  // ── Playback Position ──────────────────────────────────────

  describe('position', () => {
    it('returns undefined for unknown bookId', async () => {
      const local = useLocalData()
      expect(await local.getPosition('unknown')).toBeUndefined()
    })

    it('set and get position', async () => {
      const local = useLocalData()
      const pos: PlaybackPosition = { track_index: 3, position: 123.5, filename: 'ch03.mp3' }
      await local.setPosition('b1', pos)
      expect(await local.getPosition('b1')).toEqual(pos)
    })
  })

  // ── Bookmarks ──────────────────────────────────────────────

  describe('bookmarks', () => {
    it('returns empty array for unknown bookId', async () => {
      const local = useLocalData()
      expect(await local.getBookmarks('unknown')).toEqual([])
    })

    it('addBookmark creates entry with Date.now() id', async () => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2026-01-15T10:00:00Z'))
      try {
        const local = useLocalData()
        const bm = await local.addBookmark('b1', { track: 2, time: 55.3, note: 'good part', ts: '2026-01-15' })
        expect(bm.id).toBe(Date.now())
        expect(bm.track).toBe(2)
        expect(bm.time).toBe(55.3)
        expect(bm.note).toBe('good part')

        const list = await local.getBookmarks('b1')
        expect(list).toHaveLength(1)
        expect(list[0].id).toBe(bm.id)
      } finally {
        vi.useRealTimers()
      }
    })

    it('removeBookmark filters by id', async () => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2026-01-15T10:00:00Z'))
      try {
        const local = useLocalData()
        const bm1 = await local.addBookmark('b1', { track: 1, time: 10, note: 'a', ts: '2026-01-15' })
        vi.setSystemTime(new Date('2026-01-15T10:00:01Z'))
        await local.addBookmark('b1', { track: 2, time: 20, note: 'b', ts: '2026-01-15' })

        await local.removeBookmark('b1', bm1.id)
        const list = await local.getBookmarks('b1')
        expect(list).toHaveLength(1)
        expect(list[0].note).toBe('b')
      } finally {
        vi.useRealTimers()
      }
    })
  })

  // ── Notes ──────────────────────────────────────────────────

  describe('notes', () => {
    it('returns undefined for unknown bookId', async () => {
      const local = useLocalData()
      expect(await local.getNote('unknown')).toBeUndefined()
    })

    it('set and get a note', async () => {
      const local = useLocalData()
      await local.setNote('b1', 'Great chapter')
      expect(await local.getNote('b1')).toBe('Great chapter')
    })

    it('deleteNote removes the entry', async () => {
      const local = useLocalData()
      await local.setNote('b1', 'text')
      await local.deleteNote('b1')
      expect(await local.getNote('b1')).toBeUndefined()
    })
  })

  // ── Tags ───────────────────────────────────────────────────

  describe('tags', () => {
    it('returns empty array for unknown bookId', async () => {
      const local = useLocalData()
      expect(await local.getTags('unknown')).toEqual([])
    })

    it('set and get tags', async () => {
      const local = useLocalData()
      await local.setTags('b1', ['fiction', 'classic'])
      expect(await local.getTags('b1')).toEqual(['fiction', 'classic'])
    })

    it('getAllTagNames returns sorted unique tags across all books', async () => {
      const local = useLocalData()
      await local.setTags('b1', ['fiction', 'classic'])
      await local.setTags('b2', ['science', 'classic'])
      const names = await local.getAllTagNames()
      expect(names).toEqual(['classic', 'fiction', 'science'])
    })
  })

  // ── Ratings ────────────────────────────────────────────────

  describe('ratings', () => {
    it('returns undefined for unknown bookId', async () => {
      const local = useLocalData()
      expect(await local.getRating('unknown')).toBeUndefined()
    })

    it('set and get a rating', async () => {
      const local = useLocalData()
      await local.setRating('b1', 5)
      expect(await local.getRating('b1')).toBe(5)
    })
  })

  // ── Quotes ─────────────────────────────────────────────────

  describe('quotes', () => {
    it('returns empty array when no quotes', async () => {
      const local = useLocalData()
      expect(await local.getQuotes()).toEqual([])
    })

    it('addQuote creates entry with Date.now() id', async () => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2026-02-01T12:00:00Z'))
      try {
        const local = useLocalData()
        const q = await local.addQuote({
          text: 'To be or not',
          book: 'Hamlet',
          author: 'Shakespeare',
          ts: '2026-02-01',
        })
        expect(q.id).toBe(Date.now())
        expect(q.text).toBe('To be or not')

        const all = await local.getQuotes()
        expect(all).toHaveLength(1)
        expect(all[0].id).toBe(q.id)
      } finally {
        vi.useRealTimers()
      }
    })

    it('deleteQuote removes by id', async () => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2026-02-01T12:00:00Z'))
      try {
        const local = useLocalData()
        const q1 = await local.addQuote({ text: 'a', book: 'X', author: 'A', ts: '1' })
        vi.setSystemTime(new Date('2026-02-01T12:00:01Z'))
        await local.addQuote({ text: 'b', book: 'Y', author: 'B', ts: '2' })

        await local.deleteQuote(q1.id)
        const all = await local.getQuotes()
        expect(all).toHaveLength(1)
        expect(all[0].text).toBe('b')
      } finally {
        vi.useRealTimers()
      }
    })
  })

  // ── Collections ────────────────────────────────────────────

  describe('collections', () => {
    it('returns empty array when no collections', async () => {
      const local = useLocalData()
      expect(await local.getCollections()).toEqual([])
    })

    it('saveCollection and getCollections', async () => {
      const local = useLocalData()
      const col: Collection = {
        id: 1,
        name: 'Favorites',
        books: [10, 20],
        description: 'My favs',
        created: '2026-01-01',
      }
      await local.saveCollection(col)
      const all = await local.getCollections()
      expect(all).toHaveLength(1)
      expect(all[0]).toEqual(col)
    })

    it('deleteCollection removes by id', async () => {
      const local = useLocalData()
      const c1: Collection = { id: 1, name: 'A', books: [], description: '', created: '2026-01-01' }
      const c2: Collection = { id: 2, name: 'B', books: [], description: '', created: '2026-01-02' }
      await local.saveCollection(c1)
      await local.saveCollection(c2)

      await local.deleteCollection(1)
      const all = await local.getCollections()
      expect(all).toHaveLength(1)
      expect(all[0].name).toBe('B')
    })
  })

  // ── Settings ───────────────────────────────────────────────

  describe('settings', () => {
    it('returns undefined when no settings saved', async () => {
      const local = useLocalData()
      expect(await local.getSettings()).toBeUndefined()
    })

    it('setSettings uses defaults when no prior settings', async () => {
      const local = useLocalData()
      await local.setSettings({ playback_speed: 1.5 })
      const s = await local.getSettings()
      expect(s).toEqual({ yearly_goal: 24, playback_speed: 1.5 })
    })

    it('setSettings merges with existing settings', async () => {
      const local = useLocalData()
      await local.setSettings({ yearly_goal: 50, playback_speed: 1 })
      await local.setSettings({ playback_speed: 2 })
      const s = await local.getSettings()
      expect(s).toEqual({ yearly_goal: 50, playback_speed: 2 })
    })
  })

  // ── Bulk Imports ───────────────────────────────────────────

  describe('bulk imports', () => {
    it('importStatuses populates store', async () => {
      const local = useLocalData()
      await local.importStatuses({
        b1: { status: 'reading', updated: '2026-01-01' },
        b2: { status: 'done', updated: '2026-01-02' },
      })
      const all = await local.getAllBookStatuses()
      expect(Object.keys(all)).toHaveLength(2)
      expect(all['b1'].status).toBe('reading')
      expect(all['b2'].status).toBe('done')
    })

    it('importProgress populates store', async () => {
      const local = useLocalData()
      await local.importProgress({ b1: 25, b2: 75 })
      const all = await local.getAllProgress()
      expect(all).toEqual({ b1: 25, b2: 75 })
    })

    it('importStatuses with empty object is a no-op', async () => {
      const { setMany } = await import('idb-keyval')
      const callsBefore = (setMany as ReturnType<typeof vi.fn>).mock.calls.length
      const local = useLocalData()
      await local.importStatuses({})
      const callsAfter = (setMany as ReturnType<typeof vi.fn>).mock.calls.length
      expect(callsAfter).toBe(callsBefore)
    })
  })

  // ── Counts ─────────────────────────────────────────────────

  describe('counts', () => {
    it('bookmarkCount returns 0 when empty', async () => {
      const local = useLocalData()
      expect(await local.bookmarkCount()).toBe(0)
    })

    it('bookmarkCount reflects added bookmarks', async () => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2026-03-01T00:00:00Z'))
      try {
        const local = useLocalData()
        await local.addBookmark('b1', { track: 1, time: 0, note: '', ts: '' })
        vi.setSystemTime(new Date('2026-03-01T00:00:01Z'))
        await local.addBookmark('b2', { track: 1, time: 0, note: '', ts: '' })
        expect(await local.bookmarkCount()).toBe(2)
      } finally {
        vi.useRealTimers()
      }
    })

    it('quoteCount returns 0 when empty', async () => {
      const local = useLocalData()
      expect(await local.quoteCount()).toBe(0)
    })

    it('quoteCount reflects added quotes', async () => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2026-03-01T00:00:00Z'))
      try {
        const local = useLocalData()
        await local.addQuote({ text: 'a', book: 'X', author: 'A', ts: '' })
        vi.setSystemTime(new Date('2026-03-01T00:00:01Z'))
        await local.addQuote({ text: 'b', book: 'Y', author: 'B', ts: '' })
        expect(await local.quoteCount()).toBe(2)
      } finally {
        vi.useRealTimers()
      }
    })
  })
})
