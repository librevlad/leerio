<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserBooks } from '@/composables/useUserBooks'
import { useLocalBooks } from '@/composables/useLocalBooks'
import { useDownloads } from '@/composables/useDownloads'
import { useFileScanner } from '@/composables/useFileScanner'
import { useToast } from '@/composables/useToast'
import { usePlayer, savedPosition } from '@/composables/usePlayer'
import { api, userBookCoverUrl, coverUrl } from '@/api'
import { STORAGE } from '@/constants/storage'
import { titleInitial } from '@/utils/format'
import { IconTrash, IconMicrophone, IconFolder, IconPlus, IconUpload } from '@/components/shared/icons'
import ProgressBar from '@/components/shared/ProgressBar.vue'
import AddBookFab from '@/components/library/AddBookFab.vue'
import type { TTSJob, UserBook } from '@/types'

const { t } = useI18n()
const toast = useToast()
const { userBooks, ttsJobs, loading: ubLoading, loadUserBooks, loadTTSJobs, deleteBook, pollJob } = useUserBooks()
const { localBooks, removeLocalBook, getLocalBook, getLocalAudioUrl } = useLocalBooks()
const downloads = useDownloads()
const { fsBooks, fetchMissingCovers } = useFileScanner()
const scannedBooks = computed(() => Object.values(fsBooks.value))

const activeFilter = ref<'all' | 'downloaded' | 'local' | 'uploaded'>('all')
const coverErrors = ref(new Set<string>())
const activeJobs = computed(() => ttsJobs.value.filter((j: TTSJob) => j.status === 'processing'))

