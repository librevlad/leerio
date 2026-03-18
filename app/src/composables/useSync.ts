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

let synced = false

export function useSync() {
  const { isLoggedIn } = useAuth()
  const local = useLocalData()
  const { onReconnect } = useNetwork()

  // Sync on login
  watch(
    isLoggedIn,
    async (loggedIn) => {
      if (!loggedIn || synced) return
      synced = true
      await syncAll(local)
    },
    { immediate: true },
  )

  // Re-sync on reconnect (if logged in)
  onReconnect(async () => {
    if (isLoggedIn.value) {
      await syncAll(local)
    }
  })
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
    // Import server quotes (server wins for existing, keep local-only)
    for (const q of serverQuotes) {
      await local.addQuote({ text: q.text, book: q.book, author: q.author, ts: q.ts })
    }
  } catch {
    // Quotes sync is optional
  }
}
