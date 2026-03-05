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

const actions: { value: string; label: string; color: string; activeBg: string; activeBorder: string }[] = [
  {
    value: '',
    label: 'Все',
    color: 'text-[--accent]',
    activeBg: 'bg-[--accent-soft]',
    activeBorder: 'border-[--accent]/30',
  },
  {
    value: 'inbox',
    label: 'Добавлено',
    color: 'text-cyan-400',
    activeBg: 'bg-cyan-500/10',
    activeBorder: 'border-cyan-500/30',
  },
  {
    value: 'listen',
    label: 'Слушаю',
    color: 'text-purple-400',
    activeBg: 'bg-purple-500/10',
    activeBorder: 'border-purple-500/30',
  },
  {
    value: 'phone',
    label: 'На телефон',
    color: 'text-blue-400',
    activeBg: 'bg-blue-500/10',
    activeBorder: 'border-blue-500/30',
  },
  {
    value: 'done',
    label: 'Прослушано',
    color: 'text-emerald-400',
    activeBg: 'bg-emerald-500/10',
    activeBorder: 'border-emerald-500/30',
  },
  {
    value: 'pause',
    label: 'На паузе',
    color: 'text-yellow-400',
    activeBg: 'bg-yellow-500/10',
    activeBorder: 'border-yellow-500/30',
  },
  {
    value: 'reject',
    label: 'Забраковано',
    color: 'text-red-400',
    activeBg: 'bg-red-500/10',
    activeBorder: 'border-red-500/30',
  },
  {
    value: 'move',
    label: 'Перемещено',
    color: 'text-slate-400',
    activeBg: 'bg-slate-500/10',
    activeBorder: 'border-slate-500/30',
  },
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
    <div class="card mb-6 px-4 py-3">
      <span class="mr-2 text-[11px] font-semibold text-[--t3]">Действие:</span>
      <div class="scrollbar-hide fade-mask-r mt-1.5 flex gap-2 overflow-x-auto pb-0.5">
        <button
          v-for="a in actions"
          :key="a.value"
          class="flex-shrink-0 cursor-pointer rounded-full border px-3.5 py-1.5 text-[12px] font-semibold transition-all duration-200"
          :class="
            actionFilter === a.value
              ? [a.activeBg, a.activeBorder, a.color]
              : 'border-transparent bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
          "
          @click="actionFilter = a.value"
        >
          {{ a.label }}
        </button>
      </div>
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
            <!-- Status dot with glow -->
            <div class="relative flex-shrink-0">
              <span class="block h-2.5 w-2.5 rounded-full" :class="dotColor[e.action] || 'bg-slate-500'" />
              <span
                class="absolute inset-0 rounded-full opacity-40 blur-[3px]"
                :class="dotColor[e.action] || 'bg-slate-500'"
              />
            </div>

            <!-- Content -->
            <div class="min-w-0 flex-1">
              <div class="mb-0.5 flex items-center gap-2">
                <span class="text-[12px] font-semibold text-[--t2]">{{ e.action_label }}</span>
                <span v-if="e.rating" class="flex gap-0.5 text-amber-500/60">
                  <IconStar v-for="s in e.rating" :key="s" :size="11" />
                </span>
              </div>
              <p class="truncate text-[13px] font-medium text-[--t1]">{{ e.book }}</p>
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
