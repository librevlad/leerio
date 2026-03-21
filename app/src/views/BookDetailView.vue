<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api, coverUrl } from '../api'
import { formatSizeMB, formatRemaining as _formatRemaining } from '../utils/format'
import type { Book } from '../types'
import BookActions from '../components/book/BookActions.vue'
import BookChapters from '../components/book/BookChapters.vue'
import {
  IconArrowLeft,
  IconDownload,
  IconTrash,
  IconCheck,
  IconX,
  IconBookmark,
  IconPlay,
  IconPause,
  IconMusic,
  IconCloud,
  IconSmartphone,
} from '../components/shared/icons'
import ProgressBar from '../components/shared/ProgressBar.vue'
import PaywallModal from '../components/shared/PaywallModal.vue'
import { usePlayer } from '../composables/usePlayer'
import { useDownloads } from '../composables/useDownloads'
import { useAuth } from '../composables/useAuth'
import { useCategories } from '../composables/useCategories'
import { useLocalData } from '../composables/useLocalData'
import { useToast } from '../composables/useToast'
import { useFileScanner } from '../composables/useFileScanner'
import { Filesystem, Directory } from '@capacitor/filesystem'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const book = ref<Book | null>(null)
const loading = ref(true)
const coverError = ref(false)

const player = usePlayer()
const dl = useDownloads()
const { isLoggedIn, user } = useAuth()
const { gradient: catGradient } = useCategories()
const local = useLocalData()
const toast = useToast()
const { getFsBook, markSynced } = useFileScanner()

const isLocalBook = computed(() => {
  const id = book.value?.id
  return id?.startsWith('fs:') || id?.startsWith('lb:')
})

const isSynced = computed(() => {
  const id = book.value?.id
  if (!id?.startsWith('fs:')) return false
  return getFsBook(id)?.synced ?? false
})

const isPremium = computed(() => user.value?.plan === 'premium')

const showPaywall = ref(false)
const cloudUploading = ref(false)
const cloudProgress = ref(0)

const isCurrentBook = computed(() => player.currentBook.value?.id === book.value?.id)
const isPlaying = computed(() => player.isPlaying.value)

const isDownloaded = computed(() => (book.value ? dl.isBookDownloaded(book.value.id) : false))
const isDownloading = computed(() => (book.value ? dl.isBookDownloading(book.value.id) : false))
const dlProgress = computed(() => (book.value ? dl.bookDownloadProgress(book.value.id) : null))
const dlPercent = computed(() => {
  const p = dlProgress.value
  if (!p || p.bytesTotal === 0) return 0
  return Math.round((p.bytesDownloaded / p.bytesTotal) * 100)
})

const coverSrc = computed(() => {
  if (!book.value) return ''
  const id = book.value.id
  if (id.startsWith('lb:') || id.startsWith('ub:')) return ''
  return book.value.has_cover ? coverUrl(id) : ''
})

const isInLibrary = computed(() => !!book.value?.book_status)

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
  coverError.value = false

  const id = route.params.id as string

  // Filesystem book — load from local scanner storage, no API call
  if (id.startsWith('fs:')) {
    const fsMeta = getFsBook(id)
    if (!fsMeta) {
      toast.error(t('book.fsNotFound'))
      router.push('/library')
      return
    }
    book.value = {
      id: fsMeta.id,
      title: fsMeta.title,
      author: fsMeta.author,
      folder: fsMeta.folderPath,
      category: '',
      reader: '',
      path: '',
      progress: 0,
      tags: [],
      note: '',
      mp3_count: fsMeta.tracks.length,
    }
    document.title = `${fsMeta.title} — Leerio`
    loading.value = false
    return
  }

  try {
    const result = await api.getBook(id)
    if (gen !== loadGeneration) return
    book.value = result
    if (book.value) document.title = `${book.value.title} — Leerio`
  } catch {
    if (gen !== loadGeneration) return
    router.push('/library')
  } finally {
    if (gen === loadGeneration) loading.value = false
  }
}

