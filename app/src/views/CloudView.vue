<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useCloud, type CloudBook } from '../composables/useCloud'
import { useFileScanner, cleanTitle, extractAuthor } from '../composables/useFileScanner'
import { usePro, FREE_BOOKS } from '../composables/usePro'
import { formatSize, titleInitial } from '../utils/format'
import { IconArrowLeft } from '../components/shared/icons'
import ProgressBar from '../components/shared/ProgressBar.vue'
import PaywallModal from '../components/shared/PaywallModal.vue'

const router = useRouter()
const { t } = useI18n()
const cloud = useCloud()
const { fsBooks } = useFileScanner()
const pro = usePro()
const showPaywall = ref(false)
const ready = ref(false)

onMounted(async () => {
  await cloud.init()
  ready.value = true
  await cloud.refresh()
})

const rows = computed(() =>
  cloud.books.value.map((book) => ({
    book,
    title: cleanTitle(book.folder),
    author: extractAuthor(book.folder),
    onDevice: !!fsBooks.value[`fs:${book.folder}`],
    job: cloud.jobs.value[book.folder],
  })),
)

function percent(book: CloudBook, done: number): number {
  return book.bytes ? Math.min(100, Math.round((done / book.bytes) * 100)) : 0
}

/** Free plan: the books in My Library plus the ones on their way */
function get(book: CloudBook) {
  const coming = Object.entries(cloud.jobs.value).filter(([f, j]) => f !== book.folder && j.state !== 'failed').length
  if (pro.limited.value && Object.keys(fsBooks.value).length + coming >= FREE_BOOKS) {
    showPaywall.value = true
    return
  }
  cloud.download(book)
}
</script>

<template>
  <div class="mx-auto max-w-xl">
    <!-- Header -->
    <div class="mb-5 flex items-center gap-3">
      <button
        class="flex items-center text-(--t3) hover:text-(--t1)"
        :aria-label="t('common.back')"
        @click="router.back()"
      >
        <IconArrowLeft :size="20" />
      </button>
      <div class="min-w-0 flex-1">
        <h1 class="text-[18px] font-bold text-(--t1)">{{ t('cloud.title') }}</h1>
        <p class="mt-0.5 text-[12px] text-(--t3)">{{ t('cloud.intro') }}</p>
      </div>
    </div>

    <!-- Opened without a key on the device -->
    <p v-if="ready && !cloud.available.value" class="py-12 text-center text-[13px] text-(--t3)">
      {{ t('cloud.notConnected') }}
    </p>

    <!-- First load -->
    <div v-else-if="!rows.length && (!ready || cloud.loading.value)" class="space-y-1">
      <div v-for="i in 3" :key="i" class="flex items-center gap-3 px-2 py-2.5">
        <div class="skeleton h-14 w-14 flex-shrink-0 rounded-lg" />
        <div class="flex-1 space-y-2">
          <div class="skeleton h-3.5 w-3/4 rounded" />
          <div class="skeleton h-3 w-1/3 rounded" />
        </div>
      </div>
    </div>

    <!-- No list: offline on the first visit, or an empty bucket -->
    <div v-else-if="!rows.length" class="py-12 text-center">
      <p class="text-[13px] text-(--t2)">{{ cloud.listError.value ? t('cloud.listFailed') : t('cloud.empty') }}</p>
      <button v-if="cloud.listError.value" class="btn btn-secondary mt-4 text-[13px]" @click="cloud.refresh()">
        {{ t('common.retry') }}
      </button>
    </div>

    <!-- Books: download, then listen -->
    <div v-else class="space-y-0.5">
      <p v-if="cloud.listError.value" class="mb-3 text-[12px] text-(--t3)">{{ t('cloud.offline') }}</p>
      <div v-for="row in rows" :key="row.book.folder" class="flex items-center gap-3 rounded-xl px-2 py-2.5">
        <div
          class="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-lg bg-(--accent-soft) text-[20px] font-bold text-(--accent)"
        >
          {{ titleInitial(row.title) }}
        </div>

        <div class="min-w-0 flex-1">
          <p class="line-clamp-2 text-[14px] leading-snug font-semibold text-(--t1)">{{ row.title }}</p>
          <p v-if="row.author" class="mt-0.5 truncate text-[12px] text-(--t2)">{{ row.author }}</p>
          <p class="mt-0.5 text-[11px] text-(--t3)">
            <template v-if="row.job?.state === 'failed'">{{ t('cloud.failed') }}</template>
            <template v-else>
              {{ t('scan.tracks', row.book.files.length) }} · {{ formatSize(row.book.bytes, t) }}
            </template>
          </p>
          <ProgressBar
            v-if="row.job?.state === 'downloading'"
            class="mt-1.5"
            :percent="percent(row.book, row.job.done)"
            height="h-1"
          />
        </div>

        <router-link
          v-if="row.onDevice"
          :to="{ name: 'book', params: { id: `fs:${row.book.folder}` } }"
          class="btn btn-primary shrink-0 px-4 py-2 text-[13px]"
        >
          {{ t('cloud.listen') }}
        </router-link>
        <span v-else-if="row.job?.state === 'downloading'" class="shrink-0 text-[12px] font-semibold text-(--accent)">
          {{ percent(row.book, row.job.done) }}%
        </span>
        <span v-else-if="row.job?.state === 'queued'" class="shrink-0 text-[12px] text-(--t3)">
          {{ t('cloud.queued') }}
        </span>
        <button v-else class="btn btn-secondary shrink-0 px-4 py-2 text-[13px]" @click="get(row.book)">
          {{ row.job ? t('common.retry') : t('cloud.download') }}
        </button>
      </div>
    </div>

    <PaywallModal :open="showPaywall" reason="books" @close="showPaywall = false" />
  </div>
</template>
