<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { api, coverUrl } from '../api'
import type { HistoryEntry } from '../types'
import SearchInput from '../components/shared/SearchInput.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import PullIndicator from '../components/shared/PullIndicator.vue'
import {
  IconStar,
  IconInbox,
  IconPlay,
  IconSmartphone,
  IconCheck,
  IconPause,
  IconXCircle,
  IconSync,
  IconTrash,
  IconDownload,
} from '../components/shared/icons'
import { usePullToRefresh } from '../composables/usePullToRefresh'

const entries = ref<HistoryEntry[]>([])
const loading = ref(true)
const search = ref('')
const actionFilter = ref('')

const actions: { value: string; label: string }[] = [
  { value: '', label: 'Все' },
  { value: 'inbox', label: 'Добавлено' },
  { value: 'listen', label: 'Слушаю' },
  { value: 'phone', label: 'На телефон' },
  { value: 'done', label: 'Прослушано' },
  { value: 'pause', label: 'На паузе' },
  { value: 'reject', label: 'Забраковано' },
  { value: 'move', label: 'Перемещено' },
]

const actionIcon: Record<string, unknown> = {
  inbox: IconInbox,
  listen: IconPlay,
  phone: IconSmartphone,
  done: IconCheck,
  pause: IconPause,
  reject: IconXCircle,
  relisten: IconSync,
  move: IconInbox,
  undo: IconSync,
  delete: IconTrash,
  download: IconDownload,
}

const actionColor: Record<string, { bg: string; fg: string }> = {
  inbox: { bg: 'rgba(34, 211, 238, 0.1)', fg: '#22d3ee' },
  listen: { bg: 'rgba(192, 132, 252, 0.1)', fg: '#c084fc' },
  phone: { bg: 'rgba(96, 165, 250, 0.1)', fg: '#60a5fa' },
  done: { bg: 'rgba(52, 211, 153, 0.1)', fg: '#34d399' },
  pause: { bg: 'rgba(250, 204, 21, 0.1)', fg: '#facc15' },
  reject: { bg: 'rgba(248, 113, 113, 0.1)', fg: '#f87171' },
  relisten: { bg: 'rgba(34, 211, 238, 0.1)', fg: '#22d3ee' },
  move: { bg: 'rgba(148, 163, 184, 0.1)', fg: '#94a3b8' },
  undo: { bg: 'rgba(148, 163, 184, 0.1)', fg: '#94a3b8' },
  delete: { bg: 'rgba(248, 113, 113, 0.1)', fg: '#f87171' },
  download: { bg: 'rgba(148, 163, 184, 0.1)', fg: '#94a3b8' },
}

const fallbackColor = { bg: 'rgba(148, 163, 184, 0.1)', fg: '#94a3b8' }

async function loadHistory() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (actionFilter.value) params.action = actionFilter.value
    if (search.value) params.search = search.value
    entries.value = await api.getHistory(params)
  } catch {
    entries.value = []
  } finally {
    loading.value = false
  }
}

const { refreshing, pullProgress } = usePullToRefresh(loadHistory)

onMounted(loadHistory)
watch([actionFilter, search], loadHistory)

// Group entries by date
const grouped = computed(() => {
  const groups: { date: string; entries: HistoryEntry[] }[] = []
  let currentDate = ''
  for (const e of entries.value) {
    const d = new Date(e.ts).toLocaleDateString('ru', { day: 'numeric', month: 'long', year: 'numeric' })
    if (d !== currentDate) {
      currentDate = d
      groups.push({ date: d, entries: [] })
    }
    groups[groups.length - 1]!.entries.push(e)
  }
  return groups
})

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div>
    <PullIndicator :progress="pullProgress" :refreshing="refreshing" />

    <!-- Header -->
    <div class="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
      <div>
        <h1 class="page-title">История</h1>
        <p v-if="!loading" class="mt-1 text-[13px] text-[--t3]">
          <span class="font-bold text-[--accent]">{{ entries.length }}</span> записей
        </p>
      </div>
      <SearchInput v-model="search" placeholder="Поиск по книге..." class="w-full sm:w-56" />
    </div>

    <!-- Filters -->
    <div class="scrollbar-hide fade-mask-r mb-6 flex gap-2 overflow-x-auto pb-0.5">
      <button
        v-for="a in actions"
        :key="a.value"
        class="flex-shrink-0 cursor-pointer rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
        :class="
          actionFilter === a.value
            ? 'border-white/10 bg-white/[0.08] text-[--t1]'
            : 'border-transparent bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="actionFilter = a.value"
      >
        {{ a.label }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 6" :key="i" class="skeleton h-16" />
    </div>

    <!-- Grouped timeline -->
    <div v-else-if="grouped.length" class="fade-in space-y-8">
      <div v-for="group in grouped" :key="group.date">
        <h3 class="mb-3 text-[12px] font-bold text-[--t3]">{{ group.date }}</h3>
        <div class="space-y-2">
          <div
            v-for="(e, i) in group.entries"
            :key="i"
            class="card flex items-center gap-3.5 p-3.5 transition-colors hover:border-white/10"
          >
            <!-- Action icon -->
            <div
              class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg"
              :style="{
                background: (actionColor[e.action] || fallbackColor).bg,
                color: (actionColor[e.action] || fallbackColor).fg,
              }"
            >
              <component :is="actionIcon[e.action] || IconInbox" :size="16" />
            </div>

            <!-- Book cover -->
            <div v-if="e.book_id" class="h-10 w-10 flex-shrink-0 overflow-hidden rounded-lg">
              <img
                :src="coverUrl(e.book_id)"
                :alt="e.book"
                class="h-full w-full object-cover"
                @error="($event.target as HTMLImageElement).style.display = 'none'"
              />
            </div>

            <!-- Content -->
            <div class="min-w-0 flex-1">
              <div class="mb-0.5 flex items-center gap-2">
                <span class="text-[12px] font-semibold" :style="{ color: (actionColor[e.action] || fallbackColor).fg }">
                  {{ e.action_label }}
                </span>
                <span v-if="e.rating" class="flex gap-0.5 text-amber-400/60">
                  <IconStar v-for="s in e.rating" :key="s" :size="11" />
                </span>
              </div>
              <router-link
                v-if="e.book_id"
                :to="`/book/${e.book_id}`"
                class="block truncate text-[13px] font-medium text-[--t2] no-underline transition-colors hover:text-[--t1]"
              >
                {{ e.book }}
              </router-link>
              <p v-else class="truncate text-[13px] font-medium text-[--t2]">{{ e.book }}</p>
              <p v-if="e.detail" class="mt-0.5 truncate text-[11px] text-[--t3]">{{ e.detail }}</p>
            </div>

            <!-- Time -->
            <span class="flex-shrink-0 text-[11px] whitespace-nowrap text-[--t3]">
              {{ formatTime(e.ts) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <EmptyState v-else title="История пуста" description="Начните слушать книги, и они появятся здесь" />
  </div>
</template>
