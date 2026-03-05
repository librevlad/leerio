// ── User types ──────────────────────────────────────────────────────────────

export interface User {
  user_id: string
  email: string
  name: string
  picture: string
  role: 'admin' | 'user'
}

export type BookStatusValue = 'want_to_read' | 'reading' | 'paused' | 'done' | 'rejected'

export interface BookStatusEntry {
  status: BookStatusValue | null
  updated?: string
}

export type BookStatusMap = Record<string, BookStatusEntry>

// ── Book types ──────────────────────────────────────────────────────────────

export interface Book {
  id: string
  folder: string
  category: string
  author: string
  title: string
  reader: string
  path: string
  progress: number
  tags: string[]
  note: string
  has_cover?: boolean
  rating?: number
  book_status?: BookStatusValue
  // Detail fields
  size_mb?: number
  mp3_count?: number
  duration_hours?: number | null
  duration_fmt?: string
  timeline?: HistoryEntry[]
  // Personal book fields
  is_personal?: boolean
  source?: 'upload' | 'tts'
  slug?: string
  created_at?: string
}

export interface SimilarBook extends Book {
  score: number
}

// ── History types ───────────────────────────────────────────────────────────

export interface HistoryEntry {
  ts: string
  action: string
  book: string
  detail: string
  rating: number
  action_label: string
  action_style?: string
}

// ── Dashboard types ─────────────────────────────────────────────────────────

export interface ActiveBook {
  id: string
  title: string
  author: string
  list: string
  progress: number
}

export interface NowPlaying {
  book_id: string
  title: string
  author: string
  cover_id: string
  progress: number
  current_track: number
  current_time: number
}

export interface DashboardData {
  total_books: number
  total_done: number
  active_count: number
  active_books: ActiveBook[]
  now_playing: NowPlaying | null
  recent: HistoryEntry[]
  heatmap: Record<string, number>
  quote: Quote | null
  this_year_done: number
  yearly_goal: number
  category_counts: Record<string, number>
}

export interface Velocity {
  total: number
  span_days?: number
  avg_per_month?: number
  best_month?: string
  best_month_count?: number
  this_year?: number
  recent_90d?: number
  recent_pace?: number
}

// ── Analytics types ─────────────────────────────────────────────────────────

export interface AnalyticsData {
  total_books: number
  total_done: number
  category_counts: Record<string, number>
  done_by_category: Record<string, number>
  monthly_trend: [string, number][]
  rating_distribution: Record<string, number>
  velocity: Velocity
  heatmap: Record<string, number>
  top_authors: { author: string; count: number }[]
}

export interface Achievement {
  icon: string
  name: string
  desc: string
}

// ── Audio / Playback types ──────────────────────────────────────────────────

export interface Track {
  index: number
  filename: string
  path: string
  duration: number
  size_bytes?: number
  url?: string // Direct MP3 URL for external sources (e.g. archive.org)
}

export interface TrackList {
  book_id: string
  count: number
  tracks: Track[]
}

export interface PlaybackPosition {
  track_index: number
  position: number
  filename?: string
  updated?: string | null
}

// ── Bookmark types ─────────────────────────────────────────────────────────

export interface Bookmark {
  track: number
  time: number
  note: string
  ts: string
}

// ── Other types ─────────────────────────────────────────────────────────────

export interface Quote {
  text: string
  book: string
  author: string
  ts: string
}

export interface Collection {
  name: string
  books: string[]
  description: string
  created: string
}

export interface SessionStats {
  total_hours: number
  today_min: number
  week_hours: number
  peak_hour: number | null
}

export interface Constants {
  categories: string[]
  status_style: Record<string, string>
  action_styles: Record<string, string>
  action_labels: Record<string, string>
  list_to_status: Record<string, string>
  label_to_folder: Record<string, string>
  folder_to_label: Record<string, string>
}

// ── LibriVox types ─────────────────────────────────────────────────────────

export interface LibriVoxBook {
  id: string // "lv:12345"
  librivox_id: string
  source: 'librivox'
  title: string
  author: string
  description: string
  language: string
  copyright_year: string
  num_sections: number
  total_time: string
  total_time_secs: number
  url_librivox: string
}

export interface LibriVoxSearchResult {
  books: LibriVoxBook[]
  total: number
}

// ── User Books & TTS types ────────────────────────────────────────────────

export interface UserBook {
  id: string
  slug: string
  title: string
  author: string
  reader: string
  source: 'upload' | 'tts'
  created_at: string
  is_personal: true
  has_cover: boolean
  mp3_count: number
  size_mb?: number
  duration_hours?: number | null
}

export interface TTSVoice {
  id: string
  name: string
  lang: string
  gender: 'male' | 'female'
}

// ── Local Book types (device-only) ──────────────────────────────────────

export interface LocalTrack {
  index: number
  filename: string
  path: string // objectURL or filesystem path
  duration: number
}

export interface LocalBook {
  id: string // "lb:{uuid}"
  title: string
  author: string
  tracks: LocalTrack[]
  coverDataUrl?: string // base64
  addedAt: string
}

export interface TTSJob {
  id: string
  title: string
  author: string
  voice: string
  slug: string
  status: 'processing' | 'done' | 'error'
  progress: number
  total_chapters: number
  done_chapters: number
  error: string | null
  created_at: string
}
