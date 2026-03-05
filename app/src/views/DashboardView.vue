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
import PullIndicator from '../components/shared/PullIndicator.vue'
import { usePullToRefresh } from '../composables/usePullToRefresh'

const data = ref<DashboardData | null>(null)
const loading = ref(true)

async function loadData() {
  try {
    data.value = await api.getDashboard()
  } finally {
    loading.value = false
  }
}

const { refreshing, pullProgress } = usePullToRefresh(loadData)

onMounted(loadData)
</script>

<template>
  <div>
    <PullIndicator :progress="pullProgress" :refreshing="refreshing" />
    <h1 class="page-title mb-10">Дашборд</h1>

    <div v-if="loading" class="space-y-6">
      <div class="skeleton h-28" />
      <div class="grid grid-cols-3 gap-4">
        <div v-for="i in 3" :key="i" class="skeleton h-28" />
      </div>
      <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div class="space-y-6 lg:col-span-2">
          <div class="skeleton h-40" />
          <div class="skeleton h-36" />
        </div>
        <div class="space-y-6">
          <div class="skeleton h-28" />
          <div class="skeleton h-32" />
        </div>
      </div>
    </div>

    <div v-else-if="data" class="fade-in space-y-8">
      <HeroStats :total-books="data.total_books" :total-done="data.total_done" :active-count="data.active_count" />

      <ActiveBooks :books="data.active_books" />

      <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div class="space-y-6 lg:col-span-2">
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
