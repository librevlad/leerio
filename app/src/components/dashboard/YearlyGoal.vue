<script setup lang="ts">
import { computed } from 'vue'
import ProgressBar from '../shared/ProgressBar.vue'

const props = defineProps<{
  done: number
  goal: number
}>()

const percent = computed(() => Math.min(100, Math.round((props.done / Math.max(1, props.goal)) * 100)))
</script>

<template>
  <div class="card p-5">
    <div class="mb-4 flex items-center justify-between">
      <span class="section-label">Годовая цель</span>
      <span class="text-[12px] font-medium text-[--t3]">{{ done }}/{{ goal }}</span>
    </div>
    <ProgressBar :percent="percent" height="h-1.5" />
    <p class="gradient-text mt-3 text-[24px] leading-none font-bold tracking-tight">{{ percent }}%</p>
    <p class="mt-1 text-[12px] text-[--t3]">осталось {{ Math.max(0, goal - done) }} книг</p>
  </div>
</template>
