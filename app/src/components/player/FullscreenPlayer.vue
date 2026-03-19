<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { usePlayer } from '../../composables/usePlayer'
import { useDownloads } from '../../composables/useDownloads'
import { useToast } from '../../composables/useToast'
import { api, coverUrl, userBookCoverUrl } from '../../api'
import { trackDisplayName as _trackDisplayName } from '../../utils/format'
import { useLocalData } from '../../composables/useLocalData'
import { useAuth } from '../../composables/useAuth'
import type { Bookmark } from '../../types'
import {
  IconChevronDown,
  IconChevronUp,
  IconPlay,
  IconPause,
  IconSkipForward,
  IconSkipBack,
  IconRewind15,
  IconForward30,
  IconSpeed,
  IconMoon,
  IconBookmark,
  IconVolume,
  IconVolumeMute,
  IconList,
  IconMusic,
  IconX,
} from '../shared/icons'

const { t } = useI18n()
const router = useRouter()
const dl = useDownloads()
const toast = useToast()

const {
  currentBook,
  tracks,
  currentTrackIndex,
  isPlaying,
  currentTime,
  duration,
  volume,
  isFullscreen,
  playingOffline,
  playbackRate,
  sleepTimer,
  currentTrack,
  totalDuration,
  totalElapsed,
  overallProgress,
  isLoading,
  togglePlay,
  startSeek,
  endSeek,
  nextTrack,
  prevTrack,
  skipForward,
  skipBackward,
  setVolume,
  setPlaybackRate,
  setSleepTimer,
  playTrack,
  closeFullscreen,
  formatTime,
  audioError,
  retryAudio,
  skipErrorTrack,
} = usePlayer()

const showTrackList = ref(false)
const showSpeedMenu = ref(false)
const showSleepMenu = ref(false)
const showVolumeSlider = ref(false)
const seekPreview = ref<number | null>(null)
const isSeeking = ref(false)
const coverError = ref(false)
const desktopTab = ref<'chapters' | 'bookmarks'>('chapters')
const bookmarks = ref<Bookmark[]>([])

async function loadBookmarks() {
  if (!currentBook.value) {
    bookmarks.value = []
    return
  }
  try {
    const bms = await local.getBookmarks(currentBook.value.id)
    bookmarks.value = (bms ?? []).sort((a: Bookmark, b: Bookmark) => {
      if (a.track !== b.track) return a.track - b.track
      return a.time - b.time
    })
  } catch {
    bookmarks.value = []
  }
}

async function deleteBookmark(bm: Bookmark) {
  if (!currentBook.value) return
  try {
    await local.removeBookmark(currentBook.value.id, bm.id)
    if (isLoggedIn.value && bm.id) {
      await api.removeBookmark(bm.id).catch(() => {})
    }
    await loadBookmarks()
    toast.success(t('player.bookmarkDeleted'))
  } catch {
    toast.error(t('player.bookmarkError'))
  }
}

function seekToBookmark(bm: Bookmark) {
  if (bm.track !== currentTrackIndex.value) {
    playTrack(bm.track)
  }
  endSeek(bm.time)
  closeFullscreen()
}

