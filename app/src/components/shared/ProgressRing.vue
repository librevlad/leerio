<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    percent: number
    size?: number
    stroke?: number
  }>(),
  {
    size: 48,
    stroke: 3,
  },
)

const radius = computed(() => (props.size - props.stroke) / 2)
const circumference = computed(() => 2 * Math.PI * radius.value)
const offset = computed(() => circumference.value * (1 - Math.min(100, Math.max(0, props.percent)) / 100))
</script>

<template>
  <div class="relative inline-flex items-center justify-center">
    <svg :width="size" :height="size" class="-rotate-90">
      <defs>
        <linearGradient :id="`ring-grad-${size}`" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#E8923A" />
          <stop offset="100%" stop-color="#F8C98A" />
        </linearGradient>
      </defs>
      <circle
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        fill="none"
        :stroke-width="stroke"
        stroke="rgba(255,255,255,0.04)"
      />
      <circle
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        fill="none"
        :stroke-width="stroke"
        :stroke="`url(#ring-grad-${size})`"
        stroke-linecap="round"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="offset"
        class="transition-all duration-700 ease-out"
      />
    </svg>
    <span class="absolute font-semibold" :class="size >= 64 ? 'text-[13px] text-[--t1]' : 'text-[10px] text-[--t3]'">
      {{ percent }}%
    </span>
  </div>
</template>
