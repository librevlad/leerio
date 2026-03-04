<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, number> }>()

const cells = computed(() => {
  const result: { date: string; count: number; x: number; y: number; month: string }[] = []
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth() - 5, 1)
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0)

  let weekIdx = 0
  const d = new Date(start)
  while (d.getDay() !== 1) d.setDate(d.getDate() - 1)

  while (d <= end) {
    const dayOfWeek = (d.getDay() + 6) % 7
    const key = d.toISOString().slice(0, 10)
    const count = props.data[key] || 0
    const inRange = d >= start && d <= end
    if (inRange) {
      result.push({
        date: key,
        count,
        x: weekIdx * 14,
        y: dayOfWeek * 14,
        month: d.toLocaleDateString('ru', { month: 'short' }),
      })
    }
    if (dayOfWeek === 6) weekIdx++
    d.setDate(d.getDate() + 1)
  }
  return result
})

const months = computed(() => {
  const seen = new Map<string, number>()
  for (const c of cells.value) {
    if (!seen.has(c.month)) seen.set(c.month, c.x)
  }
  return Array.from(seen.entries())
})

function intensity(count: number): string {
  if (count === 0) return 'heatmap-0'
  if (count === 1) return 'heatmap-1'
  if (count === 2) return 'heatmap-2'
  if (count === 3) return 'heatmap-3'
  return 'heatmap-4'
}
</script>

<template>
  <div class="card p-6">
    <h2 class="section-label mb-5">Активность</h2>
    <div class="overflow-x-auto">
      <svg :width="Math.max(...cells.map((c) => c.x), 0) + 20" :height="7 * 14 + 20" class="block">
        <text v-for="[label, x] in months" :key="label" :x="x" y="10" fill="var(--t3)" font-size="9" font-weight="500">
          {{ label }}
        </text>
        <rect
          v-for="c in cells"
          :key="c.date"
          :x="c.x"
          :y="c.y + 16"
          width="10"
          height="10"
          rx="3"
          :class="intensity(c.count)"
        >
          <title>{{ c.date }}: {{ c.count }}</title>
        </rect>
      </svg>
    </div>
  </div>
</template>
