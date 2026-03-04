<script setup lang="ts">
import { ref } from 'vue'
import type { Book } from '../../types'
import { coverUrl } from '../../api'
import CategoryBadge from '../shared/CategoryBadge.vue'
import StatusBadge from '../shared/StatusBadge.vue'
import ProgressRing from '../shared/ProgressRing.vue'
import { IconStar, IconStarOutline, IconHardDrive, IconMusic, IconClock } from '../shared/icons'

const props = defineProps<{ book: Book }>()
const coverLoaded = ref(false)

const hasMetadata = () => props.book.size_mb || props.book.mp3_count || props.book.duration_fmt || props.book.rating

const coverGradient: Record<string, string> = {
  Бизнес: 'linear-gradient(135deg, #92400e 0%, #d97706 50%, #fbbf24 100%)',
  Отношения: 'linear-gradient(135deg, #9d174d 0%, #db2777 50%, #f472b6 100%)',
  Саморазвитие: 'linear-gradient(135deg, #9a5c16 0%, #E8923A 50%, #F0A85C 100%)',
  Художественная: 'linear-gradient(135deg, #155e75 0%, #0891b2 50%, #22d3ee 100%)',
  Языки: 'linear-gradient(135deg, #064e3b 0%, #059669 50%, #34d399 100%)',
}

const coverPattern: Record<string, string> = {
  Бизнес:
    'radial-gradient(circle at 80% 20%, rgba(255,255,255,0.18) 0%, transparent 50%), radial-gradient(circle at 20% 80%, rgba(0,0,0,0.15) 0%, transparent 50%)',
  Отношения:
    'radial-gradient(circle at 20% 30%, rgba(255,255,255,0.15) 0%, transparent 50%), radial-gradient(circle at 80% 70%, rgba(0,0,0,0.15) 0%, transparent 50%)',
  Саморазвитие:
    'radial-gradient(circle at 70% 20%, rgba(255,255,255,0.15) 0%, transparent 50%), radial-gradient(circle at 30% 80%, rgba(0,0,0,0.15) 0%, transparent 50%)',
  Художественная:
    'radial-gradient(circle at 30% 30%, rgba(255,255,255,0.18) 0%, transparent 50%), radial-gradient(circle at 70% 70%, rgba(0,0,0,0.15) 0%, transparent 50%)',
  Языки:
    'radial-gradient(circle at 80% 30%, rgba(255,255,255,0.15) 0%, transparent 50%), radial-gradient(circle at 20% 70%, rgba(0,0,0,0.15) 0%, transparent 50%)',
}

const fallbackGradient = 'linear-gradient(135deg, #78350f 0%, #b45309 50%, #d97706 100%)'
const fallbackPattern = 'radial-gradient(circle at 50% 30%, rgba(255,255,255,0.12) 0%, transparent 50%)'
</script>

<template>
  <div class="card overflow-hidden">
    <!-- Hero gradient banner -->
    <div
      class="relative h-40 overflow-hidden sm:h-48"
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
        style="background: linear-gradient(to bottom, transparent 30%, rgba(0, 0, 0, 0.5) 100%)"
      />

      <!-- Badges on banner -->
      <div class="absolute top-4 right-5 left-5 flex items-start justify-between gap-2">
        <CategoryBadge :category="book.category" />
        <StatusBadge v-if="book.book_status" :book-status="book.book_status" />
      </div>

      <!-- Progress ring on banner (if progress > 0) -->
      <div v-if="book.progress > 0" class="absolute right-5 bottom-4">
        <ProgressRing :percent="book.progress" :size="56" :stroke="4" />
      </div>

      <!-- Title/author on banner bottom -->
      <div class="absolute right-24 bottom-4 left-5">
        <h1
          class="text-[22px] leading-tight font-bold tracking-tight text-white drop-shadow-lg sm:text-[26px]"
          :title="book.title"
        >
          {{ book.title }}
        </h1>
        <p class="mt-1 text-[14px] text-white/70 drop-shadow" :title="book.author">
          {{ book.author }}
          <span v-if="book.reader" class="text-white/50"> · {{ book.reader }}</span>
        </p>
      </div>
    </div>

    <!-- Metadata row -->
    <div v-if="hasMetadata()" class="flex flex-wrap items-center gap-5 border-t border-white/[0.04] px-5 py-4">
      <div v-if="book.size_mb" class="flex items-center gap-2.5">
        <span class="stat-icon" style="background: rgba(232, 146, 58, 0.1)">
          <IconHardDrive :size="14" class="text-[--accent-2]" />
        </span>
        <div>
          <span class="text-[12px] font-semibold text-[--t1]">{{ book.size_mb }} МБ</span>
          <p class="text-[10px] text-[--t3]">Размер</p>
        </div>
      </div>
      <div v-if="book.mp3_count" class="flex items-center gap-2.5">
        <span class="stat-icon" style="background: rgba(6, 182, 212, 0.1)">
          <IconMusic :size="14" class="text-cyan-400" />
        </span>
        <div>
          <span class="text-[12px] font-semibold text-[--t1]">{{ book.mp3_count }}</span>
          <p class="text-[10px] text-[--t3]">Файлов</p>
        </div>
      </div>
      <div v-if="book.duration_fmt" class="flex items-center gap-2.5">
        <span class="stat-icon" style="background: rgba(245, 158, 11, 0.1)">
          <IconClock :size="14" class="text-amber-400" />
        </span>
        <div>
          <span class="text-[12px] font-semibold text-[--t1]">{{ book.duration_fmt }}</span>
          <p class="text-[10px] text-[--t3]">Длительность</p>
        </div>
      </div>
      <div v-if="book.rating" class="ml-auto flex items-center gap-2.5">
        <div class="flex gap-0.5 text-amber-400">
          <template v-for="s in 5" :key="s">
            <component :is="s <= book.rating ? IconStar : IconStarOutline" :size="16" />
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
