<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useUserBooks } from '@/composables/useUserBooks'
import { useLocalBooks } from '@/composables/useLocalBooks'
import { useDownloads } from '@/composables/useDownloads'
import { usePlayer } from '@/composables/usePlayer'
import { useToast } from '@/composables/useToast'
import { userBookCoverUrl, coverUrl } from '@/api'
import {
  IconTrash,
  IconMusic,
  IconMicrophone,
  IconFolder,
  IconPlus,
  IconCheck,
  IconSmartphone,
} from '@/components/shared/icons'
import SourceBadge from '@/components/shared/SourceBadge.vue'
import type { Book, TTSJob } from '@/types'

const toast = useToast()
const { userBooks, ttsJobs, loading: ubLoading, loadUserBooks, loadTTSJobs, deleteBook, pollJob } = useUserBooks()
const { localBooks, removeLocalBook } = useLocalBooks()
const downloads = useDownloads()
const { loadBook } = usePlayer()

const activeFilter = ref<'all' | 'downloaded' | 'local' | 'uploaded'>('all')
const activeJobs = computed(() => ttsJobs.value.filter((j: TTSJob) => j.status === 'processing'))

interface UnifiedItem {
  id: string
  title: string
  author: string
  source: 'downloaded' | 'local' | 'uploaded'
  hasCover: boolean
  coverSrc?: string
  trackCount?: number
  slug?: string
  isPersonal?: boolean
  reader?: string
}

const items = computed<UnifiedItem[]>(() => {
  const result: UnifiedItem[] = []

  // Downloaded books
  if (activeFilter.value === 'all' || activeFilter.value === 'downloaded') {
    for (const dm of downloads.downloadedBooks.value) {
      result.push({
        id: dm.bookId,
        title: dm.title ?? dm.bookId,
        author: dm.author ?? '',
        source: 'downloaded',
        hasCover: true,
        coverSrc: coverUrl(dm.bookId),
        trackCount: dm.tracks?.length,
      })
    }
  }

  // Local books
  if (activeFilter.value === 'all' || activeFilter.value === 'local') {
    for (const lb of localBooks.value) {
      result.push({
        id: lb.id,
        title: lb.title,
        author: lb.author,
        source: 'local',
        hasCover: !!lb.coverDataUrl,
        coverSrc: lb.coverDataUrl,
        trackCount: lb.tracks.length,
      })
    }
  }

  // Uploaded / TTS books
  if (activeFilter.value === 'all' || activeFilter.value === 'uploaded') {
    for (const ub of userBooks.value) {
      result.push({
        id: ub.id,
        title: ub.title,
        author: ub.author,
        source: 'uploaded',
        hasCover: ub.has_cover,
        coverSrc: ub.has_cover ? userBookCoverUrl(ub.slug) : undefined,
        trackCount: ub.mp3_count,
        slug: ub.slug,
        isPersonal: true,
        reader: ub.reader,
      })
    }
  }

  return result
})

const totalCount = computed(() => {
  return downloads.downloadedBooks.value.length + localBooks.value.length + userBooks.value.length
})

onMounted(async () => {
  await Promise.all([loadUserBooks(), loadTTSJobs()])

  for (const job of activeJobs.value) {
    pollJob(job.id, (j: TTSJob) => {
      const idx = ttsJobs.value.findIndex((x: TTSJob) => x.id === j.id)
      if (idx >= 0) ttsJobs.value[idx] = j
      if (j.status === 'done') {
        toast.success(`"${j.title}" готова!`)
        loadUserBooks()
      }
    })
  }
})

function playItem(item: UnifiedItem) {
  const asBook: Book = {
    id: item.id,
    folder: '',
    category: '',
    author: item.author,
    title: item.title,
    reader: item.reader ?? '',
    path: '',
    progress: 0,
    tags: [],
    note: '',
    has_cover: item.hasCover,
    is_personal: item.isPersonal,
  }
  loadBook(asBook)
}

async function handleDelete(item: UnifiedItem) {
  if (!confirm(`Удалить "${item.title}"?`)) return
  try {
    if (item.source === 'local') {
      await removeLocalBook(item.id)
    } else if (item.source === 'uploaded' && item.slug) {
      await deleteBook(item.slug)
    } else if (item.source === 'downloaded') {
      await downloads.deleteBook(item.id)
    }
    toast.success('Удалено')
  } catch {
    toast.error('Ошибка удаления')
  }
}

const filters = [
  { key: 'all' as const, label: 'Все' },
  { key: 'downloaded' as const, label: 'Скачанные' },
  { key: 'local' as const, label: 'Локальные' },
  { key: 'uploaded' as const, label: 'Загруженные' },
]

const sourceBadgeMap: Record<UnifiedItem['source'], 'library' | 'librivox' | 'user' | 'local'> = {
  downloaded: 'library',
  local: 'local',
  uploaded: 'user',
}

