import { ref, computed } from 'vue'
import { api } from '../api'
import type { Book } from '../types'

const books = ref<Book[]>([])
const loading = ref(false)

export function useBooks() {
  async function load(params?: Record<string, string>) {
    loading.value = true
    try {
      books.value = await api.getBooks(params)
    } catch {
      books.value = []
    } finally {
      loading.value = false
    }
  }

  const categories = computed(() => {
    const set = new Set(books.value.map((b) => b.category))
    return Array.from(set).sort()
  })

  return { books, loading, load, categories }
}
