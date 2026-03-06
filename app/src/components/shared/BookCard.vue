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
  to?: string
  coverSrc?: string
}>()
const dl = useDownloads()
const downloaded = computed(() => dl.isNative.value && dl.isBookDownloaded(props.book.id))
const coverLoaded = ref(false)
const coverError = ref(false)
const hasCover = computed(() => (props.book.has_cover || props.coverSrc) && !coverError.value)

const coverGradient: Record<string, string> = {
  Бизнес: 'linear-gradient(135deg, #92400e 0%, #d97706 50%, #fbbf24 100%)',
  Личные: 'linear-gradient(135deg, #4c1d95 0%, #7c3aed 50%, #a78bfa 100%)',
  Отношения: 'linear-gradient(135deg, #9d174d 0%, #db2777 50%, #f472b6 100%)',
  Саморазвитие: 'linear-gradient(135deg, #9a5c16 0%, #E8923A 50%, #F0A85C 100%)',
  Художественная: 'linear-gradient(135deg, #155e75 0%, #0891b2 50%, #22d3ee 100%)',
  Языки: 'linear-gradient(135deg, #064e3b 0%, #059669 50%, #34d399 100%)',
}

const coverPattern: Record<string, string> = {
  Бизнес: 'radial-gradient(circle at 80% 20%, rgba(255,255,255,0.15) 0%, transparent 50%)',
  Личные: 'radial-gradient(circle at 60% 40%, rgba(255,255,255,0.15) 0%, transparent 50%)',
  Отношения: 'radial-gradient(circle at 20% 80%, rgba(255,255,255,0.12) 0%, transparent 50%)',
  Саморазвитие: 'radial-gradient(circle at 70% 70%, rgba(255,255,255,0.12) 0%, transparent 50%)',
  Художественная: 'radial-gradient(circle at 30% 30%, rgba(255,255,255,0.15) 0%, transparent 50%)',
  Языки: 'radial-gradient(circle at 80% 80%, rgba(255,255,255,0.12) 0%, transparent 50%)',
}

const fallbackGradient = 'linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%)'
const fallbackPattern = 'radial-gradient(circle at 50% 50%, rgba(255,255,255,0.1) 0%, transparent 50%)'
</script>

<template>
  <router-link :to="to || `/book/${book.id}`" class="card card-hover group relative block overflow-hidden no-underline">
    <!-- Gradient backdrop (shorter) -->
    <div
      class="relative h-28 overflow-hidden"
      :style="{ background: coverGradient[book.category] || fallbackGradient }"
    >
      <img
        v-if="hasCover"
        :src="coverSrc || coverUrl(book.id)"
        :alt="book.title"
        class="absolute inset-0 h-full w-full object-cover transition-opacity duration-300"
        :class="coverLoaded ? 'opacity-100 blur-[1px] brightness-75' : 'opacity-0'"
        @load="coverLoaded = true"
        @error="coverError = true"
      />
      <div
        v-if="!coverLoaded"
        class="absolute inset-0"
        :style="{ background: coverPattern[book.category] || fallbackPattern }"
      />
      <div
        class="absolute inset-0"
        style="background: linear-gradient(to bottom, transparent 20%, rgba(0, 0, 0, 0.7) 100%)"
      />

      <!-- Top badges -->
      <div class="absolute top-2.5 right-3 left-3 z-10 flex items-start justify-between">
        <CategoryBadge :category="book.category" />
        <div class="flex items-center gap-1.5">
          <SourceBadge v-if="source" :source="source" />
          <StatusBadge v-if="book.book_status" :book-status="book.book_status" />
        </div>
      </div>
    </div>

    <!-- Floating cover thumbnail -->
    <div class="relative px-4">
      <div class="-mt-10 mb-3 flex items-end gap-3">
        <div class="relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-lg shadow-lg ring-2 ring-[--card-solid]">
          <img
            v-if="hasCover"
            :src="coverSrc || coverUrl(book.id)"
            :alt="book.title"
            class="h-full w-full object-cover"
            @error="coverError = true"
          />
          <div
            v-else
            class="flex h-full w-full items-center justify-center"
            :style="{
              background: coverGradient[book.category] || fallbackGradient,
              backgroundImage: coverPattern[book.category] || fallbackPattern,
            }"
          >
            <span class="text-[20px] font-bold text-white/60">{{ book.title.charAt(0) }}</span>
          </div>
          <span
            v-if="downloaded"
            class="absolute right-1 bottom-1 flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-white shadow"
          >
            <IconCheck :size="10" />
          </span>
        </div>
        <div class="min-w-0 pb-1">
          <h3
            class="line-clamp-2 text-[14px] leading-snug font-semibold text-[--t1] transition-colors group-hover:text-white"
            :title="book.title"
          >
            {{ book.title }}
          </h3>
        </div>
      </div>

      <!-- Author / Reader -->
      <p
        v-if="book.author || book.reader"
        class="mb-3 line-clamp-1 text-[12px] text-[--t2]"
        :title="book.author || book.reader"
      >
        {{ book.author
        }}<span v-if="book.reader && book.reader !== book.author" class="text-[--t3]"
          >{{ book.author ? ' · ' : '' }}{{ book.reader }}</span
        >
      </p>

      <!-- Progress bar -->
      <div v-if="book.progress > 0" class="mb-2.5">
        <div class="mb-1 flex items-center justify-between">
          <span class="text-[11px] font-medium text-[--t3]">Прогресс</span>
          <span class="text-[11px] font-bold text-[--accent]">{{ book.progress }}%</span>
        </div>
        <ProgressBar :percent="book.progress" height="h-1.5" />
      </div>

      <!-- Tags + Rating -->
      <div class="mt-auto flex items-center justify-between pb-4">
        <div v-if="book.tags.length" class="flex min-w-0 flex-1 gap-1 overflow-hidden">
          <span
            v-for="tag in book.tags.slice(0, 2)"
            :key="tag"
            class="max-w-[80px] flex-shrink-0 truncate rounded-md px-2 py-0.5 text-[11px] font-medium text-[--t3]"
            style="background: rgba(255, 255, 255, 0.05)"
          >
            {{ tag }}
          </span>
          <span v-if="book.tags.length > 2" class="flex-shrink-0 text-[11px] text-[--t3]">
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
