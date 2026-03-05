<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import type { HistoryEntry } from '../types'
import SearchInput from '../components/shared/SearchInput.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import PullIndicator from '../components/shared/PullIndicator.vue'
import { IconStar } from '../components/shared/icons'
import { dotColor } from '../composables/useStatusColors'
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
    <div v-else-if="grouped.length" class="fade-in space-y-6">
      <div v-for="group in grouped" :key="group.date">
        <h3 class="mb-3 text-[12px] font-semibold text-[--t3]">{{ group.date }}</h3>
        <div class="card overflow-hidden">
          <div
            v-for="(e, i) in group.entries"
            :key="i"
            class="flex items-center gap-4 border-b border-[--border] px-5 py-3.5 transition-colors last:border-0 hover:bg-white/[0.02]"
          >
            <span class="block h-2 w-2 flex-shrink-0 rounded-full" :class="dotColor[e.action] || 'bg-slate-500'" />

            <!-- Content -->
            <div class="min-w-0 flex-1">
              <div class="mb-0.5 flex items-center gap-2">
                <span class="text-[12px] font-semibold text-[--t2]">{{ e.action_label }}</span>
                <span v-if="e.rating" class="flex gap-0.5 text-amber-500/60">
                  <IconStar v-for="s in e.rating" :key="s" :size="11" />
                </span>
              </div>
              <router-link
                v-if="e.book_id"
                :to="`/book/${e.book_id}`"
                class="block truncate text-[13px] font-medium text-[--t1] no-underline transition-colors hover:text-[--accent]"
              >
                {{ e.book }}
              </router-link>
              <p v-else class="truncate text-[13px] font-medium text-[--t1]">{{ e.book }}</p>
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
