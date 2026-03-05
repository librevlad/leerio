<script setup lang="ts">
defineProps<{ category: string }>()
</script>

<template>
  <span
    class="inline-flex items-center rounded-md border border-white/[0.08] bg-white/[0.06] px-2 py-0.5 text-[11px] font-medium text-[--t2]"
  >
    {{ category }}
  </span>
</template>
