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
    <div class="mb-4 flex items-center justify-between">
      <h2 class="section-label">Последние действия</h2>
      <router-link to="/history" class="text-[12px] font-medium text-[--accent] no-underline hover:underline">
        Все действия
      </router-link>
    </div>
    <div class="card overflow-hidden">
      <div
        v-for="(e, i) in entries"
        :key="i"
        class="flex items-center gap-3 border-b border-[--border] px-4 py-2.5 transition-colors last:border-0 hover:bg-white/[0.02]"
      >
        <div class="relative flex-shrink-0">
          <span class="block h-2 w-2 rounded-full" :class="dotColor[e.action] || 'bg-slate-500'" />
          <span
            class="absolute inset-0 rounded-full opacity-40 blur-[3px]"
            :class="dotColor[e.action] || 'bg-slate-500'"
          />
        </div>
        <span class="flex-shrink-0 text-[12px] font-semibold text-[--t3]">
          {{ e.action_label }}
        </span>
        <router-link
          v-if="e.book_id"
          :to="`/book/${e.book_id}`"
          class="flex-1 truncate text-[12px] font-medium text-[--t2] no-underline transition-colors hover:text-[--accent]"
        >
          {{ e.book }}
        </router-link>
        <span v-else class="flex-1 truncate text-[12px] text-[--t2]">
          {{ e.book }}
        </span>
        <span v-if="e.rating" class="flex flex-shrink-0 gap-0.5 text-amber-500/50">
          <IconStar v-for="s in e.rating" :key="s" :size="11" />
        </span>
        <span class="flex-shrink-0 text-[11px] text-[--t3]">
          {{ timeAgo(e.ts) }}
        </span>
      </div>
    </div>
  </div>
</template>
