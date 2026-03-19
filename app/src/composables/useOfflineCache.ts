import { STORAGE } from '../constants/storage'

const DEFAULT_TTL = 24 * 60 * 60 * 1000 // 24 hours

interface CacheEntry<T> {
  data: T
  ts: number
  ttl: number
}

export function useOfflineCache() {
  function get<T>(key: string): T | null {
    try {
      const raw = localStorage.getItem(`${STORAGE.CACHE_PREFIX}${key}`)
      if (!raw) return null
      const entry: CacheEntry<T> = JSON.parse(raw)
      if (Date.now() - entry.ts > entry.ttl) {
        localStorage.removeItem(`${STORAGE.CACHE_PREFIX}${key}`)
        return null
      }
      return entry.data
    } catch {
      return null
    }
  }

  function set<T>(key: string, data: T, ttl = DEFAULT_TTL) {
    try {
      const entry: CacheEntry<T> = { data, ts: Date.now(), ttl }
      localStorage.setItem(`${STORAGE.CACHE_PREFIX}${key}`, JSON.stringify(entry))
    } catch {
      // localStorage full — ignore
    }
  }

  function remove(key: string) {
    localStorage.removeItem(`${STORAGE.CACHE_PREFIX}${key}`)
  }

  function clear() {
    const keys = Object.keys(localStorage).filter((k) => k.startsWith(STORAGE.CACHE_PREFIX))
    keys.forEach((k) => localStorage.removeItem(k))
  }

  function cacheSize(): number {
    let total = 0
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(STORAGE.CACHE_PREFIX)) {
        total += (localStorage.getItem(key) ?? '').length * 2 // rough byte estimate
      }
    }
    return total
  }

  return { get, set, remove, clear, cacheSize }
}
