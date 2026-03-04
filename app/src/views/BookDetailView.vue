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

const isCurrentBook = computed(() => player.currentBook.value?.id === book.value?.id)

const isDownloaded = computed(() => (book.value ? dl.isBookDownloaded(book.value.id) : false))
const isDownloading = computed(() => (book.value ? dl.isBookDownloading(book.value.id) : false))
const dlProgress = computed(() => (book.value ? dl.bookDownloadProgress(book.value.id) : null))
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
      class="mb-4 -ml-3 flex min-h-[44px] cursor-pointer items-center gap-2 rounded-xl border-0 bg-transparent px-3 py-2.5 text-[13px] text-[--t3] transition-all hover:bg-white/5 hover:text-[--t1] active:bg-white/8 md:mb-6"
      @click="router.back()"
    >
      <IconArrowLeft :size="15" />
      <span class="font-medium">Назад</span>
    </button>

    <!-- Skeleton -->
    <div v-if="loading">
      <div class="skeleton mb-0 h-48 rounded-t-[20px] rounded-b-none" />
      <div class="skeleton mb-5 h-16 rounded-t-none rounded-b-[20px] border-t-0" />
      <div class="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div class="space-y-5 lg:col-span-2">
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
      <div v-if="book.mp3_count && book.mp3_count > 0" class="mb-5 flex flex-wrap items-center gap-3">
        <button class="btn btn-primary" @click="startListening">
          <IconPlay :size="16" />
          {{ isCurrentBook ? 'Продолжить' : 'Слушать' }}
        </button>

        <!-- Download button (native only) -->
        <template v-if="dl.isNative.value">
          <!-- Not downloaded -->
          <button v-if="!isDownloaded && !isDownloading" class="btn btn-ghost" @click="startDownload">
            <IconDownload :size="16" />
            Скачать
          </button>

          <!-- Downloading -->
          <div v-else-if="isDownloading" class="flex min-w-[200px] flex-1 items-center gap-3">
            <div class="flex-1">
              <div class="mb-1 flex items-center justify-between">
                <span class="text-[11px] text-[--t3]">
                  Трек {{ (dlProgress?.currentTrack ?? 0) + 1 }} из {{ dlProgress?.totalTracks ?? 0 }}
                </span>
                <span class="text-[11px] font-bold text-[--accent]">{{ dlPercent }}%</span>
              </div>
              <ProgressBar :percent="dlPercent" height="h-1.5" />
            </div>
            <button
              class="shrink-0 cursor-pointer border-0 bg-transparent p-1.5 text-[--t3] transition-colors hover:text-red-400"
              title="Отменить"
              @click="cancelDl"
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
              class="shrink-0 cursor-pointer border-0 bg-transparent p-1.5 text-[--t3] transition-colors hover:text-red-400"
              title="Удалить загрузку"
              @click="removeDl"
            >
              <IconTrash :size="15" />
            </button>
          </div>
        </template>
      </div>

      <!-- Audio player (when this book is loaded) -->
      <AudioPlayer v-if="isCurrentBook" class="mb-5" />

      <!-- Two-column layout -->
      <div class="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div class="space-y-5 lg:col-span-2">
          <BookActions
            :card-id="book.card_id"
            :status="book.status"
            :title="book.title"
            :author="book.author"
            :category="book.category"
            @moved="loadBook"
            @card-created="
              (id: string) => {
                book!.card_id = id
                book!.status = 'Прочесть'
              }
            "
          />
          <BookProgress :title="book.title" :progress="book.progress" @updated="(p) => (book!.progress = p)" />
          <BookNotes :title="book.title" :note="book.note" />
          <BookQuotes :book-title="book.title" :book-author="book.author" />
          <BookTags :title="book.title" :tags="book.tags" @updated="(t) => (book!.tags = t)" />
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
