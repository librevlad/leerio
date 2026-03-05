<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { usePlayer } from '../../composables/usePlayer'
import { useDownloads } from '../../composables/useDownloads'
import { useToast } from '../../composables/useToast'
import { api, coverUrl, userBookCoverUrl } from '../../api'
import {
  IconChevronDown,
  IconChevronUp,
  IconPlay,
  IconPause,
  IconSkipForward,
  IconSkipBack,
  IconRewind15,
  IconForward15,
  IconSpeed,
  IconMoon,
  IconBookmark,
  IconVolume,
  IconVolumeMute,
  IconList,
  IconMusic,
} from '../shared/icons'

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
} = usePlayer()

const showTrackList = ref(false)
const showSpeedMenu = ref(false)
const showSleepMenu = ref(false)
const showVolumeSlider = ref(false)
const seekPreview = ref<number | null>(null)
const isSeeking = ref(false)

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

const trackLabel = computed(() => {
  if (!currentTrack.value) return ''
  return `Трек ${currentTrackIndex.value + 1} из ${tracks.value.length}`
})

const seekPercent = computed(() => {
  if (!duration.value) return 0
  return (currentTime.value / duration.value) * 100
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

const speeds = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]

function selectSpeed(rate: number) {
  setPlaybackRate(rate)
  showSpeedMenu.value = false
}

const sleepOptions = [
  { label: '5 мин', value: 5 },
  { label: '15 мин', value: 15 },
  { label: '30 мин', value: 30 },
  { label: '45 мин', value: 45 },
  { label: '60 мин', value: 60 },
  { label: 'Конец трека', value: -1 },
  { label: 'Выкл', value: null },
]

function selectSleep(val: number | null) {
  setSleepTimer(val)
  showSleepMenu.value = false
}

function isTrackDownloaded(index: number) {
  if (!currentBook.value) return false
  return dl.isNative.value && dl.isTrackDownloaded(currentBook.value.id, index)
}

async function addBookmark() {
  if (!currentBook.value) return
  try {
    await api.addBookmark(currentBook.value.id, currentTrackIndex.value, currentTime.value)
    toast.success('Закладка добавлена')
  } catch {
    toast.error('Не удалось добавить закладку')
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
      <!-- Header -->
      <div class="safe-top flex items-center justify-between px-4 py-3">
        <button
          class="flex h-10 w-10 items-center justify-center rounded-full border-0 bg-transparent text-[--t2] transition-colors hover:text-[--t1]"
          @click="closeFullscreen"
        >
          <IconChevronDown :size="24" />
        </button>
        <div class="min-w-0 flex-1 px-3 text-center">
          <p class="truncate text-[13px] font-semibold text-[--t1]">{{ currentBook.title }}</p>
        </div>
        <button
          class="flex h-10 w-10 items-center justify-center rounded-full border-0 bg-transparent text-[--t2] transition-colors hover:text-[--t1]"
          @click="goToBook"
        >
          <IconList :size="20" />
        </button>
      </div>

      <!-- Cover -->
      <div class="flex flex-1 items-center justify-center px-8 py-4">
        <div
          class="relative aspect-square w-full max-w-[280px] overflow-hidden rounded-2xl shadow-2xl"
          :style="coverSrc ? '' : 'background: linear-gradient(135deg, rgba(232,146,58,0.15), rgba(232,146,58,0.05))'"
        >
          <img v-if="coverSrc" :src="coverSrc" alt="" class="h-full w-full object-cover" />
          <div v-else class="flex h-full items-center justify-center">
            <IconMusic :size="64" class="text-[--t3]" />
          </div>
          <!-- Glow effect -->
          <div
            v-if="coverSrc"
            class="absolute -inset-4 -z-10 blur-3xl"
            style="background: radial-gradient(circle, rgba(232, 146, 58, 0.15) 0%, transparent 70%)"
          />
        </div>
      </div>

      <!-- Track info -->
      <div class="px-6 text-center">
        <p class="truncate text-[15px] font-semibold text-[--t1]">
          {{ currentTrack?.filename ?? '' }}
        </p>
        <p
          v-if="currentBook.author || playingOffline"
          class="mt-1 flex items-center justify-center gap-2 text-[12px] text-[--t3]"
        >
          {{ currentBook.author }}
          <span
            v-if="playingOffline"
            class="h-2 w-2 rounded-full bg-emerald-400"
            style="box-shadow: 0 0 6px rgba(52, 211, 153, 0.5)"
          />
        </p>
        <p class="mt-0.5 text-[11px] text-[--t3]">{{ trackLabel }}</p>
      </div>

      <!-- Seek bar -->
      <div class="px-6 pt-5">
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
          <span>{{ formatTime(duration) }}</span>
        </div>
      </div>

      <!-- Main controls -->
      <div class="flex items-center justify-center gap-5 px-6 py-4">
        <button
          class="flex h-11 w-11 items-center justify-center rounded-full border-0 bg-transparent text-[--t2] transition-colors hover:text-[--t1]"
          @click="prevTrack"
        >
          <IconSkipBack :size="22" />
        </button>
        <button
          class="flex h-11 w-11 items-center justify-center rounded-full border-0 bg-transparent text-[--t2] transition-colors hover:text-[--t1]"
          @click="skipBackward()"
        >
          <IconRewind15 :size="24" />
        </button>
        <button
          class="flex h-16 w-16 items-center justify-center rounded-full border-0 transition-all"
          style="background: var(--gradient-accent); box-shadow: 0 4px 20px rgba(232, 146, 58, 0.35)"
          @click="togglePlay"
        >
          <component :is="isPlaying ? IconPause : IconPlay" :size="24" style="color: #fff" />
        </button>
        <button
          class="flex h-11 w-11 items-center justify-center rounded-full border-0 bg-transparent text-[--t2] transition-colors hover:text-[--t1]"
          @click="skipForward()"
        >
          <IconForward15 :size="24" />
        </button>
        <button
          class="flex h-11 w-11 items-center justify-center rounded-full border-0 bg-transparent text-[--t2] transition-colors hover:text-[--t1]"
          @click="nextTrack"
        >
          <IconSkipForward :size="22" />
        </button>
      </div>

      <!-- Secondary controls -->
      <div class="flex items-center justify-center gap-6 px-6 pb-2">
        <!-- Speed -->
        <div class="relative">
          <button
            class="flex h-10 items-center gap-1 rounded-full border-0 bg-transparent px-2 text-[12px] font-semibold transition-colors"
            :class="playbackRate !== 1 ? 'text-[--accent]' : 'text-[--t3] hover:text-[--t2]'"
            @click="showSpeedMenu = !showSpeedMenu"
          >
            <IconSpeed :size="16" />
            {{ playbackRate }}x
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
            class="flex h-10 items-center gap-1 rounded-full border-0 bg-transparent px-2 text-[12px] font-semibold transition-colors"
            :class="sleepTimer !== null ? 'text-[--accent]' : 'text-[--t3] hover:text-[--t2]'"
            @click="showSleepMenu = !showSleepMenu"
          >
            <IconMoon :size="16" />
            {{ sleepTimer !== null ? `${sleepTimer}м` : '' }}
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
          class="flex h-10 items-center gap-1 rounded-full border-0 bg-transparent px-2 text-[--t3] transition-colors hover:text-[--t2]"
          @click="addBookmark"
        >
          <IconBookmark :size="16" />
        </button>

        <!-- Volume -->
        <div class="relative">
          <button
            class="flex h-10 items-center gap-1 rounded-full border-0 bg-transparent px-2 text-[--t3] transition-colors hover:text-[--t2]"
            @click="showVolumeSlider = !showVolumeSlider"
          >
            <component :is="volume === 0 ? IconVolumeMute : IconVolume" :size="16" />
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

      <!-- Track list (collapsible) -->
      <div class="safe-bottom border-t border-[--border]">
        <button
          class="flex w-full cursor-pointer items-center justify-center gap-1 border-0 bg-transparent py-2.5 text-[11px] font-medium text-[--t3] transition-colors hover:text-[--t2]"
          @click="showTrackList = !showTrackList"
        >
          <IconChevronUp :size="14" :class="showTrackList ? 'rotate-180' : ''" class="transition-transform" />
          {{ showTrackList ? 'Скрыть треки' : 'Показать треки' }}
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
            <span class="min-w-0 flex-1 truncate text-[12px]">{{ track.filename }}</span>
            <span
              v-if="isTrackDownloaded(i)"
              class="h-2 w-2 flex-shrink-0 rounded-full bg-emerald-400"
              title="Скачано"
            />
            <span v-if="track.duration" class="flex-shrink-0 text-[11px] text-[--t3]">{{
              formatTime(track.duration)
            }}</span>
          </button>
        </div>
      </div>

      <!-- Close overlays on background click -->
      <div
        v-if="showSpeedMenu || showSleepMenu || showVolumeSlider"
        class="fixed inset-0 z-[5]"
        @click="closeOverlays"
      />
    </div>
  </transition>
</template>
