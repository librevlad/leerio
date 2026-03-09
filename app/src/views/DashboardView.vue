<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api, coverUrl } from '../api'
import { useAuth } from '../composables/useAuth'
import type { DashboardData, ShelfData, ShelfBook } from '../types'
import ContinueListening from '../components/dashboard/ContinueListening.vue'
import BookShelf from '../components/dashboard/BookShelf.vue'
import ActivityHeatmap from '../components/dashboard/ActivityHeatmap.vue'
import YearlyGoal from '../components/dashboard/YearlyGoal.vue'
import RecentActivity from '../components/dashboard/RecentActivity.vue'
import PullIndicator from '../components/shared/PullIndicator.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import { usePullToRefresh } from '../composables/usePullToRefresh'
import { plural } from '../utils/plural'

const router = useRouter()
const { t } = useI18n()
const { user } = useAuth()
const data = ref<DashboardData | null>(null)
const shelves = ref<ShelfData[]>([])
const streak = ref({ current: 0, best: 0 })
const recommendations = ref<ShelfBook[]>([])
const loading = ref(true)

const greeting = computed(() => {
  const h = new Date().getHours()
  const base =
    h < 6
      ? t('dashboard.greetNight')
      : h < 12
        ? t('dashboard.greetMorning')
        : h < 18
          ? t('dashboard.greetDay')
          : t('dashboard.greetEvening')
  const name = user.value?.name?.split(' ')[0]
  return name ? `${base}, ${name}` : base
})

async function loadData() {
  try {
    const [d, s, st, rec] = await Promise.allSettled([
      api.getDashboard(),
      api.getShelves(),
      api.getStreak(),
      api.getRecommendations(),
    ])
    if (d.status === 'fulfilled') data.value = d.value
    if (s.status === 'fulfilled') shelves.value = s.value
    if (st.status === 'fulfilled') streak.value = st.value
    if (rec.status === 'fulfilled') recommendations.value = rec.value
  } finally {
    loading.value = false
  }
}

const { refreshing, pullProgress } = usePullToRefresh(loadData)

function randomBook() {
  const allBooks = shelves.value.flatMap((s) => s.books)
  if (!allBooks.length) return
  const pick = allBooks[Math.floor(Math.random() * allBooks.length)]!
  router.push(`/book/${pick.id}`)
}

onMounted(loadData)
</script>

