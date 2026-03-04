<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { api } from '../api'
import type { HistoryEntry } from '../types'
import SearchInput from '../components/shared/SearchInput.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import { IconStar } from '../components/shared/icons'
import { dotColor } from '../composables/useStatusColors'

const entries = ref<HistoryEntry[]>([])
const loading = ref(true)
const search = ref('')
const actionFilter = ref('')

const actions = [
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

onMounted(loadHistory)
watch([actionFilter, search], loadHistory)

function formatDate(ts: string): string {
  return new Date(ts).toLocaleString('ru', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div>
    <h1 class="page-title mb-8">История</h1>

    <div class="mb-6 flex flex-wrap items-center gap-3">
      <SearchInput v-model="search" placeholder="Поиск по книге..." class="min-w-[200px] flex-1" />
      <select v-model="actionFilter" class="input-field cursor-pointer px-3 py-2.5 text-[13px]">
        <option v-for="a in actions" :key="a.value" :value="a.value">{{ a.label }}</option>
      </select>
    </div>

    <div v-if="loading" class="space-y-2">
      <div v-for="i in 6" :key="i" class="skeleton h-16" />
    </div>

    <div v-else-if="entries.length" class="space-y-2">
      <div v-for="(e, i) in entries" :key="i" class="card flex items-center gap-4 px-5 py-3.5">
        <span class="h-2 w-2 flex-shrink-0 rounded-full opacity-60" :class="dotColor[e.action] || 'bg-slate-500'" />
        <div class="min-w-0 flex-1">
          <div class="mb-0.5 flex items-center gap-2">
            <span class="text-[12px] font-medium text-[--t2]">{{ e.action_label }}</span>
            <span v-if="e.rating" class="flex gap-0.5 text-amber-500/50">
              <IconStar v-for="s in e.rating" :key="s" :size="11" />
            </span>
          </div>
          <p class="truncate text-[13px] text-[--t1]">{{ e.book }}</p>
          <p v-if="e.detail" class="truncate text-[11px] text-[--t3]">{{ e.detail }}</p>
        </div>
        <span class="flex-shrink-0 text-[11px] whitespace-nowrap text-[--t3]">
          {{ formatDate(e.ts) }}
        </span>
      </div>
    </div>

    <EmptyState v-else title="История пуста" />
  </div>
</template>
