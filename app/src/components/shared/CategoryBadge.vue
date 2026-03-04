<script setup lang="ts">
defineProps<{ category: string }>()

const styles: Record<string, { bg: string; text: string }> = {
  Бизнес: { bg: 'bg-amber-500/12', text: 'text-amber-400' },
  Отношения: { bg: 'bg-pink-500/12', text: 'text-pink-400' },
  Саморазвитие: { bg: 'bg-violet-500/12', text: 'text-violet-400' },
  Художественная: { bg: 'bg-cyan-500/12', text: 'text-cyan-400' },
  Языки: { bg: 'bg-emerald-500/12', text: 'text-emerald-400' },
}

const fallback = { bg: 'bg-slate-500/12', text: 'text-slate-400' }
</script>

<template>
  <span
    class="inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold"
    :class="[(styles[category] || fallback).bg, (styles[category] || fallback).text]"
  >
    {{ category }}
  </span>
</template>
