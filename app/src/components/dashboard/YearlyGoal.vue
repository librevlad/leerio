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
    <div class="flex items-center justify-between mb-4">
      <span class="section-label">Годовая цель</span>
      <span class="text-[12px] font-medium text-[--t3]">{{ done }}/{{ goal }}</span>
    </div>
    <ProgressBar :percent="percent" height="h-1.5" />
    <p class="text-[24px] font-bold mt-3 tracking-tight leading-none gradient-text">{{ percent }}%</p>
    <p class="text-[12px] mt-1 text-[--t3]">осталось {{ Math.max(0, goal - done) }} книг</p>
  </div>
</template>
