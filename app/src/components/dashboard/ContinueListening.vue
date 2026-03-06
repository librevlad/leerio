<script setup lang="ts">
import { reactive } from 'vue'
import type { ActiveBook } from '../../types'
import { coverUrl } from '../../api'
import ProgressBar from '../shared/ProgressBar.vue'
import { IconMusic, IconPlay } from '../shared/icons'

defineProps<{ books: ActiveBook[] }>()

const coverErrors = reactive(new Set<string>())

const coverGradient: Record<string, string> = {
  Бизнес: 'linear-gradient(135deg, #92400e 0%, #d97706 100%)',
  Личные: 'linear-gradient(135deg, #4c1d95 0%, #7c3aed 100%)',
  Отношения: 'linear-gradient(135deg, #9d174d 0%, #db2777 100%)',
  Саморазвитие: 'linear-gradient(135deg, #9a5c16 0%, #E8923A 100%)',
  Художественная: 'linear-gradient(135deg, #155e75 0%, #0891b2 100%)',
  Языки: 'linear-gradient(135deg, #064e3b 0%, #059669 100%)',
}
const fallbackGradient = 'linear-gradient(135deg, #1e1b4b 0%, #312e81 100%)'
</script>

<template>
  <div v-if="books.length">
    <h2 class="section-label mb-4">Продолжить слушать</h2>
    <div class="fade-mask-r">
      <div class="flex gap-3 overflow-x-auto pb-2">
        <router-link
          v-for="book in books"
          :key="book.id"
          :to="`/book/${book.id}`"
          class="group relative max-w-[300px] min-w-[260px] flex-shrink-0 overflow-hidden rounded-2xl no-underline sm:min-w-[300px]"
          style="
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.04) 0%, rgba(255, 255, 255, 0.01) 100%);
            border: 1px solid rgba(255, 255, 255, 0.06);
          "
        >
          <div class="flex items-center gap-4 p-4">
            <!-- Cover -->
            <div class="relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-xl shadow-lg">
              <img
                v-if="!coverErrors.has(book.id)"
                :src="coverUrl(book.id)"
                :alt="book.title"
                class="h-full w-full object-cover"
                loading="lazy"
                @error="coverErrors.add(book.id)"
              />
              <div
                v-else
                class="flex h-full w-full items-center justify-center"
                :style="{ background: coverGradient[(book as any).category] || fallbackGradient }"
              >
                <IconMusic :size="24" class="text-white/40" />
              </div>
              <!-- Play button overlay -->
              <div
                class="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 transition-opacity group-hover:opacity-100"
              >
                <div class="flex h-10 w-10 items-center justify-center rounded-full bg-[--accent] text-white shadow-lg">
                  <IconPlay :size="18" />
                </div>
              </div>
            </div>

            <!-- Info -->
            <div class="min-w-0 flex-1">
              <h3
                class="line-clamp-2 text-[14px] leading-snug font-semibold text-[--t1] transition-colors group-hover:text-white"
              >
                {{ book.title }}
              </h3>
              <p v-if="book.author" class="mt-1 line-clamp-1 text-[12px] text-[--t3]">
                {{ book.author }}
              </p>
              <div v-if="book.progress > 0" class="mt-2.5">
                <div class="mb-1 flex items-center justify-between">
                  <span class="text-[11px] text-[--t3]">{{ book.progress }}%</span>
                </div>
                <ProgressBar :percent="book.progress" height="h-1" />
              </div>
            </div>
          </div>
        </router-link>
      </div>
    </div>
  </div>
</template>
