<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, coverUrl } from '../api'
import { useAuth } from '../composables/useAuth'
import { usePlayer } from '../composables/usePlayer'
import { useCategories } from '../composables/useCategories'
import { formatRemaining } from '../utils/format'
import { useTracking } from '../composables/useTelemetry'
import { useToast } from '../composables/useToast'
import type { DashboardData } from '../types'
import PullIndicator from '../components/shared/PullIndicator.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import ProgressBar from '../components/shared/ProgressBar.vue'
import { IconMusic, IconPlay, IconPause } from '../components/shared/icons'
import { usePullToRefresh } from '../composables/usePullToRefresh'

const { t } = useI18n()
const toast = useToast()
const { track } = useTracking()
const { user, isGuest } = useAuth()
const player = usePlayer()
const { gradient: catGradient } = useCategories()
const data = ref<DashboardData | null>(null)
const loading = ref(true)
const coverErrors = reactive(new Set<string>())

const greeting = computed(() => {
  const h = new Date().getHours()
  const base =
    h < 6
      ? t('dashboard.greetNight')
      : h < 12
        ? t('dashboard.greetMorning')
        : h < 18
          ? t('dashboard.greetDay')
          : t('dashboard.greetEvening')
  return base
})

const userName = computed(() => user.value?.name?.split(' ')[0] ?? '')

const heroBook = computed(() => {
  if (!data.value?.active_books.length) return null
  return data.value.active_books.find((b) => b.progress > 0) ?? data.value.active_books[0] ?? null
})

const otherBooks = computed(() => {
  if (!data.value?.active_books.length || !heroBook.value) return []
  return data.value.active_books.filter((b) => b.id !== heroBook.value!.id && b.progress > 0)
})

const nowPlayingId = computed(() => player.currentBook.value?.id ?? null)
const isPlaying = computed(() => player.isPlaying.value)

function fmtRemaining(totalHours: number, progress: number): string {
  return formatRemaining(totalHours, progress, t)
}

async function playBook(bookId: string) {
  track('resume_clicked', { book: bookId })
  if (nowPlayingId.value === bookId) {
    player.togglePlay()
  } else {
    try {
      const book = await api.getBook(bookId)
      player.loadBook(book)
      track('book_played', { book: bookId })
    } catch {
      toast.error(t('player.tracksLoadError'))
    }
  }
}

async function loadData() {
  if (isGuest.value) {
    loading.value = false
    return
  }
  try {
    data.value = await api.getDashboard()
  } finally {
    loading.value = false
  }
}

const { refreshing, pullProgress } = usePullToRefresh(loadData)

onMounted(loadData)
</script>

