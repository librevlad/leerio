<script setup lang="ts">
import { useRouter } from 'vue-router'
import { usePlayer } from '../../composables/usePlayer'
import { IconPlay, IconPause, IconXCircle, IconForward15 } from '../shared/icons'

const router = useRouter()
const {
  currentBook,
  isPlaying,
  isPlayerVisible,
  currentTrack,
  overallProgress,
  playingOffline,
  togglePlay,
  skipForward,
  closePlayer,
} = usePlayer()

function goToBook() {
  if (currentBook.value) {
    const id = currentBook.value.id
    router.push(id.startsWith('lv:') ? `/discover/${id.slice(3)}` : `/book/${id}`)
  }
}
</script>

<template>
  <transition name="mini-player">
    <div v-if="isPlayerVisible && currentBook" class="fixed right-0 bottom-[60px] left-0 z-40 md:bottom-0 md:left-56">
      <!-- Progress bar -->
      <div class="h-[2px] w-full" style="background: rgba(255, 255, 255, 0.06)">
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
        <button class="min-w-0 flex-1 cursor-pointer border-0 bg-transparent p-0 text-left" @click="goToBook">
          <p class="flex items-center gap-1.5 truncate text-[13px] leading-tight font-semibold text-[--t1]">
            <span
              v-if="playingOffline"
              class="h-2 w-2 shrink-0 rounded-full bg-emerald-400"
              style="box-shadow: 0 0 6px rgba(52, 211, 153, 0.5)"
              title="Офлайн"
            />
            {{ currentBook.title }}
          </p>
          <p class="mt-0.5 truncate text-[11px] leading-tight text-[--t3]">
            {{ currentTrack?.filename ?? '' }}
          </p>
        </button>

        <!-- Play / Pause -->
        <button
          class="flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full border-0 transition-all"
          style="background: var(--gradient-accent); box-shadow: 0 2px 12px rgba(232, 146, 58, 0.25)"
          @click="togglePlay"
        >
          <component :is="isPlaying ? IconPause : IconPlay" :size="16" style="color: #fff" />
        </button>

        <!-- +15s skip -->
        <button
          class="shrink-0 cursor-pointer border-0 bg-transparent p-1.5 text-[--t3] transition-colors hover:text-[--t1]"
          @click="skipForward()"
        >
          <IconForward15 :size="18" />
        </button>

        <!-- Close -->
        <button
          class="shrink-0 cursor-pointer border-0 bg-transparent p-1.5 text-[--t3] transition-colors hover:text-[--t1]"
          @click="closePlayer"
        >
          <IconXCircle :size="18" />
        </button>
      </div>
    </div>
  </transition>
</template>
