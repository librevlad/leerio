import router from './router'

const STORAGE_KEY = 'leerio_server_url'

export function getServerUrl(): string {
  return localStorage.getItem(STORAGE_KEY) || ''
}

export function setServerUrl(url: string) {
  const clean = url.replace(/\/+$/, '')
  if (clean) {
    localStorage.setItem(STORAGE_KEY, clean)
  } else {
    localStorage.removeItem(STORAGE_KEY)
  }
}

function getBaseUrl(): string {
  const server = getServerUrl()
  return server ? `${server}/api` : '/api'
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const base = getBaseUrl()
  const res = await fetch(`${base}${path}`, {
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
  const base = getBaseUrl()
  return `${base}/audio/${bookId}/${trackIndex}`
}

export function coverUrl(bookId: string): string {
  const base = getBaseUrl()
  return `${base}/books/${bookId}/cover`
}

import type {
  DashboardData,
  Book,
  SimilarBook,
  TrelloCard,
  TrelloList,
  TrelloStatus,
  SyncResult,
  CreateCardResult,
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

  // Trello (admin only)
  getTrelloStatus: () => get<TrelloStatus>('/trello/status'),
  getTrelloCards: (listName?: string) => {
    const qs = listName ? `?list_name=${encodeURIComponent(listName)}` : ''
    return get<TrelloCard[]>(`/trello/cards${qs}`)
  },
  getTrelloLists: () => get<TrelloList[]>('/trello/lists'),
  moveCard: (cardId: string, target: string, rating = 0, detail = '') =>
    post<{ ok: boolean }>(`/trello/cards/${cardId}/move`, { target, rating, detail }),
  createTrelloCard: (name: string, listName: string, label?: string, desc?: string) =>
    post<CreateCardResult>('/trello/cards', { name, list_name: listName, label, desc }),
  syncTrello: () => post<SyncResult>('/trello/sync'),

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

  // Book Status (per-user)
  getAllBookStatuses: () => get<BookStatusMap>('/user/book-status'),
  getBookStatus: (bookId: string) => get<BookStatusEntry>(`/user/book-status/${bookId}`),
  setBookStatus: (bookId: string, status: string) => put<{ ok: boolean }>(`/user/book-status/${bookId}`, { status }),
  removeBookStatus: (bookId: string) => del<{ ok: boolean }>(`/user/book-status/${bookId}`),

  // Auth
  getMe: () => get<{ user_id: string; email: string; name: string; picture: string; role: string }>('/auth/me'),
  logout: () => post<{ ok: boolean }>('/auth/logout'),
}
