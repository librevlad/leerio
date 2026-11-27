<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useFileScanner, isLikelyNotBook } from '../composables/useFileScanner'
import { useToast } from '../composables/useToast'
import { useTracking } from '../composables/useTelemetry'
import { usePlayer } from '../composables/usePlayer'
import { formatSize } from '../utils/format'
import { IconCheck, IconArrowLeft } from '../components/shared/icons'
import PaywallModal from '../components/shared/PaywallModal.vue'
import { STORAGE } from '../constants/storage'
import { usePro, FREE_BOOKS } from '../composables/usePro'
import type { FsBookMeta } from '../types'

const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const { track } = useTracking()
const scanner = useFileScanner()
const { isPlayerVisible } = usePlayer()
const pro = usePro()
const showPaywall = ref(false)

/** How many more books the free plan lets into My Library (books already there stay) */
const room = computed(() =>
  pro.limited.value ? Math.max(0, FREE_BOOKS - Object.keys(scanner.fsBooks.value).length) : Infinity,
)

// Above the bottom nav (+ mini player): at bottom 0 they cover the Add button
const barBottom = computed(() => `calc(${isPlayerVisible.value ? '120px' : '56px'} + env(safe-area-inset-bottom, 0px))`)

const scannedBooks = ref<FsBookMeta[]>([])
const selected = ref<Set<string>>(new Set())
const hasScanned = ref(false)

const selectedCount = computed(() => selected.value.size)

onMounted(async () => {
  const found = await scanner.scan()
  scannedBooks.value = found
  hasScanned.value = true

  // Select all except "not a book" heuristic, as many as the plan allows
  for (const book of found) {
    if (selected.value.size >= room.value) break
    // Use the folder path, not the cleaned title: albums under Music/ are not books
    if (!isLikelyNotBook(book.folderPath, book.tracks.length)) {
      selected.value.add(book.id)
    }
  }

  track('scan_completed', { found: found.length })
})

function toggle(id: string) {
  if (selected.value.has(id)) {
    selected.value.delete(id)
  } else if (selected.value.size >= room.value) {
    showPaywall.value = true
    return
  } else {
    selected.value.add(id)
  }
  // Force reactivity
  selected.value = new Set(selected.value)
}

function selectAll() {
  if (scannedBooks.value.length > room.value) {
    showPaywall.value = true
    return
  }
  for (const b of scannedBooks.value) selected.value.add(b.id)
  selected.value = new Set(selected.value)
}

function deselectAll() {
  selected.value = new Set()
}

function cancelScan() {
  scanner.abortScan()
  hasScanned.value = true
}

function addSelected() {
  const books = scannedBooks.value.filter((b) => selected.value.has(b.id))
  if (!books.length) return

  scanner.addFsBooks(books)
  toast.success(t('scan.added', books.length))
  track('scan_books_added', { count: books.length })
  localStorage.setItem(STORAGE.ONBOARDED, '1')
  router.push('/my-library')
}

function fmtSize(bytes: number): string {
  return formatSize(bytes, t)
}
</script>

<template>
  <div class="min-h-dvh min-h-screen px-4 py-6" style="background: var(--bg)">
    <!-- Header -->
    <div class="mb-6 flex items-center gap-3">
      <button class="flex items-center text-(--t3) hover:text-(--t1)" @click="router.back()">
        <IconArrowLeft :size="20" />
      </button>
      <div class="flex-1">
        <h1 v-if="hasScanned" class="text-[18px] font-bold text-(--t1)">
          {{ t('scan.found', scannedBooks.length) }}
        </h1>
        <h1 v-else class="text-[18px] font-bold text-(--t1)">{{ t('scan.scanning') }}</h1>
      </div>
      <button
        v-if="scannedBooks.length"
        class="text-[12px] font-semibold text-(--accent)"
        @click="selectedCount === scannedBooks.length ? deselectAll() : selectAll()"
      >
        {{ selectedCount === scannedBooks.length ? t('scan.deselectAll') : t('scan.selectAll') }}
      </button>
    </div>

    <!-- Scanning progress -->
    <div v-if="scanner.scanning.value" class="mb-6 flex flex-col items-center gap-3 py-8">
      <div class="h-8 w-8 animate-spin rounded-full border-2 border-(--accent) border-t-transparent" />
      <p class="text-[13px] text-(--t3)">{{ t('scan.scanningDir', { dir: scanner.scanProgress.value }) }}</p>
      <button class="text-[12px] text-(--t3) hover:text-(--t1)" @click="cancelScan">
        {{ t('scan.cancel') }}
      </button>
    </div>

    <!-- No results -->
    <div v-else-if="hasScanned && !scannedBooks.length" class="py-12 text-center">
      <div class="mb-4 text-[40px]">📂</div>
      <p class="text-[14px] text-(--t2)">{{ t('scan.nothingFound') }}</p>
      <p class="mt-2 text-[12px] text-(--t3)">{{ t('scan.tryFolder') }}</p>
    </div>

    <!-- Book list -->
    <div v-else class="space-y-2 pb-28">
      <p v-if="scannedBooks.length" class="mb-4 text-[12px] text-(--t3)">
        {{ pro.limited.value ? t('pro.freeBooks', { n: FREE_BOOKS }) : t('scan.uncheckHint') }}
      </p>

      <div
        v-for="book in scannedBooks"
        :key="book.id"
        class="flex cursor-pointer items-center gap-3 rounded-xl px-3 py-3 transition-all"
        :class="
          selected.has(book.id)
            ? 'border border-(--accent)/30 bg-white/[0.05]'
            : 'border border-white/[0.06] bg-white/[0.03] opacity-60'
        "
        @click="toggle(book.id)"
      >
        <!-- Checkbox -->
        <div
          class="flex h-5 w-5 shrink-0 items-center justify-center rounded-md transition-colors"
          :class="selected.has(book.id) ? 'bg-(--accent)' : 'border-2 border-(--border)'"
        >
          <IconCheck v-if="selected.has(book.id)" :size="12" class="text-white" />
        </div>

        <!-- Info -->
        <div class="min-w-0 flex-1">
          <div class="truncate text-[13px] font-semibold text-(--t1)">{{ book.title }}</div>
          <div class="mt-0.5 text-[11px] text-(--t3)">
            <span v-if="book.author">{{ book.author }} · </span>
            {{ t('scan.tracks', book.tracks.length) }}
            <span v-if="book.sizeBytes"> · {{ fmtSize(book.sizeBytes) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Add button (sticky bottom) -->
    <div
      v-if="scannedBooks.length"
      class="fixed right-0 left-0 z-30 px-4 pt-3 pb-3"
      :style="{ bottom: barBottom, background: 'linear-gradient(transparent, var(--bg) 20%)' }"
    >
      <button
        v-ripple
        class="btn btn-primary w-full justify-center py-3.5 text-[15px]"
        :disabled="!selectedCount"
        @click="addSelected"
      >
        {{ t('scan.addN', selectedCount) }}
      </button>
      <p class="mt-2 text-center text-[11px] text-(--t3)">{{ t('scan.stayOnDevice') }}</p>
    </div>

    <PaywallModal :open="showPaywall" reason="books" @close="showPaywall = false" />
  </div>
</template>