<template>
  <div>
    <PullIndicator :progress="pullProgress" :refreshing="refreshing" />

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-8">
      <div class="skeleton h-12 w-64" />
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div v-for="i in 4" :key="i" class="skeleton h-24 rounded-2xl" />
      </div>
      <div class="flex gap-4 overflow-hidden">
        <div v-for="i in 3" :key="i" class="skeleton h-32 min-w-[280px] rounded-2xl" />
      </div>
    </div>

    <div v-else-if="data" class="fade-in" style="display: flex; flex-direction: column; gap: 40px">
      <!-- Hero: Greeting + Stats -->
      <div>
        <h1 class="page-title">{{ greeting }}</h1>

        <!-- Stats cards -->
        <div class="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div class="card px-5 py-4">
            <p class="text-[11px] font-semibold tracking-wide text-[--t3] uppercase">{{ t('dashboard.statBooks') }}</p>
            <p class="mt-1 text-[28px] leading-none font-bold tracking-tight text-[--t1]">{{ data.total_books }}</p>
          </div>
          <div class="card px-5 py-4">
            <p class="text-[11px] font-semibold tracking-wide text-[--t3] uppercase">
              {{ t('dashboard.statListened') }}
            </p>
            <p class="mt-1 text-[28px] leading-none font-bold tracking-tight text-emerald-400">{{ data.total_done }}</p>
          </div>
          <div class="card px-5 py-4">
            <p class="text-[11px] font-semibold tracking-wide text-[--t3] uppercase">{{ t('dashboard.statHours') }}</p>
            <p class="mt-1 text-[28px] leading-none font-bold tracking-tight text-purple-400">
              {{ data.total_hours }}
            </p>
          </div>
          <div class="card px-5 py-4">
            <p class="text-[11px] font-semibold tracking-wide text-[--t3] uppercase">{{ t('dashboard.statStreak') }}</p>
            <div class="mt-1 flex items-baseline gap-2">
              <p class="text-[28px] leading-none font-bold tracking-tight text-[--accent]">{{ streak.current }}</p>
              <p class="text-[12px] text-[--t3]">{{ plural(streak.current, 'день', 'дня', 'дней') }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Streak banner (if active) -->
      <div
        v-if="streak.current > 0"
        class="card flex items-center gap-4 px-5 py-4"
        style="background: linear-gradient(135deg, rgba(255, 138, 0, 0.08) 0%, var(--card) 100%)"
      >
        <span class="text-[28px]">&#x1F525;</span>
        <div class="flex-1">
          <p class="text-[15px] font-bold text-[--accent]">
            {{ streak.current }} {{ plural(streak.current, 'день', 'дня', 'дней') }} подряд!
          </p>
          <p class="text-[12px] text-[--t3]">
            Лучшая серия: {{ streak.best }} {{ plural(streak.best, 'день', 'дня', 'дней') }}
          </p>
        </div>
        <!-- 7-day progress -->
        <div class="hidden items-center gap-3 sm:flex">
          <div class="flex gap-1">
            <div
              v-for="i in 7"
              :key="i"
              class="h-2 w-5 rounded-full"
              :style="{
                background:
                  i <= streak.current % 7 || (streak.current >= 7 && i <= 7)
                    ? 'var(--accent)'
                    : 'rgba(255,255,255,0.06)',
              }"
            />
          </div>
          <span class="text-[11px] text-[--t3]">{{ Math.min(streak.current, 7) }}/7</span>
        </div>
      </div>

      <!-- Continue Listening (hero) -->
      <ContinueListening :books="data.active_books" />

      <!-- Welcome CTA if no active books -->
      <EmptyState
        v-if="!data.active_books.length && !data.recent.length"
        :title="t('dashboard.welcomeTitle')"
        :description="t('dashboard.welcomeDesc')"
        :action-label="t('dashboard.welcomeAction')"
        @action="$router.push('/library')"
      />

      <!-- Recommendations -->
      <div v-if="recommendations.length">
        <div class="mb-4 flex items-center justify-between">
          <h2 class="section-label">{{ t('dashboard.todayForYou') }}</h2>
          <button
            class="inline-flex min-h-[44px] cursor-pointer items-center gap-1.5 border-0 bg-transparent text-[12px] font-medium text-[--accent] hover:underline"
            @click="randomBook"
          >
            {{ t('dashboard.randomBook') }}
          </button>
        </div>
        <div class="grid grid-cols-3 gap-4 sm:grid-cols-6">
          <router-link
            v-for="book in recommendations"
            :key="book.id"
            :to="`/book/${book.id}`"
            class="group no-underline"
          >
            <div
              class="aspect-square overflow-hidden rounded-2xl shadow-md transition-transform duration-150 group-hover:scale-[1.03]"
            >
              <img
                v-if="book.has_cover"
                :src="coverUrl(book.id)"
                :alt="book.title"
                class="h-full w-full object-cover"
                loading="lazy"
              />
              <div v-else class="flex h-full w-full items-center justify-center bg-[--card-hover]">
                <span class="text-[28px] text-[--t3]">&#x1F3B5;</span>
              </div>
            </div>
            <h4 class="mt-2 line-clamp-2 text-[12px] leading-tight font-medium text-[--t2] group-hover:text-[--t1]">
              {{ book.title }}
            </h4>
            <p class="mt-0.5 line-clamp-1 text-[11px] text-[--t3]">{{ book.author }}</p>
          </router-link>
        </div>
      </div>

      <!-- Category shelves -->
      <BookShelf
        v-for="shelf in shelves"
        :key="shelf.category"
        :category="shelf.category"
        :count="shelf.count"
        :books="shelf.books"
      />

      <!-- Compact widgets row -->
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
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
