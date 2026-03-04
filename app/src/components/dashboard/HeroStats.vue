<script setup lang="ts">
import { IconLibrary, IconQueue, IconMusic, IconBolt } from '../shared/icons'

defineProps<{
  totalBooks: number
  totalDone: number
  activeCount: number
  pace: number
}>()

const stats = [
  { key: 'totalBooks', label: 'Всего книг', icon: IconLibrary, bg: 'rgba(232,146,58,0.12)', color: 'text-orange-400' },
  { key: 'totalDone', label: 'Прослушано', icon: IconQueue, bg: 'rgba(52,211,153,0.12)', color: 'text-emerald-400' },
  { key: 'activeCount', label: 'Активных', icon: IconMusic, bg: 'rgba(96,165,250,0.12)', color: 'text-blue-400' },
  { key: 'pace', label: 'Книг / мес', icon: IconBolt, bg: 'rgba(251,191,36,0.12)', color: 'text-amber-400' },
]
</script>

<template>
  <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
    <div v-for="s in stats" :key="s.key" class="card px-5 py-5">
      <div class="mb-4 flex items-center justify-between">
        <span class="text-[12px] font-medium text-[--t3]">{{ s.label }}</span>
        <span class="stat-icon" :class="s.color" :style="{ background: s.bg }">
          <component :is="s.icon" :size="15" />
        </span>
      </div>
      <p class="text-[32px] leading-none font-bold tracking-tight text-[--t1]">
        {{
          s.key === 'pace'
            ? pace.toFixed(1)
            : s.key === 'totalBooks'
              ? totalBooks
              : s.key === 'totalDone'
                ? totalDone
                : activeCount
        }}
      </p>
    </div>
  </div>
</template>
