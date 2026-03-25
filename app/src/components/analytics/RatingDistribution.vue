<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip } from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip)

const { t } = useI18n()
const props = defineProps<{ data: Record<string, number> }>()

const hasData = computed(() => Object.values(props.data).some((v) => v > 0))

const chartData = computed(() => {
  const labels = ['1', '2', '3', '4', '5']
  return {
    labels: labels.map((l) => l + ' '),
    datasets: [
      {
        label: t('analytics.ratingsLabel'),
        data: labels.map((l) => props.data[l] || 0),
        backgroundColor: ['#1f1f26', '#2a2a34', 'rgba(255,138,0,0.3)', 'rgba(255,138,0,0.6)', '#ff8a00'],
        borderRadius: 6,
        barThickness: 24,
      },
    ],
  }
})

const options = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: {
      ticks: { color: '#505068', font: { size: 11 } },
      grid: { display: false },
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
    <h3 class="section-label mb-4">{{ t('analytics.ratingsTitle') }}</h3>
    <div class="relative h-[200px] sm:h-[250px]">
      <Bar :data="chartData" :options="options" />
      <div v-if="!hasData" class="absolute inset-0 flex items-center justify-center">
        <p class="text-[13px] text-[--t3]">{{ t('analytics.ratingsEmpty') }}</p>
      </div>
    </div>
  </div>
</template>
