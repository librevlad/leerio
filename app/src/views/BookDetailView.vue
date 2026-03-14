<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import type { Book } from '../types'
import BookInfo from '../components/book/BookInfo.vue'
import BookNotes from '../components/book/BookNotes.vue'
import BookTags from '../components/book/BookTags.vue'
import BookTimeline from '../components/book/BookTimeline.vue'
import BookSimilar from '../components/book/BookSimilar.vue'
import BookActions from '../components/book/BookActions.vue'
import BookQuotes from '../components/book/BookQuotes.vue'
import BookChapters from '../components/book/BookChapters.vue'
import {
  IconArrowLeft,
  IconDownload,
  IconTrash,
  IconCheck,
  IconX,
  IconShare,
  IconBookmark,
} from '../components/shared/icons'
import ProgressBar from '../components/shared/ProgressBar.vue'
import { usePlayer } from '../composables/usePlayer'
import { useDownloads } from '../composables/useDownloads'
import { useToast } from '../composables/useToast'
import { useAuth } from '../composables/useAuth'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const book = ref<Book | null>(null)
const loading = ref(true)

const player = usePlayer()
const dl = useDownloads()
const toast = useToast()
const { isLoggedIn } = useAuth()

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

let loadGeneration = 0

async function loadBook() {
  const gen = ++loadGeneration
  loading.value = true
  try {
    const result = await api.getBook(route.params.id as string)
    if (gen !== loadGeneration) return // stale response from previous navigation
    book.value = result
    if (book.value) document.title = `${book.value.title} — Leerio`
  } catch {
    if (gen !== loadGeneration) return
    router.push('/library')
  } finally {
    if (gen === loadGeneration) loading.value = false
  }
}

async function shareBook() {
  if (!book.value) return
  const url = window.location.href
  if (navigator.share) {
    navigator.share({ title: book.value.title, url }).catch(() => {})
  } else {
    try {
      await navigator.clipboard.writeText(url)
      toast.success(t('book.linkCopied'))
    } catch {
      // Clipboard API unavailable (Firefox/Safari restrictions)
    }
  }
}

async function onRatingChanged(rating: number) {
  if (!book.value) return
  if (!isLoggedIn.value) {
    router.push('/login')
    return
  }
  try {
    await api.setRating(book.value.id, rating)
    book.value.rating = rating
    toast.success(rating ? t('book.ratingSet', { rating }) : t('book.ratingRemoved'))
  } catch {
    toast.error(t('book.ratingError'))
  }
}

const isInLibrary = computed(() => !!book.value?.book_status)

async function addToLibrary() {
  if (!book.value) return
  if (!isLoggedIn.value) {
    router.push('/login')
    return
  }
  try {
    await api.setBookStatus(book.value.id, 'want_to_read')
    book.value.book_status = 'want_to_read'
    toast.success(t('book.addedToLibrary'))
  } catch {
    toast.error(t('book.addError'))
  }
}

async function startListening() {
  if (!book.value) return
  if (!isLoggedIn.value) {
    router.push('/login')
    return
  }
  player.loadBook(book.value)
  // Auto-set status to "reading" if not already in a terminal state
  if (!book.value.book_status || book.value.book_status === 'want_to_read') {
    try {
      await api.setBookStatus(book.value.id, 'reading')
      book.value.book_status = 'reading'
    } catch {
      /* non-critical */
    }
  }
}

onMounted(loadBook)
watch(() => route.params.id, loadBook)
</script>