watch(currentBook, () => loadBookmarks(), { immediate: true })

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}ч ${m}м`
  return `${m}м`
}

function trackDisplayName(filename: string, index: number): string {
  return _trackDisplayName(filename, index, t)
}

const coverSrc = computed(() => {
  if (!currentBook.value) return ''
  const id = currentBook.value.id
  if (id.startsWith('lb:')) return '' // local book - no server cover
  if (id.startsWith('ub:')) {
    const slug = id.split(':')[2] ?? ''
    return currentBook.value.has_cover ? userBookCoverUrl(slug) : ''
  }
  return currentBook.value.has_cover ? coverUrl(id) : ''
})

watch(currentBook, () => {
  coverError.value = false
})

const trackLabel = computed(() => {
  if (!currentTrack.value) return ''
  return t('player.trackN', { n: currentTrackIndex.value + 1, total: tracks.value.length })
})

const seekPercent = computed(() => {
  if (!duration.value) return 0
  return (currentTime.value / duration.value) * 100
})

const remainingTime = computed(() => {
  if (!duration.value) return '0:00'
  const remaining = duration.value - (seekPreview.value !== null ? seekPreview.value : currentTime.value)
  return '-' + formatTime(Math.max(0, remaining))
})

function goToBook() {
  if (!currentBook.value) return
  closeFullscreen()
  const id = currentBook.value.id
  router.push(`/book/${id}`)
}

function onSeekInput(e: Event) {
  const val = parseFloat((e.target as HTMLInputElement).value)
  seekPreview.value = val
  if (!isSeeking.value) {
    isSeeking.value = true
    startSeek()
  }
}

function onSeekChange(e: Event) {
  const val = parseFloat((e.target as HTMLInputElement).value)
  isSeeking.value = false
  seekPreview.value = null
  endSeek(val)
}

import { PLAYBACK_SPEEDS } from '../../composables/usePlayer'
const speeds = PLAYBACK_SPEEDS

function selectSpeed(rate: number) {
  setPlaybackRate(rate)
  showSpeedMenu.value = false
}

const sleepOptions = computed(() => [
  { label: t('player.sleepMin', { n: 5 }), value: 5 },
  { label: t('player.sleepMin', { n: 15 }), value: 15 },
  { label: t('player.sleepMin', { n: 30 }), value: 30 },
  { label: t('player.sleepMin', { n: 45 }), value: 45 },
  { label: t('player.sleepMin', { n: 60 }), value: 60 },
  { label: t('player.endOfTrack'), value: -1 },
  { label: t('player.off'), value: null },
])

function selectSleep(val: number | null) {
  setSleepTimer(val)
  showSleepMenu.value = false
}

function isTrackDownloaded(index: number) {
  if (!currentBook.value) return false
  return dl.isNative.value && dl.isTrackDownloaded(currentBook.value.id, index)
}

const bookmarkPop = ref(false)

const local = useLocalData()
const { isLoggedIn } = useAuth()

async function addBookmark() {
  if (!currentBook.value) return
  try {
    const bm = { track: currentTrackIndex.value, time: currentTime.value, note: '', ts: new Date().toISOString() }
    await local.addBookmark(currentBook.value.id, bm)
    if (isLoggedIn.value) {
      await api.addBookmark(currentBook.value.id, currentTrackIndex.value, currentTime.value)
    }
    bookmarkPop.value = true
    setTimeout(() => (bookmarkPop.value = false), 400)
    toast.success(t('player.bookmarkAdded'))
    await loadBookmarks()
  } catch {
    toast.error(t('player.bookmarkError'))
  }
}

let swipeStartY = 0

function onSwipeStart(e: TouchEvent) {
  const touch = e.touches[0]
  if (touch) swipeStartY = touch.clientY
}

function onSwipeEnd(e: TouchEvent) {
  const touch = e.changedTouches[0]
  if (!touch) return
  const deltaY = touch.clientY - swipeStartY
  if (deltaY > 80) closeFullscreen()
}

function closeOverlays() {
  showSpeedMenu.value = false
  showSleepMenu.value = false
  showVolumeSlider.value = false
}
</script>

<template>
  <transition name="fullscreen-player">
    <div
      v-if="isFullscreen && currentBook"
      class="fixed inset-0 z-[100] flex flex-col overflow-hidden"
      style="background: linear-gradient(180deg, #0d0d16 0%, #07070e 100%)"
      @touchstart="onSwipeStart"
      @touchend="onSwipeEnd"
    >
      <!-- ═══════════════════════════════════════════ -->
      <!-- DESKTOP: Split Layout (md+)                -->
      <!-- ═══════════════════════════════════════════ -->
      <div class="hidden h-full md:flex">
        <!-- Left panel: cover + controls -->
        <div class="relative flex w-[55%] flex-col items-center justify-center px-12">
          <!-- Ambient glow -->
          <div
            class="pointer-events-none absolute"
            style="
              width: 400px;
              height: 400px;
              background: radial-gradient(circle, rgba(255, 138, 0, 0.05) 0%, transparent 70%);
            "
          />

          <!-- Close button -->
          <button
            class="absolute top-5 left-5 z-[2] flex h-9 w-9 items-center justify-center rounded-full border-0 bg-transparent text-[--t3] transition-colors hover:text-[--t1]"
            :aria-label="t('player.minimizePlayer')"
            @click="closeFullscreen"
          >
            <IconX :size="20" />
          </button>

          <!-- Cover with progress ring -->
          <div class="relative z-[1] mb-7">
            <div
              class="h-[220px] w-[220px] overflow-hidden rounded-2xl"
              style="
                box-shadow:
                  0 20px 60px rgba(0, 0, 0, 0.5),
                  0 0 80px rgba(255, 138, 0, 0.06);
              "
            >
              <img
                v-if="coverSrc && !coverError"
                :src="coverSrc"
                alt=""
                class="h-full w-full object-cover"
                @error="coverError = true"
              />
              <div
                v-else
                class="flex h-full w-full items-center justify-center"
                style="background: linear-gradient(135deg, rgba(232, 146, 58, 0.15), rgba(232, 146, 58, 0.05))"
              >
                <IconMusic :size="56" class="text-[--t3]" />
              </div>
            </div>
            <!-- Progress ring -->
            <svg class="absolute -inset-[6px]" viewBox="0 0 232 232">
              <rect
                x="1.5"
                y="1.5"
                width="229"
                height="229"
                rx="21"
                fill="none"
                stroke="rgba(255,255,255,0.04)"
                stroke-width="3"
                pathLength="100"
              />
              <rect
                x="1.5"
                y="1.5"
                width="229"
                height="229"
                rx="21"
                fill="none"
                stroke="url(#desktop-progress-grad)"
                stroke-width="3"
                pathLength="100"
                :stroke-dasharray="100"
                :stroke-dashoffset="100 - overallProgress"
                stroke-linecap="round"
                style="transition: stroke-dashoffset 0.3s ease"
              />
              <defs>
                <linearGradient id="desktop-progress-grad" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stop-color="#ff8a00" />
                  <stop offset="100%" stop-color="#ffaa40" />
                </linearGradient>
              </defs>
            </svg>
            <!-- Progress badge -->
            <div
              v-if="overallProgress > 0"
              class="absolute -right-2 -bottom-2 rounded-full border border-[--border] px-2.5 py-0.5 text-[11px] font-semibold text-[--accent]"
              style="background: var(--card-solid)"
            >
              {{ Math.round(overallProgress) }}%
            </div>
          </div>

          <!-- Book info -->
          <div class="z-[1] w-full max-w-[420px] text-center">
            <p class="truncate text-[20px] font-bold text-[--t1]">{{ currentBook.title }}</p>
            <p class="mt-1 text-[13px] text-[--t3]">
              <span class="truncate">{{ currentBook.author }}</span>
              <span
                v-if="playingOffline"
                class="ml-2 inline-block h-2 w-2 rounded-full bg-emerald-400"
                style="box-shadow: 0 0 6px rgba(52, 211, 153, 0.5)"
              />
            </p>
            <p class="mt-1.5 text-[11px] text-[--t3]">
              <template v-if="totalElapsed > 60">
                {{ trackLabel }} · {{ formatDuration(totalElapsed) }} {{ t('player.listened') }} ·
                {{ formatDuration(Math.max(0, totalDuration - totalElapsed)) }}
                {{ t('player.remaining') }}
              </template>
              <template v-else> {{ trackLabel }} · {{ formatDuration(totalDuration) }} </template>
            </p>
          </div>

          <!-- Audio error banner -->
          <div
            v-if="audioError"
            class="z-[1] mt-3 flex w-full max-w-[420px] items-center gap-3 rounded-xl bg-red-500/10 px-4 py-3"
          >
            <span class="text-[13px] text-red-400">{{ t('player.loadError') }}</span>
            <div class="ml-auto flex gap-2">
              <button
                class="rounded-lg border-0 bg-white/10 px-3 py-1.5 text-[12px] font-semibold text-[--t1] transition-colors hover:bg-white/15"
                @click="retryAudio"
              >
                {{ t('player.retry') }}
              </button>
              <button
                v-if="tracks.length > 1"
                class="rounded-lg border-0 bg-white/10 px-3 py-1.5 text-[12px] font-semibold text-[--t1] transition-colors hover:bg-white/15"
                @click="skipErrorTrack"
              >
                {{ t('player.skipChapter') }}
              </button>
            </div>
          </div>

          <!-- Seek bar -->
          <div class="z-[1] mt-6 w-full max-w-[420px]">
            <div class="seek-bar-container" style="height: 24px">
              <div class="seek-bar-fill" :style="{ width: seekPercent + '%' }" style="height: 5px" />
              <input
                type="range"
                class="seek-bar-input"
                min="0"
                :max="duration || 0"
                step="0.1"
                :value="seekPreview !== null ? seekPreview : currentTime"
                style="height: 36px"
                @input="onSeekInput"
                @change="onSeekChange"
              />
            </div>
            <div class="mt-1 flex justify-between text-[12px]">
              <span class="text-[--t2] tabular-nums">{{
                formatTime(seekPreview !== null ? seekPreview : currentTime)
              }}</span>
              <span class="text-[--t3] tabular-nums">{{ remainingTime }}</span>
            </div>
          </div>

          <!-- Main controls -->
          <div class="z-[1] mt-5 flex items-center gap-5">
            <button
              class="flex h-10 w-10 items-center justify-center rounded-full border-0 bg-transparent text-[--t2] transition-colors hover:text-[--t1]"
              :aria-label="t('player.prevTrack')"
              @click="prevTrack"
            >
              <IconSkipBack :size="20" />
            </button>
            <button
              class="flex h-11 w-11 items-center justify-center rounded-full border-0 text-[--t2] transition-colors hover:text-[--t1]"
              style="background: rgba(255, 255, 255, 0.06)"
              :aria-label="t('player.back15')"
              @click="skipBackward()"
            >
              <IconRewind15 :size="22" />
            </button>
            <button
              class="flex h-14 w-14 items-center justify-center rounded-full border-0 transition-all"
              style="background: var(--gradient-accent); box-shadow: 0 4px 24px rgba(232, 146, 58, 0.4)"
              :aria-label="isPlaying ? t('player.pause') : t('player.play')"
              :disabled="isLoading"
              @click="togglePlay"
            >
              <div v-if="isLoading" class="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              <component v-else :is="isPlaying ? IconPause : IconPlay" :size="22" style="color: #fff" />
            </button>
            <button
              class="flex h-11 w-11 items-center justify-center rounded-full border-0 text-[--t2] transition-colors hover:text-[--t1]"
              style="background: rgba(255, 255, 255, 0.06)"
              :aria-label="t('player.forward30')"
              @click="skipForward(30)"
            >
              <IconForward30 :size="22" />
            </button>
            <button
              class="flex h-10 w-10 items-center justify-center rounded-full border-0 bg-transparent text-[--t2] transition-colors hover:text-[--t1]"
              :aria-label="t('player.nextTrack')"
              @click="nextTrack"
            >
              <IconSkipForward :size="20" />
            </button>
          </div>

          <!-- Secondary controls -->
          <div class="z-[1] mt-5 flex items-center gap-5">
            <!-- Speed -->
            <div class="relative">
              <button
                class="cursor-pointer rounded-lg border-0 px-3 py-1.5 text-[12px] font-bold transition-colors"
                :class="playbackRate !== 1 ? 'text-[--accent]' : 'text-[--t3] hover:text-[--t2]'"
                style="background: rgba(255, 255, 255, 0.04)"
                :aria-expanded="showSpeedMenu"
                @click="showSpeedMenu = !showSpeedMenu"
              >
                {{ playbackRate }}x
              </button>
              <div
                v-if="showSpeedMenu"
                class="absolute bottom-full left-1/2 z-10 mb-2 -translate-x-1/2 rounded-xl border border-[--border] p-1"
                style="background: var(--card-solid)"
              >
                <button
                  v-for="s in speeds"
                  :key="s"
                  class="block w-full cursor-pointer rounded-lg border-0 bg-transparent px-4 py-2 text-left text-[12px] transition-colors"
                  :class="playbackRate === s ? 'text-[--accent]' : 'text-[--t2] hover:bg-white/5'"
                  @click="selectSpeed(s)"
                >
                  {{ s }}x
                </button>
              </div>
            </div>

            <!-- Sleep timer -->
            <div class="relative">
              <button
                class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border-0 transition-colors"
                :class="sleepTimer !== null ? 'text-[--accent]' : 'text-[--t3] hover:text-[--t2]'"
                style="background: rgba(255, 255, 255, 0.04)"
                :aria-expanded="showSleepMenu"
                @click="showSleepMenu = !showSleepMenu"
              >
                <IconMoon :size="16" />
              </button>
              <div
                v-if="showSleepMenu"
                class="absolute bottom-full left-1/2 z-10 mb-2 -translate-x-1/2 rounded-xl border border-[--border] p-1"
                style="background: var(--card-solid)"
              >
                <button
                  v-for="opt in sleepOptions"
                  :key="String(opt.value)"
                  class="block w-full cursor-pointer rounded-lg border-0 bg-transparent px-4 py-2 text-left text-[12px] whitespace-nowrap transition-colors"
                  :class="
                    (opt.value === null && sleepTimer === null) || sleepTimer === opt.value
                      ? 'text-[--accent]'
                      : 'text-[--t2] hover:bg-white/5'
                  "
                  @click="selectSleep(opt.value)"
                >
                  {{ opt.label }}
                </button>
              </div>
            </div>

            <!-- Bookmark -->
            <button
              class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border-0 text-[--t3] transition-colors hover:text-[--t2]"
              style="background: rgba(255, 255, 255, 0.04)"
              @click="addBookmark"
            >
              <IconBookmark :size="16" :class="{ 'icon-pop': bookmarkPop }" />
            </button>

            <!-- Volume -->
            <div class="relative flex items-center gap-2">
              <button
                class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border-0 text-[--t3] transition-colors hover:text-[--t2]"
                style="background: rgba(255, 255, 255, 0.04)"
                @click="showVolumeSlider = !showVolumeSlider"
              >
                <component :is="volume === 0 ? IconVolumeMute : IconVolume" :size="16" />
              </button>
              <div
                v-if="showVolumeSlider"
                class="absolute bottom-full left-1/2 z-10 mb-2 flex -translate-x-1/2 items-center gap-2 rounded-xl border border-[--border] px-3 py-2"
                style="background: var(--card-solid)"
              >
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  :value="volume"
                  class="w-24"
                  @input="(e) => setVolume(parseFloat((e.target as HTMLInputElement).value))"
                />
              </div>
            </div>

            <!-- Go to book -->
            <button
              class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border-0 text-[--t3] transition-colors hover:text-[--t2]"
              style="background: rgba(255, 255, 255, 0.04)"
              :aria-label="t('player.bookPage')"
              @click="goToBook"
            >
              <IconList :size="16" />
            </button>
          </div>
        </div>

        <!-- Right panel: chapters -->
        <div
          class="flex w-[45%] flex-col"
          style="background: rgba(255, 255, 255, 0.015); border-left: 1px solid rgba(255, 255, 255, 0.04)"
        >
          <!-- Tabs -->
          <div class="relative flex shrink-0 px-4" style="border-bottom: 1px solid rgba(255, 255, 255, 0.04)">
            <button
              class="relative border-0 bg-transparent px-4 py-3 text-[12px] font-semibold tracking-wider transition-colors"
              :class="desktopTab === 'chapters' ? 'text-[--accent]' : 'text-[--t3] hover:text-[--t2]'"
              @click="desktopTab = 'chapters'"
            >
              {{ t('player.tracks') }}
              <span
                v-if="desktopTab === 'chapters'"
                class="absolute right-2 bottom-0 left-2 h-[2px] rounded-full bg-[--accent]"
              />
            </button>
            <button
              class="relative border-0 bg-transparent px-4 py-3 text-[12px] font-semibold tracking-wider transition-colors"
              :class="desktopTab === 'bookmarks' ? 'text-[--accent]' : 'text-[--t3] hover:text-[--t2]'"
              @click="desktopTab = 'bookmarks'"
            >
              {{ t('player.bookmarksTab') }}
              <span
                v-if="desktopTab === 'bookmarks'"
                class="absolute right-2 bottom-0 left-2 h-[2px] rounded-full bg-[--accent]"
              />
            </button>
          </div>

          <!-- Book progress bar -->
          <div class="shrink-0 border-b border-white/[0.04] px-5 py-3">
            <div class="mb-1.5 flex items-center justify-between">
              <span class="text-[11px] text-[--t3]">{{ t('player.bookProgress') }}</span>
              <span class="text-[11px] font-semibold text-[--accent]">{{ Math.round(overallProgress) }}%</span>
            </div>
            <div class="h-[3px] w-full rounded-full" style="background: rgba(255, 255, 255, 0.04)">
              <div
                class="h-full rounded-full transition-all duration-300"
                style="background: linear-gradient(90deg, #ff8a00, #ffaa40)"
                :style="{ width: overallProgress + '%' }"
              />
            </div>
          </div>

          <!-- Chapters tab -->
          <div v-if="desktopTab === 'chapters'" class="scrollbar-hide flex-1 overflow-y-auto p-2">
            <button
              v-for="(track, i) in tracks"
              :key="i"
              class="flex w-full cursor-pointer items-center gap-3 rounded-lg border-0 bg-transparent px-3 py-2.5 text-left transition-colors hover:bg-white/[0.03]"
              :style="i === currentTrackIndex ? 'background: rgba(255,138,0,0.06)' : ''"
              @click="playTrack(i)"
            >
              <span
                class="w-6 shrink-0 text-right text-[11px]"
                :class="i === currentTrackIndex ? 'font-semibold text-[--accent]' : 'text-[--t3]'"
              >
                {{ i + 1 }}
              </span>
              <div class="min-w-0 flex-1">
                <p
                  class="truncate text-[13px]"
                  :class="i === currentTrackIndex ? 'font-semibold text-[--t1]' : 'text-[--t2]'"
                >
                  {{ trackDisplayName(track.filename, i) }}
                </p>
                <!-- Mini progress for current track -->
                <div
                  v-if="i === currentTrackIndex"
                  class="mt-1.5 h-[2px] rounded-full"
                  style="background: rgba(255, 138, 0, 0.12)"
                >
                  <div
                    class="h-full rounded-full"
                    style="background: var(--accent)"
                    :style="{ width: seekPercent + '%' }"
                  />
                </div>
              </div>
              <span v-if="i === currentTrackIndex" class="shrink-0 text-[10px] text-[--accent]">▶</span>
              <span
                v-if="isTrackDownloaded(i)"
                class="h-2 w-2 shrink-0 rounded-full bg-emerald-400"
                :title="t('player.downloaded')"
              />
              <span
                v-if="track.duration"
                class="shrink-0 text-[11px]"
                :class="i === currentTrackIndex ? 'text-[--t2]' : 'text-[--t3]'"
              >
                {{ formatTime(track.duration) }}
              </span>
            </button>
          </div>

          <!-- Bookmarks tab -->
          <div v-else class="flex-1 overflow-y-auto">
            <div v-if="bookmarks.length === 0" class="flex h-full items-center justify-center p-6">
              <div class="text-center">
                <IconBookmark :size="32" class="mx-auto mb-3 text-[--t3] opacity-30" />
                <p class="text-[13px] text-[--t3]">{{ t('player.noBookmarks') }}</p>
                <p class="mt-1 text-[11px] text-[--t3] opacity-60">{{ t('player.addBookmarkHint') }}</p>
              </div>
            </div>
            <div v-else class="p-2">
              <div
                v-for="bm in bookmarks"
                :key="`${bm.track}-${bm.time}`"
                class="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-white/[0.03]"
                @click="seekToBookmark(bm)"
              >
                <IconBookmark :size="14" class="shrink-0 text-[--accent]" />
                <div class="min-w-0 flex-1">
                  <p class="text-[13px] text-[--t2]">
                    {{ trackDisplayName(tracks[bm.track]?.filename ?? '', bm.track) }}
                    · {{ formatTime(bm.time) }}
                  </p>
                  <p v-if="bm.note" class="mt-0.5 truncate text-[11px] text-[--t3]">{{ bm.note }}</p>
                </div>
                <button
                  class="shrink-0 rounded-md border-0 bg-transparent p-1 text-[--t3] opacity-0 transition-opacity group-hover:opacity-100 hover:text-red-400"
                  style="opacity: 0.4"
                  @click.stop="deleteBookmark(bm)"
                >
                  ✕
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════ -->
      <!-- MOBILE LAYOUT (< md)                       -->
      <!-- ═══════════════════════════════════════════ -->
      <div class="flex min-w-0 flex-1 flex-col md:hidden">
        <!-- Mobile header -->
        <div class="safe-top flex items-center justify-between px-4 py-3">
          <button
            class="flex h-10 w-10 items-center justify-center rounded-full border-0 bg-transparent text-[--t2] transition-colors hover:text-[--t1]"
            :aria-label="t('player.minimizePlayer')"
            @click="closeFullscreen"
          >
            <IconChevronDown :size="24" />
          </button>
          <div class="min-w-0 flex-1 px-3 text-center">
            <p class="text-[10px] font-semibold tracking-widest text-[--t3] uppercase">
              {{ t('nav.nowPlaying') }}
            </p>
          </div>
          <button
            class="flex h-10 w-10 items-center justify-center rounded-full border-0 bg-transparent text-[--t2] transition-colors hover:text-[--t1]"
            :aria-label="t('player.bookPage')"
            @click="goToBook"
          >
            <IconList :size="20" />
          </button>
        </div>

        <!-- ═══════════════════════════════════════ -->
        <!-- VINYL DISC + INFO (mobile only)         -->
        <!-- ═══════════════════════════════════════ -->
        <div class="flex flex-1 flex-col items-center justify-center px-6">
          <!-- Ambient glow -->
          <div
            class="pointer-events-none absolute"
            style="
              width: 400px;
              height: 400px;
              background: radial-gradient(circle, rgba(255, 138, 0, 0.05) 0%, transparent 70%);
            "
          />

          <!-- Vinyl disc -->
          <div class="relative z-[1]">
            <div
              class="flex h-[240px] w-[240px] items-center justify-center rounded-full"
              style="
                background: radial-gradient(
                  circle at 50% 50%,
                  #1a1a24 0%,
                  #111118 38%,
                  #1a1a24 39%,
                  #0d0d14 68%,
                  #1a1a24 69%,
                  #111118 100%
                );
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
              "
            >
              <!-- Cover in center -->
              <div
                class="h-[140px] w-[140px] overflow-hidden rounded-full border-[3px] border-white/10"
                style="box-shadow: 0 0 30px rgba(255, 138, 0, 0.08)"
              >
                <img
                  v-if="coverSrc && !coverError"
                  :src="coverSrc"
                  alt=""
                  class="h-full w-full object-cover"
                  @error="coverError = true"
                />
                <div
                  v-else
                  class="flex h-full w-full items-center justify-center"
                  style="background: linear-gradient(135deg, rgba(232, 146, 58, 0.15), rgba(232, 146, 58, 0.05))"
                >
                  <IconMusic :size="48" class="text-[--t3]" />
                </div>
              </div>
            </div>
            <!-- Playing indicator dot -->
            <div
              v-if="isPlaying"
              class="absolute -top-1 -right-1 h-6 w-6 rounded-full border-2 border-[#0d0d16]"
              style="background: var(--accent); box-shadow: 0 0 12px rgba(255, 138, 0, 0.4)"
            >
              <div class="flex h-full w-full items-center justify-center">
                <div class="h-1.5 w-1.5 rounded-full bg-white" />
              </div>
            </div>
          </div>

          <!-- Title + author -->
          <div class="z-[1] mt-5 w-full max-w-[400px] text-center">
            <p class="truncate text-[18px] font-bold text-[--t1]">
              {{ currentBook.title }}
            </p>
            <p class="mt-1 flex items-center justify-center gap-2 text-[13px] text-[--t3]">
              <span class="truncate">{{ currentBook.author }}</span>
              <span v-if="tracks.length > 1" class="shrink-0">· {{ trackLabel }}</span>
              <span
                v-if="playingOffline"
                class="h-2 w-2 shrink-0 rounded-full bg-emerald-400"
                style="box-shadow: 0 0 6px rgba(52, 211, 153, 0.5)"
              />
            </p>
          </div>

          <!-- Audio error banner -->
          <div
            v-if="audioError"
            class="z-[1] mt-3 flex w-full max-w-[400px] items-center gap-3 rounded-xl bg-red-500/10 px-4 py-3"
          >
            <span class="text-[13px] text-red-400">{{ t('player.loadError') }}</span>
            <div class="ml-auto flex gap-2">
              <button
                class="rounded-lg border-0 bg-white/10 px-3 py-1.5 text-[12px] font-semibold text-[--t1] transition-colors hover:bg-white/15"
                @click="retryAudio"
              >
                {{ t('player.retry') }}
              </button>
              <button
                v-if="tracks.length > 1"
                class="rounded-lg border-0 bg-white/10 px-3 py-1.5 text-[12px] font-semibold text-[--t1] transition-colors hover:bg-white/15"
                @click="skipErrorTrack"
              >
                {{ t('player.skipChapter') }}
              </button>
            </div>
          </div>
        </div>

        <!-- ═══════════════════════════════════════ -->
        <!-- MOBILE: Seek + Controls + Secondary    -->
        <!-- ═══════════════════════════════════════ -->
        <div>
          <!-- Seek bar -->
          <div class="px-6 pt-2">
            <div class="seek-bar-container" style="height: 24px">
              <div class="seek-bar-fill" :style="{ width: seekPercent + '%' }" style="height: 6px" />
              <input
                type="range"
                class="seek-bar-input"
                min="0"
                :max="duration || 0"
                step="0.1"
                :value="seekPreview !== null ? seekPreview : currentTime"
                style="height: 44px"
                @input="onSeekInput"
                @change="onSeekChange"
              />
            </div>
            <div class="mt-1 flex justify-between text-[11px] text-[--t3]">
              <span>{{ formatTime(seekPreview !== null ? seekPreview : currentTime) }}</span>
              <span>{{ remainingTime }}</span>
            </div>
          </div>

          <!-- Main controls -->
          <div class="flex items-center justify-center gap-5 px-6 py-4">
            <button
              class="flex h-11 w-11 items-center justify-center rounded-full border-0 bg-transparent text-[--t2] transition-colors hover:text-[--t1]"
              :aria-label="t('player.prevTrack')"
              @click="prevTrack"
            >
              <IconSkipBack :size="22" />
            </button>
            <button
              class="flex h-10 w-10 items-center justify-center rounded-full border-0 text-[--t2] transition-colors hover:text-[--t1]"
              style="background: rgba(255, 255, 255, 0.06)"
              :aria-label="t('player.back15')"
              @click="skipBackward()"
            >
              <IconRewind15 :size="22" />
            </button>
            <button
              class="flex h-16 w-16 items-center justify-center rounded-full border-0 transition-all"
              style="background: var(--gradient-accent); box-shadow: 0 4px 24px rgba(232, 146, 58, 0.4)"
              :aria-label="isPlaying ? t('player.pause') : t('player.play')"
              :disabled="isLoading"
              @click="togglePlay"
            >
              <div v-if="isLoading" class="h-6 w-6 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              <component v-else :is="isPlaying ? IconPause : IconPlay" :size="24" style="color: #fff" />
            </button>
            <button
              class="flex h-10 w-10 items-center justify-center rounded-full border-0 text-[--t2] transition-colors hover:text-[--t1]"
              style="background: rgba(255, 255, 255, 0.06)"
              :aria-label="t('player.forward30')"
              @click="skipForward(30)"
            >
              <IconForward30 :size="22" />
            </button>
            <button
              class="flex h-11 w-11 items-center justify-center rounded-full border-0 bg-transparent text-[--t2] transition-colors hover:text-[--t1]"
              :aria-label="t('player.nextTrack')"
              @click="nextTrack"
            >
              <IconSkipForward :size="22" />
            </button>
          </div>

          <!-- Secondary controls -->
          <div class="flex items-center justify-around px-8 pb-2">
            <!-- Speed -->
            <div class="relative">
              <button
                class="flex flex-col items-center gap-0.5 border-0 bg-transparent px-3 py-1 transition-colors"
                :class="playbackRate !== 1 ? 'text-[--accent]' : 'text-[--t3] hover:text-[--t2]'"
                :aria-expanded="showSpeedMenu"
                @click="showSpeedMenu = !showSpeedMenu"
              >
                <IconSpeed :size="18" />
                <span class="text-[10px] font-semibold">{{ playbackRate }}x</span>
              </button>
              <div
                v-if="showSpeedMenu"
                class="absolute bottom-12 left-1/2 z-10 -translate-x-1/2 rounded-xl border border-[--border] p-1"
                style="background: var(--card-solid)"
              >
                <button
                  v-for="s in speeds"
                  :key="s"
                  class="block w-full cursor-pointer rounded-lg border-0 bg-transparent px-4 py-2 text-left text-[12px] transition-colors"
                  :class="playbackRate === s ? 'text-[--accent]' : 'text-[--t2] hover:bg-white/5'"
                  @click="selectSpeed(s)"
                >
                  {{ s }}x
                </button>
              </div>
            </div>

            <!-- Sleep timer -->
            <div class="relative">
              <button
                class="flex flex-col items-center gap-0.5 border-0 bg-transparent px-3 py-1 transition-colors"
                :class="sleepTimer !== null ? 'text-[--accent]' : 'text-[--t3] hover:text-[--t2]'"
                :aria-expanded="showSleepMenu"
                @click="showSleepMenu = !showSleepMenu"
              >
                <IconMoon :size="18" />
                <span class="text-[10px] font-semibold">{{
                  sleepTimer !== null ? `${sleepTimer}м` : t('player.sleepLabel')
                }}</span>
              </button>
              <div
                v-if="showSleepMenu"
                class="absolute bottom-12 left-1/2 z-10 -translate-x-1/2 rounded-xl border border-[--border] p-1"
                style="background: var(--card-solid)"
              >
                <button
                  v-for="opt in sleepOptions"
                  :key="String(opt.value)"
                  class="block w-full cursor-pointer rounded-lg border-0 bg-transparent px-4 py-2 text-left text-[12px] whitespace-nowrap transition-colors"
                  :class="
                    (opt.value === null && sleepTimer === null) || sleepTimer === opt.value
                      ? 'text-[--accent]'
                      : 'text-[--t2] hover:bg-white/5'
                  "
                  @click="selectSleep(opt.value)"
                >
                  {{ opt.label }}
                </button>
              </div>
            </div>

            <!-- Bookmark -->
            <button
              class="flex flex-col items-center gap-0.5 border-0 bg-transparent px-3 py-1 text-[--t3] transition-colors hover:text-[--t2]"
              @click="addBookmark"
            >
              <IconBookmark :size="18" :class="{ 'icon-pop': bookmarkPop }" />
              <span class="text-[10px] font-semibold">{{ t('player.bookmarkLabel') }}</span>
            </button>

            <!-- Volume -->
            <div class="relative">
              <button
                class="flex flex-col items-center gap-0.5 border-0 bg-transparent px-3 py-1 text-[--t3] transition-colors hover:text-[--t2]"
                @click="showVolumeSlider = !showVolumeSlider"
              >
                <component :is="volume === 0 ? IconVolumeMute : IconVolume" :size="18" />
                <span class="text-[10px] font-semibold">{{ t('player.volumeLabel') }}</span>
              </button>
              <div
                v-if="showVolumeSlider"
                class="absolute bottom-12 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2 rounded-xl border border-[--border] px-3 py-2"
                style="background: var(--card-solid)"
              >
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  :value="volume"
                  class="w-24"
                  @input="(e) => setVolume(parseFloat((e.target as HTMLInputElement).value))"
                />
              </div>
            </div>
          </div>

          <!-- Track list (collapsible) — mobile only -->
          <div class="safe-bottom border-t border-[--border]">
            <button
              class="flex w-full cursor-pointer items-center justify-center gap-1 border-0 bg-transparent py-2.5 text-[11px] font-medium text-[--t3] transition-colors hover:text-[--t2]"
              @click="showTrackList = !showTrackList"
            >
              <IconChevronUp :size="14" :class="showTrackList ? 'rotate-180' : ''" class="transition-transform" />
              {{ showTrackList ? t('player.hideTracks') : t('player.showTracks') }}
            </button>

            <div v-if="showTrackList" class="scrollbar-hide max-h-48 overflow-y-auto px-4 pb-4">
              <button
                v-for="(track, i) in tracks"
                :key="i"
                class="flex w-full cursor-pointer items-center gap-3 rounded-lg border-0 bg-transparent px-3 py-2.5 text-left transition-colors hover:bg-white/5"
                :class="i === currentTrackIndex ? 'text-[--accent]' : 'text-[--t2]'"
                @click="playTrack(i)"
              >
                <span class="w-6 text-right text-[11px] text-[--t3]">{{ i + 1 }}</span>
                <span class="min-w-0 flex-1 truncate text-[12px]">{{ trackDisplayName(track.filename, i) }}</span>
                <span
                  v-if="isTrackDownloaded(i)"
                  class="h-2 w-2 flex-shrink-0 rounded-full bg-emerald-400"
                  :title="t('player.downloaded')"
                />
                <span v-if="track.duration" class="flex-shrink-0 text-[11px] text-[--t3]">{{
                  formatTime(track.duration)
                }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Close overlays on background click -->
      <div
        v-if="showSpeedMenu || showSleepMenu || showVolumeSlider"
        class="fixed inset-0 z-[9]"
        @click="closeOverlays"
      />
    </div>
  </transition>
</template>
