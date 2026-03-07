<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { api, coverUrl } from '../../api'
import type { Book } from '../../types'
import { IconSearch, IconMusic } from '../shared/icons'

const { t } = useI18n()
const router = useRouter()
const query = ref('')
const results = ref<Book[]>([])
const open = ref(false)
const loading = ref(false)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(query, (q) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  if (!q.trim()) {
    results.value = []
    open.value = false
    return
  }
  debounceTimer = setTimeout(async () => {
    loading.value = true
    try {
      const all = await api.getBooks({ search: q.trim() })
      results.value = all.slice(0, 8)
      open.value = results.value.length > 0
    } catch {
      results.value = []
    } finally {
      loading.value = false
    }
  }, 300)
})

const authors = computed(() => {
  const map = new Map<string, number>()
  for (const b of results.value) {
    if (b.author) map.set(b.author, (map.get(b.author) || 0) + 1)
  }
  return Array.from(map.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([name]) => name)
})

function goToBook(id: string) {
  query.value = ''
  open.value = false
  router.push(`/book/${id}`)
}

function searchAuthor(author: string) {
  query.value = ''
  open.value = false
  router.push(`/library?q=${encodeURIComponent(author)}`)
}

function goToCatalog() {
  const q = query.value.trim()
  query.value = ''
  open.value = false
  router.push(`/library?q=${encodeURIComponent(q)}`)
}

function onBlur() {
  setTimeout(() => {
    open.value = false
  }, 200)
}
</script>

<template>
  <div class="relative w-full max-w-md">
    <div class="relative">
      <IconSearch :size="16" class="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-[--t3]" />
      <input
        v-model="query"
        type="text"
        class="input-field w-full py-2.5 pr-4 pl-10 text-[13px]"
        :placeholder="t('global.search')"
        @focus="query.trim() && results.length && (open = true)"
        @blur="onBlur"
        @keyup.enter="goToCatalog"
      />
    </div>

    <!-- Dropdown results -->
    <div
      v-if="open"
      class="absolute top-full right-0 left-0 z-50 mt-2 overflow-hidden rounded-2xl border border-[--border] shadow-lg"
      style="background: var(--card-solid)"
    >
      <!-- Authors -->
      <div v-if="authors.length" class="border-b border-[--border] px-3 py-2">
        <p class="mb-1.5 text-[10px] font-bold tracking-wider text-[--t3] uppercase">{{ t('global.authors') }}</p>
        <button
          v-for="a in authors"
          :key="a"
          class="block w-full cursor-pointer truncate border-0 bg-transparent px-2 py-1.5 text-left text-[13px] text-[--t2] transition-colors hover:text-[--accent]"
          @mousedown.prevent="searchAuthor(a)"
        >
          {{ a }}
        </button>
      </div>

      <!-- Books -->
      <div class="max-h-80 overflow-y-auto py-1">
        <button
          v-for="book in results.slice(0, 5)"
          :key="book.id"
          class="flex w-full cursor-pointer items-center gap-3 border-0 bg-transparent px-3 py-2 text-left transition-colors hover:bg-[--card-hover]"
          @mousedown.prevent="goToBook(book.id)"
        >
          <div class="h-10 w-10 shrink-0 overflow-hidden rounded-lg">
            <img v-if="book.has_cover" :src="coverUrl(book.id)" :alt="book.title" class="h-full w-full object-cover" />
            <div v-else class="flex h-full w-full items-center justify-center bg-[--card-hover]">
              <IconMusic :size="14" class="text-[--t3]" />
            </div>
          </div>
          <div class="min-w-0 flex-1">
            <p class="truncate text-[13px] font-medium text-[--t1]">{{ book.title }}</p>
            <p class="truncate text-[11px] text-[--t3]">{{ book.author }}</p>
          </div>
        </button>
      </div>

      <!-- View all -->
      <button
        class="flex w-full cursor-pointer items-center justify-center border-t border-[--border] bg-transparent py-2.5 text-[12px] font-medium text-[--accent] transition-colors hover:bg-[--card-hover]"
        @mousedown.prevent="goToCatalog"
      >
        Все результаты
      </button>
    </div>
  </div>
</template>
