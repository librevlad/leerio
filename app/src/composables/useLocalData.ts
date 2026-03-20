/**
 * Local-first data store for user data.
 *
 * All user data (progress, bookmarks, notes, tags, statuses, etc.)
 * lives in IndexedDB as the primary source of truth. Server is optional sync.
 *
 * Usage:
 *   const local = useLocalData()
 *   await local.setProgress('book-123', 42)
 *   const pct = await local.getProgress('book-123')  // 42
 */
import { createStore, get, set, setMany, del, keys, entries } from 'idb-keyval'
import type { Bookmark, Quote, Collection, PlaybackPosition, Track, Book } from '../types'

// Separate IndexedDB stores for different data domains
const statusStore = createStore('leerio-status', 'book-status')
const progressStore = createStore('leerio-progress', 'progress')
const positionStore = createStore('leerio-position', 'position')
const bookmarkStore = createStore('leerio-bookmarks', 'bookmarks')
const noteStore = createStore('leerio-notes', 'notes')
const tagStore = createStore('leerio-tags', 'tags')
const ratingStore = createStore('leerio-ratings', 'ratings')
const quoteStore = createStore('leerio-quotes', 'quotes')
const collectionStore = createStore('leerio-collections', 'collections')
const settingsStore = createStore('leerio-settings', 'settings')
const trackMetaStore = createStore('leerio-track-meta', 'track-meta')
const booksStore = createStore('leerio-books-meta', 'books-meta')

export interface LocalBookStatus {
  status: string
  updated: string
}

