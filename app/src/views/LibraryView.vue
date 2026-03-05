<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useBooks } from '../composables/useBooks'
import SearchInput from '../components/shared/SearchInput.vue'
import BookCard from '../components/shared/BookCard.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import PullIndicator from '../components/shared/PullIndicator.vue'
import { usePullToRefresh } from '../composables/usePullToRefresh'
import type { BookStatusValue } from '../types'

const { books, loading, load, categories } = useBooks()

const search = ref('')
const category = ref('')
const sort = ref('title')
const statusFilter = ref<BookStatusValue | ''>('')

const statusPills: { value: BookStatusValue | ''; label: string }[] = [
  { value: '', label: 'Все' },
  { value: 'reading', label: 'Слушаю' },
  { value: 'want_to_read', label: 'Хочу' },
  { value: 'done', label: 'Готово' },
  { value: 'paused', label: 'На паузе' },
]

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

const catColors: Record<string, { bg: string; border: string; text: string }> = {
  Бизнес: { bg: 'bg-amber-500/8', border: 'border-amber-500/20', text: 'text-amber-400' },
  Отношения: { bg: 'bg-pink-500/8', border: 'border-pink-500/20', text: 'text-pink-400' },
  Саморазвитие: { bg: 'bg-violet-500/8', border: 'border-violet-500/20', text: 'text-violet-400' },
  Художественная: { bg: 'bg-cyan-500/8', border: 'border-cyan-500/20', text: 'text-cyan-400' },
  Языки: { bg: 'bg-emerald-500/8', border: 'border-emerald-500/20', text: 'text-emerald-400' },
}
const catFallback = { bg: 'bg-slate-500/8', border: 'border-slate-500/20', text: 'text-slate-400' }

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
    <div class="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
      <div>
        <h1 class="page-title">Библиотека</h1>
        <p class="mt-1 text-[13px] text-[--t3]">{{ filtered.length }} книг</p>
      </div>
      <SearchInput v-model="search" placeholder="Поиск..." class="w-full sm:w-64" />
    </div>

    <!-- Category filter pills -->
    <div class="scrollbar-hide fade-mask-r mb-4 flex gap-2 overflow-x-auto pb-1">
      <button
        class="flex-shrink-0 cursor-pointer rounded-full border px-4 py-2 text-[12px] font-semibold transition-all duration-200"
        :class="
          category === ''
            ? 'border-white/15 bg-white/10 text-[--t1]'
            : 'border-transparent bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="category = ''"
      >
        Все
      </button>
      <button
        v-for="cat in categories"
        :key="cat"
        class="flex-shrink-0 cursor-pointer rounded-full border px-4 py-2 text-[12px] font-semibold transition-all duration-200"
        :class="
          category === cat
            ? [
                (catColors[cat] || catFallback).bg,
                (catColors[cat] || catFallback).border,
                (catColors[cat] || catFallback).text,
              ]
            : 'border-transparent bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="category = cat"
      >
        {{ cat }}
      </button>
    </div>

    <!-- Status filter pills -->
    <div class="scrollbar-hide fade-mask-r mb-4 flex gap-2 overflow-x-auto pb-1">
      <button
        v-for="sp in statusPills"
        :key="sp.value"
        class="flex-shrink-0 cursor-pointer rounded-full border px-4 py-2 text-[12px] font-semibold transition-all duration-200"
        :class="
          statusFilter === sp.value
            ? 'border-[--accent]/30 bg-[--accent-soft] text-[--accent]'
            : 'border-transparent bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="statusFilter = sp.value"
      >
        {{ sp.label }}
      </button>
    </div>

    <!-- Sort chips -->
    <div class="scrollbar-hide mb-8 flex items-center gap-1.5 overflow-x-auto">
      <span class="mr-1 text-[11px] text-[--t3]">Сортировка:</span>
      <button
        v-for="s in sortOptions"
        :key="s.value"
        class="cursor-pointer rounded-full border-0 px-3 py-1.5 text-[11px] font-medium transition-all duration-200"
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

    <div v-if="loading" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <div v-for="i in 8" :key="i">
        <div class="skeleton h-44 rounded-t-[20px] rounded-b-none" />
        <div class="skeleton h-36 rounded-t-none rounded-b-[20px] border-t-0" />
      </div>
    </div>

    <div
      v-else-if="filtered.length"
      class="fade-in grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
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
