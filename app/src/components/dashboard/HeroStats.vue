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
    to: '/library',
    color: 'rgba(232, 146, 58, 0.12)',
    iconColor: 'var(--accent)',
  },
  {
    key: 'totalDone',
    label: 'Прослушано',
    icon: IconQueue,
    to: '/history',
    color: 'rgba(52, 211, 153, 0.12)',
    iconColor: '#34d399',
  },
  {
    key: 'activeCount',
    label: 'В процессе',
    icon: IconMusic,
    to: '/library',
    color: 'rgba(129, 140, 248, 0.12)',
    iconColor: '#818cf8',
  },
]
</script>

<template>
  <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4">
    <router-link
      v-for="s in stats"
      :key="s.key"
      :to="s.to"
      class="card relative overflow-hidden px-5 py-5 no-underline transition-colors hover:border-white/10"
    >
      <div class="mb-4 flex items-center justify-between">
        <span class="text-[12px] font-semibold text-[--t3]">{{ s.label }}</span>
        <span class="stat-icon" :style="{ background: s.color, color: s.iconColor }">
          <component :is="s.icon" :size="20" />
        </span>
      </div>
      <p class="text-[32px] leading-none font-bold tracking-tight text-[--t1]">
        {{ s.key === 'totalBooks' ? totalBooks : s.key === 'totalDone' ? totalDone : activeCount }}
      </p>
    </router-link>
  </div>
</template>
