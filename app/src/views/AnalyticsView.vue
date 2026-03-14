<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAnalytics } from '../composables/useAnalytics'
import CategoryChart from '../components/analytics/CategoryChart.vue'
import MonthlyTrend from '../components/analytics/MonthlyTrend.vue'
import RatingDistribution from '../components/analytics/RatingDistribution.vue'
import VelocityStats from '../components/analytics/VelocityStats.vue'
import AchievementGrid from '../components/analytics/AchievementGrid.vue'
import ActivityHeatmap from '../components/dashboard/ActivityHeatmap.vue'
import EmptyState from '../components/shared/EmptyState.vue'

const { t } = useI18n()
const { data, achievements, loading, error, load } = useAnalytics()

onMounted(load)
</script>

<template>
  <div>
    <h1 class="page-title mb-8">{{ t('analytics.title') }}</h1>

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

    <div v-else-if="error" class="card p-8 text-center">
      <p class="text-[16px] font-semibold text-[--t1]">{{ t('common.loadError') }}</p>
      <p class="mt-1 text-[13px] text-[--t3]">{{ t('common.tryAgain') }}</p>
      <button
        class="mt-4 rounded-xl px-5 py-2.5 text-[13px] font-semibold text-white"
        style="background: var(--gradient-accent)"
        @click="load"
      >
        {{ t('common.retry') }}
      </button>
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
        <h3 class="section-label mb-5">{{ t('analytics.topAuthors') }}</h3>
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

    <EmptyState v-else :title="t('analytics.emptyTitle')" :description="t('analytics.emptyDesc')" />
  </div>
</template>
