<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../../api'
import { trackDisplayName as _trackDisplayName } from '../../utils/format'
import { usePlayer } from '../../composables/usePlayer'
import { IconChevronDown, IconChevronUp, IconPlay } from '../shared/icons'
import type { Book, Track } from '../../types'

const { t } = useI18n()
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
  if (!total) return null
  const hours = Math.floor(total / 3600)
  const minutes = Math.round((total % 3600) / 60)
  if (hours > 0) return `${hours} ${t('common.unitH')} ${minutes} ${t('common.unitMin')}`
  return `${minutes} ${t('common.unitMin')}`
})

function formatDuration(sec: number): string {
  if (!sec || !isFinite(sec)) return '-'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function trackName(track: Track, index: number): string {
  return _trackDisplayName(track.filename, index, t)
}

async function handleTrackClick(index: number) {
  if (isCurrentBook.value) {
    player.playTrack(index)
  } else {
    await player.loadBook(props.book)
    player.playTrack(index)
  }
  player.openFullscreen()
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
    <p class="section-label mb-3">{{ t('book.contents') }}</p>

    <!-- Skeleton -->
    <div v-if="loading" class="space-y-2">
      <div v-for="i in 4" :key="i" class="skeleton h-10 rounded-xl" />
    </div>

    <!-- Empty -->
    <p v-else-if="tracks.length === 0" class="text-[13px] text-[--t3]">{{ t('book.noTracks') }}</p>

    <!-- Track list -->
    <div v-else>
      <div
        class="space-y-0.5"
        :class="expanded && tracks.length > 50 ? 'scrollbar-hide max-h-[60vh] overflow-y-auto' : ''"
      >
        <button
          v-for="track in visibleTracks"
          :key="track.index"
          class="group flex w-full cursor-pointer flex-col gap-0 rounded-xl border-0 px-3 py-2.5 text-left transition-colors"
          :class="
            isCurrentBook && player.currentTrackIndex.value === track.index
              ? 'bg-[--accent-soft] text-[--t1]'
              : 'bg-transparent text-[--t2] hover:bg-white/[0.04]'
          "
          :aria-label="t('player.playTrackAria', { index: track.index + 1 })"
          @click="handleTrackClick(track.index)"
        >
          <div class="flex w-full items-center gap-3">
            <!-- Track number / play icon -->
            <span class="relative w-6 shrink-0 text-center font-mono text-[12px] text-[--t3]">
              <IconPlay
                v-if="isCurrentBook && player.currentTrackIndex.value === track.index && player.isPlaying.value"
                :size="12"
                class="inline text-[--accent]"
              />
              <template v-else>
                <span class="group-hover:invisible">{{ track.index + 1 }}</span>
                <IconPlay :size="12" class="absolute inset-0 m-auto hidden text-[--t2] group-hover:block" />
              </template>
            </span>
            <!-- Track name -->
            <span class="min-w-0 flex-1 truncate text-[13px]">{{ trackName(track, track.index) }}</span>
            <!-- Duration -->
            <span v-if="track.duration" class="shrink-0 font-mono text-[12px] text-[--t3]">{{
              formatDuration(track.duration)
            }}</span>
          </div>
          <!-- Per-track progress bar (current track only) -->
          <div
            v-if="isCurrentBook && player.currentTrackIndex.value === track.index && player.duration.value > 0"
            class="mt-1.5 ml-9 h-1 overflow-hidden rounded-full bg-white/[0.08]"
          >
            <div
              class="h-full rounded-full bg-[--accent] transition-all duration-300"
              :style="{ width: `${Math.min((player.currentTime.value / player.duration.value) * 100, 100)}%` }"
            />
          </div>
          <!-- Completed track indicator (past tracks) -->
          <div
            v-else-if="isCurrentBook && track.index < player.currentTrackIndex.value"
            class="mt-1.5 ml-9 h-1 overflow-hidden rounded-full bg-white/[0.08]"
          >
            <div class="h-full w-full rounded-full bg-emerald-500/60" />
          </div>
        </button>
      </div>

      <!-- Expand toggle -->
      <button
        v-if="tracks.length > COLLAPSED_LIMIT"
        class="mt-2 flex w-full cursor-pointer items-center justify-center gap-1.5 rounded-xl border-0 bg-transparent py-2 text-[12px] font-semibold text-[--t3] transition-colors hover:text-[--t2]"
        @click="expanded = !expanded"
      >
        <template v-if="expanded">
          {{ t('book.collapse') }}
          <IconChevronUp :size="14" />
        </template>
        <template v-else>
          {{ t('book.showAllTracks', { count: tracks.length }) }}
          <IconChevronDown :size="14" />
        </template>
      </button>

      <!-- Total duration -->
      <p v-if="totalDuration" class="mt-2 border-t border-white/[0.04] pt-3 text-[12px] text-[--t3]">
        {{ t('book.totalDuration') }} {{ totalDuration }}
      </p>
    </div>
  </div>
</template>
