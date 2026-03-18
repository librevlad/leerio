<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { usePlayer } from '../../composables/usePlayer'
import { IconPlay, IconPause, IconXCircle, IconForward30, IconRewind15 } from '../shared/icons'

const { t } = useI18n()
const {
  currentBook,
  isPlaying,
  isPlayerVisible,
  isFullscreen,
  currentTrack,
  currentTrackIndex,
  overallProgress,
  totalElapsed,
  totalDuration,
  playingOffline,
  togglePlay,
  skipForward,
  skipBackward,
  closePlayer,
  openFullscreen,
  formatTime,
  audioError,
  retryAudio,
} = usePlayer()

function trackDisplayName(filename: string, index: number): string {
  const name = filename.replace(/\.\w+$/, '')
  if (/^\d+$/.test(name)) return t('book.chapterN', { n: index + 1 })
  return name
}
</script>

<template>
  <transition name="mini-player">
    <div
      v-if="isPlayerVisible && currentBook && !isFullscreen"
      class="mini-player-position fixed right-0 left-0 z-40 md:bottom-0 md:left-56"
    >
      <!-- Progress bar -->
      <div
        class="h-[2px] w-full"
        style="background: rgba(255, 255, 255, 0.06)"
        role="progressbar"
        :aria-valuenow="overallProgress"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-label="t('player.progressAria')"
      >
        <div
          class="h-full transition-all duration-300"
          style="background: var(--gradient-bar)"
          :style="{ width: overallProgress + '%' }"
        />
      </div>

      <!-- Content -->
      <div
        class="flex items-center gap-3 px-4 py-2.5"
        style="background: rgba(17, 17, 25, 0.92); backdrop-filter: blur(20px); border-top: 1px solid var(--border)"
      >
        <!-- Info (clickable) -->
        <button class="min-w-0 flex-1 cursor-pointer border-0 bg-transparent p-0 text-left" @click="openFullscreen">
          <p class="flex items-center gap-1.5 truncate text-[13px] leading-tight font-semibold text-[--t1]">
            <span
              v-if="playingOffline"
              class="h-2 w-2 shrink-0 rounded-full bg-emerald-400"
              style="box-shadow: 0 0 6px rgba(52, 211, 153, 0.5)"
              :title="t('player.offline')"
            />
            {{ currentBook.title }}
          </p>
          <p v-if="currentBook?.author" class="line-clamp-1 text-[11px] text-[--t3]">
            {{ currentBook.author }}
          </p>
          <p class="mt-0.5 flex items-center gap-1.5 truncate text-[11px] leading-tight text-[--t3]">
            <span class="truncate">{{
              currentTrack ? trackDisplayName(currentTrack.filename, currentTrackIndex) : ''
            }}</span>
            <span v-if="totalDuration > 0" class="shrink-0 tabular-nums">
              {{ formatTime(totalElapsed) }} / {{ formatTime(totalDuration) }}
            </span>
          </p>
        </button>

        <!-- -15s skip -->
        <button
          class="hidden shrink-0 cursor-pointer border-0 bg-transparent p-1.5 text-[--t3] transition-colors hover:text-[--t1] sm:block"
          :aria-label="t('player.back15Aria')"
          @click="skipBackward()"
        >
          <IconRewind15 :size="18" />
        </button>

        <!-- Play / Pause / Retry -->
        <button
          v-if="audioError"
          class="flex h-10 shrink-0 cursor-pointer items-center justify-center rounded-full border-0 px-4 text-[12px] font-semibold text-white transition-all"
          style="background: linear-gradient(135deg, #dc2626, #b91c1c)"
          :aria-label="t('player.retry')"
          @click="retryAudio"
        >
          {{ t('player.retry') }}
        </button>
        <button
          v-else
          class="flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full border-0 transition-all"
          style="background: var(--gradient-accent); box-shadow: 0 2px 12px rgba(232, 146, 58, 0.25)"
          :aria-label="isPlaying ? t('player.pause') : t('player.play')"
          @click="togglePlay"
        >
          <component :is="isPlaying ? IconPause : IconPlay" :size="16" style="color: #fff" />
        </button>

        <!-- +30s skip -->
        <button
          class="shrink-0 cursor-pointer border-0 bg-transparent p-1.5 text-[--t3] transition-colors hover:text-[--t1]"
          :aria-label="t('player.forward30Aria')"
          @click="skipForward(30)"
        >
          <IconForward30 :size="18" />
        </button>

        <!-- Close -->
        <button
          class="shrink-0 cursor-pointer border-0 bg-transparent p-1.5 text-[--t3] transition-colors hover:text-[--t1]"
          :aria-label="t('player.closePlayer')"
          @click="closePlayer"
        >
          <IconXCircle :size="18" />
        </button>
      </div>
    </div>
  </transition>
</template>
