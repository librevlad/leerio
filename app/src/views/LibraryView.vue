<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useBooks } from '../composables/useBooks'
import SearchInput from '../components/shared/SearchInput.vue'
import BookCard from '../components/shared/BookCard.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import PullIndicator from '../components/shared/PullIndicator.vue'
import { usePullToRefresh } from '../composables/usePullToRefresh'
import { IconShuffle } from '../components/shared/icons'
import type { BookStatusValue } from '../types'
import { plural } from '../utils/plural'

const route = useRoute()
const { t } = useI18n()
const router = useRouter()
const { books, loading, load, categories } = useBooks()

const search = ref((route.query.q as string) || '')
const category = ref((route.query.category as string) || '')
const sort = ref((route.query.sort as string) || 'title')
const statusFilter = ref<BookStatusValue | ''>((route.query.status as BookStatusValue) || '')
const langFilter = ref((route.query.lang as string) || '')
const visibleCount = ref(40)

const PAGE_SIZE = 40

const categoryCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const b of books.value) {
    counts[b.category] = (counts[b.category] || 0) + 1
  }
  return counts
})

const hasActiveFilters = computed(
  () => search.value !== '' || category.value !== '' || statusFilter.value !== '' || langFilter.value !== '',
)

onMounted(() => loadBooks())

function syncQuery() {
  const query: Record<string, string> = {}
  if (category.value) query.category = category.value
  if (sort.value && sort.value !== 'title') query.sort = sort.value
  if (statusFilter.value) query.status = statusFilter.value
  if (langFilter.value) query.lang = langFilter.value
  if (search.value) query.q = search.value
  router.replace({ query })
}

watch([category, sort, langFilter], () => {
  visibleCount.value = PAGE_SIZE
  loadBooks()
  syncQuery()
  window.scrollTo({ top: 0, behavior: 'smooth' })
})
watch([statusFilter, search], () => {
  visibleCount.value = PAGE_SIZE
  syncQuery()
  window.scrollTo({ top: 0, behavior: 'smooth' })
})

function loadBooks() {
  const params: Record<string, string> = {}
  if (category.value) params.category = category.value
  if (sort.value) params.sort = sort.value
  if (langFilter.value) params.language = langFilter.value
  load(params)
}

const filtered = computed(() => {
  let result = books.value
  if (statusFilter.value) {
    result = result.filter((b) => b.book_status === statusFilter.value)
  }
  if (search.value) {
    const q = search.value.toLowerCase()
    result = result.filter(
      (b) =>
        b.title.toLowerCase().includes(q) || b.author.toLowerCase().includes(q) || b.folder.toLowerCase().includes(q),
    )
  }
  return result
})

const visibleBooks = computed(() => filtered.value.slice(0, visibleCount.value))
const hasMore = computed(() => visibleCount.value < filtered.value.length)

const sortOptions = computed(() => [
  { value: 'title', label: t('library.sortTitle') },
  { value: 'author', label: t('library.sortAuthor') },
  { value: 'category', label: t('library.sortCategory') },
  { value: 'progress', label: t('library.sortProgress') },
  { value: 'rating', label: t('library.sortRating') },
])

// Status counts from actual book_status field (consistent with filter)
const statusCounts = computed(() => {
  const all = books.value
  return {
    reading: all.filter((b) => b.book_status === 'reading').length,
    done: all.filter((b) => b.book_status === 'done').length,
  }
})

// Status pills with live counts
const statusPills = computed(() => [
  { value: '' as BookStatusValue | '', label: 'Все' },
  { value: 'reading' as BookStatusValue | '', label: 'Слушаю', count: statusCounts.value.reading },
  { value: 'want_to_read' as BookStatusValue | '', label: 'Хочу' },
  { value: 'done' as BookStatusValue | '', label: 'Готово', count: statusCounts.value.done },
  { value: 'paused' as BookStatusValue | '', label: 'На паузе' },
])

function randomBook() {
  const pool = filtered.value
  if (!pool.length) return
  const pick = pool[Math.floor(Math.random() * pool.length)]!
  router.push(`/book/${pick.id}`)
}

function resetFilters() {
  search.value = ''
  category.value = ''
  sort.value = 'title'
  statusFilter.value = ''
  langFilter.value = ''
  visibleCount.value = PAGE_SIZE
}

function showMore() {
  visibleCount.value += PAGE_SIZE
}

const BOOK_LANGS = [
  { code: 'ru', label: 'Рус', flag: '🇷🇺' },
  { code: 'uk', label: 'Укр', flag: '🇺🇦' },
  { code: 'en', label: 'Eng', flag: '🇬🇧' },
]

const langCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const b of books.value) {
    if (b.language) counts[b.language] = (counts[b.language] || 0) + 1
  }
  return counts
})

const { refreshing, pullProgress } = usePullToRefresh(async () => loadBooks())
</script>

