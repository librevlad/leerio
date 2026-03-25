<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Line } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler } from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler)

const { t } = useI18n()
const props = defineProps<{ data: [string, number][] }>()

const hasData = computed(() => props.data.some(([, c]) => c > 0))

const chartData = computed(() => ({
  labels: props.data.map(([m]) => m),
  datasets: [
    {
      label: t('analytics.monthlyLabel'),
      data: props.data.map(([, c]) => c),
      borderColor: '#ff8a00',
      backgroundColor: 'rgba(255, 138, 0, 0.06)',
      fill: true,
      tension: 0.4,
      pointRadius: 2,
      pointBackgroundColor: '#ff8a00',
      borderWidth: 2,
    },
  ],
}))

const options = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: {
      ticks: { color: '#505068', font: { size: 10 } },
      grid: { color: 'rgba(255,255,255,0.03)' },
    },
    y: {
      beginAtZero: true,
      ticks: { color: '#505068', font: { size: 10 }, stepSize: 1 },
      grid: { color: 'rgba(255,255,255,0.03)' },
    },
  },
}
</script>

<template>
  <div class="card p-6">
    <h3 class="section-label mb-4">{{ t('analytics.monthlyTitle') }}</h3>
    <div class="relative h-[200px] sm:h-[250px]">
      <Line :data="chartData" :options="options" />
      <div v-if="!hasData" class="absolute inset-0 flex items-center justify-center">
        <p class="text-[13px] text-[--t3]">{{ t('analytics.monthlyEmpty') }}</p>
      </div>
    </div>
  </div>
</template>
