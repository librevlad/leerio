<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserBooks } from '@/composables/useUserBooks'
import { useLocalBooks } from '@/composables/useLocalBooks'
import { useDownloads } from '@/composables/useDownloads'
import { useFileScanner } from '@/composables/useFileScanner'
import { useToast } from '@/composables/useToast'
import { api, userBookCoverUrl, coverUrl } from '@/api'
import {
  IconTrash,
  IconMusic,
  IconMicrophone,
  IconFolder,
  IconPlus,
  IconCheck,
  IconSmartphone,
  IconUpload,
} from '@/components/shared/icons'
import SourceBadge from '@/components/shared/SourceBadge.vue'
import ProgressBar from '@/components/shared/ProgressBar.vue'
import AddBookFab from '@/components/library/AddBookFab.vue'
import type { TTSJob } from '@/types'

const { t } = useI18n()
const toast = useToast()
const { userBooks, ttsJobs, loading: ubLoading, loadUserBooks, loadTTSJobs, deleteBook, pollJob } = useUserBooks()
const { localBooks, removeLocalBook, getLocalBook, getLocalAudioUrl } = useLocalBooks()
const downloads = useDownloads()
const { fsBooks, scanning, scan: scanDevice } = useFileScanner()
const scannedBooks = computed(() => Object.values(fsBooks.value))

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
    // Scanned device books
    for (const sb of scannedBooks.value) {
      result.push({
        id: sb.id,
        title: sb.title,
        author: sb.author,
        source: 'local',
        hasCover: false,
        trackCount: sb.tracks.length,
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
  return (
    downloads.downloadedBooks.value.length +
    localBooks.value.length +
    scannedBooks.value.length +
    userBooks.value.length
  )
})

onMounted(async () => {
  await Promise.all([loadUserBooks(), loadTTSJobs(), scanDevice()])

  for (const job of activeJobs.value) {
    pollJob(job.id, (j: TTSJob) => {
      const idx = ttsJobs.value.findIndex((x: TTSJob) => x.id === j.id)
      if (idx >= 0) ttsJobs.value[idx] = j
      if (j.status === 'done') {
        toast.success(t('myLibrary.ttsComplete', { title: j.title }))
        loadUserBooks()
      }
    })
  }
})

async function handleDelete(item: UnifiedItem) {
  if (!confirm(t('myLibrary.deleteConfirm', { title: item.title }))) return
  try {
    if (item.source === 'local') {
      await removeLocalBook(item.id)
    } else if (item.source === 'uploaded' && item.slug) {
      await deleteBook(item.slug)
    } else if (item.source === 'downloaded') {
      await downloads.deleteBook(item.id)
    }
    toast.success(t('myLibrary.deleted'))
  } catch {
    toast.error(t('myLibrary.deleteError'))
  }
}

const filters: { key: 'all' | 'downloaded' | 'local' | 'uploaded'; labelKey: string; titleKey?: string }[] = [
  { key: 'all', labelKey: 'myLibrary.filterAll' },
  { key: 'downloaded', labelKey: 'myLibrary.filterDownloaded', titleKey: 'myLibrary.filterDownloadedHint' },
  { key: 'local', labelKey: 'myLibrary.filterLocal', titleKey: 'myLibrary.filterLocalHint' },
  { key: 'uploaded', labelKey: 'myLibrary.filterUploaded', titleKey: 'myLibrary.filterUploadedHint' },
]

const sourceBadgeMap: Record<UnifiedItem['source'], 'library' | 'librivox' | 'user' | 'local'> = {
  downloaded: 'library',
  local: 'local',
  uploaded: 'user',
}

const coverGradients: Record<string, string> = {
  downloaded: 'linear-gradient(135deg, #064e3b 0%, #059669 50%, #34d399 100%)',
  local: 'linear-gradient(135deg, #1e1b4b 0%, #4338ca 50%, #818cf8 100%)',
  uploaded: 'linear-gradient(135deg, #134e4a 0%, #0d9488 50%, #5eead4 100%)',
}

const coverPatterns: Record<string, string> = {
  downloaded: 'radial-gradient(circle at 80% 20%, rgba(255,255,255,0.12) 0%, transparent 50%)',
  local: 'radial-gradient(circle at 20% 80%, rgba(255,255,255,0.12) 0%, transparent 50%)',
  uploaded: 'radial-gradient(circle at 70% 70%, rgba(255,255,255,0.12) 0%, transparent 50%)',
}

const uploadingToCloud = ref<string | null>(null)

async function uploadToCloud(item: UnifiedItem) {
  if (!item.id.startsWith('lb:') || uploadingToCloud.value) return

  const book = getLocalBook(item.id)
  if (!book || !book.tracks.length) {
    toast.error('Книга не найдена')
    return
  }

  uploadingToCloud.value = item.id

  try {
    const files: File[] = []
    for (const track of book.tracks) {
      const url = await getLocalAudioUrl(item.id, track.index)
      if (!url) continue
      const res = await fetch(url)
      const blob = await res.blob()
      files.push(new File([blob], track.filename || `chapter-${track.index + 1}.mp3`, { type: 'audio/mpeg' }))
    }

    if (!files.length) {
      toast.error('Нет треков для загрузки')
      return
    }

    if (files.length !== book.tracks.length) {
      toast.error(`Загружено только ${files.length}/${book.tracks.length} треков`)
      return
    }

    const formData = new FormData()
    formData.append('title', book.title)
    formData.append('author', book.author)
    for (const file of files) {
      formData.append('files', file)
    }

    await api.uploadBook(formData)

    await removeLocalBook(item.id)

    toast.success('Книга загружена в облако')
    await loadUserBooks()
  } catch (e) {
    toast.error(e instanceof Error ? e.message : 'Ошибка загрузки')
  } finally {
    uploadingToCloud.value = null
  }
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="page-title">{{ t('myLibrary.title') }}</h1>
        <p class="mt-1 text-[13px] text-[--t3]">
          {{ totalCount > 0 ? `${totalCount} ${t('plural.book', totalCount)}` : t('myLibrary.noBooks') }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button
          v-if="downloads.isNative.value"
          v-ripple
          class="btn btn-ghost flex items-center gap-1.5 px-3 py-2 text-[12px] font-semibold"
          :disabled="scanning"
          @click="scanDevice"
        >
          <IconFolder :size="14" />
          {{ scanning ? t('myLibrary.scanning') : t('myLibrary.scan') }}
        </button>
        <router-link to="/upload" class="btn btn-primary flex items-center gap-1.5 px-4 py-2 text-[12px] font-semibold">
          <IconPlus :size="14" />
          {{ t('myLibrary.add') }}
        </router-link>
      </div>
    </div>

    <!-- Active TTS Jobs -->
    <div v-if="activeJobs.length" class="card mb-6 space-y-3 px-4 py-3">
      <h2 class="section-label">{{ t('myLibrary.conversion') }}</h2>
      <div v-for="job in activeJobs" :key="job.id">
        <div class="mb-1.5 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <IconMicrophone :size="14" class="text-violet-400" />
            <span class="text-[13px] font-medium text-[--t1]">{{ job.title }}</span>
          </div>
          <span class="text-[12px] text-[--t3]">{{ job.done_chapters }}/{{ job.total_chapters }}</span>
        </div>
        <ProgressBar :percent="job.progress" height="h-1.5" />
      </div>
    </div>

    <!-- Filter tabs (color-coded) -->
    <div class="scrollbar-hide mb-5 flex gap-2 overflow-x-auto">
      <button
        v-for="f in filters"
        :key="f.key"
        class="flex-shrink-0 cursor-pointer rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
        :class="
          activeFilter === f.key
            ? 'border-white/10 bg-white/[0.08] text-[--t1]'
            : 'border-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        :title="f.titleKey ? t(f.titleKey) : undefined"
        @click="activeFilter = f.key"
      >
        {{ t(f.labelKey) }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="ubLoading" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <div v-for="i in 4" :key="i">
        <div class="skeleton h-28 rounded-t-xl rounded-b-none" />
        <div class="skeleton h-36 rounded-t-none rounded-b-xl border-t-0" />
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="items.length === 0" class="flex flex-col items-center justify-center py-16 text-center">
      <IconFolder :size="48" class="mb-4 text-[--t3]" />
      <p class="mb-2 text-[14px] font-medium text-[--t2]">
        {{ activeFilter === 'all' ? t('myLibrary.emptyTitle') : t('myLibrary.emptyCategory') }}
      </p>
      <p class="mb-5 text-[13px] text-[--t3]">{{ t('myLibrary.emptyDesc') }}</p>
      <div class="flex gap-3">
        <router-link to="/library" class="btn btn-secondary flex items-center gap-2 text-[13px]">
          {{ t('myLibrary.goToCatalog') }}
        </router-link>
        <router-link to="/upload" class="btn btn-primary flex items-center gap-2 text-[13px]">
          <IconPlus :size="16" />
          {{ t('upload.uploadBtn') }}
        </router-link>
      </div>
    </div>

    <!-- Grid -->
    <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <router-link
        v-for="item in items"
        :key="item.id"
        :to="`/book/${item.id}`"
        class="card card-hover group cursor-pointer overflow-hidden no-underline"
      >
        <!-- Gradient backdrop with blurred cover -->
        <div class="relative h-28 overflow-hidden" :style="{ background: coverGradients[item.source] }">
          <img
            v-if="item.coverSrc"
            :src="item.coverSrc"
            class="absolute inset-0 h-full w-full object-cover blur-[1px] brightness-75"
            alt=""
          />
          <div v-else class="absolute inset-0" :style="{ background: coverPatterns[item.source] }" />
          <div
            class="absolute inset-0"
            style="background: linear-gradient(to bottom, transparent 20%, rgba(0, 0, 0, 0.7) 100%)"
          />

          <!-- Top badges -->
          <div class="absolute top-2.5 right-3 flex items-center gap-1.5">
            <SourceBadge :source="sourceBadgeMap[item.source]" />
          </div>

          <span
            v-if="item.source === 'downloaded'"
            class="absolute bottom-2.5 left-3 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/90 text-white shadow"
          >
            <IconCheck :size="12" />
          </span>
        </div>

        <!-- Floating cover + content -->
        <div class="relative px-4">
          <div class="-mt-9 mb-2.5 flex items-end gap-3">
            <div
              class="relative h-[72px] w-[72px] flex-shrink-0 overflow-hidden rounded-lg shadow-lg ring-2 ring-[--card-solid]"
            >
              <img v-if="item.coverSrc" :src="item.coverSrc" class="h-full w-full object-cover" alt="" />
              <div
                v-else
                class="flex h-full w-full items-center justify-center"
                :style="{ background: coverGradients[item.source], backgroundImage: coverPatterns[item.source] }"
              >
                <component
                  :is="item.source === 'local' ? IconSmartphone : IconMusic"
                  :size="24"
                  class="text-white/50"
                />
              </div>
            </div>
            <div class="min-w-0 pb-1">
              <h3
                class="line-clamp-2 text-[13px] leading-snug font-semibold text-[--t1] transition-colors group-hover:text-white"
              >
                {{ item.title }}
              </h3>
            </div>
          </div>

          <div class="pb-3">
            <p v-if="item.author" class="mb-2 truncate text-[12px] text-[--t3]">{{ item.author }}</p>
            <div class="flex items-center justify-between">
              <span v-if="item.trackCount" class="flex items-center gap-1 text-[11px] text-[--t3]">
                <IconMusic :size="12" />
                {{ item.trackCount }} {{ t('plural.track', item.trackCount) }}
              </span>
              <div class="flex items-center gap-1">
                <div v-if="uploadingToCloud === item.id" class="flex h-7 items-center text-[11px] text-[--accent]">
                  Загрузка...
                </div>
                <button
                  v-else-if="item.id.startsWith('lb:')"
                  class="rounded-full p-1.5 text-[--t3] opacity-0 transition-all group-hover:opacity-100 hover:bg-white/10 hover:text-[--accent]"
                  title="В облако"
                  @click.prevent="uploadToCloud(item)"
                >
                  <IconUpload :size="14" />
                </button>
                <button
                  class="rounded-full p-1.5 text-[--t3] opacity-0 transition-all group-hover:opacity-100 hover:bg-red-500/15 hover:text-red-400"
                  :aria-label="t('myLibrary.deleteAriaLabel')"
                  @click.stop="handleDelete(item)"
                >
                  <IconTrash :size="14" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </router-link>
    </div>

    <AddBookFab />
  </div>
</template>
