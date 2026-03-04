<script setup lang="ts">
import type { TrelloCard } from '../../types'
import ProgressRing from '../shared/ProgressRing.vue'
import StatusBadge from '../shared/StatusBadge.vue'

defineProps<{ books: TrelloCard[] }>()
</script>

<template>
  <div v-if="books.length">
    <h2 class="section-label mb-4">Сейчас слушаю</h2>
    <div class="fade-mask-r">
      <div class="flex gap-3 overflow-x-auto pb-2">
        <router-link
          v-for="book in books"
          :key="book.id"
          :to="`/book/${book.id}`"
          class="card card-hover p-5 min-w-[210px] max-w-[230px] flex-shrink-0 no-underline relative overflow-hidden"
        >
          <div class="absolute top-0 left-0 right-0 h-[2px] rounded-t-xl" style="background: var(--gradient-bar); opacity: 0.5" />
          <div class="flex items-center justify-between mb-3">
            <StatusBadge :status="book.list" />
            <ProgressRing :percent="book.progress" :size="36" :stroke="2.5" />
          </div>
          <h4 class="text-[13px] font-semibold line-clamp-2 text-[--t1] leading-snug" :title="book.title">
            {{ book.title }}
          </h4>
          <p class="text-[12px] mt-1.5 line-clamp-1 text-[--t3]">{{ book.author }}</p>
        </router-link>
      </div>
    </div>
  </div>
</template>
