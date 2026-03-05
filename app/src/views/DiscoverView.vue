<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { useLibriVox } from '../composables/useLibriVox'
import { librivoxCoverUrl } from '../api'
import SearchInput from '../components/shared/SearchInput.vue'
import BookCard from '../components/shared/BookCard.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import type { Book } from '../types'

const { books, loading, hasMore, search: lvSearch, loadMore } = useLibriVox()

const title = ref('')
const language = ref('')

const languages = [
  { value: '', label: 'Все' },
  { value: 'English', label: 'English' },
  { value: 'Russian', label: 'Русский' },
  { value: 'German', label: 'Deutsch' },
  { value: 'French', label: 'Français' },
  { value: 'Spanish', label: 'Español' },
  { value: 'Chinese', label: '中文' },
  { value: 'Italian', label: 'Italiano' },
]

function doSearch() {
  if (!title.value.trim() && !language.value) return
  lvSearch(title.value.trim(), language.value)
}

const debouncedSearch = useDebounceFn(doSearch, 400)
watch(title, () => debouncedSearch())
watch(language, () => doSearch())

/** Map LibriVox book to Book interface for BookCard */
function toBook(lv: (typeof books.value)[number]): Book {
  return {
    id: lv.id,
    folder: '',
    category: lv.language || '',
    author: lv.author,
    title: lv.title,
    reader: '',
    path: '',
    progress: 0,
    tags: [],
    note: '',
    has_cover: true,
    duration_fmt: lv.total_time || undefined,
  }
}

const mapped = computed(() => books.value.map(toBook))

const hasSearched = computed(() => title.value.trim() !== '' || language.value !== '')
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
      <div>
        <h1 class="page-title">LibriVox</h1>
        <p class="mt-1 text-[13px] text-[--t3]">
          <template v-if="books.length">
            <span class="font-bold text-[--accent]">{{ books.length }}</span> книг
          </template>
          <template v-else>Бесплатные аудиокниги</template>
        </p>
      </div>
      <SearchInput v-model="title" placeholder="Поиск по названию..." class="w-full sm:w-56" />
    </div>

    <!-- Language pills (same style as category pills in catalog) -->
    <div class="scrollbar-hide fade-mask-r mb-6 flex gap-2 overflow-x-auto pb-0.5">
      <button
        v-for="lang in languages"
        :key="lang.value"
        class="flex-shrink-0 cursor-pointer rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
        :class="
          language === lang.value
            ? 'border-white/10 bg-white/[0.08] text-[--t1]'
            : 'border-transparent bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="language = lang.value"
      >
        {{ lang.label }}
      </button>
    </div>

    <!-- Loading skeletons -->
    <div
      v-if="loading && books.length === 0"
      class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
    >
      <div v-for="i in 8" :key="i">
        <div class="skeleton h-28 rounded-t-xl rounded-b-none" />
        <div class="skeleton h-44 rounded-t-none rounded-b-xl border-t-0" />
      </div>
    </div>

    <!-- Results -->
    <div v-else-if="mapped.length">
      <div class="fade-in grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <BookCard
          v-for="(book, i) in mapped"
          :key="book.id"
          :book="book"
          source="librivox"
          :to="`/discover/${books[i]!.librivox_id}`"
          :cover-src="librivoxCoverUrl(books[i]!.librivox_id)"
        />
      </div>

      <!-- Load more -->
      <div v-if="hasMore" class="mt-6 text-center">
        <button class="btn btn-ghost" :disabled="loading" @click="loadMore(title.trim(), language)">
          {{ loading ? 'Загрузка...' : 'Загрузить ещё' }}
        </button>
      </div>
    </div>

    <!-- Empty state after search -->
    <EmptyState
      v-else-if="!loading && hasSearched"
      title="Ничего не найдено"
      description="Попробуйте другой запрос или язык"
    />

    <!-- Initial state -->
    <EmptyState
      v-else-if="!loading"
      title="Откройте мир бесплатных аудиокниг"
      description="Введите название или выберите язык для поиска в каталоге LibriVox"
    />
  </div>
</template>
