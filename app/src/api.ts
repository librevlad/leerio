import { Capacitor } from '@capacitor/core'
import router from './router'

const API_BASE = Capacitor.isNativePlatform() ? 'https://app.leerio.app/api' : '/api'

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(apiUrl(path), {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...options,
  })
  if (res.status === 401) {
    router.push('/login')
    throw new Error('Not authenticated')
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

function get<T>(path: string): Promise<T> {
  return request<T>(path)
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
}

function put<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'PUT', body: JSON.stringify(body) })
}

function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' })
}

export function audioUrl(bookId: string, trackIndex: number): string {
  return apiUrl(`/audio/${bookId}/${trackIndex}`)
}

export function coverUrl(bookId: string): string {
  return apiUrl(`/books/${bookId}/cover`)
}

import type {
  DashboardData,
  Book,
  SimilarBook,
  Bookmark,
  HistoryEntry,
  AnalyticsData,
  Achievement,
  Quote,
  Collection,
  SessionStats,
  Constants,
  TrackList,
  PlaybackPosition,
  BookStatusMap,
  BookStatusEntry,
} from './types'

export const api = {
  // Config
  getConstants: () => get<Constants>('/config/constants'),

  // Dashboard
  getDashboard: () => get<DashboardData>('/dashboard'),

  // Books
  getBooks: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return get<Book[]>(`/books${qs}`)
  },
  getBook: (id: string) => get<Book>(`/books/${id}`),
  getSimilar: (id: string) => get<SimilarBook[]>(`/books/${id}/similar`),

  // Audio / Playback
  getBookTracks: (bookId: string) => get<TrackList>(`/books/${bookId}/tracks`),
  getPlaybackPosition: (bookId: string) => get<PlaybackPosition>(`/books/${bookId}/playback`),
  setPlaybackPosition: (bookId: string, trackIndex: number, position: number, filename = '') =>
    put<{ ok: boolean }>(`/books/${bookId}/playback`, { track_index: trackIndex, position, filename }),

  // History
  getHistory: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return get<HistoryEntry[]>(`/history${qs}`)
  },

  // Notes
  getNote: (title: string) => get<{ title: string; text: string }>(`/notes/${encodeURIComponent(title)}`),
  setNote: (title: string, text: string) => put<{ ok: boolean }>(`/notes/${encodeURIComponent(title)}`, { text }),
  deleteNote: (title: string) => del<{ ok: boolean }>(`/notes/${encodeURIComponent(title)}`),

  // Tags
  getTags: (title: string) => get<string[]>(`/tags?title=${encodeURIComponent(title)}`),
  getAllTags: () => get<string[]>('/tags/all'),
  setTags: (title: string, tags: string[]) => put<{ ok: boolean }>(`/tags/${encodeURIComponent(title)}`, { tags }),

  // Progress
  getAllProgress: () => get<Record<string, { pct: number }>>('/progress'),
  setProgress: (title: string, pct: number) => put<{ ok: boolean }>(`/progress/${encodeURIComponent(title)}`, { pct }),

  // Quotes
  getQuotes: () => get<Quote[]>('/quotes'),
  addQuote: (text: string, book: string, author = '') => post<{ ok: boolean }>('/quotes', { text, book, author }),
  deleteQuote: (idx: number) => del<{ ok: boolean }>(`/quotes/${idx}`),

  // Collections
  getCollections: () => get<Collection[]>('/collections'),
  createCollection: (name: string, books: string[] = [], description = '') =>
    post<{ ok: boolean }>('/collections', { name, books, description }),
  updateCollection: (idx: number, name: string, books: string[], description: string) =>
    put<{ ok: boolean }>(`/collections/${idx}`, { name, books, description }),
  deleteCollection: (idx: number) => del<{ ok: boolean }>(`/collections/${idx}`),

  // Sessions
  getSessionStats: (days = 7) => get<SessionStats>(`/sessions/stats?days=${days}`),
  startSession: (book: string) => post<{ book: string; start: string }>('/sessions/start', { book }),
  stopSession: (book: string) => post<{ minutes: number }>('/sessions/stop', { book }),

  // Analytics
  getAnalytics: () => get<AnalyticsData>('/analytics'),
  getAchievements: () => get<Achievement[]>('/analytics/achievements'),

  // Bookmarks
  getBookmarks: (bookId: string) => get<Bookmark[]>(`/user/bookmarks/${bookId}`),
  addBookmark: (bookId: string, track: number, time: number, note = '') =>
    post<Bookmark>(`/user/bookmarks/${bookId}`, { track, time, note }),
  removeBookmark: (bookId: string, ts: string) => del<{ ok: boolean }>(`/user/bookmarks/${bookId}/${ts}`),

  // Book Status (per-user)
  getAllBookStatuses: () => get<BookStatusMap>('/user/book-status'),
  getBookStatus: (bookId: string) => get<BookStatusEntry>(`/user/book-status/${bookId}`),
  setBookStatus: (bookId: string, status: string) => put<{ ok: boolean }>(`/user/book-status/${bookId}`, { status }),
  removeBookStatus: (bookId: string) => del<{ ok: boolean }>(`/user/book-status/${bookId}`),

  // Auth
  getMe: () => get<{ user_id: string; email: string; name: string; picture: string; role: string }>('/auth/me'),
  logout: () => post<{ ok: boolean }>('/auth/logout'),
}
