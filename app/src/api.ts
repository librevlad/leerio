import { Capacitor } from '@capacitor/core'
import { useNetwork } from './composables/useNetwork'
import { useOfflineCache } from './composables/useOfflineCache'
import { useOfflineQueue } from './composables/useOfflineQueue'

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
    // Don't redirect — guest users can use app without login
    throw new Error('Not authenticated')
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  try {
    return await res.json()
  } catch {
    throw new Error(`${res.status}: Invalid JSON response`)
  }
}

async function requestFormData<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(apiUrl(path), {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })
  if (res.status === 401) {
    throw new Error('Not authenticated')
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

// Cacheable GET paths (prefix match)
const CACHEABLE = ['/books', '/dashboard', '/config/constants', '/progress', '/user/book-status', '/books/shelves']

function cacheKey(path: string): string {
  return path.replace(/[^a-zA-Z0-9_/-]/g, '_')
}

function get<T>(path: string): Promise<T> {
  const { isOnline } = useNetwork()
  const cache = useOfflineCache()
  const key = cacheKey(path)
  const isCacheable = CACHEABLE.some((p) => path.startsWith(p))

  if (!isOnline.value && isCacheable) {
    const cached = cache.get<T>(key)
    if (cached !== null) return Promise.resolve(cached)
  }

  return request<T>(path).then((data) => {
    if (isCacheable) cache.set(key, data)
    return data
  })
}

function post<T>(path: string, body?: unknown): Promise<T> {
  const { isOnline } = useNetwork()
  const queue = useOfflineQueue()

  if (!isOnline.value) {
    queue.enqueue('POST', apiUrl(path), body)
    return Promise.resolve({ ok: true } as T)
  }
  return request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
}

function put<T>(path: string, body: unknown): Promise<T> {
  const { isOnline } = useNetwork()
  const queue = useOfflineQueue()

  if (!isOnline.value) {
    queue.enqueue('PUT', apiUrl(path), body)
    return Promise.resolve({ ok: true } as T)
  }
  return request<T>(path, { method: 'PUT', body: JSON.stringify(body) })
}

function del<T>(path: string): Promise<T> {
  const { isOnline } = useNetwork()
  const queue = useOfflineQueue()

  if (!isOnline.value) {
    queue.enqueue('DELETE', apiUrl(path))
    return Promise.resolve({ ok: true } as T)
  }
  return request<T>(path, { method: 'DELETE' })
}

export function audioUrl(bookId: string, trackIndex: number): string {
  return apiUrl(`/audio/${bookId}/${trackIndex}`)
}

export function coverUrl(bookId: string): string {
  return apiUrl(`/books/${bookId}/cover`)
}

export function userBookCoverUrl(slug: string): string {
  return apiUrl(`/user/books/${slug}/cover`)
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
  Category,
  TrackList,
  PlaybackPosition,
  BookStatusMap,
  BookStatusEntry,
  User,
  UserBook,
  TTSVoice,
  TTSEngine,
  TTSJob,
  ShelfBook,
  YouTubeResolveResult,
} from './types'

export const api = {
  // Config
  getConstants: () => get<Constants>('/config/constants'),
  getCategories: () => get<Category[]>('/categories'),

  // Dashboard
  getDashboard: () => get<DashboardData>('/dashboard'),
  getRecommendations: () => get<ShelfBook[]>('/recommendations'),

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
  getNote: (bookId: string) => get<{ title: string; text: string }>(`/books/${bookId}/notes`),
  setNote: (bookId: string, text: string) => put<{ ok: boolean }>(`/books/${bookId}/notes`, { text }),
  deleteNote: (bookId: string) => del<{ ok: boolean }>(`/books/${bookId}/notes`),

  // Tags
  getTags: (bookId: string) => get<string[]>(`/books/${bookId}/tags`),
  getAllTags: () => get<string[]>('/tags/all'),
  setTags: (bookId: string, tags: string[]) => put<{ ok: boolean }>(`/books/${bookId}/tags`, { tags }),

  // Progress
  getAllProgress: () => get<Record<string, { pct: number }>>('/progress'),
  setProgress: (bookId: string, pct: number) => put<{ ok: boolean }>(`/books/${bookId}/progress`, { pct }),

  // Quotes
  getQuotes: () => get<Quote[]>('/quotes'),
  addQuote: (text: string, book: string, author = '') => post<{ ok: boolean }>('/quotes', { text, book, author }),
  deleteQuote: (quoteId: number) => del<{ ok: boolean }>(`/quotes/${quoteId}`),

  // Bulk sync endpoints
  getAllBookmarksMap: () => get<Record<string, unknown[]>>('/user/bookmarks/all'),
  getAllNotesMap: () => get<Record<string, string>>('/user/notes/all'),
  getAllTagsMap: () => get<Record<string, string[]>>('/user/tags/all'),

  // Collections
  getCollections: () => get<Collection[]>('/collections'),
  createCollection: (name: string, books: number[] = [], description = '') =>
    post<{ ok: boolean; id?: number }>('/collections', { name, books, description }),
  updateCollection: (id: number, name: string, books: number[], description: string) =>
    put<{ ok: boolean }>(`/collections/${id}`, { name, books, description }),
  deleteCollection: (id: number) => del<{ ok: boolean }>(`/collections/${id}`),

  // Sessions
  getSessionStats: (days = 7) => get<SessionStats>(`/sessions/stats?days=${days}`),
  startSession: (book: string) => post<{ book: string; start: string }>('/sessions/start', { book }),
  stopSession: (book: string) => post<{ minutes: number }>('/sessions/stop', { book }),

  // User Settings
  getUserSettings: () => get<{ yearly_goal: number; playback_speed: number }>('/user/settings'),
  updateUserSettings: (data: { yearly_goal?: number; playback_speed?: number }) =>
    put<{ yearly_goal: number; playback_speed: number }>('/user/settings', data),
  getStreak: () => get<{ current: number; best: number }>('/user/streak'),

  // Analytics
  getAnalytics: () => get<AnalyticsData>('/analytics'),
  getAchievements: () => get<Achievement[]>('/analytics/achievements'),

  // Bookmarks
  getBookmarks: (bookId: string) => get<Bookmark[]>(`/user/bookmarks/${bookId}`),
  addBookmark: (bookId: string, track: number, time: number, note = '') =>
    post<Bookmark>(`/user/bookmarks/${bookId}`, { track, time, note }),
  removeBookmark: (bookmarkId: number) => del<{ ok: boolean }>(`/user/bookmarks/${bookmarkId}`),

  // Book Status (per-user)
  getAllBookStatuses: () => get<BookStatusMap>('/user/book-status'),
  getBookStatus: (bookId: string) => get<BookStatusEntry>(`/user/book-status/${bookId}`),
  setBookStatus: (bookId: string, status: string) => put<{ ok: boolean }>(`/user/book-status/${bookId}`, { status }),
  removeBookStatus: (bookId: string) => del<{ ok: boolean }>(`/user/book-status/${bookId}`),

  // Rating
  setRating: (bookId: string, rating: number) => put<{ ok: boolean }>(`/user/rating/${bookId}`, { rating }),

  // Auth
  logout: () => post<{ ok: boolean }>('/auth/logout'),

  // Auth registration
  register: (name: string, email: string, password: string) =>
    post<{ ok: boolean }>('/auth/register', { name, email, password }),
  verifyEmail: (email: string, code: string) => post<User>('/auth/verify-email', { email, code }),
  forgotPassword: (email: string) => post<{ ok: boolean }>('/auth/forgot-password', { email }),
  resetPassword: (email: string, code: string, password: string) =>
    post<{ ok: boolean }>('/auth/reset-password', { email, code, password }),

  // User Books (personal library)
  getUserBooks: () => get<UserBook[]>('/user/books'),
  getPaymentPlan: () => get<{ price_id: string; client_token: string; free_limit: number }>('/payments/plan'),

  uploadBook: (formData: FormData) => requestFormData<UserBook>('/user/books', formData),
  getUserBook: (slug: string) => get<UserBook>(`/user/books/${slug}`),
  deleteUserBook: (slug: string) => del<{ ok: boolean }>(`/user/books/${slug}`),
  getUserBookTracks: (slug: string) => get<TrackList>(`/user/books/${slug}/tracks`),

  // TTS
  getTTSEngines: () => get<TTSEngine[]>('/tts/engines'),
  getTTSVoices: (engine?: string) => get<TTSVoice[]>(engine ? `/tts/voices?engine=${engine}` : '/tts/voices'),
  startTTSConversion: (formData: FormData) => requestFormData<TTSJob>('/tts/convert', formData),
  getTTSJobs: () => get<TTSJob[]>('/tts/jobs'),
  getTTSJob: (jobId: string) => get<TTSJob>(`/tts/jobs/${jobId}`),

  // YouTube
  youtubeResolve: (url: string) => post<YouTubeResolveResult>('/youtube/resolve', { url }),
  youtubeStreamUrl: (videoId: string): string => apiUrl(`/youtube/stream/${videoId}`),

  // Cloud sync (local → server)
  cloudSyncBook: (formData: FormData) => {
    return fetch(apiUrl('/user/books/cloud-sync'), {
      method: 'POST',
      credentials: 'include',
      body: formData,
    }).then((r) => {
      if (!r.ok) throw new Error(`Upload failed: ${r.status}`)
      return r.json()
    })
  },
}
