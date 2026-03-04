<script setup lang="ts">
import type { HistoryEntry } from '../../types'
import { dotColor } from '../../composables/useStatusColors'

defineProps<{ entries: HistoryEntry[] }>()

const glowColor: Record<string, string> = {
  'В телефоне':  'rgba(96,165,250,0.3)',
  'В процессе':  'rgba(168,85,247,0.3)',
  'На Паузе':    'rgba(250,204,21,0.3)',
  'Прочитано':   'rgba(74,222,128,0.3)',
  'Забраковано':  'rgba(248,113,113,0.3)',
  'Прочесть':    'rgba(148,163,184,0.2)',
  'Скачать':     'rgba(148,163,184,0.2)',
}

function formatDate(ts: string): string {
  return new Date(ts).toLocaleDateString('ru', { day: 'numeric', month: 'short', year: 'numeric' })
}
</script>

<template>
  <div v-if="entries.length" class="card p-5">
    <h3 class="section-label mb-5">Хронология</h3>
    <div class="relative">
      <div
        v-for="(e, i) in entries"
        :key="i"
        class="flex items-start gap-3.5 relative"
        :class="i < entries.length - 1 ? 'pb-5' : ''"
      >
        <!-- Dot column -->
        <div class="flex flex-col items-center relative">
          <!-- Vertical line -->
          <div
            v-if="i < entries.length - 1"
            class="absolute top-4 bottom-0 w-px"
            style="background: linear-gradient(to bottom, var(--border-light), var(--border))"
          />
          <!-- Dot with glow -->
          <span
            class="w-3 h-3 rounded-full flex-shrink-0 relative z-[1]"
            :class="dotColor[e.action] || 'bg-slate-500'"
            :style="{ boxShadow: `0 0 0 3px ${glowColor[e.action] || 'rgba(148,163,184,0.15)'}` }"
          />
        </div>

        <!-- Content -->
        <div class="flex-1 min-w-0 -mt-0.5">
          <div class="flex items-baseline gap-2 flex-wrap">
            <span class="text-[12px] font-semibold text-[--t1]">{{ e.action_label }}</span>
            <span v-if="e.detail" class="text-[11px] text-[--t3]">{{ e.detail }}</span>
          </div>
          <p class="text-[10px] mt-0.5 text-[--t3]">{{ formatDate(e.ts) }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
