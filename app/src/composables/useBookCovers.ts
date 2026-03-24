/**
 * Fetches book covers from Open Library API by title.
 *
 * - Searches Open Library: /search.json?title={title}&limit=1
 * - Builds cover URL from cover_i field
 * - Caches results in localStorage (key: leerio_cover_cache)
 * - Rate-limited: 500ms delay between requests
 * - Never blocks UI — all fetches are background
 */
import { STORAGE } from '../constants/storage'

type CoverCache = Record<string, string | null>

let cache: CoverCache | null = null

function loadCache(): CoverCache {
  if (cache) return cache
  try {
    cache = JSON.parse(localStorage.getItem(STORAGE.COVER_CACHE) || '{}')
    return cache!
  } catch {
    cache = {}
    return cache
  }
}

function saveCache() {
  if (cache) {
    localStorage.setItem(STORAGE.COVER_CACHE, JSON.stringify(cache))
  }
}

const SEARCH_URL = 'https://openlibrary.org/search.json'
const COVER_URL = 'https://covers.openlibrary.org/b/id'

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

/** Look up a single book title. Returns cover URL or null. */
export async function fetchCover(title: string): Promise<string | null> {
  const c = loadCache()

  // Already cached (hit or miss)
  if (title in c) return c[title] ?? null

  try {
    const params = new URLSearchParams({
      title,
      limit: '1',
      fields: 'cover_i,title,author_name',
    })

    const res = await fetch(`${SEARCH_URL}?${params}`)
    if (!res.ok) return null

    const data = await res.json()
    const coverId = data?.docs?.[0]?.cover_i

    if (coverId) {
      const url = `${COVER_URL}/${coverId}-M.jpg`
      c[title] = url
      saveCache()
      return url
    }

    // No cover found — cache the miss
    c[title] = null
    saveCache()
    return null
  } catch {
    // Network error — don't cache, allow retry later
    return null
  }
}

/**
 * Fetch covers for multiple books in background.
 * Returns a map of title -> coverUrl for books that got covers.
 * Rate-limited with 500ms delay between requests.
 */
export async function fetchCoversForBooks(
  titles: string[],
): Promise<Record<string, string>> {
  const results: Record<string, string> = {}
  const c = loadCache()

  for (let i = 0; i < titles.length; i++) {
    const title = titles[i]!
    // Skip if already cached
    if (title in c) {
      if (c[title]) results[title] = c[title]!
      continue
    }

    // Rate limit between actual API calls
    if (i > 0) await delay(500)

    const url = await fetchCover(title)
    if (url) results[title] = url
  }

  return results
}

/** Read cached cover URL for a title (sync, no fetch). */
export function getCachedCover(title: string): string | null {
  const c = loadCache()
  return c[title] ?? null
}

/** Clear the in-memory cache (for testing). */
export function _resetCache() {
  cache = null
}
