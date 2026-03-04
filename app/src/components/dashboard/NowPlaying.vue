<script setup lang="ts">
import { coverUrl } from '../../api'
import { usePlayer } from '../../composables/usePlayer'
import type { NowPlaying } from '../../types'
import { IconPlay } from '../shared/icons'

const props = defineProps<{ data: NowPlaying }>()
const { loadBook } = usePlayer()

async function play() {
  // Create a minimal Book object to load into player
  const book = {
    id: props.data.book_id,
    title: props.data.title,
    author: props.data.author,
    folder: '',
    category: '',
    reader: '',
    path: '',
    progress: props.data.progress,
    tags: [],
    note: '',
  }
  await loadBook(book)
}
</script>

<template>
  <div
    class="card relative flex cursor-pointer items-center gap-5 overflow-hidden p-5 transition-all hover:brightness-110"
    style="background: linear-gradient(135deg, rgba(232, 146, 58, 0.08) 0%, rgba(96, 165, 250, 0.06) 100%)"
    @click="play"
  >
    <!-- Blurred cover background -->
    <img
      :src="coverUrl(data.cover_id)"
      alt=""
      class="pointer-events-none absolute inset-0 h-full w-full scale-110 object-cover opacity-20 blur-[40px]"
      loading="lazy"
    />
    <div class="absolute inset-0 bg-black/40" />

    <!-- Content (above blur layer) -->
    <img
      :src="coverUrl(data.cover_id)"
      :alt="data.title"
      class="relative z-10 h-28 w-28 shrink-0 rounded-xl object-cover shadow-lg"
      loading="lazy"
      @error="($event.target as HTMLImageElement).style.display = 'none'"
    />
    <div class="relative z-10 min-w-0 flex-1">
      <p class="mb-0.5 flex items-center gap-2 text-[11px] font-medium tracking-wider text-[--accent] uppercase">
        <span class="inline-block h-2 w-2 animate-pulse rounded-full bg-[--accent]" />
        Сейчас слушаю
      </p>
      <p class="mb-1 truncate text-[16px] font-bold text-[--t1]">{{ data.title }}</p>
      <p class="mb-3 truncate text-[13px] text-[--t3]">{{ data.author }}</p>
      <div class="flex items-center gap-3">
        <div class="h-1.5 flex-1 overflow-hidden rounded-full" style="background: rgba(255, 255, 255, 0.08)">
          <div
            class="h-full rounded-full transition-all duration-500"
            style="background: var(--gradient-bar)"
            :style="{ width: data.progress + '%' }"
          />
        </div>
        <span class="text-[11px] font-medium text-[--t3]">{{ data.progress }}%</span>
      </div>
    </div>
    <button
      class="relative z-10 flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-white transition-transform hover:scale-105"
      style="background: var(--gradient-bar)"
      @click.stop="play"
    >
      <IconPlay :size="22" />
    </button>
  </div>
</template>
