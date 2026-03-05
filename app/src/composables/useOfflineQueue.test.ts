import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('./useNetwork', () => ({
  useNetwork: () => ({
    isOnline: { value: true },
    onReconnect: vi.fn(),
  }),
}))

import { useOfflineQueue } from './useOfflineQueue'

describe('useOfflineQueue', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('enqueue() persists to localStorage', () => {
    const q = useOfflineQueue()
    q.enqueue('POST', '/api/test', { data: 1 })

    const stored = JSON.parse(localStorage.getItem('leerio_offline_queue') || '[]')
    expect(stored).toHaveLength(1)
    expect(stored[0].method).toBe('POST')
    expect(stored[0].url).toBe('/api/test')
    expect(stored[0].body).toBe('{"data":1}')
  })

  it('enqueue() accumulates multiple items', () => {
    const q = useOfflineQueue()
    q.enqueue('POST', '/api/a')
    q.enqueue('PUT', '/api/b', { x: 2 })

    const stored = JSON.parse(localStorage.getItem('leerio_offline_queue') || '[]')
    expect(stored).toHaveLength(2)
  })

  it('replay() calls fetch for each queued item', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response())
    const q = useOfflineQueue()
    q.enqueue('POST', '/api/a', { x: 1 })
    q.enqueue('PUT', '/api/b')

    await q.replay()
    expect(fetchSpy).toHaveBeenCalledTimes(2)
    expect(fetchSpy).toHaveBeenCalledWith('/api/a', expect.objectContaining({ method: 'POST' }))
    expect(fetchSpy).toHaveBeenCalledWith('/api/b', expect.objectContaining({ method: 'PUT' }))
  })

  it('replay() re-queues failed items', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response()).mockRejectedValueOnce(new Error('network'))

    const q = useOfflineQueue()
    q.enqueue('POST', '/api/ok')
    q.enqueue('POST', '/api/fail')

    await q.replay()
    const remaining = JSON.parse(localStorage.getItem('leerio_offline_queue') || '[]')
    expect(remaining).toHaveLength(1)
    expect(remaining[0].url).toBe('/api/fail')
  })

  it('replay() clears queue on full success', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response())
    const q = useOfflineQueue()
    q.enqueue('POST', '/api/a')

    await q.replay()
    const remaining = JSON.parse(localStorage.getItem('leerio_offline_queue') || '[]')
    expect(remaining).toHaveLength(0)
  })

  it('replay() is a no-op on empty queue', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const q = useOfflineQueue()
    await q.replay()
    expect(fetchSpy).not.toHaveBeenCalled()
  })
})
