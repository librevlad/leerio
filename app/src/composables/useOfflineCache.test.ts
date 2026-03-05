import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useOfflineCache } from './useOfflineCache'

describe('useOfflineCache', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    localStorage.clear()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('set + get round-trips JSON data', () => {
    const cache = useOfflineCache()
    cache.set('test', { name: 'Alice', score: 42 })
    expect(cache.get('test')).toEqual({ name: 'Alice', score: 42 })
  })

  it('returns null for missing key', () => {
    const cache = useOfflineCache()
    expect(cache.get('nonexistent')).toBeNull()
  })

  it('expires after TTL', () => {
    const cache = useOfflineCache()
    cache.set('ttl-test', 'value', 5000)
    expect(cache.get('ttl-test')).toBe('value')

    vi.advanceTimersByTime(6000)
    expect(cache.get('ttl-test')).toBeNull()
  })

  it('remove() deletes a specific key', () => {
    const cache = useOfflineCache()
    cache.set('a', 1)
    cache.set('b', 2)
    cache.remove('a')
    expect(cache.get('a')).toBeNull()
    expect(cache.get('b')).toBe(2)
  })

  it('clear() removes all prefixed keys', () => {
    const cache = useOfflineCache()
    cache.set('x', 1)
    cache.set('y', 2)
    localStorage.setItem('other_key', 'keep')
    cache.clear()
    expect(cache.get('x')).toBeNull()
    expect(cache.get('y')).toBeNull()
    expect(localStorage.getItem('other_key')).toBe('keep')
  })

  it('cacheSize() returns byte estimate', () => {
    const cache = useOfflineCache()
    cache.set('size-test', 'hello')
    const size = cache.cacheSize()
    expect(size).toBeGreaterThan(0)
  })

  it('returns null for corrupted JSON in storage', () => {
    localStorage.setItem('leerio_cache_broken', '{invalid json')
    const cache = useOfflineCache()
    expect(cache.get('broken')).toBeNull()
  })
})
