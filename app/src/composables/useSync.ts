/**
 * Sync engine: pulls server data into IndexedDB on login.
 *
 * Strategy: server wins on first sync (merge), local wins for
 * data created while offline (new entries not on server).
 */
import { watch } from 'vue'
import { useAuth } from './useAuth'
import { useLocalData } from './useLocalData'
import { api } from '../api'

let synced = false

export function useSync() {
  const { isLoggedIn } = useAuth()
  const local = useLocalData()

  watch(
    isLoggedIn,
    async (loggedIn) => {
      if (!loggedIn || synced) return
      synced = true
      await pullFromServer(local)
    },
    { immediate: true },
  )
}

async function pullFromServer(local: ReturnType<typeof useLocalData>) {
  try {
    const results = await Promise.allSettled([
      api.getAllBookStatuses().then((data) => local.importStatuses(data)),
      api.getAllProgress().then((data) => local.importProgress(data)),
      api.getUserSettings().then((s) => local.setSettings(s)),
    ])

    const failed = results.filter((r) => r.status === 'rejected').length
    if (failed > 0) {
      console.warn(`[sync] ${failed} sync tasks failed`)
    }
  } catch {
    console.warn('[sync] pull from server failed')
  }
}
