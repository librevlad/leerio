<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useBooks } from '../composables/useBooks'
import SearchInput from '../components/shared/SearchInput.vue'
import BookCard from '../components/shared/BookCard.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import PullIndicator from '../components/shared/PullIndicator.vue'
import { usePullToRefresh } from '../composables/usePullToRefresh'
import type { BookStatusValue } from '../types'
import { plural } from '../utils/plural'

const { books, loading, load, categories } = useBooks()

const search = ref('')
const category = ref('')
const sort = ref('title')
const statusFilter = ref<BookStatusValue | ''>('')

onMounted(() => loadBooks())

watch([category, sort], () => loadBooks())

function loadBooks() {
  const params: Record<string, string> = {}
  if (category.value) params.category = category.value
  if (sort.value) params.sort = sort.value
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

const sortOptions = [
  { value: 'title', label: 'Название' },
  { value: 'author', label: 'Автор' },
  { value: 'category', label: 'Категория' },
  { value: 'progress', label: 'Прогресс' },
  { value: 'rating', label: 'Оценка' },
]

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

function resetFilters() {
  search.value = ''
  category.value = ''
  sort.value = 'title'
  statusFilter.value = ''
}

const { refreshing, pullProgress } = usePullToRefresh(async () => loadBooks())
</script>

<template>
  <div>
    <PullIndicator :progress="pullProgress" :refreshing="refreshing" />

    <!-- Header -->
    <div class="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
      <div>
        <h1 class="page-title">Каталог</h1>
        <p class="mt-1 text-[13px] text-[--t3]">
          <span class="font-bold text-[--accent]">{{ filtered.length }}</span>
          {{ plural(filtered.length, 'книга', 'книги', 'книг') }}
        </p>
      </div>
      <SearchInput v-model="search" placeholder="Поиск..." class="w-full sm:w-56" />
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
        class="flex-shrink-0 cursor-pointer rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
        :class="
          category === cat
            ? 'border-white/10 bg-white/[0.08] text-[--t1]'
            : 'border-transparent bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="category = cat"
      >
        {{ cat }}
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

    <!-- Loading skeletons -->
    <div v-if="loading" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <div v-for="i in 8" :key="i">
        <div class="skeleton h-28 rounded-t-xl rounded-b-none" />
        <div class="skeleton h-44 rounded-t-none rounded-b-xl border-t-0" />
      </div>
    </div>

    <div
      v-else-if="filtered.length"
      class="fade-in grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
    >
      <BookCard v-for="book in filtered" :key="book.id" :book="book" />
    </div>

    <EmptyState
      v-else
      title="Книги не найдены"
      description="Попробуйте изменить фильтры"
      action-label="Сбросить фильтры"
      @action="resetFilters"
    />
  </div>
</template>
