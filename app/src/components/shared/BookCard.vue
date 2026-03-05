<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Book } from '../../types'
import { coverUrl } from '../../api'
import CategoryBadge from './CategoryBadge.vue'
import StatusBadge from './StatusBadge.vue'
import SourceBadge from './SourceBadge.vue'
import ProgressBar from './ProgressBar.vue'
import { IconStar, IconStarOutline, IconCheck } from './icons'
import { useDownloads } from '../../composables/useDownloads'

const props = defineProps<{
  book: Book
  source?: 'library' | 'librivox' | 'user' | 'local'
}>()
const dl = useDownloads()
const downloaded = computed(() => dl.isNative.value && dl.isBookDownloaded(props.book.id))
const coverLoaded = ref(false)

const coverGradient: Record<string, string> = {
  Бизнес: 'linear-gradient(135deg, #92400e 0%, #d97706 50%, #fbbf24 100%)',
  Отношения: 'linear-gradient(135deg, #9d174d 0%, #db2777 50%, #f472b6 100%)',
  Саморазвитие: 'linear-gradient(135deg, #9a5c16 0%, #E8923A 50%, #F0A85C 100%)',
  Художественная: 'linear-gradient(135deg, #155e75 0%, #0891b2 50%, #22d3ee 100%)',
  Языки: 'linear-gradient(135deg, #064e3b 0%, #059669 50%, #34d399 100%)',
}

const coverPattern: Record<string, string> = {
  Бизнес: 'radial-gradient(circle at 80% 20%, rgba(255,255,255,0.15) 0%, transparent 50%)',
  Отношения: 'radial-gradient(circle at 20% 80%, rgba(255,255,255,0.12) 0%, transparent 50%)',
  Саморазвитие: 'radial-gradient(circle at 70% 70%, rgba(255,255,255,0.12) 0%, transparent 50%)',
  Художественная: 'radial-gradient(circle at 30% 30%, rgba(255,255,255,0.15) 0%, transparent 50%)',
  Языки: 'radial-gradient(circle at 80% 80%, rgba(255,255,255,0.12) 0%, transparent 50%)',
}

const fallbackGradient = 'linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%)'
const fallbackPattern = 'radial-gradient(circle at 50% 50%, rgba(255,255,255,0.1) 0%, transparent 50%)'
</script>

<template>
  <router-link :to="`/book/${book.id}`" class="card card-hover group relative block overflow-hidden no-underline">
    <!-- Cover gradient banner -->
    <div
      class="relative h-44 overflow-hidden"
      :style="{ background: coverGradient[book.category] || fallbackGradient }"
    >
      <img
        v-if="book.has_cover"
        :src="coverUrl(book.id)"
        :alt="book.title"
        class="absolute inset-0 h-full w-full object-cover transition-opacity duration-300"
        :class="coverLoaded ? 'opacity-100' : 'opacity-0'"
        @load="coverLoaded = true"
      />
      <div
        v-if="!coverLoaded"
        class="absolute inset-0"
        :style="{ background: coverPattern[book.category] || fallbackPattern }"
      />
      <div
        class="absolute inset-0"
        style="background: linear-gradient(to bottom, transparent 30%, rgba(0, 0, 0, 0.6) 100%)"
      />
      <div v-if="source" class="absolute top-2.5 right-3 z-10">
        <SourceBadge :source="source" />
      </div>
      <div class="absolute right-3 bottom-2.5 left-3 flex items-end justify-between gap-2">
        <div class="flex items-center gap-1.5">
          <CategoryBadge :category="book.category" />
          <span
            v-if="downloaded"
            class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/90 text-white"
            title="Скачано"
          >
            <IconCheck :size="12" />
          </span>
        </div>
        <StatusBadge v-if="book.book_status" :book-status="book.book_status" />
      </div>
    </div>

    <!-- Content -->
    <div class="p-4 pt-3.5">
      <h3
        class="mb-1 line-clamp-2 text-[14px] leading-snug font-semibold text-[--t1] transition-colors group-hover:text-white"
        :title="book.title"
      >
        {{ book.title }}
      </h3>
      <p class="mb-3 line-clamp-1 text-[12px] text-[--t2]" :title="book.author">
        {{ book.author }}
        <span v-if="book.reader" class="text-[--t3]"> · {{ book.reader }}</span>
      </p>

      <div v-if="book.progress > 0" class="mb-2.5">
        <div class="mb-1 flex items-center justify-between">
          <span class="text-[10px] font-semibold text-[--t3]">Прогресс</span>
          <span class="text-[10px] font-bold text-[--accent]">{{ book.progress }}%</span>
        </div>
        <ProgressBar :percent="book.progress" height="h-1" />
      </div>

      <div class="mt-auto flex items-center justify-between">
        <div v-if="book.tags.length" class="flex min-w-0 flex-1 gap-1 overflow-hidden">
          <span
            v-for="tag in book.tags.slice(0, 2)"
            :key="tag"
            class="max-w-[80px] flex-shrink-0 truncate rounded-full px-2 py-0.5 text-[10px] font-medium text-[--t3]"
            style="background: rgba(255, 255, 255, 0.05)"
          >
            {{ tag }}
          </span>
          <span v-if="book.tags.length > 2" class="flex-shrink-0 text-[10px] text-[--t3]">
            +{{ book.tags.length - 2 }}
          </span>
        </div>

        <div v-if="book.rating" class="ml-2 flex flex-shrink-0 gap-0.5 text-amber-400/70">
          <template v-for="s in 5" :key="s">
            <component :is="s <= book.rating ? IconStar : IconStarOutline" :size="11" />
          </template>
        </div>
      </div>
    </div>
  </router-link>
</template>
