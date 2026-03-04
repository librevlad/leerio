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
  status?: string
  card_id?: string
  // Detail fields
  size_mb?: number
  mp3_count?: number
  duration_hours?: number | null
  duration_fmt?: string
  timeline?: HistoryEntry[]
}

export interface SimilarBook extends Book {
  score: number
}

// ── Trello types ────────────────────────────────────────────────────────────

export interface TrelloCard {
  id: string
  name: string
  list: string
  status: string
  author: string
  title: string
  reader: string
  category: string
  labels: string[]
  desc: string
  progress: number
}

export interface TrelloList {
  id: string
  name: string
}

export interface TrelloStatus {
  total_cards: number
  list_counts: Record<string, number>
  cache_ts: string | null
  cache_age_min: number | null
}

export interface SyncResult {
  ok: boolean
  cards: number
  list_counts: Record<string, number>
  synced_at: string
}

export interface CreateCardResult {
  ok: boolean
  card_id: string
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

export interface DashboardData {
  total_books: number
  total_done: number
  active_count: number
  velocity: Velocity
  active_books: TrelloCard[]
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
  trello_connected: boolean
}
