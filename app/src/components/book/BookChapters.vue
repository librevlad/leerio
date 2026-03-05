<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '../../api'
import { usePlayer } from '../../composables/usePlayer'
import { IconChevronDown, IconChevronUp, IconPlay } from '../shared/icons'
import type { Book, Track } from '../../types'

const props = defineProps<{ book: Book }>()

const player = usePlayer()
const tracks = ref<Track[]>([])
const loading = ref(true)
const expanded = ref(false)

const COLLAPSED_LIMIT = 8

const isCurrentBook = computed(() => player.currentBook.value?.id === props.book.id)

const visibleTracks = computed(() => {
  if (expanded.value || tracks.value.length <= COLLAPSED_LIMIT) return tracks.value
  return tracks.value.slice(0, COLLAPSED_LIMIT)
})

const totalDuration = computed(() => {
  const total = tracks.value.reduce((sum, t) => sum + t.duration, 0)
  const hours = Math.floor(total / 3600)
  const minutes = Math.round((total % 3600) / 60)
  if (hours > 0) return `${hours} ч ${minutes} мин`
  return `${minutes} мин`
})

function formatDuration(sec: number): string {
  if (!sec || !isFinite(sec)) return '-'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

async function handleTrackClick(index: number) {
  if (isCurrentBook.value) {
    player.playTrack(index)
  } else {
    await player.loadBook(props.book)
    player.playTrack(index)
  }
}

onMounted(async () => {
  try {
    const res = await api.getBookTracks(props.book.id)
    tracks.value = res.tracks
  } catch {
    // silent — no tracks
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="card px-5 py-4">
    <p class="section-label mb-3">Содержание</p>

    <!-- Skeleton -->
    <div v-if="loading" class="space-y-2">
      <div v-for="i in 4" :key="i" class="skeleton h-10 rounded-xl" />
    </div>

    <!-- Empty -->
    <p v-else-if="tracks.length === 0" class="text-[13px] text-[--t3]">Нет треков</p>

    <!-- Track list -->
    <div v-else>
      <div class="space-y-0.5">
        <button
          v-for="track in visibleTracks"
          :key="track.index"
          class="flex w-full cursor-pointer items-center gap-3 rounded-xl border-0 px-3 py-2.5 text-left transition-colors"
          :class="
            isCurrentBook && player.currentTrackIndex.value === track.index
              ? 'bg-[--accent-soft] text-[--t1]'
              : 'bg-transparent text-[--t2] hover:bg-white/[0.04]'
          "
          @click="handleTrackClick(track.index)"
        >
          <!-- Track number / play icon -->
          <span class="w-6 shrink-0 text-center font-mono text-[12px] text-[--t3]">
            <IconPlay
              v-if="isCurrentBook && player.currentTrackIndex.value === track.index && player.isPlaying.value"
              :size="12"
              class="inline text-[--accent]"
            />
            <span v-else>{{ track.index + 1 }}</span>
          </span>
          <!-- Filename -->
          <span class="min-w-0 flex-1 truncate text-[13px]">{{ track.filename }}</span>
          <!-- Duration -->
          <span class="shrink-0 font-mono text-[12px] text-[--t3]">{{ formatDuration(track.duration) }}</span>
        </button>
      </div>

      <!-- Expand toggle -->
      <button
        v-if="tracks.length > COLLAPSED_LIMIT"
        class="mt-2 flex w-full cursor-pointer items-center justify-center gap-1.5 rounded-xl border-0 bg-transparent py-2 text-[12px] font-semibold text-[--t3] transition-colors hover:text-[--t2]"
        @click="expanded = !expanded"
      >
        <template v-if="expanded">
          Свернуть
          <IconChevronUp :size="14" />
        </template>
        <template v-else>
          Показать все ({{ tracks.length }})
          <IconChevronDown :size="14" />
        </template>
      </button>

      <!-- Total duration -->
      <p class="mt-2 border-t border-white/[0.04] pt-3 text-[12px] text-[--t3]">Всего: {{ totalDuration }}</p>
    </div>
  </div>
</template>
