<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    percent: number
    height?: string
  }>(),
  {
    height: 'h-[3px]',
  },
)

const animatedWidth = ref(0)

onMounted(() => {
  requestAnimationFrame(() => {
    animatedWidth.value = props.percent
  })
})

watch(
  () => props.percent,
  (val) => {
    animatedWidth.value = val
  },
)
</script>

<template>
  <div class="w-full overflow-hidden rounded-full" :class="height" style="background: rgba(255, 255, 255, 0.04)">
    <div
      class="h-full rounded-full transition-all duration-700 ease-out"
      style="background: var(--gradient-bar)"
      :style="{ width: `${Math.min(100, Math.max(0, animatedWidth))}%` }"
    />
  </div>
</template>
