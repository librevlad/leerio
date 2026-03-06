<script setup lang="ts">
import { useCategories } from '../../composables/useCategories'

defineProps<{ category: string }>()

const { color: catColor } = useCategories()
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-white/[0.06] px-2 py-0.5 text-[11px] font-medium text-[--t2]"
  >
    <span class="inline-block h-1.5 w-1.5 rounded-full" :style="{ background: catColor(category) }" />
    {{ category }}
  </span>
</template>
