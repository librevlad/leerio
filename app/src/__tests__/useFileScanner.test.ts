import { describe, it, expect, vi, beforeEach } from 'vitest'

const native = vi.hoisted(() => ({ isNative: false, audioGranted: true }))

// Mock Capacitor
vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => native.isNative },
  registerPlugin: () => ({ request: vi.fn(async () => ({ granted: native.audioGranted })) }),
}))
vi.mock('@capacitor/filesystem', () => ({
  Filesystem: {
    readdir: vi.fn(),
    stat: vi.fn(),
    getUri: vi.fn(),
    mkdir: vi.fn(),
    requestPermissions: vi.fn(async () => ({ publicStorage: 'granted' })),
  },
  Directory: { ExternalStorage: 'EXTERNAL_STORAGE' },
}))

import { Filesystem } from '@capacitor/filesystem'
import { useFileScanner } from '../composables/useFileScanner'

type Entry = { name: string; type: 'file' | 'directory'; size?: number }

/** Fake ExternalStorage tree: path → entries */
function mockTree(tree: Record<string, Entry[]>) {
  vi.mocked(Filesystem.readdir).mockImplementation((async ({ path }: { path: string }) => {
    const files = tree[path]
    if (!files) throw new Error('ENOENT')
    return { files: files.map((f) => ({ size: 0, ...f })) }
  }) as unknown as typeof Filesystem.readdir)
}

