<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { usePlayer } from '../composables/usePlayer'
import { trackDisplayName } from '../utils/format'
import { IconPlay, IconPause, IconX } from '../components/shared/icons'

const router = useRouter()
const { t } = useI18n()

const { currentBook, currentTrack, isPlaying, isLoading, overallProgress, togglePlay, skipForward, skipBackward } =
  usePlayer()

const chapterName = computed(() => {
  if (!currentTrack.value) return ''
  return trackDisplayName(currentTrack.value.filename, currentTrack.value.index ?? 0, t)
})

function exit() {
  router.back()
}
</script>

<template>
  <div
    class="fixed inset-0 z-[200] flex flex-col select-none"
    style="background: #0b0b0f; color: #fff; -webkit-user-select: none; user-select: none"
  >
    <!-- Top: Book title + chapter + exit button -->
    <div class="safe-top flex items-start justify-between px-6 pt-6 pb-2">
      <div class="min-w-0 flex-1 pr-4">
        <p class="truncate text-[20px] font-bold text-white/90">
          {{ currentBook?.title ?? '' }}
        </p>
        <p class="mt-1 truncate text-[16px] text-white/50">
          {{ chapterName }}
        </p>
      </div>
      <button
        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-0 transition-colors"
        style="background: rgba(255, 255, 255, 0.08)"
        :aria-label="t('player.carModeExit')"
        @click="exit"
      >
        <IconX :size="20" style="color: rgba(255, 255, 255, 0.6)" />
      </button>
    </div>

    <!-- Center: Huge playback controls -->
    <div class="flex flex-1 items-center justify-center gap-6 px-6 sm:gap-10">
      <!-- Skip backward -30s -->
      <button
        class="flex h-20 w-20 items-center justify-center rounded-full border-0 transition-all active:scale-95 sm:h-24 sm:w-24"
        style="background: rgba(255, 255, 255, 0.06)"
        :aria-label="t('player.carModeBack30')"
        @click="skipBackward(30)"
      >
        <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor" style="color: rgba(255, 255, 255, 0.7)">
          <path
            d="M12.5 3C17.15 3 21.08 6.03 22.47 10.22L20.1 11C19.05 7.81 16.04 5.5 12.5 5.5C10.54 5.5 8.77 6.22 7.38 7.38L10 10H3V3L5.6 5.6C7.45 4 9.85 3 12.5 3M11 20C11 21.11 10.1 22 9 22H5V20H9V18H7V16H9V14H5V12H9A2 2 0 0 1 11 14V15.5A1.5 1.5 0 0 1 9.5 17A1.5 1.5 0 0 1 11 18.5V20M19 14V20C19 21.11 18.11 22 17 22H15A2 2 0 0 1 13 20V14A2 2 0 0 1 15 12H17C18.11 12 19 12.9 19 14M15 14V20H17V14H15Z"
          />
        </svg>
      </button>

      <!-- Play / Pause -->
      <button
        class="flex h-[120px] w-[120px] items-center justify-center rounded-full border-0 transition-all active:scale-95 sm:h-[140px] sm:w-[140px]"
        style="background: var(--gradient-accent); box-shadow: 0 8px 40px rgba(232, 146, 58, 0.4)"
        :aria-label="isPlaying ? t('player.pause') : t('player.play')"
        :disabled="isLoading"
        @click="togglePlay"
      >
        <div v-if="isLoading" class="h-10 w-10 animate-spin rounded-full border-[3px] border-white/30 border-t-white" />
        <component :is="isPlaying ? IconPause : IconPlay" v-else :size="48" style="color: #fff" />
      </button>

      <!-- Skip forward +30s -->
      <button
        class="flex h-20 w-20 items-center justify-center rounded-full border-0 transition-all active:scale-95 sm:h-24 sm:w-24"
        style="background: rgba(255, 255, 255, 0.06)"
        :aria-label="t('player.carModeForward30')"
        @click="skipForward(30)"
      >
        <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor" style="color: rgba(255, 255, 255, 0.7)">
          <path
            d="M11.5 3C6.85 3 2.92 6.03 1.53 10.22L3.9 11C4.95 7.81 7.96 5.5 11.5 5.5C13.46 5.5 15.23 6.22 16.62 7.38L14 10H21V3L18.4 5.6C16.55 4 14.15 3 11.5 3M19 14V20C19 21.11 18.11 22 17 22H15A2 2 0 0 1 13 20V14A2 2 0 0 1 15 12H17C18.11 12 19 12.9 19 14M15 14V20H17V14H15M11 20C11 21.11 10.1 22 9 22H5V20H9V18H7V16H9V14H5V12H9A2 2 0 0 1 11 14V15.5A1.5 1.5 0 0 1 9.5 17A1.5 1.5 0 0 1 11 18.5V20Z"
          />
        </svg>
      </button>
    </div>

    <!-- Bottom: Simple progress bar -->
    <div class="safe-bottom px-6 pt-2 pb-8">
      <div class="h-[6px] w-full rounded-full" style="background: rgba(255, 255, 255, 0.08)">
        <div
          class="h-full rounded-full transition-all duration-500"
          style="background: linear-gradient(90deg, #ff8a00, #ffaa40)"
          :style="{ width: overallProgress + '%' }"
        />
      </div>
    </div>
  </div>
</template>