function coverGradient(source: string) {
  if (source === 'local') return 'from-indigo-500/10 to-blue-500/10'
  if (source === 'uploaded') return 'from-teal-500/10 to-violet-500/10'
  return 'from-emerald-500/10 to-teal-500/10'
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-[20px] font-bold text-[--t1]">Моя библиотека</h1>
        <p class="mt-1 text-[13px] text-[--t3]">
          {{ totalCount > 0 ? `${totalCount} книг` : 'Пока нет книг' }}
        </p>
      </div>
      <router-link
        to="/upload"
        class="flex items-center gap-1.5 rounded-lg bg-[--accent-soft] px-3 py-2 text-[12px] font-medium text-[--accent-2] transition-all hover:bg-[--accent-soft]"
      >
        <IconPlus :size="14" />
        Добавить
      </router-link>
    </div>

    <!-- Active TTS Jobs -->
    <div v-if="activeJobs.length" class="mb-6 space-y-3">
      <h2 class="text-[14px] font-semibold text-[--t2]">Конвертация</h2>
      <div v-for="job in activeJobs" :key="job.id" class="rounded-xl border border-violet-500/30 bg-violet-500/5 p-4">
        <div class="mb-1 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <IconMicrophone :size="14" class="text-violet-400" />
            <span class="text-[13px] font-medium text-[--t1]">{{ job.title }}</span>
          </div>
          <span class="text-[12px] text-[--t3]">{{ job.done_chapters }}/{{ job.total_chapters }}</span>
        </div>
        <div class="h-1.5 overflow-hidden rounded-full bg-white/10">
          <div
            class="h-full rounded-full bg-violet-500 transition-all duration-300"
            :style="{ width: `${job.progress}%` }"
          />
        </div>
      </div>
    </div>

    <!-- Filter tabs -->
    <div class="scrollbar-hide mb-5 flex gap-2 overflow-x-auto">
      <button
        v-for="f in filters"
        :key="f.key"
        class="flex-shrink-0 rounded-full border px-3.5 py-1.5 text-[12px] font-medium transition-all"
        :class="
          activeFilter === f.key
            ? 'border-[--accent]/40 bg-[--accent-soft] text-[--accent-2]'
            : 'border-[--border] text-[--t3] hover:text-[--t2]'
        "
        @click="activeFilter = f.key"
      >
        {{ f.label }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="ubLoading" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="i in 3" :key="i" class="skeleton h-36 rounded-2xl" />
    </div>

    <!-- Empty state -->
    <div v-else-if="items.length === 0" class="flex flex-col items-center justify-center py-16 text-center">
      <IconFolder :size="48" class="mb-4 text-[--t3]" />
      <p class="mb-2 text-[14px] font-medium text-[--t2]">
        {{ activeFilter === 'all' ? 'Библиотека пуста' : 'Нет книг в этой категории' }}
      </p>
      <p class="mb-4 text-[13px] text-[--t3]">Загрузите, скачайте или добавьте книгу с устройства</p>
      <router-link to="/upload" class="btn btn-primary flex items-center gap-2 text-[13px]">
        <IconPlus :size="16" />
        Добавить
      </router-link>
    </div>

    <!-- Grid -->
    <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <div
        v-for="item in items"
        :key="item.id"
        class="group cursor-pointer overflow-hidden rounded-2xl border border-[--border] transition-all hover:border-[--accent]/20 hover:shadow-lg"
      >
        <!-- Cover -->
        <div
          class="relative flex h-32 items-center justify-center overflow-hidden"
          :class="item.coverSrc ? '' : `bg-gradient-to-br ${coverGradient(item.source)}`"
          @click="playItem(item)"
        >
          <img v-if="item.coverSrc" :src="item.coverSrc" class="h-full w-full object-cover" alt="" />
          <component :is="item.source === 'local' ? IconSmartphone : IconMusic" v-else :size="36" class="text-[--t3]" />

          <div class="absolute top-2 right-2">
            <SourceBadge :source="sourceBadgeMap[item.source]" />
          </div>

          <span
            v-if="item.source === 'downloaded'"
            class="absolute right-2 bottom-2 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/90 text-white"
          >
            <IconCheck :size="12" />
          </span>
        </div>

        <!-- Info -->
        <div class="p-3" @click="playItem(item)">
          <h3 class="mb-1 line-clamp-2 text-[13px] font-semibold text-[--t1]">{{ item.title }}</h3>
          <p v-if="item.author" class="truncate text-[12px] text-[--t3]">{{ item.author }}</p>
          <div class="mt-2 flex items-center justify-between">
            <span v-if="item.trackCount" class="flex items-center gap-1 text-[11px] text-[--t3]">
              <IconMusic :size="12" />
              {{ item.trackCount }} треков
            </span>
            <button
              class="rounded-lg p-1.5 text-[--t3] opacity-0 transition-all group-hover:opacity-100 hover:bg-red-500/15 hover:text-red-400"
              @click.stop="handleDelete(item)"
            >
              <IconTrash :size="14" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
