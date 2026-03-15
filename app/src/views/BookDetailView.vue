<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api, coverUrl } from '../api'
import type { Book } from '../types'
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
  IconPlay,
  IconPause,
  IconMusic,
  IconList,
  IconEdit,
  IconQuote,
  IconTag,
  IconInfo,
} from '../components/shared/icons'
import ProgressBar from '../components/shared/ProgressBar.vue'
import { usePlayer } from '../composables/usePlayer'
import { useDownloads } from '../composables/useDownloads'
import { useToast } from '../composables/useToast'
import { useAuth } from '../composables/useAuth'
import { useCategories } from '../composables/useCategories'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const book = ref<Book | null>(null)
const loading = ref(true)
const coverError = ref(false)
const activeTab = ref<'chapters' | 'notes' | 'quotes' | 'tags' | 'about'>('chapters')

const player = usePlayer()
const dl = useDownloads()
const toast = useToast()
const { isLoggedIn } = useAuth()
const { gradient: catGradient } = useCategories()

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

const tabs = computed(() => {
  const t: { key: string; label: string }[] = []
  if (isLoggedIn.value && book.value?.mp3_count) t.push({ key: 'chapters', label: 'book.contents' })
  if (isLoggedIn.value) t.push({ key: 'notes', label: 'book.notes' })
  if (isLoggedIn.value) t.push({ key: 'quotes', label: 'book.quotes' })
  if (isLoggedIn.value) t.push({ key: 'tags', label: 'book.tagsLabel' })
  t.push({ key: 'about', label: 'book.aboutBook' })
  return t
})

const tabIcons: Record<string, typeof IconList> = {
  chapters: IconList,
  notes: IconEdit,
  quotes: IconQuote,
  tags: IconTag,
  about: IconInfo,
}

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
  try {
    const result = await api.getBook(route.params.id as string)
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
      /* ignored */
    }
  }
}

async function onRatingChanged(rating: number) {
  if (!book.value) return
  if (!isLoggedIn.value) return router.push('/login')
  try {
    await api.setRating(book.value.id, rating)
    book.value.rating = rating
    toast.success(rating ? t('book.ratingSet', { rating }) : t('book.ratingRemoved'))
  } catch {
    toast.error(t('book.ratingError'))
  }
}

