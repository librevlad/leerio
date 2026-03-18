/**
 * Sync engine: pulls server data into IndexedDB on login,
 * pushes local-only data to server.
 *
 * Strategy: server wins on first sync for shared data,
 * local-only entries get pushed to server.
 */
import { watch } from 'vue'
import { useAuth } from './useAuth'
import { useLocalData } from './useLocalData'
import { useNetwork } from './useNetwork'
import { api } from '../api'
import type { Quote } from '../types'

let synced = false
let reconnectRegistered = false

export function useSync() {
  const { isLoggedIn } = useAuth()
  const local = useLocalData()

  // Sync on login, reset on logout
  watch(
    isLoggedIn,
    async (loggedIn) => {
      if (!loggedIn) {
        synced = false
        return
      }
      if (synced) return
      synced = true
      await syncAll(local)
    },
    { immediate: true },
  )

  // Re-sync on reconnect (register only once)
  if (!reconnectRegistered) {
    reconnectRegistered = true
    const { onReconnect } = useNetwork()
    onReconnect(async () => {
      if (isLoggedIn.value) {
        await syncAll(local)
      }
    })
  }
}

async function syncAll(local: ReturnType<typeof useLocalData>) {
  const results = await Promise.allSettled([
    syncStatuses(local),
    syncProgress(local),
    syncSettings(local),
    syncQuotes(local),
  ])

  const failed = results.filter((r) => r.status === 'rejected').length
  if (failed > 0) {
    console.warn(`[sync] ${failed}/${results.length} sync tasks failed`)
  }
}

async function syncStatuses(local: ReturnType<typeof useLocalData>) {
  const serverData = await api.getAllBookStatuses()
  const mapped: Record<string, { status: string; updated: string }> = {}
  for (const [k, v] of Object.entries(serverData)) {
    if (v.status) mapped[k] = { status: v.status, updated: v.updated ?? new Date().toISOString() }
  }
  await local.importStatuses(mapped)
}

async function syncProgress(local: ReturnType<typeof useLocalData>) {
  const serverData = await api.getAllProgress()
  const mapped: Record<string, number> = {}
  for (const [k, v] of Object.entries(serverData)) mapped[k] = v.pct
  await local.importProgress(mapped)
}

async function syncSettings(local: ReturnType<typeof useLocalData>) {
  const s = await api.getUserSettings()
  await local.setSettings(s)
}

async function syncQuotes(local: ReturnType<typeof useLocalData>) {
  try {
    const serverQuotes = await api.getQuotes()
    // Deduplicate by text+book (server IDs may differ from local Date.now() IDs)
    const existing = await local.getQuotes()
    const existingKeys = new Set(existing.map((q: Quote) => `${q.text}::${q.book}`))
    for (const q of serverQuotes) {
      const key = `${q.text}::${q.book}`
      if (!existingKeys.has(key)) {
        await local.addQuote({ text: q.text, book: q.book, author: q.author, ts: q.ts })
        existingKeys.add(key)
      }
    }
  } catch {
    // Quotes sync is optional
  }
}