<template>
  <div>
    <PullIndicator :progress="pullProgress" :refreshing="refreshing" />

    <!-- Header -->
    <div class="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
      <div>
        <h1 class="page-title">{{ t('library.title') }}</h1>
        <p class="mt-1 text-[13px] text-[--t3]">
          <span class="font-bold text-[--accent]">{{ filtered.length }}</span>
          {{ plural(filtered.length, 'книга', 'книги', 'книг') }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <SearchInput v-model="search" :placeholder="t('library.search')" class="w-full sm:w-56" />
        <button
          class="flex h-[42px] w-[42px] flex-shrink-0 cursor-pointer items-center justify-center rounded-xl border border-white/[0.06] bg-white/[0.03] text-[--t3] transition-colors hover:bg-white/[0.08] hover:text-[--accent]"
          :title="t('library.randomBook')"
          @click="randomBook"
        >
          <IconShuffle :size="16" />
        </button>
      </div>
    </div>

    <!-- Category pills -->
    <div class="scrollbar-hide fade-mask-r mb-3 flex gap-2 overflow-x-auto pb-0.5">
      <button
        class="flex-shrink-0 cursor-pointer rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
        :class="
          category === ''
            ? 'border-white/10 bg-white/[0.08] text-[--t1]'
            : 'border-transparent bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="category = ''"
      >
        Все
      </button>
      <button
        v-for="cat in categories"
        :key="cat"
        class="flex flex-shrink-0 cursor-pointer items-center gap-1 rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
        :class="
          category === cat
            ? 'border-white/10 bg-white/[0.08] text-[--t1]'
            : 'border-transparent bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="category = cat"
      >
        {{ cat }}
        <span class="text-[10px] opacity-50">{{ categoryCounts[cat] || 0 }}</span>
      </button>
    </div>

    <!-- Language filter pills -->
    <div class="scrollbar-hide fade-mask-r mb-3 flex gap-2 overflow-x-auto pb-0.5">
      <button
        class="flex-shrink-0 cursor-pointer rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
        :class="
          langFilter === ''
            ? 'border-white/10 bg-white/[0.08] text-[--t1]'
            : 'border-transparent bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="langFilter = ''"
      >
        {{ t('library.filterAll') }}
      </button>
      <button
        v-for="lang in BOOK_LANGS"
        :key="lang.code"
        class="flex-shrink-0 cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
        :class="
          langFilter === lang.code
            ? 'border-white/10 bg-white/[0.08] text-[--t1]'
            : 'border-transparent bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="langFilter = lang.code"
      >
        {{ lang.flag }} {{ lang.label }}
        <span v-if="langCounts[lang.code]" class="ml-0.5 text-[10px] opacity-50">{{ langCounts[lang.code] }}</span>
      </button>
    </div>

    <!-- Status + Sort row -->
    <div class="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div class="scrollbar-hide fade-mask-r flex gap-1.5 overflow-x-auto pb-0.5">
        <button
          v-for="sp in statusPills"
          :key="sp.value"
          class="flex flex-shrink-0 cursor-pointer items-center gap-1 rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
          :class="
            statusFilter === sp.value
              ? 'border-white/10 bg-white/[0.08] text-[--t1]'
              : 'border-transparent bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
          "
          @click="statusFilter = sp.value"
        >
          {{ sp.label }}
          <span
            v-if="sp.count"
            class="ml-0.5 rounded-md bg-white/[0.08] px-1.5 py-0.5 text-[10px] leading-none text-[--t3]"
          >
            {{ sp.count }}
          </span>
        </button>
      </div>
      <div class="scrollbar-hide flex flex-shrink-0 items-center gap-1 overflow-x-auto">
        <button
          v-for="s in sortOptions"
          :key="s.value"
          class="cursor-pointer rounded-full border-0 px-2.5 py-1 text-[11px] font-medium transition-colors"
          :class="
            sort === s.value
              ? 'bg-[--accent-soft] text-[--accent]'
              : 'bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
          "
          @click="sort = s.value"
        >
          {{ s.label }}
        </button>
      </div>
    </div>

    <!-- Active filter summary -->
    <div v-if="hasActiveFilters && !loading" class="mb-4 flex items-center gap-2 text-[12px] text-[--t3]">
      <span>
        Найдено <span class="font-bold text-[--t1]">{{ filtered.length }}</span>
        {{ plural(filtered.length, 'книга', 'книги', 'книг') }}
      </span>
      <span v-if="category" class="rounded-full bg-white/[0.06] px-2 py-0.5">{{ category }}</span>
      <span v-if="statusFilter" class="rounded-full bg-white/[0.06] px-2 py-0.5">
        {{ statusPills.find((p) => p.value === statusFilter)?.label }}
      </span>
      <span v-if="search" class="rounded-full bg-white/[0.06] px-2 py-0.5">&laquo;{{ search }}&raquo;</span>
      <button class="ml-1 cursor-pointer text-[--accent] hover:underline" @click="resetFilters">
        {{ t('library.reset') }}
      </button>
    </div>

    <!-- Loading skeletons -->
    <div v-if="loading" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <div v-for="i in 8" :key="i">
        <div class="skeleton h-28 rounded-t-xl rounded-b-none" />
        <div class="skeleton h-44 rounded-t-none rounded-b-xl border-t-0" />
      </div>
    </div>

    <div v-else-if="filtered.length" class="fade-in">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <BookCard v-for="book in visibleBooks" :key="book.id" :book="book" />
      </div>
      <div v-if="hasMore" class="mt-8 flex flex-col items-center gap-2">
        <div class="flex items-center gap-2 text-[12px] text-[--t3]">
          <div class="h-1 w-24 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              class="h-full rounded-full bg-[--accent] transition-all duration-300"
              :style="{ width: `${(visibleCount / filtered.length) * 100}%` }"
            />
          </div>
          <span>{{ visibleCount }} из {{ filtered.length }}</span>
        </div>
        <button class="btn btn-ghost px-8 py-2.5 text-[13px] font-semibold" @click="showMore">
          Показать ещё {{ Math.min(PAGE_SIZE, filtered.length - visibleCount) }}
        </button>
      </div>
    </div>

    <EmptyState
      v-else
      :title="t('library.notFound')"
      :description="t('library.notFoundDesc')"
      :action-label="t('library.resetFilters')"
      @action="resetFilters"
    />
  </div>
</template>
