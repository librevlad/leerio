<script setup lang="ts">
defineProps<{ status: string }>()

const colorMap: Record<string, { bg: string; text: string; dot: string }> = {
  Прочесть: { bg: 'bg-slate-500/8', text: 'text-slate-400', dot: 'bg-slate-400' },
  'В телефоне': { bg: 'bg-blue-500/10', text: 'text-blue-400', dot: 'bg-blue-400' },
  'В процессе': { bg: 'bg-purple-500/10', text: 'text-purple-400', dot: 'bg-purple-400' },
  'На Паузе': { bg: 'bg-yellow-500/10', text: 'text-yellow-400', dot: 'bg-yellow-400' },
  Прочитано: { bg: 'bg-green-500/10', text: 'text-green-400', dot: 'bg-green-400' },
  Забраковано: { bg: 'bg-red-500/10', text: 'text-red-400', dot: 'bg-red-400' },
  Скачать: { bg: 'bg-slate-500/8', text: 'text-slate-400', dot: 'bg-slate-400' },
}

const fallback = { bg: 'bg-slate-500/8', text: 'text-slate-400', dot: 'bg-slate-400' }
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-semibold"
    :class="[(colorMap[status] || fallback).bg, (colorMap[status] || fallback).text]"
  >
    <span class="h-1.5 w-1.5 rounded-full" :class="(colorMap[status] || fallback).dot" />
    {{ status }}
  </span>
</template>
