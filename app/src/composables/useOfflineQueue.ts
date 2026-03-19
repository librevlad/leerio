import { useNetwork } from './useNetwork'

interface QueuedRequest {
  method: string
  url: string
  body?: string
}

const STORAGE_KEY = 'leerio_offline_queue'

function loadQueue(): QueuedRequest[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

function saveQueue(queue: QueuedRequest[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(queue))
}

let replayRegistered = false

export function useOfflineQueue() {
  function enqueue(method: string, url: string, body?: unknown) {
    const queue = loadQueue()
    queue.push({ method, url, body: body ? JSON.stringify(body) : undefined })
    saveQueue(queue)
  }

  async function replay() {
    const queue = loadQueue()
    if (!queue.length) return
    saveQueue([]) // clear before replay to avoid duplicates

    const failed: QueuedRequest[] = []
    for (const req of queue) {
      try {
        const res = await fetch(req.url, {
          method: req.method,
          headers: req.body ? { 'Content-Type': 'application/json' } : undefined,
          credentials: 'include',
          body: req.body,
        })
        if (!res.ok && res.status !== 409) failed.push(req)
      } catch {
        failed.push(req)
      }
    }
    if (failed.length) saveQueue(failed)
  }

  if (!replayRegistered) {
    replayRegistered = true
    const { onReconnect } = useNetwork()
    onReconnect(() => replay())
  }

  return { enqueue, replay }
}
