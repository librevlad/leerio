<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePlayer } from '../../composables/usePlayer'
import { api } from '../../api'
import type { Bookmark } from '../../types'
import {
  IconPlay,
  IconPause,
  IconSkipForward,
  IconSkipBack,
  IconVolume,
  IconVolumeMute,
  IconRewind15,
  IconForward30,
  IconMoon,
  IconBookmark,
  IconTrash,
} from '../shared/icons'

const { t } = useI18n()
const {
  currentBook,
  tracks,
  currentTrackIndex,
  isPlaying,
  currentTime,
  duration,
  volume,
  currentTrack,
  playbackRate,
  sleepTimer,
  formatTime,
  togglePlay,
  nextTrack,
  prevTrack,
  playTrack,
  setVolume,
  startSeek,
  endSeek,
  skipForward,
  skipBackward,
  setPlaybackRate,
  setSleepTimer,
} = usePlayer()

const seekPercent = computed(() => (duration.value > 0 ? (currentTime.value / duration.value) * 100 : 0))

function onSeekInput() {
  startSeek()
}

function onSeekChange(e: Event) {
  const val = parseFloat((e.target as HTMLInputElement).value)
  endSeek(val)
}

// ── Bookmarks ──
const bookmarks = ref<Bookmark[]>([])
const showBookmarks = ref(false)
const bookmarkNote = ref('')
const showBookmarkInput = ref(false)

async function loadBookmarks() {
  if (!currentBook.value) return
  try {
    bookmarks.value = await api.getBookmarks(currentBook.value.id)
  } catch {
    bookmarks.value = []
  }
}

async function addBookmark() {
  if (!currentBook.value) return
  await api.addBookmark(currentBook.value.id, currentTrackIndex.value, currentTime.value, bookmarkNote.value)
  bookmarkNote.value = ''
  showBookmarkInput.value = false
  await loadBookmarks()
}

async function removeBookmark(bookmarkId: number) {
  await api.removeBookmark(bookmarkId)
  await loadBookmarks()
}

function seekToBookmark(bm: Bookmark) {
  if (bm.track !== currentTrackIndex.value) {
    playTrack(bm.track)
    // After track loads, seek to position
    const unwatch = watch(currentTime, () => {
      endSeek(bm.time)
      unwatch()
    })
  } else {
    endSeek(bm.time)
  }
}

watch(currentBook, () => loadBookmarks())

// ── Speed control ──
const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]
const showSpeedPicker = ref(false)

function cycleSpeed() {
  const idx = SPEEDS.indexOf(playbackRate.value)
  const next = SPEEDS[(idx + 1) % SPEEDS.length] ?? 1
  setPlaybackRate(next)
}

function pickSpeed(s: number) {
  setPlaybackRate(s)
  showSpeedPicker.value = false
}

// ── Sleep timer ──
const showSleepMenu = ref(false)

function pickSleep(v: number | null) {
  setSleepTimer(v)
  showSleepMenu.value = false
}
const SLEEP_OPTIONS = computed(() => [
  { label: t('player.sleepMin', { n: 15 }), value: 15 },
  { label: t('player.sleepMin', { n: 30 }), value: 30 },
  { label: t('player.sleepMin', { n: 45 }), value: 45 },
  { label: t('player.sleepMin', { n: 60 }), value: 60 },
  { label: t('player.endOfTrack'), value: -1 },
])
</script>

