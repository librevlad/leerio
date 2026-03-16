<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Doughnut } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { useCategories } from '../../composables/useCategories'

ChartJS.register(ArcElement, Tooltip, Legend)

const { t } = useI18n()
const props = defineProps<{ data: Record<string, number> }>()

const { color: catColor } = useCategories()

const hasData = computed(() => Object.values(props.data).some((v) => v > 0))

const chartData = computed(() => ({
  labels: Object.keys(props.data),
  datasets: [
    {
      data: Object.values(props.data),
      backgroundColor: Object.keys(props.data).map((k) => catColor(k)),
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
    <h3 class="section-label mb-4">{{ t('analytics.categoryTitle') }}</h3>
    <div class="relative h-[200px] sm:h-[250px]">
      <Doughnut :data="chartData" :options="options" />
      <div v-if="!hasData" class="absolute inset-0 flex items-center justify-center">
        <p class="text-[13px] text-[--t3]">{{ t('analytics.categoryEmpty') }}</p>
      </div>
    </div>
  </div>
</template>
