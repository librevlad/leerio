import { ref, computed } from 'vue'
import { api } from '../api'
import type { Book } from '../types'
import { useLocalData } from './useLocalData'

const books = ref<Book[]>([])
const loading = ref(false)
let inflight: Promise<void> | null = null
const localData = useLocalData()

export function useBooks() {
  async function load(params?: Record<string, string>) {
    if (inflight) return inflight
    loading.value = true
    inflight = api
      .getBooks(params)
      .then((b) => {
        books.value = b
        // Cache full list for offline browsing
        if (!params) localData.setBooks(b).catch(() => {})
      })
      .catch(async () => {
        // Preserve existing books on network error — don't wipe the library
        if (!books.value.length) {
          try {
            const cached = await localData.getBooks()
            if (cached.length) {
              books.value = cached
            }
          } catch {
            /* IndexedDB failed too */
          }
        }
      })
      .finally(() => {
        loading.value = false
        inflight = null
      })
    return inflight
  }

  const categories = computed(() => {
    const set = new Set(books.value.map((b) => b.category))
    return Array.from(set).sort((a, b) => {
      if (a === 'Другое') return 1
      if (b === 'Другое') return -1
      return a.localeCompare(b)
    })
  })

  return { books, loading, load, categories }
}
