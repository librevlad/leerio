<script setup lang="ts">
import type { HistoryEntry } from '../../types'
import { IconStar } from '../shared/icons'
import { dotColor } from '../../composables/useStatusColors'

defineProps<{ entries: HistoryEntry[] }>()

function timeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins} мин`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} ч`
  const days = Math.floor(hrs / 24)
  return `${days} д`
}
</script>

<template>
  <div v-if="entries.length">
    <h2 class="section-label mb-4">Последние действия</h2>
    <div class="card p-2">
      <div
        v-for="(e, i) in entries"
        :key="i"
        class="flex items-center gap-3 px-4 py-2.5 rounded-2xl hover:bg-white/[0.03] transition-colors"
      >
        <span class="w-2 h-2 rounded-full flex-shrink-0" :class="dotColor[e.action] || 'bg-slate-500'" />
        <span class="text-[12px] font-semibold flex-shrink-0 text-[--t3]">
          {{ e.action_label }}
        </span>
        <span class="text-[12px] truncate flex-1 text-[--t2]">
          {{ e.book }}
        </span>
        <span v-if="e.rating" class="flex gap-0.5 text-amber-500/50 flex-shrink-0">
          <IconStar v-for="s in e.rating" :key="s" :size="11" />
        </span>
        <span class="text-[11px] flex-shrink-0 text-[--t3]">
          {{ timeAgo(e.ts) }}
        </span>
      </div>
    </div>
  </div>
</template>
