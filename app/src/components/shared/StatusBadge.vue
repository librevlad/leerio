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

const colorMap: Record<string, { bg: string; text: string; dot: string }> = {
  Прочесть: { bg: 'bg-slate-500/8', text: 'text-slate-400', dot: 'bg-slate-400' },
  'В телефоне': { bg: 'bg-blue-500/10', text: 'text-blue-400', dot: 'bg-blue-400' },
  'В процессе': { bg: 'bg-purple-500/10', text: 'text-purple-400', dot: 'bg-purple-400' },
  'На Паузе': { bg: 'bg-yellow-500/10', text: 'text-yellow-400', dot: 'bg-yellow-400' },
  Прочитано: { bg: 'bg-green-500/10', text: 'text-green-400', dot: 'bg-green-400' },
  Забраковано: { bg: 'bg-red-500/10', text: 'text-red-400', dot: 'bg-red-400' },
  Скачать: { bg: 'bg-slate-500/8', text: 'text-slate-400', dot: 'bg-slate-400' },
  Слушаю: { bg: 'bg-purple-500/10', text: 'text-purple-400', dot: 'bg-purple-400' },
  'На паузе': { bg: 'bg-yellow-500/10', text: 'text-yellow-400', dot: 'bg-yellow-400' },
  Прослушано: { bg: 'bg-green-500/10', text: 'text-green-400', dot: 'bg-green-400' },
  'Хочу прочесть': { bg: 'bg-slate-500/8', text: 'text-slate-400', dot: 'bg-slate-400' },
}

const fallback = { bg: 'bg-slate-500/8', text: 'text-slate-400', dot: 'bg-slate-400' }

const displayStatus = computed(() => {
  if (props.status) return props.status
  if (props.bookStatus) return bookStatusLabel[props.bookStatus] || props.bookStatus
  return ''
})
</script>

<template>
  <span
    v-if="displayStatus"
    class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-semibold"
    :class="[(colorMap[displayStatus] || fallback).bg, (colorMap[displayStatus] || fallback).text]"
  >
    <span class="h-1.5 w-1.5 rounded-full" :class="(colorMap[displayStatus] || fallback).dot" />
    {{ displayStatus }}
  </span>
</template>
