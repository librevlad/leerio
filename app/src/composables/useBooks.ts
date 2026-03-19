import { ref, computed } from 'vue'
import { api } from '../api'
import type { Book } from '../types'

const books = ref<Book[]>([])
const loading = ref(false)
let inflight: Promise<void> | null = null

export function useBooks() {
  async function load(params?: Record<string, string>) {
    if (inflight) return inflight
    loading.value = true
    inflight = api
      .getBooks(params)
      .then((b) => {
        books.value = b
      })
      .catch(() => {
        books.value = []
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