<template>
  <div>
    <div class="mb-4 flex items-center justify-between md:mb-6">
      <button
        class="-ml-3 flex min-h-[44px] cursor-pointer items-center gap-2 rounded-xl border-0 bg-transparent px-3 py-2.5 text-[13px] text-[--t3] transition-all hover:bg-white/5 hover:text-[--t1] active:bg-white/8"
        @click="router.back()"
      >
        <IconArrowLeft :size="15" />
        <span class="font-medium">{{ t('book.back') }}</span>
      </button>
      <button
        v-if="book"
        class="flex min-h-[44px] cursor-pointer items-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.04] px-3.5 py-2 text-[13px] text-[--t2] transition-all hover:bg-white/[0.08] hover:text-[--t1] active:bg-white/10"
        @click="shareBook"
      >
        <IconShare :size="15" />
        <span class="font-medium">{{ t('book.share') }}</span>
      </button>
    </div>

    <!-- Skeleton -->
    <div v-if="loading">
      <div class="skeleton mb-0 h-48 rounded-t-[20px] rounded-b-none" />
      <div class="skeleton mb-5 h-24 rounded-t-none rounded-b-[20px] border-t-0" />
      <div class="skeleton mb-5 h-14" />
      <div class="skeleton mb-5 h-40" />
      <div class="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div class="space-y-5 lg:col-span-2">
          <div class="skeleton h-24" />
          <div class="skeleton h-28" />
        </div>
        <div class="space-y-5">
          <div class="skeleton h-40" />
          <div class="skeleton h-48" />
        </div>
      </div>
    </div>

    <div v-else-if="book" class="fade-in">
      <!-- 1. Hero card -->
      <BookInfo
        :book="book"
        :is-current-book="isCurrentBook"
        class="mb-5"
        @listen="startListening"
        @rating-changed="onRatingChanged"
      />

      <!-- Login prompt for guests -->
      <div v-if="!isLoggedIn" class="card mb-5 p-6 text-center">
        <p class="text-[16px] font-semibold text-[--t1]">{{ t('book.guestTitle') }}</p>
        <p class="mt-1 text-[13px] text-[--t3]">{{ t('book.guestDesc') }}</p>
        <router-link
          to="/login"
          class="mt-4 inline-flex items-center gap-2 rounded-xl px-6 py-3 text-[14px] font-semibold text-white no-underline"
          style="background: var(--gradient-accent)"
        >
          {{ t('book.guestLogin') }}
        </router-link>
      </div>

      <!-- Add to library (for users without a status set) -->
      <button
        v-if="isLoggedIn && !isInLibrary"
        class="mb-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.04] py-3 text-[14px] font-medium text-[--t2] transition-colors hover:bg-white/[0.08] hover:text-[--t1]"
        @click="addToLibrary"
      >
        <IconBookmark :size="18" />
        {{ t('book.addToLibrary') }}
      </button>

      <!-- 2. Action bar: status pills + download (auth only) -->
      <div v-if="isLoggedIn" class="mb-5 space-y-3">
        <div class="flex flex-wrap items-center gap-3">
          <BookActions :book-id="book.id" :book-status="book.book_status" @status-changed="loadBook" />

          <!-- Download controls (native only) — pushed right -->
          <template v-if="dl.isNative.value && book.mp3_count && book.mp3_count > 0">
            <div class="ml-auto flex items-center">
              <!-- Not downloaded -->
              <button v-if="!isDownloaded && !isDownloading" class="btn btn-ghost" @click="startDownload">
                <IconDownload :size="16" />
                {{ t('book.download') }}
              </button>

              <!-- Downloading -->
              <div v-else-if="isDownloading" class="flex min-w-[200px] items-center gap-3">
                <div class="flex-1">
                  <div class="mb-1 flex items-center justify-between">
                    <span class="text-[11px] text-[--t3]">
                      {{ t('player.trackN', { n: (dlProgress?.currentTrack ?? 0) + 1, total: dlProgress?.totalTracks ?? 0 }) }}
                    </span>
                    <span class="text-[11px] font-bold text-[--accent]">{{ dlPercent }}%</span>
                  </div>
                  <ProgressBar :percent="dlPercent" height="h-1.5" />
                </div>
                <button
                  class="shrink-0 cursor-pointer border-0 bg-transparent p-1.5 text-[--t3] transition-colors hover:text-red-400"
                  :title="t('book.cancelDownload')"
                  @click="cancelDl"
                >
                  <IconX :size="16" />
                </button>
              </div>

              <!-- Downloaded -->
              <div v-else class="flex items-center gap-2">
                <span class="flex items-center gap-1.5 text-[13px] font-medium text-emerald-400">
                  <IconCheck :size="16" />
                  {{ t('book.downloaded') }}
                </span>
                <button
                  class="shrink-0 cursor-pointer border-0 bg-transparent p-1.5 text-[--t3] transition-colors hover:text-red-400"
                  :title="t('book.deleteDownload')"
                  @click="removeDl"
                >
                  <IconTrash :size="15" />
                </button>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- 3. Chapters (auth only) -->
      <BookChapters v-if="isLoggedIn && book.mp3_count && book.mp3_count > 0" :book="book" class="mb-5" />

      <!-- 5. Two-column layout -->
      <div class="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div v-if="isLoggedIn" class="space-y-5 lg:col-span-2">
          <BookNotes :book-id="book.id" :title="book.title" :note="book.note" />
          <BookQuotes :book-title="book.title" :book-author="book.author" />
        </div>
        <div :class="isLoggedIn ? 'space-y-5' : 'space-y-5 lg:col-span-3'">
          <BookTags
            v-if="isLoggedIn"
            :book-id="book.id"
            :title="book.title"
            :tags="book.tags"
            @updated="(t) => (book!.tags = t)"
          />
          <BookTimeline v-if="isLoggedIn" :entries="book.timeline || []" />
          <BookSimilar :book-id="book.id" />
        </div>
      </div>
    </div>
  </div>
</template>
