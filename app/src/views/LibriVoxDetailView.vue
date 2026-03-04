<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, librivoxCoverUrl } from '../api'
import { usePlayer } from '../composables/usePlayer'
import AudioPlayer from '../components/player/AudioPlayer.vue'
import { IconArrowLeft, IconPlay, IconClock, IconMusic } from '../components/shared/icons'
import type { LibriVoxBook, Book, Track } from '../types'

const route = useRoute()
const router = useRouter()
const player = usePlayer()

const book = ref<LibriVoxBook | null>(null)
const chapters = ref<Track[]>([])
const loading = ref(true)

const bookId = computed(() => (book.value ? `lv:${book.value.librivox_id}` : ''))
const isCurrentBook = computed(() => player.currentBook.value?.id === bookId.value)
const coverSrc = computed(() => (book.value ? librivoxCoverUrl(book.value.librivox_id) : ''))

function mapRaw(raw: Record<string, unknown>): LibriVoxBook {
  const lvId = String(raw.librivox_id ?? '')
  return {
    id: `lv:${lvId}`,
    librivox_id: lvId,
    source: 'librivox',
    title: String(raw.title ?? ''),
    author: String(raw.author ?? ''),
    description: String(raw.description ?? ''),
    language: String(raw.language ?? ''),
    copyright_year: String(raw.copyright_year ?? ''),
    num_sections: Number(raw.num_sections ?? 0),
    total_time: String(raw.total_time ?? ''),
    total_time_secs: Number(raw.total_time_secs ?? 0),
    url_librivox: String(raw.url_librivox ?? ''),
  }
}

async function loadBook() {
  loading.value = true
  try {
    const lvId = route.params.id as string
    const [rawBook, trackData] = await Promise.all([api.librivoxBook(lvId), api.librivoxChapters(lvId)])
    book.value = mapRaw(rawBook as unknown as Record<string, unknown>)
    chapters.value = trackData.tracks
  } catch {
    router.push('/discover')
  } finally {
    loading.value = false
  }
}

function startListening() {
  if (!book.value) return
  // Build a Book-compatible object for the player
  const b: Book = {
    id: `lv:${book.value.librivox_id}`,
    folder: '',
    category: '',
    author: book.value.author,
    title: book.value.title,
    reader: '',
    path: '',
    progress: 0,
    tags: [],
    note: '',
  }
  player.loadBook(b)
}

function formatDuration(secs: number): string {
  if (!secs) return ''
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  if (h > 0) return `${h}ч ${m}м`
  return `${m}м`
}

function formatChapterDuration(secs: number): string {
  if (!secs) return ''
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

const coverError = ref(false)

onMounted(loadBook)
</script>

<template>
  <div>
    <button
      class="mb-4 -ml-3 flex min-h-[44px] cursor-pointer items-center gap-2 rounded-xl border-0 bg-transparent px-3 py-2.5 text-[13px] text-[--t3] transition-all hover:bg-white/5 hover:text-[--t1] active:bg-white/8 md:mb-6"
      @click="router.back()"
    >
      <IconArrowLeft :size="15" />
      <span class="font-medium">Назад</span>
    </button>

    <!-- Skeleton -->
    <div v-if="loading">
      <div class="skeleton mb-5 h-48 rounded-2xl" />
      <div class="skeleton mb-3 h-8 w-3/4" />
      <div class="skeleton mb-5 h-5 w-1/2" />
      <div class="skeleton mb-5 h-10 w-32" />
      <div class="space-y-2">
        <div v-for="i in 5" :key="i" class="skeleton h-12" />
      </div>
    </div>

    <div v-else-if="book" class="fade-in">
      <!-- Hero -->
      <div class="card mb-5 overflow-hidden rounded-2xl p-5" style="border: 1px solid var(--border)">
        <div class="flex flex-col gap-5 sm:flex-row">
          <!-- Cover -->
          <div
            class="flex h-40 w-32 shrink-0 items-center justify-center overflow-hidden rounded-xl sm:h-48 sm:w-36"
            style="background: linear-gradient(135deg, rgba(20, 184, 166, 0.15) 0%, rgba(7, 7, 14, 0.6) 100%)"
          >
            <img
              v-if="!coverError"
              :src="coverSrc"
              :alt="book.title"
              class="h-full w-full object-cover"
              @error="coverError = true"
            />
            <span v-else class="text-3xl text-teal-400/40">LV</span>
          </div>

          <!-- Info -->
          <div class="flex-1">
            <h1 class="mb-1.5 text-[20px] leading-tight font-bold text-[--t1]">{{ book.title }}</h1>
            <p class="mb-3 text-[14px] text-[--t2]">{{ book.author }}</p>
            <div class="mb-3 flex flex-wrap gap-3 text-[12px] text-[--t3]">
              <span v-if="book.language" class="rounded-md bg-teal-500/10 px-2 py-0.5 font-medium text-teal-400">
                {{ book.language }}
              </span>
              <span v-if="book.copyright_year" class="flex items-center gap-1">
                {{ book.copyright_year }}
              </span>
              <span v-if="book.total_time_secs" class="flex items-center gap-1">
                <IconClock :size="13" />
                {{ formatDuration(book.total_time_secs) }}
              </span>
              <span class="flex items-center gap-1">
                <IconMusic :size="13" />
                {{ book.num_sections }} глав
              </span>
            </div>
            <!-- eslint-disable vue/no-v-html -->
            <p
              v-if="book.description"
              class="line-clamp-4 text-[13px] leading-relaxed text-[--t3]"
              v-html="book.description"
            />
            <!-- eslint-enable vue/no-v-html -->
          </div>
        </div>
      </div>

      <!-- Listen button -->
      <div class="mb-5 flex flex-wrap items-center gap-3">
        <button class="btn btn-primary" @click="startListening">
          <IconPlay :size="16" />
          {{ isCurrentBook ? 'Продолжить' : 'Слушать' }}
        </button>
        <a
          v-if="book.url_librivox"
          :href="book.url_librivox"
          target="_blank"
          rel="noopener"
          class="btn btn-ghost text-[12px]"
        >
          LibriVox.org
        </a>
      </div>

      <!-- Audio player (when this book is loaded) -->
      <AudioPlayer v-if="isCurrentBook" class="mb-5" />

      <!-- Chapter list -->
      <div v-if="chapters.length > 0" class="card rounded-2xl p-4" style="border: 1px solid var(--border)">
        <h2 class="mb-3 text-[14px] font-semibold text-[--t1]">
          Главы <span class="font-normal text-[--t3]">({{ chapters.length }})</span>
        </h2>
        <div class="divide-y" style="border-color: var(--border)">
          <button
            v-for="ch in chapters"
            :key="ch.index"
            class="flex w-full cursor-pointer items-center gap-3 border-0 bg-transparent px-2 py-2.5 text-left transition-colors hover:bg-white/[0.03]"
            :class="isCurrentBook && player.currentTrackIndex.value === ch.index ? 'text-teal-400' : 'text-[--t2]'"
            @click="isCurrentBook ? player.playTrack(ch.index) : startListening()"
          >
            <span class="w-6 shrink-0 text-center text-[11px] text-[--t3]">{{ ch.index + 1 }}</span>
            <span class="flex-1 truncate text-[13px]">{{ ch.filename }}</span>
            <span v-if="ch.duration" class="shrink-0 text-[11px] text-[--t3]">
              {{ formatChapterDuration(ch.duration) }}
            </span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
