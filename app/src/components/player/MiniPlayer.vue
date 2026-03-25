<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { usePlayer } from '../../composables/usePlayer'
import { IconPlay, IconPause, IconForward30, IconRewind15 } from '../shared/icons'

const { t } = useI18n()
const {
  currentBook,
  isPlaying,
  isPlayerVisible,
  isFullscreen,
  isLoading,
  overallProgress,
  totalElapsed,
  totalDuration,
  currentTime,
  duration,
  togglePlay,
  skipForward,
  skipBackward,
  openFullscreen,
  formatTime,
  audioError,
  retryAudio,
} = usePlayer()
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
          <p class="truncate text-[13px] leading-tight font-semibold text-[--t1]">
            {{ currentBook.title }}
          </p>
          <p class="mt-0.5 text-[11px] text-[--t3] tabular-nums">
            {{ formatTime(totalDuration > 0 ? totalElapsed : currentTime) }} /
            {{ formatTime(totalDuration > 0 ? totalDuration : duration) }}
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
          style="background: var(--gradient-accent); box-shadow: 0 2px 12px var(--accent-glow)"
          :aria-label="isPlaying ? t('player.pause') : t('player.play')"
          :disabled="isLoading"
          @click="togglePlay"
        >
          <div v-if="isLoading" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          <component :is="isPlaying ? IconPause : IconPlay" v-else :size="16" style="color: #fff" />
        </button>

        <!-- +30s skip -->
        <button
          class="shrink-0 cursor-pointer border-0 bg-transparent p-1.5 text-[--t3] transition-colors hover:text-[--t1]"
          :aria-label="t('player.forward30Aria')"
          @click="skipForward(30)"
        >
          <IconForward30 :size="18" />
        </button>
      </div>
    </div>
  </transition>
</template>
