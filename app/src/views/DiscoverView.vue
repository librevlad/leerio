<script setup lang="ts">
import { ref, watch } from 'vue'
import { useLibriVox } from '../composables/useLibriVox'
import SearchInput from '../components/shared/SearchInput.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import { IconClock, IconMusic } from '../components/shared/icons'

const { books, loading, hasMore, search, loadMore } = useLibriVox()

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
  search(title.value.trim(), language.value)
}

watch(title, () => doSearch())
watch(language, () => doSearch())

function formatDuration(secs: number): string {
  if (!secs) return ''
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  if (h > 0) return `${h}ч ${m}м`
  return `${m}м`
}
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-[20px] font-bold text-[--t1]">LibriVox</h1>
      <p class="mt-1 text-[13px] text-[--t3]">Бесплатные аудиокниги</p>
    </div>

    <!-- Search -->
    <div class="mb-4">
      <SearchInput v-model="title" placeholder="Поиск по названию..." />
    </div>

    <!-- Language filter -->
    <div class="mb-6 flex flex-wrap gap-2">
      <button
        v-for="lang in languages"
        :key="lang.value"
        class="cursor-pointer rounded-full border px-3 py-1.5 text-[12px] font-medium transition-all"
        :class="
          language === lang.value
            ? 'border-teal-500/40 bg-teal-500/15 text-teal-300'
            : 'border-[--border] bg-transparent text-[--t3] hover:border-[--t3] hover:text-[--t2]'
        "
        @click="language = lang.value"
      >
        {{ lang.label }}
      </button>
    </div>

    <!-- Loading skeletons -->
    <div v-if="loading && books.length === 0" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="i in 6" :key="i" class="skeleton h-44 rounded-2xl" />
    </div>

    <!-- Results -->
    <div v-else-if="books.length > 0">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <router-link
          v-for="book in books"
          :key="book.id"
          :to="`/discover/${book.librivox_id}`"
          class="card group cursor-pointer overflow-hidden rounded-2xl border border-[--border] no-underline transition-all hover:border-teal-500/30 hover:shadow-lg"
          style="background: linear-gradient(135deg, rgba(20, 184, 166, 0.06) 0%, rgba(7, 7, 14, 0.4) 100%)"
        >
          <div class="p-4">
            <h3 class="mb-1.5 line-clamp-2 text-[14px] leading-snug font-semibold text-[--t1]">
              {{ book.title }}
            </h3>
            <p class="mb-3 truncate text-[12px] text-[--t3]">{{ book.author }}</p>
            <div class="flex flex-wrap items-center gap-2">
              <span
                v-if="book.language"
                class="rounded-md bg-teal-500/10 px-2 py-0.5 text-[10px] font-medium text-teal-400"
              >
                {{ book.language }}
              </span>
              <span v-if="book.total_time_secs" class="flex items-center gap-1 text-[11px] text-[--t3]">
                <IconClock :size="12" />
                {{ formatDuration(book.total_time_secs) }}
              </span>
              <span v-if="book.num_sections" class="flex items-center gap-1 text-[11px] text-[--t3]">
                <IconMusic :size="12" />
                {{ book.num_sections }} глав
              </span>
            </div>
          </div>
        </router-link>
      </div>

      <!-- Load more -->
      <div v-if="hasMore" class="mt-6 text-center">
        <button class="btn btn-ghost" :disabled="loading" @click="loadMore(title.trim(), language)">
          {{ loading ? 'Загрузка...' : 'Загрузить ещё' }}
        </button>
      </div>
    </div>

    <!-- Empty state -->
    <EmptyState
      v-else-if="!loading && title.trim()"
      title="Ничего не найдено"
      description="Попробуйте другой запрос или язык"
    />

    <!-- Initial state -->
    <EmptyState
      v-else-if="!loading"
      title="Откройте мир бесплатных аудиокниг"
      description="Введите название для поиска в каталоге LibriVox"
    />
  </div>
</template>
