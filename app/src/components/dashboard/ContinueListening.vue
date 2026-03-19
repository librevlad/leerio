<script setup lang="ts">
import { reactive, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ActiveBook } from '../../types'
import { coverUrl } from '../../api'
import ProgressBar from '../shared/ProgressBar.vue'
import { IconMusic, IconPlay } from '../shared/icons'
import { useCategories } from '../../composables/useCategories'
import { usePlayer } from '../../composables/usePlayer'
import { useToast } from '../../composables/useToast'
import { api } from '../../api'

const props = defineProps<{ books: ActiveBook[] }>()

const { t } = useI18n()
const toast = useToast()
const activeBooks = computed(() => props.books.filter((b) => b.progress > 0))
const { currentBook, loadBook, togglePlay } = usePlayer()
const nowPlayingId = computed(() => currentBook.value?.id ?? null)

const coverErrors = reactive(new Set<string>())
const { gradient: catGradient } = useCategories()

function formatRemaining(totalHours: number, progress: number): string {
  const remaining = totalHours * (1 - progress / 100)
  if (remaining < 1 / 60) return `< 1 ${t('common.unitMin')}`
  if (remaining < 1) return `${Math.round(remaining * 60)} ${t('common.unitMin')}`
  const h = Math.floor(remaining)
  const m = Math.round((remaining - h) * 60)
  return m > 0 ? `${h}${t('common.unitH')} ${m}${t('common.unitM')}` : `${h}${t('common.unitH')}`
}

async function playBook(bookId: string) {
  if (nowPlayingId.value === bookId) {
    togglePlay()
  } else {
    try {
      const book = await api.getBook(bookId)
      loadBook(book)
    } catch {
      toast.error(t('player.tracksLoadError'))
    }
  }
}
</script>

<template>
  <div v-if="books.length">
    <h2 class="section-label mb-4">{{ t('dashboard.continueListening') }}</h2>
    <div v-if="activeBooks.length" class="fade-mask-r">
      <div class="flex gap-4 overflow-x-auto pb-2">
        <div
          v-for="book in activeBooks"
          :key="book.id"
          class="card group relative max-w-[320px] min-w-[280px] flex-shrink-0 overflow-hidden sm:min-w-[320px]"
        >
          <router-link :to="`/book/${book.id}`" class="flex items-center gap-4 p-4 no-underline">
            <!-- Cover -->
            <div class="relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-xl shadow-md">
              <img
                v-if="book.has_cover !== false && !coverErrors.has(book.id)"
                :src="coverUrl(book.id)"
                :alt="book.title"
                class="h-full w-full object-cover"
                loading="lazy"
                @error="coverErrors.add(book.id)"
              />
              <div
                v-else
                class="flex h-full w-full items-center justify-center"
                :style="{ background: catGradient(book.category ?? '') }"
              >
                <IconMusic :size="24" class="text-white/40" />
              </div>
            </div>

            <!-- Info -->
            <div class="min-w-0 flex-1">
              <h3 class="line-clamp-2 text-[14px] leading-snug font-semibold text-[--t1]">
                <span
                  v-if="nowPlayingId === book.id"
                  class="mr-1 inline-flex items-center gap-1 align-middle text-[10px] font-bold tracking-wide text-[--accent]"
                >
                  <span class="now-playing-bars inline-flex items-end gap-px"> <span /><span /><span /> </span>
                </span>
                {{ book.title }}
              </h3>
              <p v-if="book.author" class="mt-1 line-clamp-1 text-[12px] text-[--t3]">{{ book.author }}</p>
              <div class="mt-2.5">
                <div class="mb-1 flex items-center justify-between">
                  <span class="text-[11px] text-[--t3]">{{ book.progress }}%</span>
                  <span v-if="book.duration_hours && book.progress < 100" class="text-[10px] text-[--t3]">
                    {{ formatRemaining(book.duration_hours, book.progress) }} {{ t('common.remaining') }}
                  </span>
                </div>
                <ProgressBar :percent="book.progress" height="h-1" />
              </div>
            </div>
          </router-link>

          <!-- Play button -->
          <button
            class="absolute right-3 bottom-3 flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border-0 shadow-lg transition-transform duration-150 hover:scale-110"
            style="background: var(--gradient-accent)"
            :aria-label="nowPlayingId === book.id ? t('book.pauseAria') : t('book.continueAria')"
            @click.prevent="playBook(book.id)"
          >
            <IconPlay :size="14" style="color: #fff" />
          </button>
        </div>
      </div>
    </div>
    <p v-else class="text-sm text-[--t3]">{{ t('dashboard.startListening') }}</p>
  </div>
</template>
