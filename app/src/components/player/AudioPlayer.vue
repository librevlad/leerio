<script setup lang="ts">
import { usePlayer } from '../../composables/usePlayer'
import { IconPlay, IconPause, IconSkipForward, IconSkipBack, IconVolume, IconVolumeMute } from '../shared/icons'

const {
  currentBook,
  tracks,
  currentTrackIndex,
  isPlaying,
  currentTime,
  duration,
  volume,
  currentTrack,
  formatTime,
  togglePlay,
  nextTrack,
  prevTrack,
  playTrack,
  setVolume,
  startSeek,
  endSeek,
} = usePlayer()

function onSeekInput() {
  startSeek()
}

function onSeekChange(e: Event) {
  const val = parseFloat((e.target as HTMLInputElement).value)
  endSeek(val)
}
</script>

<template>
  <div v-if="currentBook" class="card p-5">
    <h3 class="section-label mb-4">Плеер</h3>

    <!-- Now playing -->
    <div class="mb-4">
      <p class="truncate text-[14px] font-semibold text-[--t1]">
        {{ currentTrack?.filename ?? '—' }}
      </p>
      <p class="text-[12px] text-[--t3]">Трек {{ currentTrackIndex + 1 }} из {{ tracks.length }}</p>
    </div>

    <!-- Controls -->
    <div class="mb-5 flex items-center justify-center gap-5">
      <button
        class="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-full border-0 bg-transparent p-2.5 text-[--t2] transition-colors hover:text-[--t1]"
        @click="prevTrack"
      >
        <IconSkipBack :size="20" />
      </button>

      <button
        class="flex h-14 w-14 cursor-pointer items-center justify-center rounded-full border-0 transition-all"
        style="background: var(--gradient-accent); box-shadow: 0 4px 20px rgba(232, 146, 58, 0.3)"
        @click="togglePlay"
      >
        <component :is="isPlaying ? IconPause : IconPlay" :size="22" style="color: #fff" />
      </button>

      <button
        class="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-full border-0 bg-transparent p-2.5 text-[--t2] transition-colors hover:text-[--t1]"
        @click="nextTrack"
      >
        <IconSkipForward :size="20" />
      </button>
    </div>

    <!-- Seek bar -->
    <div class="mb-4">
      <input
        type="range"
        :min="0"
        :max="duration || 0"
        :value="currentTime"
        step="0.1"
        class="w-full"
        @input="onSeekInput"
        @change="onSeekChange"
      />
      <div class="mt-1 flex justify-between text-[11px] text-[--t3]">
        <span>{{ formatTime(currentTime) }}</span>
        <span>{{ formatTime(duration) }}</span>
      </div>
    </div>

    <!-- Volume -->
    <div class="mb-5 flex items-center gap-3">
      <button
        class="cursor-pointer border-0 bg-transparent p-1 text-[--t3] transition-colors hover:text-[--t1]"
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
        style="max-width: 120px"
        @input="(e: Event) => setVolume(parseFloat((e.target as HTMLInputElement).value))"
      />
    </div>

    <!-- Track list -->
    <div class="border-t border-[--border] pt-4">
      <p class="section-label mb-3">Треки</p>
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
          <span class="shrink-0 text-[11px] text-[--t3]">
            {{ formatTime(track.duration) }}
          </span>
        </button>
      </div>
    </div>
  </div>
</template>
