<script setup lang="ts">
import { computed } from 'vue'
import { Doughnut } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'

ChartJS.register(ArcElement, Tooltip, Legend)

const props = defineProps<{ data: Record<string, number> }>()

const hasData = computed(() => Object.values(props.data).some((v) => v > 0))

const categoryColors: Record<string, string> = {
  Бизнес: '#d4940c',
  Личные: '#7c3aed',
  Отношения: '#c9366d',
  Саморазвитие: '#7c5bf0',
  Художественная: '#0e8a99',
  Языки: '#0f8660',
  Другое: '#64748b',
}

const chartData = computed(() => ({
  labels: Object.keys(props.data),
  datasets: [
    {
      data: Object.values(props.data),
      backgroundColor: Object.keys(props.data).map((k) => categoryColors[k] || '#3e3e50'),
      borderWidth: 0,
      hoverOffset: 6,
    },
  ],
}))

const options = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: { color: '#4e4e5e', font: { size: 11 }, padding: 12 },
    },
  },
}
</script>

<template>
  <div class="card p-6">
    <h3 class="section-label mb-4">По категориям</h3>
    <div class="relative h-[200px] sm:h-[250px]">
      <Doughnut :data="chartData" :options="options" />
      <div v-if="!hasData" class="absolute inset-0 flex items-center justify-center">
        <p class="text-[13px] text-[--t3]">Начните слушать книги</p>
      </div>
    </div>
  </div>
</template>
