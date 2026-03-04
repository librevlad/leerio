import { ref } from 'vue'
import { api } from '../api'
import type { LibriVoxBook } from '../types'

const books = ref<LibriVoxBook[]>([])
const loading = ref(false)
const hasMore = ref(false)

let currentOffset = 0
const PAGE_SIZE = 20

function mapBook(raw: Record<string, unknown>): LibriVoxBook {
  const lvId = String(raw.librivox_id ?? '')
  return {
    id: `lv:${lvId}`,
    librivox_id: lvId,
    source: 'librivox',
    title: String(raw.title ?? ''),
    author: String(raw.author ?? ''),
    description: String(raw.description ?? ''),
    language: String(raw.language ?? ''),
    copyright_year: String(raw.copyright_year ?? ''),
    num_sections: Number(raw.num_sections ?? 0),
    total_time: String(raw.total_time ?? ''),
    total_time_secs: Number(raw.total_time_secs ?? 0),
    url_librivox: String(raw.url_librivox ?? ''),
  }
}

async function search(title: string, language: string, reset = true) {
  if (reset) {
    currentOffset = 0
    books.value = []
  }
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (title) params.title = title
    if (language) params.language = language
    params.limit = String(PAGE_SIZE)
    params.offset = String(currentOffset)

    const res = await api.librivoxSearch(params)
    const mapped = (res.books as unknown as Record<string, unknown>[]).map(mapBook)
    if (reset) {
      books.value = mapped
    } else {
      books.value = [...books.value, ...mapped]
    }
    hasMore.value = mapped.length >= PAGE_SIZE
    currentOffset += mapped.length
  } catch {
    hasMore.value = false
  } finally {
    loading.value = false
  }
}

async function loadMore(title: string, language: string) {
  await search(title, language, false)
}

export function useLibriVox() {
  return { books, loading, hasMore, search, loadMore }
}
