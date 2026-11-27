import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import type { Book } from '../../types'

/**
 * Promise to the listener (live hunt, 27.11.2026): a book page shows that book's chapters —
 * also after moving straight from one book's page to another (search, "Book page" in the player).
 */

const local: Record<string, { tracks: { filename: string; duration: number }[] }> = {
  'lb:a': {
    tracks: [
      { filename: '01 Глава 1.mp3', duration: 40 },
      { filename: '02 Глава 2.mp3', duration: 30 },
      { filename: '03 Глава 3.mp3', duration: 20 },
    ],
  },
  'lb:b': {
    tracks: [
      { filename: '01 Часть 1.mp3', duration: 60 },
      { filename: '02 Часть 2.mp3', duration: 60 },
    ],
  },
}

vi.mock('../../composables/useLocalBooks', () => ({
  useLocalBooks: () => ({ getLocalBook: (id: string) => local[id] }),
}))
vi.mock('../../composables/useFileScanner', () => ({ useFileScanner: () => ({ getFsBook: () => undefined }) }))
vi.mock('../../composables/usePlayer', () => ({
  usePlayer: () => ({
    currentBook: { value: null },
    currentTrackIndex: { value: 0 },
    isPlaying: { value: false },
    playTrack: vi.fn(),
    loadBook: vi.fn(),
    openFullscreen: vi.fn(),
  }),
}))
vi.mock('../../api', () => ({ api: { getBookTracks: vi.fn() } }))

const book = (id: string, title: string): Book =>
  ({
    id,
    title,
    author: 'Охота',
    folder: '',
    category: '',
    reader: '',
    path: '',
    progress: 0,
    tags: [],
    note: '',
  }) as Book

async function mountChapters(b: Book) {
  const { default: BookChapters } = await import('./BookChapters.vue')
  const i18n = createI18n({
    legacy: false,
    locale: 'en',
    missingWarn: false,
    fallbackWarn: false,
    messages: { en: {} },
  })
  return mount(BookChapters, { props: { book: b }, global: { plugins: [i18n] } })
}

describe('BookChapters', () => {
  it("shows the book's own chapters", async () => {
    const w = await mountChapters(book('lb:a', 'Три главы'))
    await flushPromises()
    expect(w.text()).toContain('Глава 3')
    expect(w.text()).not.toContain('Часть')
  })

  it('switches to the new book when the page moves from one book to another', async () => {
    const w = await mountChapters(book('lb:a', 'Три главы'))
    await flushPromises()
    await w.setProps({ book: book('lb:b', 'Книга Б') })
    await flushPromises()
    expect(w.text()).toContain('Часть 2')
    expect(w.text()).not.toContain('Глава')
  })
})
