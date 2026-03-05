<script setup lang="ts">
import { IconCloud, IconSmartphone } from './icons'

defineProps<{
  source: 'library' | 'librivox' | 'user' | 'local'
}>()

const config = {
  library: { label: 'Облако' },
  librivox: { label: 'LibriVox' },
  user: { label: 'Загружено' },
  local: { label: 'Устройство' },
}
</script>

<template>
  <span
    class="inline-flex items-center gap-1 rounded-md bg-white/[0.06] px-2 py-0.5 text-[9px] leading-tight font-medium text-[--t3] backdrop-blur-sm"
  >
    <component :is="source === 'local' ? IconSmartphone : IconCloud" :size="10" />
    {{ config[source].label }}
  </span>
</template>
