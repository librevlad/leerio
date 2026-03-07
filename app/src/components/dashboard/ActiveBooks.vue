<script setup lang="ts">
import { reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ActiveBook } from '../../types'
import { coverUrl } from '../../api'
import ProgressRing from '../shared/ProgressRing.vue'
import StatusBadge from '../shared/StatusBadge.vue'
import { IconMusic } from '../shared/icons'

defineProps<{ books: ActiveBook[] }>()

const { t } = useI18n()
const coverErrors = reactive(new Set<string>())
</script>

<template>
  <div v-if="books.length">
    <h2 class="section-label mb-4">{{ t('dashboard.currentlyListening') }}</h2>
    <div class="fade-mask-r">
      <div class="flex gap-3 overflow-x-auto pb-2">
        <router-link
          v-for="book in books"
          :key="book.id"
          :to="`/book/${book.id}`"
          class="card card-hover relative max-w-[230px] min-w-[210px] flex-shrink-0 overflow-hidden p-5 no-underline"
        >
          <div
            class="absolute top-0 right-0 left-0 h-[2px] rounded-t-xl"
            style="background: var(--gradient-bar); opacity: 0.5"
          />
          <div class="mb-3 flex items-center justify-between">
            <StatusBadge :status="book.list" />
            <ProgressRing :percent="book.progress" :size="36" :stroke="2.5" />
          </div>
          <div class="flex items-start gap-3">
            <img
              v-if="!coverErrors.has(book.id)"
              :src="coverUrl(book.id)"
              :alt="book.title"
              class="h-12 w-12 shrink-0 rounded-lg object-cover"
              loading="lazy"
              @error="coverErrors.add(book.id)"
            />
            <div
              v-else
              class="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg"
              style="background: rgba(232, 146, 58, 0.1)"
            >
              <IconMusic :size="16" class="text-[--t3]" />
            </div>
            <div class="min-w-0">
              <h4 class="line-clamp-2 text-[13px] leading-snug font-semibold text-[--t1]" :title="book.title">
                {{ book.title }}
              </h4>
              <p v-if="book.author" class="mt-1.5 line-clamp-1 text-[12px] text-[--t3]">{{ book.author }}</p>
            </div>
          </div>
        </router-link>
      </div>
    </div>
  </div>
</template>
