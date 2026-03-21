import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock Capacitor
vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => false },
}))
vi.mock('@capacitor/filesystem', () => ({
  Filesystem: {
    readdir: vi.fn(),
    stat: vi.fn(),
    getUri: vi.fn(),
    mkdir: vi.fn(),
    requestPermissions: vi.fn(),
  },
  Directory: { ExternalStorage: 'EXTERNAL_STORAGE' },
}))

import { useFileScanner } from '../composables/useFileScanner'

describe('useFileScanner', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns empty on web (not native)', async () => {
    const { scan } = useFileScanner()
    const result = await scan()
    expect(result).toEqual([])
  })

  it('loads persisted books from localStorage', () => {
    const books = { 'fs:test': { id: 'fs:test', title: 'Test', author: '', folderPath: 'Audiobooks/test', tracks: [], sizeBytes: 0, synced: false, addedAt: '2026-01-01' } }
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
    expect(isLikelyNotBook('podcast_episodes', 1)).toBe(true)
    expect(isLikelyNotBook('My Audiobook', 10)).toBe(false)
    expect(isLikelyNotBook('music_collection', 5)).toBe(true)
    expect(isLikelyNotBook('book', 1)).toBe(true) // < 2 tracks
  })

  it('addFsBooks persists to localStorage', () => {
    const { addFsBooks, fsBooks } = useFileScanner()
    addFsBooks([{
      id: 'fs:mybook',
      title: 'My Book',
      author: 'Author',
      folderPath: 'Audiobooks/mybook',
      tracks: [{ index: 0, filename: '01.mp3', path: 'Audiobooks/mybook/01.mp3', duration: 0 }],
      sizeBytes: 1000,
      synced: false,
      addedAt: '2026-01-01',
    }])
    expect(fsBooks.value['fs:mybook']).toBeDefined()
    const stored = JSON.parse(localStorage.getItem('leerio_fs_books') || '{}')
    expect(stored['fs:mybook']).toBeDefined()
  })

  it('removeFsBook removes from localStorage', () => {
    const { addFsBooks, removeFsBook, fsBooks } = useFileScanner()
    addFsBooks([{ id: 'fs:x', title: 'X', author: '', folderPath: 'Audiobooks/x', tracks: [], sizeBytes: 0, synced: false, addedAt: '' }])
    removeFsBook('fs:x')
    expect(fsBooks.value['fs:x']).toBeUndefined()
  })
})
