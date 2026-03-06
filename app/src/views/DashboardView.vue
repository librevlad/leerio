<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'
import type { DashboardData, ShelfData } from '../types'
import ContinueListening from '../components/dashboard/ContinueListening.vue'
import BookShelf from '../components/dashboard/BookShelf.vue'
import ActivityHeatmap from '../components/dashboard/ActivityHeatmap.vue'
import YearlyGoal from '../components/dashboard/YearlyGoal.vue'
import RecentActivity from '../components/dashboard/RecentActivity.vue'
import PullIndicator from '../components/shared/PullIndicator.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import { usePullToRefresh } from '../composables/usePullToRefresh'

const data = ref<DashboardData | null>(null)
const shelves = ref<ShelfData[]>([])
const loading = ref(true)

async function loadData() {
  try {
    const [d, s] = await Promise.all([api.getDashboard(), api.getShelves()])
    data.value = d
    shelves.value = s
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

    <!-- Loading -->
    <div v-if="loading" class="space-y-6">
      <div class="skeleton h-10 w-48" />
      <div class="flex gap-3 overflow-hidden">
        <div v-for="i in 3" :key="i" class="skeleton h-28 min-w-[260px]" />
      </div>
      <div v-for="j in 2" :key="j" class="space-y-3">
        <div class="skeleton h-5 w-32" />
        <div class="flex gap-3 overflow-hidden">
          <div v-for="i in 5" :key="i" class="skeleton h-40 min-w-[130px]" />
        </div>
      </div>
    </div>

    <div v-else-if="data" class="fade-in space-y-8">
      <!-- Greeting -->
      <div>
        <h1 class="page-title">Главная</h1>
        <p class="mt-1 text-[13px] text-[--t3]">
          <span class="font-bold text-[--accent]">{{ data.total_books }}</span> книг в библиотеке ·
          <span class="font-bold text-emerald-400">{{ data.total_done }}</span> прослушано
        </p>
      </div>

      <!-- Continue Listening (hero) -->
      <ContinueListening :books="data.active_books" />

      <!-- Welcome CTA if no active books -->
      <EmptyState
        v-if="!data.active_books.length && !data.recent.length"
        title="Добро пожаловать!"
        description="Начните с каталога — выберите книгу и поставьте статус «Слушаю»"
        action-label="Открыть каталог"
        @action="$router.push('/library')"
      />

      <!-- Category shelves -->
      <BookShelf
        v-for="shelf in shelves"
        :key="shelf.category"
        :category="shelf.category"
        :count="shelf.count"
        :books="shelf.books"
      />

      <!-- Compact widgets row -->
      <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div class="lg:col-span-2">
          <ActivityHeatmap :data="data.heatmap" />
        </div>
        <div>
          <YearlyGoal :done="data.this_year_done" :goal="data.yearly_goal" />
        </div>
      </div>

      <!-- Recent activity -->
      <RecentActivity :entries="data.recent" />
    </div>
  </div>
</template>
