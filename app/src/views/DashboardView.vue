<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, coverUrl } from '../api'
import { useAuth } from '../composables/useAuth'
import { usePlayer } from '../composables/usePlayer'
import { useCategories } from '../composables/useCategories'
import type { DashboardData, ShelfBook } from '../types'
import ActivityHeatmap from '../components/dashboard/ActivityHeatmap.vue'
import YearlyGoal from '../components/dashboard/YearlyGoal.vue'
import RecentActivity from '../components/dashboard/RecentActivity.vue'
import PullIndicator from '../components/shared/PullIndicator.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import ProgressBar from '../components/shared/ProgressBar.vue'
import { IconMusic, IconPlay, IconPause } from '../components/shared/icons'
import { usePullToRefresh } from '../composables/usePullToRefresh'

const { t } = useI18n()
const { user } = useAuth()
const player = usePlayer()
const { gradient: catGradient } = useCategories()
const data = ref<DashboardData | null>(null)
const streak = ref({ current: 0, best: 0 })
const recommendations = ref<ShelfBook[]>([])
const loading = ref(true)
const coverErrors = reactive(new Set<string>())

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
  return base
})

const userName = computed(() => user.value?.name?.split(' ')[0] ?? '')

const heroBook = computed(() => {
  if (!data.value?.active_books.length) return null
  return data.value.active_books.find((b) => b.progress > 0) ?? data.value.active_books[0] ?? null
})

const otherBooks = computed(() => {
  if (!data.value?.active_books.length || !heroBook.value) return []
  return data.value.active_books.filter((b) => b.id !== heroBook.value!.id && b.progress > 0)
})

const smartRecommendation = computed(() => {
  if (!recommendations.value.length || !heroBook.value) return null
  return recommendations.value[0] ?? null
})

const nowPlayingId = computed(() => player.currentBook.value?.id ?? null)
const isPlaying = computed(() => player.isPlaying.value)

function formatRemaining(totalHours: number, progress: number): string {
  const remaining = totalHours * (1 - progress / 100)
  if (remaining < 1 / 60) return `< 1 ${t('common.unitMin')}`
  if (remaining < 1) return `${Math.round(remaining * 60)} ${t('common.unitMin')}`
  const h = Math.floor(remaining)
  const m = Math.round((remaining - h) * 60)
  return m > 0 ? `${h}${t('common.unitH')} ${m}${t('common.unitM')}` : `${h}${t('common.unitH')}`
}

async function playBook(bookId: string) {
  if (nowPlayingId.value === bookId) {
    player.togglePlay()
  } else {
    const book = await api.getBook(bookId)
    player.loadBook(book)
  }
}

async function loadData() {
  try {
    const [d, st, rec] = await Promise.allSettled([api.getDashboard(), api.getStreak(), api.getRecommendations()])
    if (d.status === 'fulfilled') data.value = d.value
    if (st.status === 'fulfilled') streak.value = st.value
    if (rec.status === 'fulfilled') recommendations.value = rec.value
  } finally {
    loading.value = false
  }
}

const hasActivity = computed(() => {
  if (!data.value?.heatmap) return false
  return Object.values(data.value.heatmap).some((count) => count > 0)
})

const { refreshing, pullProgress } = usePullToRefresh(loadData)

onMounted(loadData)
</script>

