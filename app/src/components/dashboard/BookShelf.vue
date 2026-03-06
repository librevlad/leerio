<script setup lang="ts">
import { reactive } from 'vue'
import type { ShelfBook } from '../../types'
import { coverUrl } from '../../api'
import { IconMusic } from '../shared/icons'
import ProgressBar from '../shared/ProgressBar.vue'
import { useCategories } from '../../composables/useCategories'

defineProps<{
  category: string
  count: number
  books: ShelfBook[]
}>()

const coverErrors = reactive(new Set<string>())
const { color: catColor, gradient: catGradient } = useCategories()
</script>

<template>
  <div>
    <div class="mb-3 flex items-center justify-between">
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
      <div class="flex gap-3 overflow-x-auto pb-2">
        <router-link
          v-for="book in books"
          :key="book.id"
          :to="`/book/${book.id}`"
          class="group max-w-[130px] min-w-[130px] flex-shrink-0 no-underline"
        >
          <!-- Cover -->
          <div class="relative mb-2 aspect-square overflow-hidden rounded-xl shadow-lg">
            <img
              v-if="book.has_cover && !coverErrors.has(book.id)"
              :src="coverUrl(book.id)"
              :alt="book.title"
              class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
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
            <!-- Progress overlay -->
            <div
              v-if="book.progress > 0"
              class="absolute right-0 bottom-0 left-0 bg-gradient-to-t from-black/70 to-transparent px-2 pt-4 pb-2"
            >
              <ProgressBar :percent="book.progress" height="h-1" />
            </div>
          </div>
          <!-- Title / Author -->
          <h4
            class="line-clamp-2 text-[12px] leading-tight font-medium text-[--t2] transition-colors group-hover:text-[--t1]"
          >
            {{ book.title }}
          </h4>
          <p class="mt-0.5 line-clamp-1 text-[11px] text-[--t3]">{{ book.author }}</p>
        </router-link>
      </div>
    </div>
  </div>
</template>