describe('useFileScanner', () => {
  beforeEach(() => {
    localStorage.clear()
    native.isNative = false
    native.audioGranted = true
    vi.mocked(Filesystem.readdir).mockReset()
  })

  it('native scan: nested part folders become tracks in natural path order', async () => {
    native.isNative = true
    mockTree({
      Audiobooks: [{ name: 'Фромм - Бегство от свободы', type: 'directory' }],
      'Audiobooks/Фромм - Бегство от свободы': [
        { name: '10_1', type: 'directory' },
        { name: '2_1', type: 'directory' },
        { name: 'cover.jpg', type: 'file', size: 5 },
      ],
      'Audiobooks/Фромм - Бегство от свободы/2_1': [{ name: '2_1_01.mp3', type: 'file', size: 100 }],
      'Audiobooks/Фромм - Бегство от свободы/10_1': [
        { name: '10_1_02.mp3', type: 'file', size: 300 },
        { name: '10_1_01.mp3', type: 'file', size: 200 },
      ],
    })
    const [book] = await useFileScanner().scan()
    expect(book?.tracks.map((t) => t.path)).toEqual([
      'Audiobooks/Фромм - Бегство от свободы/2_1/2_1_01.mp3',
      'Audiobooks/Фромм - Бегство от свободы/10_1/10_1_01.mp3',
      'Audiobooks/Фромм - Бегство от свободы/10_1/10_1_02.mp3',
    ])
    expect(book?.tracks.map((t) => t.index)).toEqual([0, 1, 2])
    expect(book?.tracks[0]?.filename).toBe('2_1_01.mp3')
    expect(book?.sizeBytes).toBe(600)
    expect(Filesystem.stat).not.toHaveBeenCalled()
  })

  it('native scan: accepts truncated names that lost the dot before "mp3"', async () => {
    native.isNative = true
    mockTree({
      Audiobooks: [{ name: 'Book', type: 'directory' }],
      'Audiobooks/Book': [
        { name: 'Глава 1 - где мы гmp3', type: 'file' },
        { name: 'Глава 2.mp3', type: 'file' },
        { name: 'notes.docx', type: 'file' },
      ],
    })
    const [book] = await useFileScanner().scan()
    expect(book?.tracks.map((t) => t.filename)).toEqual(['Глава 1 - где мы гmp3', 'Глава 2.mp3'])
  })

  it('native scan: returns nothing when audio permission is denied', async () => {
    native.isNative = true
    native.audioGranted = false
    mockTree({
      Audiobooks: [{ name: 'Book', type: 'directory' }],
      'Audiobooks/Book': [{ name: '1.mp3', type: 'file' }],
    })
    expect(await useFileScanner().scan()).toEqual([])
    expect(Filesystem.readdir).not.toHaveBeenCalled()
  })

  it('cleanTitle / extractAuthor handle real-world folder names', () => {
    const { cleanTitle, extractAuthor } = useFileScanner()
    const cases: [string, string, string][] = [
      ['Брайан Трейси «Мастер времени» [чит. Алексей Мужицкий]', 'Мастер времени', 'Брайан Трейси'],
      ['Вастикова Ольга – Парень, ты просто Космос! [Татьяна Бур]', 'Парень, ты просто Космос!', 'Вастикова Ольга'],
      ['Брегман_П_-_Эмоциональная_смелость_(Владимир_Г)', 'Эмоциональная смелость', 'Брегман П'],
      ['Хьюлинг, Макчесни, Кови - Как достичь цели (Курилов', 'Как достичь цели', 'Хьюлинг, Макчесни, Кови'],
      ['Лэй Эндрю - Харизма[Даниил Крылов].mp3', 'Харизма', 'Лэй Эндрю'],
      ['Бегство от свободы', 'Бегство от свободы', ''],
    ]
    for (const [folder, title, author] of cases) {
      expect(cleanTitle(folder)).toBe(title)
      expect(extractAuthor(folder)).toBe(author)
    }
  })

  it('returns empty on web (not native)', async () => {
    const { scan } = useFileScanner()
    const result = await scan()
    expect(result).toEqual([])
  })

  it('loads persisted books from localStorage', () => {
    const books = {
      'fs:test': {
        id: 'fs:test',
        title: 'Test',
        author: '',
        folderPath: 'Audiobooks/test',
        tracks: [],
        sizeBytes: 0,
        synced: false,
        addedAt: '2026-01-01',
      },
    }
    localStorage.setItem('leerio_fs_books', JSON.stringify(books))
    const { fsBooks } = useFileScanner()
    expect(fsBooks.value['fs:test']?.title).toBe('Test')
  })

  it('cleanTitle extracts title from "Author - Title [Reader]"', () => {
    const { cleanTitle } = useFileScanner()
    expect(cleanTitle('Толстой - Война и мир [Иванов]')).toBe('Война и мир')
    expect(cleanTitle('Simple Book')).toBe('Simple Book')
  })

  it('extractAuthor extracts author from "Author - Title"', () => {
    const { extractAuthor } = useFileScanner()
    expect(extractAuthor('Толстой - Война и мир')).toBe('Толстой')
    expect(extractAuthor('NoAuthor')).toBe('')
  })

  it('isLikelyNotBook returns true for short or keyword folders', () => {
    const { isLikelyNotBook } = useFileScanner()
    const mp3s = (n: number) => Array.from({ length: n }, (_, i) => ({ filename: `${i + 1}.mp3` }))
    expect(isLikelyNotBook('podcast_episodes', mp3s(1))).toBe(true)
    expect(isLikelyNotBook('My Audiobook', mp3s(10))).toBe(false)
    expect(isLikelyNotBook('music_collection', mp3s(5))).toBe(true)
    expect(isLikelyNotBook('book', mp3s(1))).toBe(true) // one MP3 is a single
    expect(isLikelyNotBook('Music/Scorpions', mp3s(18))).toBe(true) // albums under Music/
    expect(isLikelyNotBook('Audiobooks/Сенека Луций - Нравственные письма', mp3s(39))).toBe(false)
  })

  it('isLikelyNotBook keeps a one-file M4B audiobook', () => {
    const { isLikelyNotBook } = useFileScanner()
    expect(isLikelyNotBook('Audiobooks/Толстой - Война и мир', [{ filename: 'Война и мир.m4b' }])).toBe(false)
    expect(isLikelyNotBook('Audiobooks/Book', [{ filename: 'BOOK.M4B' }])).toBe(false)
    expect(isLikelyNotBook('Music/Podcast', [{ filename: 'episode.m4b' }])).toBe(true) // Music/ still means music
    expect(isLikelyNotBook('Audiobooks/Single', [{ filename: 'track.m4a' }])).toBe(true)
  })

  it('addFsBooks persists to localStorage', () => {
    const { addFsBooks, fsBooks } = useFileScanner()
    addFsBooks([
      {
        id: 'fs:mybook',
        title: 'My Book',
        author: 'Author',
        folderPath: 'Audiobooks/mybook',
        tracks: [{ index: 0, filename: '01.mp3', path: 'Audiobooks/mybook/01.mp3', duration: 0 }],
        sizeBytes: 1000,
        synced: false,
        addedAt: '2026-01-01',
      },
    ])
    expect(fsBooks.value['fs:mybook']).toBeDefined()
    const stored = JSON.parse(localStorage.getItem('leerio_fs_books') || '{}')
    expect(stored['fs:mybook']).toBeDefined()
  })

  it('removeFsBook removes from localStorage', () => {
    const { addFsBooks, removeFsBook, fsBooks } = useFileScanner()
    addFsBooks([
      {
        id: 'fs:x',
        title: 'X',
        author: '',
        folderPath: 'Audiobooks/x',
        tracks: [],
        sizeBytes: 0,
        synced: false,
        addedAt: '',
      },
    ])
    removeFsBook('fs:x')
    expect(fsBooks.value['fs:x']).toBeUndefined()
  })

  it('checkFsBook keeps a book whose folder is there and drops a vanished one', async () => {
    native.isNative = true
    const { addFsBooks, checkFsBook, fsBooks } = useFileScanner()
    const book = (name: string) => ({
      id: `fs:${name}`,
      title: name,
      author: '',
      folderPath: `Audiobooks/${name}`,
      tracks: [],
      sizeBytes: 0,
      synced: false,
      addedAt: '',
    })
    addFsBooks([book('here'), book('gone')])
    vi.mocked(Filesystem.stat).mockImplementation((async ({ path }: { path: string }) => {
      if (path !== 'Audiobooks/here') throw new Error('ENOENT')
      return {}
    }) as unknown as typeof Filesystem.stat)

    expect(await checkFsBook('fs:here')).toBe(true)
    expect(await checkFsBook('fs:gone')).toBe(false)
    expect(await checkFsBook('fs:unknown')).toBe(false)
    expect(Object.keys(fsBooks.value)).toContain('fs:here')
    expect(fsBooks.value['fs:gone']).toBeUndefined()
    expect(JSON.parse(localStorage.getItem('leerio_fs_books') || '{}')['fs:gone']).toBeUndefined()
  })
})