async function addToLibrary() {
  if (!book.value) return
  if (!isLoggedIn.value) {
    toast.info(t('book.loginToListen'))
    return router.push('/login')
  }
  try {
    local.setBookStatus(book.value.id, 'want_to_read').catch(() => {})
    await api.setBookStatus(book.value.id, 'want_to_read')
    book.value.book_status = 'want_to_read'
  } catch {
    toast.error(t('common.error'))
  }
}

async function startListening() {
  if (!book.value) return
  // Allow local books (fs: / lb:) without login
  if (!isLoggedIn.value && !book.value.id.startsWith('fs:') && !book.value.id.startsWith('lb:')) {
    toast.info(t('book.loginToListen'))
    return router.push('/login')
  }
  player.loadBook(book.value)
  if (!book.value.book_status || book.value.book_status === 'want_to_read') {
    try {
      local.setBookStatus(book.value.id, 'reading').catch(() => {})
      await api.setBookStatus(book.value.id, 'reading')
      book.value.book_status = 'reading'
    } catch {
      toast.error(t('common.error'))
    }
  }
}

function formatDuration(hours: number | undefined): string {
  if (!hours) return ''
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  return h > 0 ? `${h}${t('common.unitH')} ${m}${t('common.unitM')}` : `${m} ${t('common.unitMin')}`
}

function formatRemaining(totalHours: number, progress: number): string {
  return _formatRemaining(totalHours, progress, t)
}

async function cloudUpload() {
  if (!isPremium.value) {
    showPaywall.value = true
    return
  }
  if (!book.value || cloudUploading.value) return

  const fsBook = getFsBook(book.value.id)
  if (!fsBook) return

  // Warn if total size is very large
  if (fsBook.sizeBytes > 200_000_000) {
    if (!confirm(t('book.cloudUploadLarge'))) return
  }

  cloudUploading.value = true
  cloudProgress.value = 0

  try {
    const formData = new FormData()
    formData.append('title', fsBook.title)
    formData.append('author', fsBook.author)

    for (let i = 0; i < fsBook.tracks.length; i++) {
      const track = fsBook.tracks[i]!
      const result = await Filesystem.readFile({
        path: track.path,
        directory: Directory.ExternalStorage,
      })
      const blob =
        typeof result.data === 'string'
          ? new Blob([Uint8Array.from(atob(result.data), (c) => c.charCodeAt(0))])
          : new Blob([result.data])
      formData.append('files', new File([blob], track.filename, { type: 'audio/mpeg' }))
      cloudProgress.value = Math.round(((i + 1) / fsBook.tracks.length) * 50)
    }

    await api.cloudSyncBook(formData)
    markSynced(book.value.id)
    cloudProgress.value = 100
    toast.success(t('book.cloudUploadDone'))
  } catch {
    toast.error(t('book.cloudUploadFailed'))
  } finally {
    cloudUploading.value = false
  }
}

onMounted(loadBook)
watch(() => route.params.id, loadBook)
</script>

