<script setup lang="ts">
withDefaults(defineProps<{
  percent: number
  height?: string
}>(), {
  height: 'h-[3px]',
})
</script>

<template>
  <div class="w-full rounded-full overflow-hidden" :class="height" style="background: rgba(255,255,255,0.04)">
    <div
      class="h-full rounded-full transition-all duration-700 ease-out"
      style="background: var(--gradient-bar)"
      :style="{ width: `${Math.min(100, Math.max(0, percent))}%` }"
    />
  </div>
</template>
