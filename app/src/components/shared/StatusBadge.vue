<script setup lang="ts">
import { computed } from 'vue'
import type { BookStatusValue } from '../../types'

const props = defineProps<{ status?: string; bookStatus?: BookStatusValue }>()

const bookStatusLabel: Record<string, string> = {
  want_to_read: 'Хочу прочесть',
  reading: 'Слушаю',
  paused: 'На паузе',
  done: 'Прослушано',
  rejected: 'Забраковано',
}

const colorMap: Record<string, { bg: string; text: string }> = {
  Слушаю: { bg: 'bg-[--accent-soft]', text: 'text-[--accent]' },
  'В процессе': { bg: 'bg-[--accent-soft]', text: 'text-[--accent]' },
  Прочитано: { bg: 'bg-emerald-500/10', text: 'text-emerald-400' },
  Прослушано: { bg: 'bg-emerald-500/10', text: 'text-emerald-400' },
}

const fallback = { bg: 'bg-white/[0.06]', text: 'text-[--t2]' }

const displayStatus = computed(() => {
  if (props.status) return props.status
  if (props.bookStatus) return bookStatusLabel[props.bookStatus] || props.bookStatus
  return ''
})
</script>

<template>
  <span
    v-if="displayStatus"
    class="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-medium"
    :class="[(colorMap[displayStatus] || fallback).bg, (colorMap[displayStatus] || fallback).text]"
  >
    {{ displayStatus }}
  </span>
</template>