<template>
  <div>
    <PullIndicator :progress="pullProgress" :refreshing="refreshing" />

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-6">
      <div class="skeleton h-10 w-48" />
      <div class="skeleton h-[200px] rounded-2xl" />
      <div class="grid grid-cols-2 gap-3">
        <div class="skeleton h-24 rounded-2xl" />
        <div class="skeleton h-24 rounded-2xl" />
      </div>
    </div>

    <div v-else-if="data" class="fade-in" style="display: flex; flex-direction: column; gap: 20px">
      <!-- Greeting -->
      <div>
        <p class="text-[12px] font-semibold tracking-widest text-[--t3] uppercase">{{ greeting }}</p>
        <h1 class="mt-1 text-[22px] font-extrabold text-[--t1] md:text-[26px]">{{ userName }}</h1>
      </div>

      <!-- Desktop: Widget Grid 2:1 -->
      <!-- Mobile: stacked -->
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
        <!-- Hero Card -->
        <div
          v-if="heroBook"
          class="overflow-hidden rounded-2xl"
          style="
            background: linear-gradient(135deg, #1a1520 0%, #0d1420 100%);
            border: 1px solid rgba(255, 255, 255, 0.06);
          "
        >
          <div class="p-5">
            <p class="text-[10px] font-semibold tracking-widest text-[--accent] uppercase">
              {{ t('dashboard.continueListening') }}
            </p>
            <div class="mt-3 flex gap-4 sm:gap-5">
              <!-- Cover -->
              <router-link
                :to="`/book/${heroBook.id}`"
                class="relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-xl shadow-md sm:h-[120px] sm:w-[120px] sm:rounded-2xl"
              >
                <img
                  v-if="heroBook.has_cover !== false && !coverErrors.has(heroBook.id)"
                  :src="coverUrl(heroBook.id)"
                  :alt="heroBook.title"
                  class="h-full w-full object-cover"
                  @error="coverErrors.add(heroBook.id)"
                />
                <div
                  v-else
                  class="flex h-full w-full items-center justify-center"
                  :style="{ background: catGradient(heroBook.category ?? '') }"
                >
                  <IconMusic :size="32" class="text-white/40" />
                </div>
              </router-link>

              <!-- Info -->
              <div class="flex min-w-0 flex-1 flex-col justify-center">
                <router-link
                  :to="`/book/${heroBook.id}`"
                  class="line-clamp-2 text-[15px] leading-snug font-bold text-[--t1] no-underline hover:text-[--accent] sm:text-[20px]"
                >
                  {{ heroBook.title }}
                </router-link>
                <p class="mt-1 text-[12px] text-[--t3] sm:text-[13px]">
                  {{ heroBook.author }}
                  <template v-if="heroBook.current_chapter">
                    · {{ t('player.trackN', { n: heroBook.current_chapter, total: heroBook.total_chapters }) }}
                  </template>
                </p>
                <div class="mt-3 flex items-center gap-2 sm:max-w-[300px]">
                  <div class="flex-1">
                    <ProgressBar :percent="heroBook.progress" height="h-[3px]" />
                  </div>
                  <span class="flex-shrink-0 text-[11px] text-[--t3] tabular-nums">{{ heroBook.progress }}%</span>
                </div>
              </div>
            </div>

            <!-- Play button -->
            <button
              class="mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl border-0 py-3 text-[14px] font-bold text-white transition-all hover:brightness-110 sm:py-3.5 sm:text-[15px]"
              style="
                background: linear-gradient(135deg, #ff8a00, #e07000);
                box-shadow: 0 4px 20px rgba(255, 138, 0, 0.25);
              "
              @click="playBook(heroBook.id)"
            >
              <component :is="nowPlayingId === heroBook.id && isPlaying ? IconPause : IconPlay" :size="16" />
              {{
                nowPlayingId === heroBook.id && isPlaying
                  ? t('player.pause')
                  : heroBook.duration_hours
                    ? `${t('player.play')} · ${formatRemaining(heroBook.duration_hours, heroBook.progress)} ${t('common.remaining')}`
                    : t('player.play')
              }}
            </button>
          </div>
        </div>

        <!-- Welcome CTA if no active books -->
        <EmptyState
          v-else-if="!data.active_books.length && !data.recent.length"
          :title="t('dashboard.welcomeTitle')"
          :description="t('dashboard.welcomeDesc')"
          :action-label="t('dashboard.welcomeAction')"
          @action="$router.push('/library')"
        />

        <!-- Right column (desktop) / Below hero (mobile): Streak + Goal -->
        <div class="grid grid-cols-2 gap-3 lg:grid-cols-1 lg:gap-4">
          <!-- Streak -->
          <div
            v-if="streak.current > 0"
            class="rounded-2xl px-4 py-4"
            style="background: rgba(255, 138, 0, 0.06); border: 1px solid rgba(255, 138, 0, 0.1)"
          >
            <div class="flex items-center gap-2">
              <span class="text-[22px] lg:text-[24px]">&#x1F525;</span>
              <div>
                <p class="text-[20px] leading-none font-extrabold text-[--accent] lg:text-[22px]">
                  {{ streak.current }}
                </p>
                <p class="text-[10px] text-[--t3]">{{ t('plural.day', streak.current) }} {{ t('book.inARow') }}</p>
              </div>
            </div>
            <div class="mt-2.5 flex gap-[5px]">
              <div
                v-for="i in 7"
                :key="i"
                class="h-3 w-3 rounded-full lg:h-3.5 lg:w-3.5"
                :style="{
                  background:
                    i <= streak.current % 7 || (streak.current >= 7 && i <= 7) ? '#ff8a00' : 'rgba(255, 138, 0, 0.12)',
                }"
              />
            </div>
          </div>

          <!-- Yearly Goal -->
          <div
            v-if="data.yearly_goal > 0"
            class="rounded-2xl px-4 py-4"
            style="background: rgba(52, 211, 153, 0.06); border: 1px solid rgba(52, 211, 153, 0.1)"
          >
            <div class="flex items-center gap-2">
              <span class="text-[22px] lg:text-[24px]">&#x1F3AF;</span>
              <div>
                <p class="text-[20px] leading-none font-extrabold text-emerald-400 lg:text-[22px]">
                  {{ data.this_year_done }}<span class="text-[13px] text-[--t3]">/{{ data.yearly_goal }}</span>
                </p>
                <p class="text-[10px] text-[--t3]">{{ t('dashboard.yearlyGoal') }}</p>
              </div>
            </div>
            <div class="mt-2.5 h-1.5 overflow-hidden rounded-full" style="background: rgba(52, 211, 153, 0.1)">
              <div
                class="h-full rounded-full bg-emerald-400 transition-all duration-500"
                :style="{ width: Math.min((data.this_year_done / data.yearly_goal) * 100, 100) + '%' }"
              />
            </div>
          </div>

          <!-- Stats fallback when no streak/goal -->
          <div
            v-if="streak.current === 0 && data.yearly_goal === 0"
            class="col-span-2 flex justify-around rounded-2xl px-4 py-4 lg:col-span-1 lg:flex-col lg:gap-3"
            style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.04)"
          >
            <div class="text-center lg:text-left">
              <p class="text-[18px] font-extrabold text-[--t1]">{{ data.total_books }}</p>
              <p class="text-[10px] text-[--t3]">{{ t('dashboard.statBooks') }}</p>
            </div>
            <div class="text-center lg:text-left">
              <p class="text-[18px] font-extrabold text-emerald-400">{{ data.total_hours }}{{ t('common.unitH') }}</p>
              <p class="text-[10px] text-[--t3]">{{ t('dashboard.statHours') }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Second row: Other books + Recommendation -->
      <div v-if="otherBooks.length || smartRecommendation" class="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
        <!-- Other active books -->
        <div v-if="otherBooks.length" class="flex flex-col gap-2">
          <p class="text-[11px] font-semibold tracking-widest text-[--t3] uppercase">
            {{ t('dashboard.alsoListening') }}
          </p>
          <div
            v-for="book in otherBooks.slice(0, 4)"
            :key="book.id"
            class="flex items-center gap-3 rounded-xl px-3.5 py-2.5 transition-colors hover:bg-white/[0.03]"
            style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.03)"
          >
            <router-link :to="`/book/${book.id}`" class="h-11 w-11 flex-shrink-0 overflow-hidden rounded-lg">
              <img
                v-if="book.has_cover !== false && !coverErrors.has(book.id)"
                :src="coverUrl(book.id)"
                :alt="book.title"
                class="h-full w-full object-cover"
                @error="coverErrors.add(book.id)"
              />
              <div
                v-else
                class="flex h-full w-full items-center justify-center"
                :style="{ background: catGradient(book.category ?? '') }"
              >
                <IconMusic :size="14" class="text-white/40" />
              </div>
            </router-link>
            <router-link :to="`/book/${book.id}`" class="min-w-0 flex-1 no-underline">
              <p class="truncate text-[13px] font-semibold text-[--t2]">{{ book.title }}</p>
              <p class="text-[11px] text-[--t3]">
                {{ book.progress }}%
                <template v-if="book.duration_hours">
                  · {{ formatRemaining(book.duration_hours, book.progress) }}
                </template>
              </p>
            </router-link>
            <button
              class="flex h-7 w-7 flex-shrink-0 cursor-pointer items-center justify-center rounded-full border-0 transition-colors hover:bg-white/10"
              style="background: rgba(255, 255, 255, 0.06)"
              :aria-label="t('player.play') + ': ' + book.title"
              @click="playBook(book.id)"
            >
              <component
                :is="nowPlayingId === book.id && isPlaying ? IconPause : IconPlay"
                :size="10"
                class="text-[--t2]"
              />
            </button>
          </div>
        </div>

        <!-- Smart recommendation -->
        <div
          v-if="smartRecommendation"
          class="flex flex-col rounded-2xl px-4 py-4"
          style="
            background: linear-gradient(135deg, rgba(192, 132, 252, 0.06), rgba(96, 165, 250, 0.04));
            border: 1px solid rgba(192, 132, 252, 0.08);
          "
        >
          <p class="text-[10px] font-semibold tracking-widest text-purple-400 uppercase">
            &#x1F4A1; {{ t('dashboard.recommendation') }}
          </p>
          <div class="mt-3 flex flex-1 items-center gap-3">
            <router-link
              :to="`/book/${smartRecommendation.id}`"
              class="h-14 w-14 flex-shrink-0 overflow-hidden rounded-xl"
            >
              <img
                v-if="smartRecommendation.has_cover"
                :src="coverUrl(smartRecommendation.id)"
                :alt="smartRecommendation.title"
                class="h-full w-full object-cover"
              />
              <div v-else class="flex h-full w-full items-center justify-center bg-[--card-hover]">
                <IconMusic :size="18" class="text-[--t3]" />
              </div>
            </router-link>
            <div class="min-w-0 flex-1">
              <router-link
                :to="`/book/${smartRecommendation.id}`"
                class="line-clamp-2 text-[13px] font-bold text-[--t1] no-underline hover:text-purple-300"
              >
                {{ smartRecommendation.title }}
              </router-link>
              <p class="mt-0.5 text-[11px] text-[--t3]">{{ smartRecommendation.author }}</p>
              <p v-if="heroBook" class="mt-1 text-[10px] text-purple-400">
                {{ t('dashboard.similarTo', { title: heroBook.title }) }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Activity & Goal widgets (existing, for users who scroll) -->
      <div v-if="hasActivity" class="grid grid-cols-1 gap-4 lg:grid-cols-3">
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
