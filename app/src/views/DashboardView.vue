<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'
import type { DashboardData } from '../types'
import HeroStats from '../components/dashboard/HeroStats.vue'
import ActiveBooks from '../components/dashboard/ActiveBooks.vue'
import ActivityHeatmap from '../components/dashboard/ActivityHeatmap.vue'
import RecentActivity from '../components/dashboard/RecentActivity.vue'
import QuoteOfDay from '../components/dashboard/QuoteOfDay.vue'
import YearlyGoal from '../components/dashboard/YearlyGoal.vue'

const data = ref<DashboardData | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    data.value = await api.getDashboard()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <h1 class="page-title mb-10">Дашборд</h1>

    <div v-if="loading" class="space-y-6">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="skeleton h-28" />
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="lg:col-span-2 space-y-6">
          <div class="skeleton h-40" />
          <div class="skeleton h-36" />
        </div>
        <div class="space-y-6">
          <div class="skeleton h-28" />
          <div class="skeleton h-32" />
        </div>
      </div>
    </div>

    <div v-else-if="data" class="space-y-8">
      <HeroStats
        :total-books="data.total_books"
        :total-done="data.total_done"
        :active-count="data.active_count"
        :pace="data.velocity.avg_per_month || 0"
      />

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="lg:col-span-2 space-y-6">
          <ActiveBooks :books="data.active_books" />
          <ActivityHeatmap :data="data.heatmap" />
        </div>
        <div class="space-y-6">
          <YearlyGoal :done="data.this_year_done" :goal="data.yearly_goal" />
          <QuoteOfDay :quote="data.quote" />
        </div>
      </div>

      <RecentActivity :entries="data.recent" />
    </div>
  </div>
</template>
