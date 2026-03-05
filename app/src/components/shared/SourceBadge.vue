<script setup lang="ts">
import { IconCloud, IconSmartphone } from './icons'

defineProps<{
  source: 'library' | 'librivox' | 'user' | 'local'
}>()

const config = {
  library: { label: 'Облако', color: 'bg-blue-500/80 text-blue-100' },
  librivox: { label: 'LibriVox', color: 'bg-teal-500/80 text-teal-100' },
  user: { label: 'Загружено', color: 'bg-violet-500/80 text-violet-100' },
  local: { label: 'Устройство', color: 'bg-amber-500/80 text-amber-100' },
}
</script>

<template>
  <span
    class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] leading-tight font-semibold backdrop-blur-sm"
    :class="config[source].color"
  >
    <component :is="source === 'local' ? IconSmartphone : IconCloud" :size="10" />
    {{ config[source].label }}
  </span>
</template>