<template>
  <div>
    <!-- Back -->
    <div class="mb-4 flex items-center lg:mb-6">
      <button
        class="-ml-3 flex min-h-[44px] cursor-pointer items-center gap-2 rounded-xl border-0 bg-transparent px-3 py-2.5 text-[13px] text-[--t3] transition-all hover:bg-white/5 hover:text-[--t1]"
        @click="router.back()"
      >
        <IconArrowLeft :size="15" />
        <span class="font-medium">{{ book?.category || t('book.back') }}</span>
      </button>
    </div>

    <!-- Skeleton -->
    <div v-if="loading">
      <div class="flex gap-5">
        <div class="skeleton h-[120px] w-[120px] rounded-2xl lg:h-[200px] lg:w-[200px]" />
        <div class="flex-1 space-y-3">
          <div class="skeleton h-6 w-3/4" />
          <div class="skeleton h-4 w-1/2" />
          <div class="skeleton h-12 w-full rounded-xl" />
        </div>
      </div>
    </div>

    <div v-else-if="book" class="fade-in">
      <!-- Desktop: sidebar layout / Mobile: stacked -->
      <div class="flex flex-col gap-5 lg:flex-row lg:gap-8">
        <!-- Sidebar (desktop: sticky, mobile: top section) -->
        <div class="lg:sticky lg:top-8 lg:w-[260px] lg:shrink-0 lg:self-start">
          <!-- Mobile: horizontal layout -->
          <div class="flex gap-4 lg:flex-col lg:gap-0">
            <!-- Cover -->
            <router-link
              :to="`/book/${book.id}`"
              class="relative h-[120px] w-[120px] shrink-0 overflow-hidden rounded-2xl shadow-lg lg:mx-auto lg:h-[200px] lg:w-[200px]"
              style="box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4)"
            >
              <img
                v-if="coverSrc && !coverError"
                :src="coverSrc"
                :alt="book.title"
                class="h-full w-full object-cover"
                @error="coverError = true"
              />
              <div
                v-else
                class="flex h-full w-full items-center justify-center"
                :style="{ background: catGradient(book.category ?? '') }"
              >
                <IconMusic :size="32" class="text-white/40 lg:!h-12 lg:!w-12" />
              </div>
            </router-link>

            <!-- Mobile: info next to cover -->
            <div class="flex min-w-0 flex-1 flex-col justify-center lg:mt-4 lg:text-center">
              <h1 class="line-clamp-3 text-[18px] leading-tight font-bold text-[--t1] lg:text-[20px]">
                {{ book.title }}
              </h1>
              <p class="mt-1 text-[13px] text-[--t3]">{{ book.author }}</p>
            </div>
          </div>

          <!-- Progress card -->
          <div
            v-if="book.progress > 0 || isCurrentBook"
            class="mt-4 rounded-xl px-4 py-3"
            style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.04)"
          >
            <div class="flex items-center justify-between text-[12px]">
              <span class="font-semibold text-[--t1]">{{ book.progress }}%</span>
              <span v-if="book.duration_hours" class="text-[--t3]">
                {{ formatRemaining(book.duration_hours, book.progress) }} {{ t('common.remaining') }}
              </span>
            </div>
            <div class="mt-2">
              <ProgressBar :percent="book.progress" height="h-1" />
            </div>
          </div>

          <!-- Play button -->
          <button
            class="mt-3 flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl border-0 py-3 text-[14px] font-bold text-white transition-all hover:brightness-110"
            style="
              background: linear-gradient(135deg, #ff8a00, #e07000);
              box-shadow: 0 4px 16px rgba(255, 138, 0, 0.25);
            "
            @click="startListening"
          >
            <component :is="isCurrentBook && isPlaying ? IconPause : IconPlay" :size="16" />
            {{ isCurrentBook && isPlaying ? t('player.pause') : t('player.play') }}
          </button>

          <!-- Actions (desktop only, below play) -->
          <div class="mt-3 hidden flex-col gap-2 lg:flex">
            <!-- Add to library -->
            <button
              v-if="isLoggedIn && !isInLibrary"
              class="flex w-full cursor-pointer items-center gap-2 rounded-lg border-0 px-3 py-2 text-[12px] text-[--t2] transition-colors hover:bg-white/5"
              style="background: rgba(255, 255, 255, 0.03)"
              @click="addToLibrary"
            >
              <IconBookmark :size="14" />
              {{ t('book.addToLibrary') }}
            </button>

            <!-- Download (native) -->
            <template v-if="dl.isNative.value && book.mp3_count && book.mp3_count > 0">
              <button
                v-if="!isDownloaded && !isDownloading"
                v-ripple
                class="flex w-full cursor-pointer items-center gap-2 rounded-lg border-0 px-3 py-2 text-[12px] text-[--t2] transition-colors hover:bg-white/5"
                style="background: rgba(255, 255, 255, 0.03)"
                @click="startDownload"
              >
                <IconDownload :size="14" />
                {{ t('book.download') }}
              </button>
              <div v-else-if="isDownloading" class="px-3 py-2">
                <ProgressBar :percent="dlPercent" height="h-1" />
                <div class="mt-1 flex items-center justify-between text-[11px] text-[--t3]">
                  <span>{{ dlPercent }}%</span>
                  <button
                    class="cursor-pointer border-0 bg-transparent text-[--t3] hover:text-red-400"
                    @click="cancelDl"
                  >
                    <IconX :size="12" />
                  </button>
                </div>
              </div>
              <div v-else class="flex items-center gap-2 px-3 py-2 text-[12px] text-emerald-400">
                <IconCheck :size="14" />
                {{ t('book.downloaded') }}
                <button
                  class="ml-auto cursor-pointer border-0 bg-transparent text-[--t3] hover:text-red-400"
                  @click="removeDl"
                >
                  <IconTrash :size="12" />
                </button>
              </div>
            </template>
          </div>

          <!-- Device badge + Cloud upload -->
          <div v-if="isLocalBook" class="mt-3 space-y-2">
            <div
              class="inline-flex items-center gap-1.5 rounded-md bg-white/[0.06] px-2.5 py-1 text-[11px] text-[--t3]"
            >
              <IconSmartphone :size="12" />
              {{ isSynced ? t('book.inCloud') : t('book.onDevice') }}
            </div>

            <button
              v-if="!isSynced"
              v-ripple
              class="flex w-full items-center justify-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.05] px-4 py-3 text-[13px] font-semibold text-[--t1]"
              :disabled="cloudUploading"
              @click="cloudUpload"
            >
              <template v-if="cloudUploading">
                <div class="h-4 w-4 animate-spin rounded-full border-2 border-[--accent] border-t-transparent" />
                {{ cloudProgress }}%
              </template>
              <template v-else>
                <IconCloud :size="16" />
                {{ t('book.uploadToCloud') }}
              </template>
            </button>
            <p v-if="!isSynced" class="text-center text-[10px] text-[--t3]">
              {{ t('book.cloudHint') }}
            </p>
          </div>

          <PaywallModal :open="showPaywall" @close="showPaywall = false" />

          <!-- Meta (desktop) -->
          <div class="mt-4 hidden space-y-2 border-t border-white/[0.04] pt-4 text-[12px] text-[--t3] lg:block">
            <p v-if="book.duration_hours">{{ formatDuration(book.duration_hours) }}</p>
            <p v-if="book.mp3_count">{{ book.mp3_count }} {{ t('book.tracks') }}</p>
            <p v-if="book.size_mb">{{ formatSizeMB(book.size_mb, t) }}</p>
          </div>
        </div>

        <!-- Main content -->
        <div class="min-w-0 flex-1">
          <!-- Mobile: status pills + add to library -->
          <div class="mb-4 lg:hidden">
            <div class="flex flex-wrap items-center gap-2">
              <BookActions :book-id="book.id" :book-status="book.book_status" @status-changed="loadBook" />
            </div>
          </div>

          <!-- Chapters -->
          <BookChapters v-if="book.mp3_count && book.mp3_count > 0" :book="book" />

          <!-- Description -->
          <div class="mt-6">
            <div v-if="book.description" class="text-[13px] leading-relaxed text-[--t2]">
              {{ book.description }}
            </div>
            <p v-else class="text-[13px] text-[--t3]">{{ t('book.noDescription') }}</p>

            <!-- Meta (mobile only) -->
            <div class="mt-4 flex gap-3 text-[12px] text-[--t3] lg:hidden">
              <span v-if="book.duration_hours">{{ formatDuration(book.duration_hours) }}</span>
              <span v-if="book.mp3_count">{{ book.mp3_count }} {{ t('book.tracks') }}</span>
              <span v-if="book.size_mb">{{ formatSizeMB(book.size_mb, t) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Desktop: status pills (below sidebar+content grid) -->
      <div v-if="isLoggedIn" class="mt-5 hidden lg:block">
        <BookActions :book-id="book.id" :book-status="book.book_status" @status-changed="loadBook" />
      </div>
    </div>
  </div>
</template>
