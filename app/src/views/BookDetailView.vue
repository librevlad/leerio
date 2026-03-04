<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import type { Book } from '../types'
import BookInfo from '../components/book/BookInfo.vue'
import BookProgress from '../components/book/BookProgress.vue'
import BookNotes from '../components/book/BookNotes.vue'
import BookTags from '../components/book/BookTags.vue'
import BookTimeline from '../components/book/BookTimeline.vue'
import BookSimilar from '../components/book/BookSimilar.vue'
import BookActions from '../components/book/BookActions.vue'
import BookQuotes from '../components/book/BookQuotes.vue'
import BookFolder from '../components/book/BookFolder.vue'
import AudioPlayer from '../components/player/AudioPlayer.vue'
import { IconArrowLeft, IconPlay, IconDownload, IconTrash, IconCheck, IconX } from '../components/shared/icons'
import ProgressBar from '../components/shared/ProgressBar.vue'
import { usePlayer } from '../composables/usePlayer'
import { useDownloads } from '../composables/useDownloads'

const route = useRoute()
const router = useRouter()
const book = ref<Book | null>(null)
const loading = ref(true)

const player = usePlayer()
const dl = useDownloads()

const isCurrentBook = computed(() =>
  player.currentBook.value?.id === book.value?.id
)

const isDownloaded = computed(() => book.value ? dl.isBookDownloaded(book.value.id) : false)
const isDownloading = computed(() => book.value ? dl.isBookDownloading(book.value.id) : false)
const dlProgress = computed(() => book.value ? dl.bookDownloadProgress(book.value.id) : null)
const dlPercent = computed(() => {
  const p = dlProgress.value
  if (!p || p.bytesTotal === 0) return 0
  return Math.round((p.bytesDownloaded / p.bytesTotal) * 100)
})

async function startDownload() {
  if (!book.value) return
  const res = await api.getBookTracks(book.value.id)
  dl.downloadBook(book.value, res.tracks)
}

function cancelDl() {
  if (book.value) dl.cancelDownload(book.value.id)
}

async function removeDl() {
  if (book.value) await dl.deleteBook(book.value.id)
}

async function loadBook() {
  loading.value = true
  try {
    book.value = await api.getBook(route.params.id as string)
  } catch {
    router.push('/library')
  } finally {
    loading.value = false
  }
}

function startListening() {
  if (book.value) player.loadBook(book.value)
}

onMounted(loadBook)
</script>

<template>
  <div>
    <button
      class="flex items-center gap-2 text-[13px] mb-4 md:mb-6 text-[--t3] hover:text-[--t1] transition-all cursor-pointer bg-transparent border-0 px-3 py-2.5 -ml-3 rounded-xl hover:bg-white/5 active:bg-white/8 min-h-[44px]"
      @click="router.back()"
    >
      <IconArrowLeft :size="15" />
      <span class="font-medium">Назад</span>
    </button>

    <!-- Skeleton -->
    <div v-if="loading">
      <div class="skeleton h-48 rounded-t-[20px] rounded-b-none mb-0" />
      <div class="skeleton h-16 rounded-t-none rounded-b-[20px] border-t-0 mb-5" />
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div class="lg:col-span-2 space-y-5">
          <div class="skeleton h-14" />
          <div class="skeleton h-24" />
          <div class="skeleton h-28" />
        </div>
        <div class="space-y-5">
          <div class="skeleton h-40" />
          <div class="skeleton h-48" />
        </div>
      </div>
    </div>

    <div v-else-if="book">
      <!-- Hero card spans full width -->
      <BookInfo :book="book" class="mb-5" />

      <!-- Listen button + Download -->
      <div v-if="book.mp3_count && book.mp3_count > 0" class="flex flex-wrap items-center gap-3 mb-5">
        <button
          class="btn btn-primary"
          @click="startListening"
        >
          <IconPlay :size="16" />
          {{ isCurrentBook ? 'Продолжить' : 'Слушать' }}
        </button>

        <!-- Download button (native only) -->
        <template v-if="dl.isNative.value">
          <!-- Not downloaded -->
          <button
            v-if="!isDownloaded && !isDownloading"
            class="btn btn-ghost"
            @click="startDownload"
          >
            <IconDownload :size="16" />
            Скачать
          </button>

          <!-- Downloading -->
          <div v-else-if="isDownloading" class="flex items-center gap-3 flex-1 min-w-[200px]">
            <div class="flex-1">
              <div class="flex items-center justify-between mb-1">
                <span class="text-[11px] text-[--t3]">
                  Трек {{ (dlProgress?.currentTrack ?? 0) + 1 }} из {{ dlProgress?.totalTracks ?? 0 }}
                </span>
                <span class="text-[11px] font-bold text-[--accent]">{{ dlPercent }}%</span>
              </div>
              <ProgressBar :percent="dlPercent" height="h-1.5" />
            </div>
            <button
              class="p-1.5 bg-transparent border-0 text-[--t3] hover:text-red-400 transition-colors cursor-pointer shrink-0"
              @click="cancelDl"
              title="Отменить"
            >
              <IconX :size="16" />
            </button>
          </div>

          <!-- Downloaded -->
          <div v-else class="flex items-center gap-2">
            <span class="flex items-center gap-1.5 text-[13px] font-medium text-emerald-400">
              <IconCheck :size="16" />
              Загружено
            </span>
            <button
              class="p-1.5 bg-transparent border-0 text-[--t3] hover:text-red-400 transition-colors cursor-pointer shrink-0"
              @click="removeDl"
              title="Удалить загрузку"
            >
              <IconTrash :size="15" />
            </button>
          </div>
        </template>
      </div>

      <!-- Audio player (when this book is loaded) -->
      <AudioPlayer v-if="isCurrentBook" class="mb-5" />

      <!-- Two-column layout -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div class="lg:col-span-2 space-y-5">
          <BookActions
            :card-id="book.card_id"
            :status="book.status"
            :title="book.title"
            :author="book.author"
            :category="book.category"
            @moved="loadBook"
            @card-created="(id: string) => { book!.card_id = id; book!.status = 'Прочесть' }"
          />
          <BookProgress :title="book.title" :progress="book.progress" @updated="(p) => book!.progress = p" />
          <BookNotes :title="book.title" :note="book.note" />
          <BookQuotes :book-title="book.title" :book-author="book.author" />
          <BookTags :title="book.title" :tags="book.tags" @updated="(t) => book!.tags = t" />
        </div>
        <div class="space-y-5">
          <BookTimeline :entries="book.timeline || []" />
          <BookSimilar :book-id="book.id" />
          <BookFolder v-if="book.folder" :folder="book.folder" :path="book.path" />
        </div>
      </div>
    </div>
  </div>
</template>
