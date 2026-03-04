<script setup lang="ts">
import { IconLibrary, IconQueue, IconMusic } from '../shared/icons'

defineProps<{
  totalBooks: number
  totalDone: number
  activeCount: number
}>()

const stats = [
  {
    key: 'totalBooks',
    label: 'Всего книг',
    icon: IconLibrary,
    bg: 'rgba(232,146,58,0.12)',
    color: 'text-orange-400',
    bar: 'linear-gradient(90deg, #e8923a, #f0a85c)',
  },
  {
    key: 'totalDone',
    label: 'Прослушано',
    icon: IconQueue,
    bg: 'rgba(52,211,153,0.12)',
    color: 'text-emerald-400',
    bar: 'linear-gradient(90deg, #34d399, #6ee7b7)',
  },
  {
    key: 'activeCount',
    label: 'В процессе',
    icon: IconMusic,
    bg: 'rgba(96,165,250,0.12)',
    color: 'text-blue-400',
    bar: 'linear-gradient(90deg, #60a5fa, #93c5fd)',
  },
]
</script>

<template>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
    <div v-for="s in stats" :key="s.key" class="card relative overflow-hidden px-5 py-5">
      <div class="absolute top-0 right-0 left-0 h-[2px]" :style="{ background: s.bar }" />
      <div class="mb-4 flex items-center justify-between">
        <span class="text-[12px] font-medium text-[--t3]">{{ s.label }}</span>
        <span class="stat-icon" :class="s.color" :style="{ background: s.bg }">
          <component :is="s.icon" :size="20" />
        </span>
      </div>
      <p class="text-[32px] leading-none font-bold tracking-tight text-[--t1]">
        {{ s.key === 'totalBooks' ? totalBooks : s.key === 'totalDone' ? totalDone : activeCount }}
      </p>
    </div>
  </div>
</template>
