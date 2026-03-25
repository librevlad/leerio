<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { BookStatusValue } from '../../types'

const props = defineProps<{ status?: string; bookStatus?: BookStatusValue }>()

const { t } = useI18n()

const bookStatusLabel: Record<string, () => string> = {
  want_to_read: () => t('common.statusWant'),
  reading: () => t('common.statusReading'),
  paused: () => t('common.statusPaused'),
  done: () => t('common.statusDone'),
  rejected: () => t('common.statusRejected'),
}

const colorByStatus: Record<string, { bg: string; text: string }> = {
  want_to_read: { bg: 'bg-[--info]/10', text: 'text-[--info]' },
  reading: { bg: 'bg-[--accent-soft]', text: 'text-[--accent]' },
  paused: { bg: 'bg-[--warning]/10', text: 'text-[--warning]' },
  done: { bg: 'bg-[--success]/10', text: 'text-[--success]' },
  rejected: { bg: 'bg-[--error]/10', text: 'text-[--error]' },
}

const fallback = { bg: 'bg-white/[0.06]', text: 'text-[--t2]' }

const displayStatus = computed(() => {
  if (props.status) return props.status
  if (props.bookStatus) return bookStatusLabel[props.bookStatus]?.() || props.bookStatus
  return ''
})

const colors = computed(() => {
  if (props.bookStatus && colorByStatus[props.bookStatus]) return colorByStatus[props.bookStatus]
  return fallback
})
</script>

<template>
  <span
    v-if="displayStatus"
    class="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-medium"
    :class="[colors?.bg, colors?.text]"
  >
    {{ displayStatus }}
  </span>
</template>