<template>
  <div v-if="currentBook" class="card p-5">
    <h3 class="section-label mb-4">{{ t('player.title') }}</h3>

    <!-- Now playing -->
    <div class="mb-4">
      <p class="truncate text-[14px] font-semibold text-[--t1]">
        {{ currentTrack?.filename ?? '—' }}
      </p>
      <p class="text-[12px] text-[--t3]">
        {{ t('player.trackN', { n: currentTrackIndex + 1, total: tracks.length }) }}
      </p>
    </div>

    <!-- Controls -->
    <div class="mb-5 flex items-center justify-center gap-3">
      <button
        class="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-full border-0 bg-transparent p-2 text-[--t2] transition-colors hover:text-[--t1]"
        :title="t('player.back15')"
        @click="skipBackward()"
      >
        <IconRewind15 :size="22" />
      </button>

      <button
        class="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-full border-0 bg-transparent p-2.5 text-[--t2] transition-colors hover:text-[--t1]"
        :aria-label="t('player.prevTrack')"
        @click="prevTrack"
      >
        <IconSkipBack :size="20" />
      </button>

      <button
        class="flex h-14 w-14 cursor-pointer items-center justify-center rounded-full border-0 transition-all"
        style="background: var(--gradient-accent); box-shadow: 0 4px 20px rgba(232, 146, 58, 0.3)"
        :aria-label="isPlaying ? t('player.pause') : t('player.play')"
        @click="togglePlay"
      >
        <component :is="isPlaying ? IconPause : IconPlay" :size="22" style="color: #fff" />
      </button>

      <button
        class="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-full border-0 bg-transparent p-2.5 text-[--t2] transition-colors hover:text-[--t1]"
        :aria-label="t('player.nextTrack')"
        @click="nextTrack"
      >
        <IconSkipForward :size="20" />
      </button>

      <button
        class="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-full border-0 bg-transparent p-2 text-[--t2] transition-colors hover:text-[--t1]"
        :title="t('player.forward30')"
        @click="skipForward(30)"
      >
        <IconForward30 :size="22" />
      </button>
    </div>

    <!-- Seek bar -->
    <div class="mb-4">
      <div class="seek-bar-container">
        <div class="seek-bar-fill" :style="{ width: seekPercent + '%' }" />
        <input
          type="range"
          :min="0"
          :max="duration || 0"
          :value="currentTime"
          step="0.1"
          class="seek-bar-input"
          @input="onSeekInput"
          @change="onSeekChange"
        />
      </div>
      <div class="mt-1 flex justify-between text-[11px] text-[--t3]">
        <span>{{ formatTime(currentTime) }}</span>
        <span>{{ formatTime(duration) }}</span>
      </div>
    </div>

    <!-- Feature bar: Volume, Speed, Sleep, Bookmark -->
    <div class="mb-5 flex items-center gap-4">
      <!-- Volume -->
      <div class="flex items-center gap-2">
        <button
          class="cursor-pointer border-0 bg-transparent p-1 text-[--t3] transition-colors hover:text-[--t1]"
          :aria-label="volume > 0 ? t('player.mute') : t('player.unmute')"
          @click="setVolume(volume > 0 ? 0 : 1)"
        >
          <component :is="volume > 0 ? IconVolume : IconVolumeMute" :size="16" />
        </button>
        <input
          type="range"
          :min="0"
          :max="1"
          :value="volume"
          step="0.01"
          class="flex-1"
          style="max-width: 80px"
          @input="(e: Event) => setVolume(parseFloat((e.target as HTMLInputElement).value))"
        />
      </div>

      <div class="flex-1" />

      <!-- Speed -->
      <div class="relative">
        <button
          class="cursor-pointer rounded-lg border border-[--border] bg-transparent px-2 py-1 text-[12px] font-semibold text-[--t2] transition-colors hover:text-[--t1]"
          @click="cycleSpeed"
          @contextmenu.prevent="showSpeedPicker = !showSpeedPicker"
        >
          {{ playbackRate }}x
        </button>
        <div
          v-if="showSpeedPicker"
          class="absolute right-0 bottom-full z-10 mb-1 rounded-xl border border-[--border] py-1 shadow-lg"
          style="background: var(--bg-card)"
        >
          <button
            v-for="s in SPEEDS"
            :key="s"
            class="block w-full cursor-pointer border-0 bg-transparent px-4 py-1.5 text-left text-[12px] transition-colors hover:bg-white/5"
            :class="s === playbackRate ? 'font-semibold text-[--accent]' : 'text-[--t2]'"
            @click="pickSpeed(s)"
          >
            {{ s }}x
          </button>
        </div>
      </div>

      <!-- Sleep timer -->
      <div class="relative">
        <button
          class="relative cursor-pointer border-0 bg-transparent p-1 text-[--t3] transition-colors hover:text-[--t1]"
          :class="sleepTimer !== null ? 'text-[--accent]' : ''"
          :aria-label="t('player.sleepTimer')"
          @click="showSleepMenu = !showSleepMenu"
        >
          <IconMoon :size="16" />
          <span
            v-if="sleepTimer !== null"
            class="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full px-0.5 text-[9px] font-bold text-white"
            style="background: var(--accent)"
          >
            {{ sleepTimer }}
          </span>
        </button>
        <div
          v-if="showSleepMenu"
          class="absolute right-0 bottom-full z-10 mb-1 rounded-xl border border-[--border] py-1 shadow-lg"
          style="background: var(--bg-card)"
        >
          <button
            v-for="opt in SLEEP_OPTIONS"
            :key="opt.value"
            class="block w-full cursor-pointer border-0 bg-transparent px-4 py-1.5 text-left text-[12px] text-[--t2] transition-colors hover:bg-white/5"
            @click="pickSleep(opt.value)"
          >
            {{ opt.label }}
          </button>
          <button
            v-if="sleepTimer !== null"
            class="block w-full cursor-pointer border-0 bg-transparent px-4 py-1.5 text-left text-[12px] text-red-400 transition-colors hover:bg-white/5"
            @click="pickSleep(null)"
          >
            {{ t('player.cancel') }}
          </button>
        </div>
      </div>

      <!-- Bookmark -->
      <button
        class="cursor-pointer border-0 bg-transparent p-1 text-[--t3] transition-colors hover:text-[--t1]"
        :title="t('player.addBookmark')"
        @click="showBookmarkInput = !showBookmarkInput"
      >
        <IconBookmark :size="16" />
      </button>
    </div>

    <!-- Bookmark add input -->
    <div v-if="showBookmarkInput" class="mb-4 flex gap-2">
      <input
        v-model="bookmarkNote"
        class="input-field flex-1 px-3 py-2 text-[13px]"
        :placeholder="t('player.bookmarkNote')"
        @keyup.enter="addBookmark"
      />
      <button class="btn btn-primary shrink-0 text-[12px]" @click="addBookmark">{{ t('player.save') }}</button>
    </div>

    <!-- Bookmarks list -->
    <div v-if="bookmarks.length" class="mb-4 border-t border-[--border] pt-4">
      <button
        class="section-label mb-3 flex w-full cursor-pointer items-center gap-2 border-0 bg-transparent text-left"
        @click="showBookmarks = !showBookmarks"
      >
        <IconBookmark :size="14" />
        {{ t('player.bookmarksN', { n: bookmarks.length }) }}
        <span class="text-[10px] text-[--t3]">{{ showBookmarks ? '▲' : '▼' }}</span>
      </button>
      <div v-if="showBookmarks" class="scrollbar-hide max-h-48 space-y-1 overflow-y-auto">
        <div
          v-for="bm in bookmarks"
          :key="bm.ts"
          class="flex min-h-[40px] items-center gap-3 rounded-xl px-3 py-2 transition-colors hover:bg-white/[0.03]"
        >
          <button class="flex-1 cursor-pointer border-0 bg-transparent text-left" @click="seekToBookmark(bm)">
            <span class="text-[12px] font-medium text-[--t2]">
              {{ t('player.trackN', { n: bm.track + 1, total: tracks.length }) }} · {{ formatTime(bm.time) }}
            </span>
            <span v-if="bm.note" class="ml-2 text-[11px] text-[--t3]">{{ bm.note }}</span>
          </button>
          <button
            class="shrink-0 cursor-pointer border-0 bg-transparent p-1 text-[--t3] transition-colors hover:text-red-400"
            :aria-label="t('player.deleteBookmark')"
            @click="removeBookmark(bm.id)"
          >
            <IconTrash :size="13" />
          </button>
        </div>
      </div>
    </div>

    <!-- Track list -->
    <div class="border-t border-[--border] pt-4">
      <p class="section-label mb-3">{{ t('player.tracks') }}</p>
      <div class="scrollbar-hide max-h-64 space-y-1 overflow-y-auto">
        <button
          v-for="track in tracks"
          :key="track.index"
          class="flex min-h-[44px] w-full cursor-pointer items-center gap-3 rounded-xl border-0 px-3 py-2.5 text-left transition-all"
          :class="track.index === currentTrackIndex ? 'text-[--accent]' : 'text-[--t2] hover:text-[--t1]'"
          :style="track.index === currentTrackIndex ? 'background: var(--accent-soft)' : 'background: transparent'"
          @click="playTrack(track.index)"
        >
          <span class="w-6 shrink-0 text-right font-mono text-[11px] opacity-50">
            {{ track.index + 1 }}
          </span>
          <span class="flex-1 truncate text-[13px] font-medium">
            {{ track.filename }}
          </span>
          <span v-if="track.duration" class="shrink-0 text-[11px] text-[--t3]">
            {{ formatTime(track.duration) }}
          </span>
        </button>
      </div>
    </div>
  </div>
</template>
