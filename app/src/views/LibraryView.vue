<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useBooks } from '../composables/useBooks'
import BookCard from '../components/shared/BookCard.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import PullIndicator from '../components/shared/PullIndicator.vue'
import { usePullToRefresh } from '../composables/usePullToRefresh'
import type { BookStatusValue } from '../types'
import AddBookFab from '../components/library/AddBookFab.vue'

const route = useRoute()
const { t } = useI18n()
const router = useRouter()
const { books, loading, load, categories } = useBooks()

const search = ref((route.query.q as string) || '')
const category = ref((route.query.category as string) || '')
const statusFilter = ref<BookStatusValue | ''>((route.query.status as BookStatusValue) || '')
const visibleCount = ref(40)
const showStatusMenu = ref(false)

const PAGE_SIZE = 40

const categoryCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const b of books.value) {
    counts[b.category] = (counts[b.category] || 0) + 1
  }
  return counts
})

const hasActiveFilters = computed(() => search.value !== '' || category.value !== '' || statusFilter.value !== '')

onMounted(() => loadBooks())

function syncQuery() {
  const query: Record<string, string> = {}
  if (category.value) query.category = category.value
  if (statusFilter.value) query.status = statusFilter.value
  if (search.value) query.q = search.value
  router.replace({ query })
}

watch(category, () => {
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
  const params: Record<string, string> = { sort: 'title' }
  if (category.value) params.category = category.value
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
  { value: '' as BookStatusValue | '', label: t('library.filterAll') },
  { value: 'reading' as BookStatusValue | '', label: t('library.filterListening'), count: statusCounts.value.reading },
  { value: 'want_to_read' as BookStatusValue | '', label: t('library.filterWant') },
  { value: 'done' as BookStatusValue | '', label: t('library.filterDone'), count: statusCounts.value.done },
  { value: 'paused' as BookStatusValue | '', label: t('library.filterPaused') },
  { value: 'rejected' as BookStatusValue | '', label: t('library.filterRejected') },
])

function selectStatus(value: BookStatusValue | '') {
  statusFilter.value = value
  showStatusMenu.value = false
}

function resetFilters() {
  search.value = ''
  category.value = ''
  statusFilter.value = ''
  visibleCount.value = PAGE_SIZE
}

function showMore() {
  visibleCount.value += PAGE_SIZE
}

const { refreshing, pullProgress } = usePullToRefresh(async () => loadBooks())

// Auto-load more on scroll (intersection observer)
const loadMoreRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

onMounted(() => {
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting && hasMore.value) showMore()
    },
    { rootMargin: '200px' },
  )
})

onUnmounted(() => observer?.disconnect())

watch(loadMoreRef, (el) => {
  if (!observer) return
  observer.disconnect()
  if (el) observer.observe(el)
})
</script>

<template>
  <div>
    <PullIndicator :progress="pullProgress" :refreshing="refreshing" />

    <!-- Header -->
    <div class="mb-4">
      <h1 class="page-title">{{ t('library.title') }}</h1>
    </div>

    <!-- Search -->
    <div class="mb-3">
      <input
        v-model="search"
        type="search"
        :placeholder="t('library.search')"
        class="input-field min-h-[44px] w-full rounded-xl px-4 py-3 text-[13px]"
      />
    </div>

    <!-- Category pills -->
    <div class="scrollbar-hide fade-mask-r mb-2 flex gap-1.5 overflow-x-auto pb-0.5">
      <button
        class="flex min-h-[44px] flex-shrink-0 cursor-pointer items-center rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
        :class="
          category === ''
            ? 'border-white/10 bg-white/[0.08] text-[--t1]'
            : 'border-transparent bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="category = ''"
      >
        {{ t('library.filterAll') }}
      </button>
      <button
        v-for="cat in categories.filter((c) => categoryCounts[c])"
        :key="cat"
        class="flex min-h-[44px] flex-shrink-0 cursor-pointer items-center gap-1 rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
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

    <!-- Status dropdown -->
    <div class="relative mb-5 inline-block">
      <button
        class="flex min-h-[44px] cursor-pointer items-center gap-1 rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
        :class="
          statusFilter
            ? 'border-white/10 bg-white/[0.08] text-[--t1]'
            : 'border-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="showStatusMenu = !showStatusMenu"
      >
        {{ statusFilter ? statusPills.find((p) => p.value === statusFilter)?.label : t('library.filterStatus') }}
        <span class="text-[10px] opacity-50">▾</span>
      </button>
      <div
        v-if="showStatusMenu"
        class="absolute top-full left-0 z-20 mt-1 rounded-xl border border-[--border] p-1"
        style="background: var(--card-solid)"
      >
        <button
          v-for="sp in statusPills"
          :key="sp.value"
          class="block w-full cursor-pointer rounded-lg border-0 bg-transparent px-3 py-2 text-left text-[12px] whitespace-nowrap transition-colors"
          :class="statusFilter === sp.value ? 'text-[--accent]' : 'text-[--t2] hover:bg-white/5'"
          @click="selectStatus(sp.value)"
        >
          {{ sp.label }}
          <span v-if="sp.count" class="ml-1 text-[10px] opacity-50">{{ sp.count }}</span>
        </button>
      </div>
    </div>

    <!-- Status menu overlay -->
    <div v-if="showStatusMenu" class="fixed inset-0 z-10" @click="showStatusMenu = false" />

    <!-- Active filter summary -->
    <div v-if="hasActiveFilters && !loading" class="mb-4 flex items-center gap-2 text-[12px] text-[--t3]">
      <span>
        {{ t('library.found') }} <span class="font-bold text-[--t1]">{{ filtered.length }}</span>
        {{ t('plural.book', filtered.length) }}
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
      <!-- Grid view -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <BookCard
          v-for="(book, i) in visibleBooks"
          :key="book.id"
          :book="book"
          class="stagger-item"
          :style="{ animationDelay: `${Math.min(i, 11) * 40}ms` }"
        />
      </div>
      <!-- Infinite scroll trigger -->
      <div v-if="hasMore" ref="loadMoreRef" class="mt-6 flex justify-center py-4">
        <div class="flex items-center gap-3 text-[12px] text-[--t3]">
          <div class="h-1 w-20 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              class="h-full rounded-full bg-[--accent] transition-all duration-300"
              :style="{ width: `${(visibleCount / filtered.length) * 100}%` }"
            />
          </div>
          <span class="tabular-nums">{{ visibleCount }} {{ t('library.of') }} {{ filtered.length }}</span>
        </div>
      </div>
    </div>

    <EmptyState
      v-else
      :title="t('library.notFound')"
      :description="t('library.notFoundDesc')"
      :action-label="t('library.resetFilters')"
      @action="resetFilters"
    />

    <AddBookFab />
  </div>
</template>
