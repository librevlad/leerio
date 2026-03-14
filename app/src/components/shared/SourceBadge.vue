<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { IconCloud, IconSmartphone } from './icons'

const props = defineProps<{
  source: 'library' | 'librivox' | 'user' | 'local'
}>()

const { t } = useI18n()

const label = computed(() => {
  const map: Record<string, string> = {
    library: t('common.sourceCloud'),
    librivox: 'LibriVox',
    user: t('common.sourceUploaded'),
    local: t('common.sourceDevice'),
  }
  return map[props.source] ?? props.source
})
</script>

<template>
  <span
    class="inline-flex items-center gap-1 rounded-md bg-white/[0.06] px-2 py-0.5 text-[9px] leading-tight font-medium text-[--t3] backdrop-blur-sm"
  >
    <component :is="source === 'local' ? IconSmartphone : IconCloud" :size="10" />
    {{ label }}
  </span>
</template>
