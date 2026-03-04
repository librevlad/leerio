<script setup lang="ts">
import { useRouter } from 'vue-router'
import { usePlayer } from '../../composables/usePlayer'
import { IconPlay, IconPause, IconXCircle } from '../shared/icons'

const router = useRouter()
const {
  currentBook, isPlaying, isPlayerVisible,
  currentTrack, overallProgress, playingOffline,
  togglePlay, closePlayer,
} = usePlayer()

function goToBook() {
  if (currentBook.value) {
    router.push(`/book/${currentBook.value.id}`)
  }
}
</script>

<template>
  <transition name="mini-player">
    <div
      v-if="isPlayerVisible && currentBook"
      class="fixed bottom-[60px] md:bottom-0 left-0 right-0 z-40 md:left-56"
    >
      <!-- Progress bar -->
      <div class="h-[2px] w-full" style="background: rgba(255,255,255,0.06)">
        <div
          class="h-full transition-all duration-300"
          style="background: var(--gradient-bar)"
          :style="{ width: overallProgress + '%' }"
        />
      </div>

      <!-- Content -->
      <div
        class="flex items-center gap-3 px-4 py-2.5"
        style="background: rgba(17,17,25,0.92); backdrop-filter: blur(20px); border-top: 1px solid var(--border)"
      >
        <!-- Info (clickable) -->
        <button
          class="flex-1 min-w-0 text-left bg-transparent border-0 cursor-pointer p-0"
          @click="goToBook"
        >
          <p class="text-[13px] font-semibold text-[--t1] truncate leading-tight flex items-center gap-1.5">
            <span
              v-if="playingOffline"
              class="w-2 h-2 rounded-full bg-emerald-400 shrink-0"
              style="box-shadow: 0 0 6px rgba(52,211,153,0.5)"
              title="Офлайн"
            />
            {{ currentBook.title }}
          </p>
          <p class="text-[11px] text-[--t3] truncate leading-tight mt-0.5">
            {{ currentTrack?.filename ?? '' }}
          </p>
        </button>

        <!-- Play / Pause -->
        <button
          class="w-10 h-10 rounded-full flex items-center justify-center border-0 cursor-pointer shrink-0 transition-all"
          style="background: var(--gradient-accent); box-shadow: 0 2px 12px rgba(232,146,58,0.25)"
          @click="togglePlay"
        >
          <component :is="isPlaying ? IconPause : IconPlay" :size="16" style="color: #fff" />
        </button>

        <!-- Close -->
        <button
          class="p-1.5 bg-transparent border-0 text-[--t3] hover:text-[--t1] transition-colors cursor-pointer shrink-0"
          @click="closePlayer"
        >
          <IconXCircle :size="18" />
        </button>
      </div>
    </div>
  </transition>
</template>
