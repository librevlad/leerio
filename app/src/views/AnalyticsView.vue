<script setup lang="ts">
import { onMounted } from 'vue'
import { useAnalytics } from '../composables/useAnalytics'
import CategoryChart from '../components/analytics/CategoryChart.vue'
import MonthlyTrend from '../components/analytics/MonthlyTrend.vue'
import RatingDistribution from '../components/analytics/RatingDistribution.vue'
import VelocityStats from '../components/analytics/VelocityStats.vue'
import AchievementGrid from '../components/analytics/AchievementGrid.vue'
import ActivityHeatmap from '../components/dashboard/ActivityHeatmap.vue'
import EmptyState from '../components/shared/EmptyState.vue'

const { data, achievements, loading, load } = useAnalytics()

onMounted(load)
</script>

<template>
  <div>
    <h1 class="page-title mb-8">Аналитика</h1>

    <div v-if="loading" class="space-y-6">
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div class="skeleton h-52" />
        <div class="skeleton h-52" />
      </div>
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div class="skeleton h-64" />
        <div class="skeleton h-64" />
      </div>
    </div>

    <div v-else-if="data" class="fade-in space-y-6">
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <VelocityStats :velocity="data.velocity" />
        <CategoryChart :data="data.category_counts" />
      </div>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <MonthlyTrend :data="data.monthly_trend" />
        <RatingDistribution :data="data.rating_distribution" />
      </div>

      <ActivityHeatmap :data="data.heatmap" />

      <div v-if="data.top_authors.length" class="card p-6">
        <h3 class="section-label mb-5">Топ авторов</h3>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <router-link
            v-for="a in data.top_authors"
            :key="a.author"
            :to="`/library?q=${encodeURIComponent(a.author)}`"
            class="card card-hover rounded-2xl p-4 text-center no-underline transition-transform hover:scale-[1.03]"
          >
            <p class="truncate text-[12px] font-medium text-[--t2]">{{ a.author }}</p>
            <p class="mt-1 text-[20px] font-bold tracking-tight text-[--t1]">{{ a.count }}</p>
          </router-link>
        </div>
      </div>

      <AchievementGrid :achievements="achievements" />
    </div>

    <EmptyState v-else title="Нет данных" description="Начните слушать книги, чтобы увидеть аналитику" />
  </div>
</template>
