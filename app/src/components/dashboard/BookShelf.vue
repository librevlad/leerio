<script setup lang="ts">
import { reactive } from 'vue'
import type { ShelfBook } from '../../types'
import { coverUrl } from '../../api'
import { IconMusic, IconCheck, IconPause, IconPlay } from '../shared/icons'
import ProgressBar from '../shared/ProgressBar.vue'
import { useCategories } from '../../composables/useCategories'

defineProps<{
  category: string
  count: number
  books: ShelfBook[]
}>()

const coverErrors = reactive(new Set<string>())
const { color: catColor, gradient: catGradient } = useCategories()

const statusBadge: Record<string, { icon: unknown; bg: string; fg: string }> = {
  done: { icon: IconCheck, bg: 'rgba(52, 211, 153, 0.85)', fg: '#fff' },
  reading: { icon: IconPlay, bg: 'rgba(192, 132, 252, 0.85)', fg: '#fff' },
  paused: { icon: IconPause, bg: 'rgba(250, 204, 21, 0.85)', fg: '#fff' },
}
</script>

<template>
  <div>
    <div class="mb-4 flex items-center justify-between">
      <h2 class="section-label flex items-center gap-2">
        <span class="inline-block h-2 w-2 rounded-full" :style="{ background: catColor(category) }" />
        {{ category }}
        <span class="font-normal text-[--t3]">({{ count }})</span>
      </h2>
      <router-link
        :to="`/library?category=${encodeURIComponent(category)}`"
        class="inline-flex min-h-[44px] items-center text-[12px] font-medium text-[--accent] no-underline hover:underline"
      >
        Показать все
      </router-link>
    </div>
    <div class="fade-mask-r">
      <div class="flex gap-4 overflow-x-auto pb-2">
        <router-link
          v-for="book in books"
          :key="book.id"
          :to="`/book/${book.id}`"
          class="group max-w-[160px] min-w-[160px] flex-shrink-0 no-underline"
        >
          <!-- Cover -->
          <div class="relative aspect-square overflow-hidden rounded-2xl shadow-md">
            <img
              v-if="book.has_cover && !coverErrors.has(book.id)"
              :src="coverUrl(book.id)"
              :alt="book.title"
              class="h-full w-full object-cover transition-transform duration-150 group-hover:scale-[1.03]"
              loading="lazy"
              @error="coverErrors.add(book.id)"
            />
            <div
              v-else
              class="flex h-full w-full items-center justify-center"
              :style="{ background: catGradient(book.category) }"
            >
              <IconMusic :size="28" class="text-white/40" />
            </div>
            <!-- Status badge -->
            <div
              v-if="book.book_status && statusBadge[book.book_status]"
              class="absolute top-2 right-2 flex h-5 w-5 items-center justify-center rounded-full shadow-sm"
              :style="{ background: statusBadge[book.book_status]!.bg }"
            >
              <component
                :is="statusBadge[book.book_status]!.icon"
                :size="10"
                :style="{ color: statusBadge[book.book_status]!.fg }"
              />
            </div>
            <!-- Progress overlay -->
            <div
              v-if="book.progress > 0"
              class="absolute right-0 bottom-0 left-0 bg-gradient-to-t from-black/70 to-transparent px-2.5 pt-5 pb-2.5"
            >
              <ProgressBar :percent="book.progress" height="h-1" />
            </div>
          </div>
          <!-- Title / Author -->
          <h4
            class="mt-2.5 line-clamp-2 text-[13px] leading-tight font-medium text-[--t2] transition-colors group-hover:text-[--t1]"
          >
            {{ book.title }}
          </h4>
          <p class="mt-0.5 line-clamp-1 text-[11px] text-[--t3]">{{ book.author }}</p>
        </router-link>
      </div>
    </div>
  </div>
</template>
