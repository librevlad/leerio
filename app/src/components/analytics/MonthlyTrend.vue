<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Tooltip, Filler,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler)

const props = defineProps<{ data: [string, number][] }>()

const chartData = computed(() => ({
  labels: props.data.map(([m]) => m),
  datasets: [{
    label: 'Прослушано',
    data: props.data.map(([, c]) => c),
    borderColor: '#7c5bf0',
    backgroundColor: 'rgba(124, 91, 240, 0.06)',
    fill: true,
    tension: 0.4,
    pointRadius: 2,
    pointBackgroundColor: '#7c5bf0',
    borderWidth: 2,
  }],
}))

const options = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: {
      ticks: { color: '#4e4e5e', font: { size: 10 } },
      grid: { color: 'rgba(255,255,255,0.03)' },
    },
    y: {
      beginAtZero: true,
      ticks: { color: '#4e4e5e', font: { size: 10 }, stepSize: 1 },
      grid: { color: 'rgba(255,255,255,0.03)' },
    },
  },
}
</script>

<template>
  <div class="card p-6">
    <h3 class="section-label mb-4">Тренд по месяцам</h3>
    <div class="h-[200px] sm:h-[250px]">
      <Line :data="chartData" :options="options" />
    </div>
  </div>
</template>