interface UnifiedItem {
  id: string
  title: string
  author: string
  source: 'downloaded' | 'local' | 'uploaded' | 'catalog'
  category?: string
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
        hasCover: !!sb.coverUrl,
        coverSrc: sb.coverUrl,
        trackCount: sb.tracks.length,
      })
    }
  }

  // Uploaded / TTS books + owned catalog books
  if (activeFilter.value === 'all' || activeFilter.value === 'uploaded') {
    for (const ub of userBooks.value) {
      const isCatalog = (ub.source as string) === 'catalog'
      result.push({
        id: ub.id,
        title: ub.title,
        author: ub.author,
        source: isCatalog ? 'catalog' : 'uploaded',
        category: isCatalog ? (ub as UserBook & { category?: string }).category : undefined,
        hasCover: ub.has_cover,
        coverSrc: isCatalog
          ? ub.has_cover
            ? coverUrl(ub.id)
            : undefined
          : ub.has_cover
            ? userBookCoverUrl(ub.slug)
            : undefined,
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

// ── List order: last played first, then started books, then the rest ──
const player = usePlayer()
const lastPlayedId = (() => {
  try {
    return (JSON.parse(localStorage.getItem(STORAGE.LAST_PLAYED) || '{}') as { id?: string }).id ?? ''
  } catch {
    return ''
  }
})()
const currentId = computed(() => player.currentBook.value?.id ?? lastPlayedId)

const listItems = computed(() =>
  items.value.map((item) => ({ ...item, pos: savedPosition(item.id) })).sort((a, b) => rank(a) - rank(b)),
)

function rank(item: { id: string; pos: unknown }): number {
  if (item.id === currentId.value) return 0
  return item.pos ? 1 : 2
}

// Filter chips only when the library mixes sources (device-only library needs none)
const sourceCounts = computed<Record<string, number>>(() => ({
  downloaded: downloads.downloadedBooks.value.length,
  local: localBooks.value.length + scannedBooks.value.length,
  uploaded: userBooks.value.length,
}))
const visibleFilters = computed(() => {
  const present = filters.filter((f) => f.key !== 'all' && (sourceCounts.value[f.key] ?? 0) > 0)
  return present.length > 1 ? [filters[0]!, ...present] : []
})

onMounted(async () => {
  await Promise.all([loadUserBooks(), loadTTSJobs()])

  // Fetch covers in background for scanned books without covers
  fetchMissingCovers()

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
    } else if (item.source === 'catalog') {
      await api.deleteOwnedBook(item.id)
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

const uploadingToCloud = ref<string | null>(null)

async function uploadToCloud(item: UnifiedItem) {
  if (!item.id.startsWith('lb:') || uploadingToCloud.value) return

  const book = getLocalBook(item.id)
  if (!book || !book.tracks.length) {
    toast.error(t('myLibrary.fsNotFound'))
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
      toast.error(t('myLibrary.noTracks'))
      return
    }

    if (files.length !== book.tracks.length) {
      toast.error(t('myLibrary.cloudUploadFailed'))
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

    toast.success(t('myLibrary.cloudUploadDone'))
    await loadUserBooks()
  } catch (e) {
    toast.error(e instanceof Error ? e.message : t('myLibrary.cloudUploadFailed'))
  } finally {
    uploadingToCloud.value = null
  }
}
</script>

<template>
  <div>
    <!-- Header (adding books lives in the "+" button) -->
    <div class="mb-5">
      <h1 class="page-title">{{ t('myLibrary.title') }}</h1>
      <p class="mt-1 text-[13px] text-(--t3)">
        {{ totalCount > 0 ? `${totalCount} ${t('plural.book', totalCount)}` : t('myLibrary.noBooks') }}
      </p>
    </div>

    <!-- Active TTS Jobs -->
    <div v-if="activeJobs.length" class="card mb-6 space-y-3 px-4 py-3">
      <h2 class="section-label">{{ t('myLibrary.conversion') }}</h2>
      <div v-for="job in activeJobs" :key="job.id">
        <div class="mb-1.5 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <IconMicrophone :size="14" class="text-violet-400" />
            <span class="text-[13px] font-medium text-(--t1)">{{ job.title }}</span>
          </div>
          <span class="text-[12px] text-(--t3)">{{ job.done_chapters }}/{{ job.total_chapters }}</span>
        </div>
        <ProgressBar :percent="job.progress" height="h-1.5" />
      </div>
    </div>

    <!-- Filter tabs (only when sources are mixed) -->
    <div v-if="visibleFilters.length" class="scrollbar-hide mb-5 flex gap-2 overflow-x-auto">
      <button
        v-for="f in visibleFilters"
        :key="f.key"
        class="flex-shrink-0 cursor-pointer rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
        :class="
          activeFilter === f.key
            ? 'border-white/10 bg-white/[0.08] text-(--t1)'
            : 'border-transparent text-(--t3) hover:bg-white/5 hover:text-(--t2)'
        "
        :title="f.titleKey ? t(f.titleKey) : undefined"
        @click="activeFilter = f.key"
      >
        {{ t(f.labelKey) }}
      </button>
    </div>

    <!-- Loading (server list only — device books render immediately) -->
    <div v-if="ubLoading && items.length === 0" class="space-y-1">
      <div v-for="i in 6" :key="i" class="flex items-center gap-3 px-2 py-2.5">
        <div class="skeleton h-14 w-14 flex-shrink-0 rounded-lg" />
        <div class="flex-1 space-y-2">
          <div class="skeleton h-3.5 w-3/4 rounded" />
          <div class="skeleton h-3 w-1/3 rounded" />
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="items.length === 0" class="flex flex-col items-center justify-center py-16 text-center">
      <IconFolder :size="48" class="mb-4 text-(--t3)" />
      <p class="mb-2 text-[14px] font-medium text-(--t2)">
        {{ activeFilter === 'all' ? t('myLibrary.emptyTitle') : t('myLibrary.emptyCategory') }}
      </p>
      <p class="mb-5 text-[13px] text-(--t3)">{{ t('myLibrary.emptyDesc') }}</p>
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

    <!-- Book list: one compact row per book -->
    <div v-else class="space-y-0.5">
      <router-link
        v-for="item in listItems"
        :key="item.id"
        :to="`/book/${item.id}`"
        class="group flex items-center gap-3 rounded-xl px-2 py-2.5 no-underline transition-colors hover:bg-white/[0.04]"
      >
        <!-- Cover: image or the title's first letter -->
        <div class="h-14 w-14 flex-shrink-0 overflow-hidden rounded-lg bg-(--accent-soft)">
          <img
            v-if="item.coverSrc && !coverErrors.has(item.id)"
            :src="item.coverSrc"
            class="h-full w-full object-cover"
            alt=""
            loading="lazy"
            @error="coverErrors.add(item.id)"
          />
          <div v-else class="flex h-full w-full items-center justify-center text-[20px] font-bold text-(--accent)">
            {{ titleInitial(item.title) }}
          </div>
        </div>

        <!-- Title, author, where I am -->
        <div class="min-w-0 flex-1">
          <p
            class="line-clamp-2 text-[14px] leading-snug font-semibold"
            :class="item.id === currentId ? 'text-(--accent)' : 'text-(--t1)'"
          >
            {{ item.title }}
          </p>
          <p v-if="item.author" class="mt-0.5 truncate text-[12px] text-(--t2)">{{ item.author }}</p>
          <p v-if="item.trackCount" class="mt-0.5 text-[11px] text-(--t3)">
            <template v-if="item.pos">
              {{ t('player.trackN', { n: item.pos.trackIndex + 1, total: item.trackCount }) }}
            </template>
            <template v-else>{{ item.trackCount }} {{ t('plural.track', item.trackCount) }}</template>
          </p>
        </div>

        <!-- Actions: desktop hover only (touch has no hover — avoid invisible tap targets) -->
        <div class="hidden flex-shrink-0 items-center gap-1 md:flex">
          <div v-if="uploadingToCloud === item.id" class="text-[11px] text-(--accent)">
            {{ t('myLibrary.uploading') }}
          </div>
          <button
            v-else-if="item.id.startsWith('lb:')"
            class="rounded-full p-1.5 text-(--t3) opacity-0 transition-all group-hover:opacity-100 hover:bg-white/10 hover:text-(--accent)"
            :title="t('myLibrary.cloudHint')"
            @click.prevent="uploadToCloud(item)"
          >
            <IconUpload :size="14" />
          </button>
          <button
            class="rounded-full p-1.5 text-(--t3) opacity-0 transition-all group-hover:opacity-100 hover:bg-red-500/15 hover:text-red-400"
            :aria-label="t('myLibrary.deleteAriaLabel')"
            @click.prevent.stop="handleDelete(item)"
          >
            <IconTrash :size="14" />
          </button>
        </div>
      </router-link>
    </div>

    <AddBookFab />
  </div>
</template>
