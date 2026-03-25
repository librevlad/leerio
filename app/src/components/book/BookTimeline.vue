<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { HistoryEntry } from '../../types'
import { dotColor, glowColor } from '../../composables/useStatusColors'

defineProps<{ entries: HistoryEntry[] }>()

const { t } = useI18n()

function formatDate(ts: string): string {
  return new Date(ts).toLocaleDateString('ru', { day: 'numeric', month: 'short', year: 'numeric' })
}
</script>

<template>
  <div v-if="entries.length" class="card p-5">
    <h3 class="section-label mb-5">{{ t('book.timeline') }}</h3>
    <div class="relative">
      <div
        v-for="(e, i) in entries"
        :key="i"
        class="relative flex items-start gap-3"
        :class="i < entries.length - 1 ? 'pb-5' : ''"
      >
        <!-- Dot column -->
        <div class="relative flex flex-col items-center">
          <!-- Vertical line -->
          <div
            v-if="i < entries.length - 1"
            class="absolute top-4 bottom-0 w-px"
            style="background: linear-gradient(to bottom, var(--border-light), var(--border))"
          />
          <!-- Dot with glow -->
          <span
            class="relative z-[1] h-3 w-3 flex-shrink-0 rounded-full"
            :class="dotColor[e.action] || 'bg-slate-500'"
            :style="{ boxShadow: `0 0 0 3px ${glowColor[e.action] || 'rgba(148,163,184,0.15)'}` }"
          />
        </div>

        <!-- Content -->
        <div class="-mt-0.5 min-w-0 flex-1">
          <div class="flex flex-wrap items-baseline gap-2">
            <span class="text-[12px] font-semibold text-[--t1]">{{ e.action_label }}</span>
            <span v-if="e.detail && e.detail !== e.action_label" class="text-[11px] text-[--t3]">{{ e.detail }}</span>
          </div>
          <p class="mt-0.5 text-[10px] text-[--t3]">{{ formatDate(e.ts) }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
