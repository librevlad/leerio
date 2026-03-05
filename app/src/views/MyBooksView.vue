<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useUserBooks } from '@/composables/useUserBooks'
import { usePlayer } from '@/composables/usePlayer'
import { useToast } from '@/composables/useToast'
import { userBookCoverUrl } from '@/api'
import { IconTrash, IconMusic, IconMicrophone, IconUpload, IconFolder, IconPlus } from '@/components/shared/icons'
import type { Book, TTSJob } from '@/types'

const toast = useToast()
const { userBooks, ttsJobs, loading, loadUserBooks, loadTTSJobs, deleteBook, pollJob } = useUserBooks()
const { loadBook } = usePlayer()

const activeJobs = computed(() => ttsJobs.value.filter((j: TTSJob) => j.status === 'processing'))

onMounted(async () => {
  await Promise.all([loadUserBooks(), loadTTSJobs()])

  // Poll active jobs
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

function playBook(book: { id: string; title: string; author: string; reader: string; has_cover: boolean }) {
  const asBook: Book = {
    id: book.id,
    folder: '',
    category: 'Личные',
    author: book.author,
    title: book.title,
    reader: book.reader,
    path: '',
    progress: 0,
    tags: [],
    note: '',
    has_cover: book.has_cover,
    is_personal: true,
  }
  loadBook(asBook)
}

async function handleDelete(slug: string, title: string) {
  if (!confirm(`Удалить "${title}"?`)) return
  try {
    await deleteBook(slug)
    toast.success('Книга удалена')
  } catch {
    toast.error('Ошибка удаления')
  }
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-[20px] font-bold text-[--t1]">Мои книги</h1>
        <p class="mt-1 text-[13px] text-[--t3]">
          {{ userBooks.length ? `${userBooks.length} книг` : 'Пока нет загруженных книг' }}
        </p>
      </div>
      <router-link
        to="/upload"
        class="flex items-center gap-1.5 rounded-lg bg-teal-500/15 px-3 py-2 text-[12px] font-medium text-teal-300 transition-all hover:bg-teal-500/25"
      >
        <IconPlus :size="14" />
        Загрузить
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

    <!-- Loading -->
    <div v-if="loading" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="i in 3" :key="i" class="skeleton h-36 rounded-2xl" />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="userBooks.length === 0 && !activeJobs.length"
      class="flex flex-col items-center justify-center py-16 text-center"
    >
      <IconFolder :size="48" class="mb-4 text-[--t3]" />
      <p class="mb-2 text-[14px] font-medium text-[--t2]">Библиотека пуста</p>
      <p class="mb-4 text-[13px] text-[--t3]">Загрузите MP3 или создайте аудиокнигу из документа</p>
      <router-link
        to="/upload"
        class="flex items-center gap-2 rounded-lg bg-teal-500 px-4 py-2.5 text-[13px] font-semibold text-white transition-all hover:bg-teal-600"
      >
        <IconUpload :size="16" />
        Загрузить
      </router-link>
    </div>

    <!-- Book grid -->
    <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <div
        v-for="book in userBooks"
        :key="book.id"
        class="group cursor-pointer overflow-hidden rounded-2xl border border-[--border] transition-all hover:border-teal-500/30 hover:shadow-lg"
      >
        <!-- Cover or placeholder -->
        <div
          class="relative flex h-32 items-center justify-center overflow-hidden"
          :class="book.has_cover ? '' : 'bg-gradient-to-br from-teal-500/10 to-violet-500/10'"
          @click="playBook(book)"
        >
          <img v-if="book.has_cover" :src="userBookCoverUrl(book.slug)" class="h-full w-full object-cover" alt="" />
          <IconMusic v-else :size="36" class="text-[--t3]" />
          <!-- Source badge -->
          <span
            class="absolute top-2 right-2 rounded-full px-2 py-0.5 text-[10px] font-medium"
            :class="book.source === 'tts' ? 'bg-violet-500/20 text-violet-300' : 'bg-teal-500/20 text-teal-300'"
          >
            {{ book.source === 'tts' ? 'TTS' : 'MP3' }}
          </span>
        </div>

        <!-- Info -->
        <div class="p-3" @click="playBook(book)">
          <h3 class="mb-1 line-clamp-2 text-[13px] font-semibold text-[--t1]">{{ book.title }}</h3>
          <p v-if="book.author" class="truncate text-[12px] text-[--t3]">{{ book.author }}</p>
          <div class="mt-2 flex items-center justify-between">
            <span class="flex items-center gap-1 text-[11px] text-[--t3]">
              <IconMusic :size="12" />
              {{ book.mp3_count }} треков
            </span>
            <button
              class="rounded-lg p-1.5 text-[--t3] opacity-0 transition-all group-hover:opacity-100 hover:bg-red-500/15 hover:text-red-400"
              @click.stop="handleDelete(book.slug, book.title)"
            >
              <IconTrash :size="14" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
