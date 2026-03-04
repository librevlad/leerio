<script setup lang="ts">
import { usePlayer } from '../../composables/usePlayer'
import {
  IconPlay, IconPause, IconSkipForward, IconSkipBack,
  IconVolume, IconVolumeMute,
} from '../shared/icons'

const {
  currentBook, tracks, currentTrackIndex, isPlaying,
  currentTime, duration, volume,
  currentTrack, formatTime,
  togglePlay, nextTrack, prevTrack, playTrack,
  setVolume, startSeek, endSeek,
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
      <p class="text-[14px] font-semibold text-[--t1] truncate">
        {{ currentTrack?.filename ?? '—' }}
      </p>
      <p class="text-[12px] text-[--t3]">
        Трек {{ currentTrackIndex + 1 }} из {{ tracks.length }}
      </p>
    </div>

    <!-- Controls -->
    <div class="flex items-center justify-center gap-5 mb-5">
      <button
        class="p-2.5 rounded-full bg-transparent border-0 text-[--t2] hover:text-[--t1] transition-colors cursor-pointer min-h-[44px] min-w-[44px] flex items-center justify-center"
        @click="prevTrack"
      >
        <IconSkipBack :size="20" />
      </button>

      <button
        class="w-14 h-14 rounded-full flex items-center justify-center border-0 cursor-pointer transition-all"
        style="background: var(--gradient-accent); box-shadow: 0 4px 20px rgba(232,146,58,0.3)"
        @click="togglePlay"
      >
        <component :is="isPlaying ? IconPause : IconPlay" :size="22" style="color: #fff" />
      </button>

      <button
        class="p-2.5 rounded-full bg-transparent border-0 text-[--t2] hover:text-[--t1] transition-colors cursor-pointer min-h-[44px] min-w-[44px] flex items-center justify-center"
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
      <div class="flex justify-between text-[11px] text-[--t3] mt-1">
        <span>{{ formatTime(currentTime) }}</span>
        <span>{{ formatTime(duration) }}</span>
      </div>
    </div>

    <!-- Volume -->
    <div class="flex items-center gap-3 mb-5">
      <button
        class="p-1 bg-transparent border-0 text-[--t3] hover:text-[--t1] transition-colors cursor-pointer"
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
      <div class="max-h-64 overflow-y-auto scrollbar-hide space-y-1">
        <button
          v-for="track in tracks"
          :key="track.index"
          class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border-0 cursor-pointer transition-all text-left min-h-[44px]"
          :class="track.index === currentTrackIndex
            ? 'text-[--accent]'
            : 'text-[--t2] hover:text-[--t1]'"
          :style="track.index === currentTrackIndex
            ? 'background: var(--accent-soft)'
            : 'background: transparent'"
          @click="playTrack(track.index)"
        >
          <span class="text-[11px] font-mono w-6 text-right shrink-0 opacity-50">
            {{ track.index + 1 }}
          </span>
          <span class="text-[13px] font-medium truncate flex-1">
            {{ track.filename }}
          </span>
          <span class="text-[11px] text-[--t3] shrink-0">
            {{ formatTime(track.duration) }}
          </span>
        </button>
      </div>
    </div>
  </div>
</template>