<template>
  <div>
    <PullIndicator :progress="pullProgress" :refreshing="refreshing" />

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-6">
      <div class="skeleton h-10 w-48" />
      <div class="skeleton h-[200px] rounded-2xl" />
    </div>

    <!-- Guest welcome -->
    <div v-else-if="isGuest" class="fade-in flex flex-col gap-5">
      <div>
        <p class="text-[12px] font-semibold tracking-widest text-[--t3] uppercase">{{ greeting }}</p>
        <h1 class="mt-1 text-[22px] font-extrabold text-[--t1] md:text-[26px]">Leerio</h1>
      </div>

      <div
        class="overflow-hidden rounded-2xl p-6 text-center"
        style="
          background: linear-gradient(135deg, rgba(255, 138, 0, 0.08), rgba(255, 138, 0, 0.02));
          border: 1px solid rgba(255, 138, 0, 0.15);
        "
      >
        <p class="text-[32px]">🎧</p>
        <h2 class="mt-3 text-[16px] font-bold text-[--t1]">{{ t('dashboard.guestTitle') }}</h2>
        <p class="mt-2 text-[13px] text-[--t2]">{{ t('dashboard.guestSubtitle') }}</p>
        <div class="mt-5 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <router-link to="/library" class="btn btn-primary px-6 py-2.5 text-[13px] no-underline">
            {{ t('dashboard.guestBrowse') }}
          </router-link>
          <router-link to="/login" class="btn btn-ghost px-6 py-2.5 text-[13px] no-underline">
            {{ t('dashboard.guestLogin') }}
          </router-link>
        </div>
      </div>
    </div>

    <div v-else-if="data" class="fade-in flex flex-col gap-5">
      <!-- Greeting -->
      <div>
        <p class="text-[12px] font-semibold tracking-widest text-[--t3] uppercase">{{ greeting }}</p>
        <h1 class="mt-1 text-[22px] font-extrabold text-[--t1] md:text-[26px]">{{ userName }}</h1>
      </div>

      <!-- Hero Card -->
      <div class="py-3">
        <div
          v-if="heroBook"
          class="overflow-hidden rounded-2xl"
          style="
            background: linear-gradient(135deg, #1a1520 0%, #0d1420 100%);
            border: 1px solid rgba(255, 255, 255, 0.06);
          "
        >
          <div class="p-5">
            <p class="text-[10px] font-semibold tracking-widest text-[--accent] uppercase">
              {{ t('dashboard.continueListening') }}
            </p>
            <div class="mt-3 flex gap-4 sm:gap-5">
              <!-- Cover -->
              <router-link
                :to="`/book/${heroBook.id}`"
                class="relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-xl shadow-md sm:h-[120px] sm:w-[120px] sm:rounded-2xl"
              >
                <img
                  v-if="heroBook.has_cover !== false && !coverErrors.has(heroBook.id)"
                  :src="coverUrl(heroBook.id)"
                  :alt="heroBook.title"
                  class="h-full w-full object-cover"
                  @error="coverErrors.add(heroBook.id)"
                />
                <div
                  v-else
                  class="flex h-full w-full items-center justify-center"
                  :style="{ background: catGradient(heroBook.category ?? '') }"
                >
                  <IconMusic :size="32" class="text-white/40" />
                </div>
              </router-link>

              <!-- Info -->
              <div class="flex min-w-0 flex-1 flex-col justify-center">
                <router-link
                  :to="`/book/${heroBook.id}`"
                  class="line-clamp-2 text-[15px] leading-snug font-bold text-[--t1] no-underline hover:text-[--accent] sm:text-[20px]"
                >
                  {{ heroBook.title }}
                </router-link>
                <p class="mt-1 text-[12px] text-[--t3] sm:text-[13px]">
                  {{ heroBook.author }}
                  <template v-if="heroBook.current_chapter">
                    · {{ t('player.trackN', { n: heroBook.current_chapter, total: heroBook.total_chapters }) }}
                  </template>
                </p>
                <div class="mt-3 flex items-center gap-2 sm:max-w-[300px]">
                  <div class="flex-1">
                    <ProgressBar :percent="heroBook.progress" height="h-[3px]" />
                  </div>
                  <span class="flex-shrink-0 text-[11px] text-[--t3] tabular-nums">{{ heroBook.progress }}%</span>
                </div>
              </div>
            </div>

            <!-- Play button -->
            <button
              class="mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl border-0 py-3 text-[14px] font-bold text-white transition-all hover:brightness-110 sm:py-3.5 sm:text-[15px]"
              style="
                background: linear-gradient(135deg, #ff8a00, #e07000);
                box-shadow: 0 4px 20px rgba(255, 138, 0, 0.25);
              "
              @click="playBook(heroBook.id)"
            >
              <component :is="nowPlayingId === heroBook.id && isPlaying ? IconPause : IconPlay" :size="16" />
              {{
                nowPlayingId === heroBook.id && isPlaying
                  ? t('player.pause')
                  : heroBook.duration_hours
                    ? `${t('player.play')} · ${fmtRemaining(heroBook.duration_hours, heroBook.progress)} ${t('common.remaining')}`
                    : t('player.play')
              }}
            </button>
          </div>
        </div>

        <!-- Welcome CTA if no active books -->
        <EmptyState
          v-else-if="!data.active_books.length && !data.recent.length"
          :title="t('dashboard.welcomeTitle')"
          :description="t('dashboard.welcomeDesc')"
          :action-label="t('dashboard.welcomeAction')"
          @action="$router.push('/library')"
        />
      </div>

      <!-- Also listening -->
      <div v-if="otherBooks.length" class="flex flex-col gap-2">
        <p class="text-[11px] font-semibold tracking-widest text-[--t3] uppercase">
          {{ t('dashboard.alsoListening') }}
        </p>
        <div
          v-for="book in otherBooks.slice(0, 4)"
          :key="book.id"
          class="flex items-center gap-3 rounded-xl px-3.5 py-2.5 transition-colors hover:bg-white/[0.03]"
          style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.03)"
        >
          <router-link :to="`/book/${book.id}`" class="h-11 w-11 flex-shrink-0 overflow-hidden rounded-lg">
            <img
              v-if="book.has_cover !== false && !coverErrors.has(book.id)"
              :src="coverUrl(book.id)"
              :alt="book.title"
              class="h-full w-full object-cover"
              @error="coverErrors.add(book.id)"
            />
            <div
              v-else
              class="flex h-full w-full items-center justify-center"
              :style="{ background: catGradient(book.category ?? '') }"
            >
              <IconMusic :size="14" class="text-white/40" />
            </div>
          </router-link>
          <router-link :to="`/book/${book.id}`" class="min-w-0 flex-1 no-underline">
            <p class="truncate text-[13px] font-semibold text-[--t2]">{{ book.title }}</p>
            <p class="text-[11px] text-[--t3]">
              {{ book.progress }}%
              <template v-if="book.duration_hours"> · {{ fmtRemaining(book.duration_hours, book.progress) }} </template>
            </p>
          </router-link>
          <button
            class="flex h-7 w-7 flex-shrink-0 cursor-pointer items-center justify-center rounded-full border-0 transition-colors hover:bg-white/10"
            style="background: rgba(255, 255, 255, 0.06)"
            :aria-label="t('player.play') + ': ' + book.title"
            @click="playBook(book.id)"
          >
            <component
              :is="nowPlayingId === book.id && isPlaying ? IconPause : IconPlay"
              :size="10"
              class="text-[--t2]"
            />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