export function useLocalData() {
  // ── Book Status ──────────────────────────────────────────────
  async function getBookStatus(bookId: string): Promise<LocalBookStatus | undefined> {
    return get<LocalBookStatus>(bookId, statusStore)
  }

  async function setBookStatus(bookId: string, status: string): Promise<void> {
    await set(bookId, { status, updated: new Date().toISOString() }, statusStore)
  }

  async function removeBookStatus(bookId: string): Promise<void> {
    await del(bookId, statusStore)
  }

  async function getAllBookStatuses(): Promise<Record<string, LocalBookStatus>> {
    const all = (await entries(statusStore)) as unknown as [IDBValidKey, LocalBookStatus][]
    const map: Record<string, LocalBookStatus> = {}
    for (const [k, v] of all) map[String(k)] = v
    return map
  }

  // ── Progress ─────────────────────────────────────────────────
  async function getProgress(bookId: string): Promise<number | undefined> {
    return get<number>(bookId, progressStore)
  }

  async function setProgress(bookId: string, percent: number): Promise<void> {
    await set(bookId, percent, progressStore)
  }

  async function getAllProgress(): Promise<Record<string, number>> {
    const all = (await entries(progressStore)) as unknown as [IDBValidKey, number][]
    const map: Record<string, number> = {}
    for (const [k, v] of all) map[String(k)] = v
    return map
  }

  // ── Playback Position ────────────────────────────────────────
  async function getPosition(bookId: string): Promise<PlaybackPosition | undefined> {
    return get<PlaybackPosition>(bookId, positionStore)
  }

  async function setPosition(bookId: string, pos: PlaybackPosition): Promise<void> {
    await set(bookId, pos, positionStore)
  }

  // ── Bookmarks ────────────────────────────────────────────────
  async function getBookmarks(bookId: string): Promise<Bookmark[]> {
    return (await get<Bookmark[]>(bookId, bookmarkStore)) ?? []
  }

  async function addBookmark(bookId: string, bm: Omit<Bookmark, 'id'>): Promise<Bookmark> {
    const list = await getBookmarks(bookId)
    const entry: Bookmark = { ...bm, id: Date.now() } as Bookmark
    list.push(entry)
    await set(bookId, list, bookmarkStore)
    return entry
  }

  async function removeBookmark(bookId: string, bookmarkId: number): Promise<void> {
    const list = await getBookmarks(bookId)
    await set(
      bookId,
      list.filter((b) => b.id !== bookmarkId),
      bookmarkStore,
    )
  }

  // ── Notes ────────────────────────────────────────────────────
  async function getNote(bookId: string): Promise<string | undefined> {
    return get<string>(bookId, noteStore)
  }

  async function setNote(bookId: string, text: string): Promise<void> {
    await set(bookId, text, noteStore)
  }

  async function deleteNote(bookId: string): Promise<void> {
    await del(bookId, noteStore)
  }

  // ── Tags ─────────────────────────────────────────────────────
  async function getTags(bookId: string): Promise<string[]> {
    return (await get<string[]>(bookId, tagStore)) ?? []
  }

  async function setTags(bookId: string, tags: string[]): Promise<void> {
    await set(bookId, tags, tagStore)
  }

  async function getAllTagNames(): Promise<string[]> {
    const all = (await entries(tagStore)) as unknown as [IDBValidKey, string[]][]
    const tagSet = new Set<string>()
    for (const [, tags] of all) {
      for (const t of tags) tagSet.add(t)
    }
    return [...tagSet].sort()
  }

  // ── Ratings ──────────────────────────────────────────────────
  async function getRating(bookId: string): Promise<number | undefined> {
    return get<number>(bookId, ratingStore)
  }

  async function setRating(bookId: string, rating: number): Promise<void> {
    await set(bookId, rating, ratingStore)
  }

  // ── Quotes ───────────────────────────────────────────────────
  async function getQuotes(): Promise<Quote[]> {
    const all = (await entries(quoteStore)) as unknown as [IDBValidKey, Quote][]
    return all.map(([, v]) => v)
  }

  async function addQuote(quote: Omit<Quote, 'id'>): Promise<Quote> {
    const entry = { ...quote, id: Date.now() } as Quote
    await set(String(entry.id), entry, quoteStore)
    return entry
  }

  async function deleteQuote(quoteId: number): Promise<void> {
    await del(String(quoteId), quoteStore)
  }

  // ── Collections ──────────────────────────────────────────────
  async function getCollections(): Promise<Collection[]> {
    const all = (await entries(collectionStore)) as unknown as [IDBValidKey, Collection][]
    return all.map(([, v]) => v)
  }

  async function saveCollection(col: Collection): Promise<void> {
    await set(String(col.id), col, collectionStore)
  }

  async function deleteCollection(colId: number): Promise<void> {
    await del(String(colId), collectionStore)
  }

  // ── Track Metadata (for offline playback) ─────────────────────────
  async function getTrackMeta(bookId: string): Promise<Track[] | undefined> {
    return get<Track[]>(bookId, trackMetaStore)
  }

  async function setTrackMeta(bookId: string, tracks: Track[]): Promise<void> {
    await set(bookId, tracks, trackMetaStore)
  }

  // ── Books Metadata (for offline browsing/search) ───────────────────
  async function getBooks(): Promise<Book[]> {
    return (await get<Book[]>('all_books', booksStore)) ?? []
  }

  async function setBooks(books: Book[]): Promise<void> {
    await set('all_books', books, booksStore)
  }

  // ── Settings ─────────────────────────────────────────────────
  async function getSettings(): Promise<{ yearly_goal: number; playback_speed: number } | undefined> {
    return get('user_settings', settingsStore)
  }

  async function setSettings(s: { yearly_goal?: number; playback_speed?: number }): Promise<void> {
    const current = (await getSettings()) ?? { yearly_goal: 24, playback_speed: 1 }
    await set('user_settings', { ...current, ...s }, settingsStore)
  }

  // ── Bulk import (for initial sync from server) ────────────────
  async function bulkImport<T>(data: Record<string, T>, store: ReturnType<typeof createStore>): Promise<void> {
    const entries = Object.entries(data) as [IDBValidKey, T][]
    if (entries.length) await setMany(entries, store)
  }

  const importStatuses = (data: Record<string, LocalBookStatus>) => bulkImport(data, statusStore)
  const importProgress = (data: Record<string, number>) => bulkImport(data, progressStore)
  const importBookmarks = (data: Record<string, unknown[]>) => bulkImport(data, bookmarkStore)
  const importNotes = (data: Record<string, string>) => bulkImport(data, noteStore)
  const importTags = (data: Record<string, string[]>) => bulkImport(data, tagStore)

  // ── Key counts (for UI) ──────────────────────────────────────
  async function bookmarkCount(): Promise<number> {
    return (await keys(bookmarkStore)).length
  }

  async function quoteCount(): Promise<number> {
    return (await keys(quoteStore)).length
  }

  return {
    // Status
    getBookStatus,
    setBookStatus,
    removeBookStatus,
    getAllBookStatuses,
    importStatuses,
    // Progress
    getProgress,
    setProgress,
    getAllProgress,
    importProgress,
    // Bulk imports (for sync)
    importBookmarks,
    importNotes,
    importTags,
    // Position
    getPosition,
    setPosition,
    // Bookmarks
    getBookmarks,
    addBookmark,
    removeBookmark,
    bookmarkCount,
    // Notes
    getNote,
    setNote,
    deleteNote,
    // Tags
    getTags,
    setTags,
    getAllTagNames,
    // Ratings
    getRating,
    setRating,
    // Quotes
    getQuotes,
    addQuote,
    deleteQuote,
    quoteCount,
    // Collections
    getCollections,
    saveCollection,
    deleteCollection,
    // Track metadata
    getTrackMeta,
    setTrackMeta,
    // Books metadata
    getBooks,
    setBooks,
    // Settings
    getSettings,
    setSettings,
  }
}
