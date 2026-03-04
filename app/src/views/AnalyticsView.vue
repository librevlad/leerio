<script setup lang="ts">
import { onMounted } from 'vue'
import { useAnalytics } from '../composables/useAnalytics'
import CategoryChart from '../components/analytics/CategoryChart.vue'
import MonthlyTrend from '../components/analytics/MonthlyTrend.vue'
import RatingDistribution from '../components/analytics/RatingDistribution.vue'
import VelocityStats from '../components/analytics/VelocityStats.vue'
import AchievementGrid from '../components/analytics/AchievementGrid.vue'
import ActivityHeatmap from '../components/dashboard/ActivityHeatmap.vue'

const { data, achievements, loading, load } = useAnalytics()

onMounted(load)
</script>

<template>
  <div>
    <h1 class="page-title mb-8">Аналитика</h1>

    <div v-if="loading" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="skeleton h-52" />
        <div class="skeleton h-52" />
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="skeleton h-64" />
        <div class="skeleton h-64" />
      </div>
    </div>

    <div v-else-if="data" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <VelocityStats :velocity="data.velocity" />
        <CategoryChart :data="data.category_counts" />
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <MonthlyTrend :data="data.monthly_trend" />
        <RatingDistribution :data="data.rating_distribution" />
      </div>

      <ActivityHeatmap :data="data.heatmap" />

      <div v-if="data.top_authors.length" class="card p-6">
        <h3 class="section-label mb-5">Топ авторов</h3>
        <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div
            v-for="a in data.top_authors"
            :key="a.author"
            class="text-center p-4 rounded-2xl transition-all duration-200 hover:scale-[1.03]"
            style="background: rgba(255,255,255,0.03); border: 1px solid var(--border)"
          >
            <p class="text-[12px] font-medium truncate text-[--t2]">{{ a.author }}</p>
            <p class="text-[20px] font-bold text-[--t1] tracking-tight mt-1">{{ a.count }}</p>
          </div>
        </div>
      </div>

      <AchievementGrid :achievements="achievements" />
    </div>
  </div>
</template>
