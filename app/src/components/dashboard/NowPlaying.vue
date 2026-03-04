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
    class="card flex cursor-pointer items-center gap-5 p-5 transition-all hover:brightness-110"
    style="background: linear-gradient(135deg, rgba(232, 146, 58, 0.08) 0%, rgba(96, 165, 250, 0.06) 100%)"
    @click="play"
  >
    <img
      :src="coverUrl(data.cover_id)"
      :alt="data.title"
      class="h-20 w-20 shrink-0 rounded-xl object-cover shadow-lg"
      loading="lazy"
      @error="($event.target as HTMLImageElement).style.display = 'none'"
    />
    <div class="min-w-0 flex-1">
      <p class="mb-0.5 text-[11px] font-medium tracking-wider text-[--accent] uppercase">Сейчас слушаю</p>
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
      class="flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-white transition-transform hover:scale-105"
      style="background: var(--gradient-bar)"
      @click.stop="play"
    >
      <IconPlay :size="20" />
    </button>
  </div>
</template>