async function addToLibrary() {
  if (!book.value) return
  if (!isLoggedIn.value) return router.push('/login')
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
  if (!isLoggedIn.value) return router.push('/login')
  player.loadBook(book.value)
  if (!book.value.book_status || book.value.book_status === 'want_to_read') {
    try {
      await api.setBookStatus(book.value.id, 'reading')
      book.value.book_status = 'reading'
    } catch {
      /* ignored */
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
  const remaining = totalHours * (1 - progress / 100)
  if (remaining < 1 / 60) return `< 1 ${t('common.unitMin')}`
  if (remaining < 1) return `${Math.round(remaining * 60)} ${t('common.unitMin')}`
  const h = Math.floor(remaining)
  const m = Math.round((remaining - h) * 60)
  return m > 0 ? `${h}${t('common.unitH')} ${m}${t('common.unitM')}` : `${h}${t('common.unitH')}`
}

onMounted(loadBook)
watch(() => route.params.id, loadBook)
</script>

<template>
  <div>
    <!-- Back + Share -->
    <div class="mb-4 flex items-center justify-between lg:mb-6">
      <button
        class="-ml-3 flex min-h-[44px] cursor-pointer items-center gap-2 rounded-xl border-0 bg-transparent px-3 py-2.5 text-[13px] text-[--t3] transition-all hover:bg-white/5 hover:text-[--t1]"
        @click="router.back()"
      >
        <IconArrowLeft :size="15" />
        <span class="font-medium">{{ book?.category || t('book.back') }}</span>
      </button>
      <button
        v-if="book"
        class="flex min-h-[44px] cursor-pointer items-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.04] px-3.5 py-2 text-[13px] text-[--t2] transition-all hover:bg-white/[0.08]"
        @click="shareBook"
      >
        <IconShare :size="15" />
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
              <!-- Rating -->
              <div class="mt-2 flex gap-0.5 lg:justify-center">
                <button
                  v-for="i in 5"
                  :key="i"
                  class="cursor-pointer border-0 bg-transparent p-0 text-[16px] transition-colors"
                  :class="i <= (book.rating || 0) ? 'text-amber-400' : 'text-[--t3]/30'"
                  @click="onRatingChanged(i === book.rating ? 0 : i)"
                >
                  ★
                </button>
              </div>
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

            <!-- Share -->
            <button
              class="flex w-full cursor-pointer items-center gap-2 rounded-lg border-0 px-3 py-2 text-[12px] text-[--t2] transition-colors hover:bg-white/5"
              style="background: rgba(255, 255, 255, 0.03)"
              @click="shareBook"
            >
              <IconShare :size="14" />
              {{ t('book.share') }}
            </button>

            <!-- Download (native) -->
            <template v-if="dl.isNative.value && book.mp3_count && book.mp3_count > 0">
              <button
                v-if="!isDownloaded && !isDownloading"
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

          <!-- Meta (desktop) -->
          <div class="mt-4 hidden space-y-2 border-t border-white/[0.04] pt-4 text-[12px] text-[--t3] lg:block">
            <p v-if="book.duration_hours">🕐 {{ formatDuration(book.duration_hours) }}</p>
            <p v-if="book.mp3_count">🎵 {{ book.mp3_count }} {{ t('book.tracks') }}</p>
            <p v-if="book.size_mb">💾 {{ book.size_mb }} {{ t('common.mb') }}</p>
          </div>
        </div>

        <!-- Main content -->
        <div class="min-w-0 flex-1">
          <!-- Mobile: status pills + add to library -->
          <div class="mb-4 lg:hidden">
            <div v-if="isLoggedIn" class="flex flex-wrap items-center gap-2">
              <BookActions :book-id="book.id" :book-status="book.book_status" @status-changed="loadBook" />
            </div>
            <button
              v-else-if="!isLoggedIn"
              class="w-full rounded-xl py-3 text-center text-[14px] font-semibold text-white no-underline"
              style="background: var(--gradient-accent)"
              @click="$router.push('/login')"
            >
              {{ t('book.guestLogin') }}
            </button>
          </div>

          <!-- Tabs: pill segments -->
          <div
            class="scrollbar-hide flex gap-1 overflow-x-auto rounded-2xl p-1"
            style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.04)"
          >
            <button
              v-for="tab in tabs"
              :key="tab.key"
              class="flex cursor-pointer items-center gap-1.5 rounded-xl border-0 px-3.5 py-2.5 text-[12px] font-semibold whitespace-nowrap transition-all duration-200"
              :class="
                activeTab === tab.key
                  ? 'bg-[--accent-soft] text-[--accent] shadow-sm'
                  : 'bg-transparent text-[--t3] hover:bg-white/[0.04] hover:text-[--t2]'
              "
              :style="activeTab === tab.key ? 'box-shadow: 0 2px 8px rgba(255, 138, 0, 0.12)' : ''"
              @click="activeTab = tab.key as typeof activeTab"
            >
              <component
                :is="tabIcons[tab.key]"
                :size="14"
                class="transition-transform duration-200"
                :class="activeTab === tab.key ? 'scale-110' : 'group-hover:scale-105'"
              />
              {{ t(tab.label) }}
            </button>
          </div>

          <!-- Tab content + desktop context panel -->
          <div class="mt-4 flex gap-5">
            <!-- Main tab content -->
            <div class="min-w-0 flex-1 tab-content-enter" :key="activeTab">
              <!-- Chapters -->
              <BookChapters
                v-if="activeTab === 'chapters' && isLoggedIn && book.mp3_count && book.mp3_count > 0"
                :book="book"
              />

              <!-- Notes -->
              <BookNotes
                v-if="activeTab === 'notes' && isLoggedIn"
                :book-id="book.id"
                :title="book.title"
                :note="book.note"
              />

              <!-- Quotes -->
              <BookQuotes
                v-if="activeTab === 'quotes' && isLoggedIn"
                :book-title="book.title"
                :book-author="book.author"
              />

              <!-- Tags -->
              <div v-if="activeTab === 'tags' && isLoggedIn" class="space-y-5">
                <BookTags
                  :book-id="book.id"
                  :title="book.title"
                  :tags="book.tags"
                  @updated="(t) => (book!.tags = t)"
                />
                <BookTimeline :entries="book.timeline || []" />
              </div>

              <!-- About -->
              <div v-if="activeTab === 'about'">
                <div v-if="book.description" class="text-[13px] leading-relaxed text-[--t2]">
                  {{ book.description }}
                </div>
                <p v-else class="text-[13px] text-[--t3]">{{ t('book.noDescription') }}</p>

                <!-- Meta (mobile only, shown in About tab) -->
                <div class="mt-4 flex gap-3 text-[12px] text-[--t3] lg:hidden">
                  <span v-if="book.duration_hours">🕐 {{ formatDuration(book.duration_hours) }}</span>
                  <span v-if="book.mp3_count">🎵 {{ book.mp3_count }} {{ t('book.tracks') }}</span>
                  <span v-if="book.size_mb">💾 {{ book.size_mb }} {{ t('common.mb') }}</span>
                </div>

                <!-- Similar books -->
                <div class="mt-6">
                  <BookSimilar :book-id="book.id" />
                </div>
              </div>
            </div>

            <!-- Desktop context panel -->
            <div
              v-if="isLoggedIn && activeTab !== 'about'"
              class="hidden w-[260px] shrink-0 space-y-4 lg:block"
            >
              <!-- Notes preview (when not on notes tab) -->
              <div v-if="activeTab !== 'notes' && book.note" class="card p-4">
                <p class="section-label mb-2">{{ t('book.notes') }}</p>
                <p class="line-clamp-4 text-[12px] leading-relaxed text-[--t2]">{{ book.note }}</p>
              </div>

              <!-- Tags (when not on tags tab) -->
              <div v-if="activeTab !== 'tags' && book.tags?.length" class="card p-4">
                <p class="section-label mb-2">{{ t('book.tagsLabel') }}</p>
                <div class="flex flex-wrap gap-1.5">
                  <span
                    v-for="tag in book.tags"
                    :key="tag"
                    class="rounded-full px-2.5 py-0.5 text-[11px] font-medium"
                    style="background: var(--accent-soft); color: var(--accent)"
                  >
                    {{ tag }}
                  </span>
                </div>
              </div>

              <!-- Timeline snippet (when not on tags tab) -->
              <div
                v-if="activeTab !== 'tags' && book.timeline?.length"
                class="card p-4"
              >
                <p class="section-label mb-2">{{ t('book.timeline') }}</p>
                <div class="space-y-2">
                  <div
                    v-for="(e, i) in book.timeline.slice(0, 3)"
                    :key="i"
                    class="flex items-center gap-2 text-[11px]"
                  >
                    <span class="h-1.5 w-1.5 shrink-0 rounded-full bg-[--accent]" />
                    <span class="text-[--t2]">{{ e.action_label }}</span>
                    <span class="ml-auto text-[--t3]">{{
                      new Date(e.ts).toLocaleDateString('ru', { day: 'numeric', month: 'short' })
                    }}</span>
                  </div>
                </div>
              </div>
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
