<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useDownloads } from '../composables/useDownloads'
import { useLocalBooks } from '../composables/useLocalBooks'
import { useOfflineCache } from '../composables/useOfflineCache'
import { useAuth } from '../composables/useAuth'
import type { SessionStats } from '../types'
import { IconTrash, IconDownload, IconHardDrive } from '../components/shared/icons'
import { plural } from '../utils/plural'

const router = useRouter()
const dl = useDownloads()
const { localBooks } = useLocalBooks()
const cache = useOfflineCache()
const { user, isAdmin, logout } = useAuth()
const cacheBytes = ref(cache.cacheSize())
const sessionStats = ref<SessionStats | null>(null)
const statsLoading = ref(true)
const yearlyGoal = ref(24)
const playbackSpeed = ref(1.0)
const streak = ref({ current: 0, best: 0 })
const goalSaving = ref(false)

const speeds = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]

onMounted(async () => {
  const [, settings, streakData] = await Promise.allSettled([
    api.getSessionStats(30).then((s) => (sessionStats.value = s)),
    api.getUserSettings(),
    api.getStreak(),
  ])
  if (settings.status === 'fulfilled') {
    yearlyGoal.value = settings.value.yearly_goal
    playbackSpeed.value = settings.value.playback_speed
  }
  if (streakData.status === 'fulfilled') {
    streak.value = streakData.value
  }
  statsLoading.value = false
})

async function saveGoal() {
  goalSaving.value = true
  try {
    await api.updateUserSettings({ yearly_goal: yearlyGoal.value })
  } finally {
    goalSaving.value = false
  }
}

async function setSpeed(speed: number) {
  playbackSpeed.value = speed
  localStorage.setItem('leerio_playback_rate', String(speed))
  await api.updateUserSettings({ playback_speed: speed }).catch(() => {})
}

function fmtSize(bytes: number): string {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' КБ'
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' МБ'
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' ГБ'
}

function clearCache() {
  cache.clear()
  cacheBytes.value = 0
}

async function handleLogout() {
  await logout()
  router.push('/login')
}
</script>

<template>
  <div>
    <h1 class="page-title mb-8">Настройки</h1>

    <div class="max-w-2xl space-y-5">
      <!-- Profile -->
      <div class="card p-5">
        <h3 class="section-label mb-4">Профиль</h3>
        <div v-if="user" class="flex items-center gap-4">
          <img
            v-if="user.picture"
            :src="user.picture"
            :alt="user.name"
            class="h-14 w-14 rounded-full object-cover ring-2 ring-[--border]"
            referrerpolicy="no-referrer"
          />
          <div
            v-else
            class="flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-[18px] font-bold text-[--t2]"
            style="background: rgba(255, 255, 255, 0.08)"
          >
            {{ user.name?.charAt(0) || '?' }}
          </div>
          <div class="min-w-0 flex-1">
            <p class="text-[15px] font-semibold text-[--t1]">{{ user.name }}</p>
            <p class="text-[13px] text-[--t3]">{{ user.email }}</p>
            <span
              v-if="isAdmin"
              class="mt-1 inline-block rounded-md bg-[--accent-soft] px-2 py-0.5 text-[11px] font-medium text-[--accent]"
            >
              Администратор
            </span>
          </div>
        </div>
        <button class="btn btn-ghost mt-4 text-red-400 hover:text-red-300" @click="handleLogout">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          Выйти
        </button>
      </div>

      <!-- Listening stats: skeleton -->
      <div v-if="statsLoading" class="card p-5">
        <div class="skeleton mb-4 h-4 w-48 rounded" />
        <div class="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
          <div v-for="i in 4" :key="i">
            <div class="skeleton mb-2 h-3 w-16 rounded" />
            <div class="skeleton h-7 w-14 rounded" />
          </div>
        </div>
      </div>

      <!-- Listening stats -->
      <div v-else-if="sessionStats" class="card p-5">
        <h3 class="section-label mb-4">Статистика прослушивания</h3>
        <div class="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
          <div>
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">Всего часов</p>
            <p class="text-[22px] leading-none font-bold tracking-tight text-[--t1]">
              {{ sessionStats.total_hours.toFixed(1) }}
            </p>
          </div>
          <div>
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">Сегодня</p>
            <p class="text-[22px] leading-none font-bold tracking-tight text-[--t1]">
              {{ sessionStats.today_min }}<span class="ml-0.5 text-[12px] text-[--t3]">мин</span>
            </p>
          </div>
          <div>
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">За неделю</p>
            <p class="text-[22px] leading-none font-bold tracking-tight text-[--t1]">
              {{ sessionStats.week_hours.toFixed(1) }}<span class="ml-0.5 text-[12px] text-[--t3]">ч</span>
            </p>
          </div>
          <div v-if="sessionStats.peak_hour !== null">
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">Пик активности</p>
            <p class="gradient-text text-[22px] leading-none font-bold tracking-tight">
              {{ sessionStats.peak_hour }}:00
            </p>
          </div>
        </div>
      </div>

      <!-- Downloads (native only) -->
      <div v-if="dl.isNative.value" class="card p-5">
        <h3 class="section-label mb-4">
          <span class="flex items-center gap-2">
            <IconDownload :size="16" />
            Загрузки
          </span>
        </h3>

        <div v-if="dl.downloadedBooks.value.length" class="space-y-2">
          <div
            v-for="b in dl.downloadedBooks.value"
            :key="b.bookId"
            class="flex items-center justify-between gap-3 rounded-xl bg-white/[0.03] px-3.5 py-3"
          >
            <div class="min-w-0 flex-1">
              <p class="truncate text-[13px] font-medium text-[--t1]">{{ b.title }}</p>
              <p class="text-[11px] text-[--t3]">
                {{ b.tracks.length }} {{ plural(b.tracks.length, 'трек', 'трека', 'треков') }} ·
                {{ fmtSize(b.totalSize) }}
              </p>
            </div>
            <button
              class="shrink-0 rounded-full p-2 text-[--t3] transition-colors hover:bg-red-500/15 hover:text-red-400"
              title="Удалить"
              @click="dl.deleteBook(b.bookId)"
            >
              <IconTrash :size="14" />
            </button>
          </div>
          <p class="pt-1 text-[12px] text-[--t3]">
            Всего: <span class="font-semibold text-[--t2]">{{ fmtSize(dl.totalDownloadedSize.value) }}</span>
          </p>
          <button
            v-if="dl.downloadedBooks.value.length > 1"
            class="btn btn-ghost mt-2 text-red-400 hover:text-red-300"
            @click="dl.deleteAllBooks()"
          >
            <IconTrash :size="14" />
            Удалить все загрузки
          </button>
        </div>

        <p v-else class="text-[12px] text-[--t3]">Нет скачанных книг</p>
      </div>

      <!-- Listening Streak -->
      <div class="card p-5">
        <h3 class="section-label mb-4">Серия прослушивания</h3>
        <div class="flex items-center gap-6">
          <div class="text-center">
            <p
              class="text-[32px] leading-none font-bold tracking-tight"
              :class="streak.current > 0 ? 'text-[--accent]' : 'text-[--t3]'"
            >
              {{ streak.current }}
            </p>
            <p class="mt-1 text-[11px] font-semibold text-[--t3]">
              {{ plural(streak.current, 'день', 'дня', 'дней') }} подряд
            </p>
          </div>
          <div
            class="h-10 w-px"
            style="background: var(--border)"
          />
          <div class="text-center">
            <p class="text-[22px] leading-none font-bold tracking-tight text-[--t2]">
              {{ streak.best }}
            </p>
            <p class="mt-1 text-[11px] font-semibold text-[--t3]">лучшая серия</p>
          </div>
        </div>
      </div>

      <!-- Playback Preferences -->
      <div class="card p-5">
        <h3 class="section-label mb-4">Воспроизведение</h3>

        <div class="space-y-5">
          <!-- Default playback speed -->
          <div>
            <p class="mb-2.5 text-[12px] font-semibold text-[--t3]">Скорость по умолчанию</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="s in speeds"
                :key="s"
                class="rounded-lg px-3 py-1.5 text-[13px] font-semibold transition-colors"
                :class="
                  playbackSpeed === s
                    ? 'bg-[--accent] text-white'
                    : 'bg-white/[0.06] text-[--t2] hover:bg-white/[0.1]'
                "
                @click="setSpeed(s)"
              >
                {{ s }}x
              </button>
            </div>
          </div>

          <!-- Yearly goal -->
          <div>
            <p class="mb-2.5 text-[12px] font-semibold text-[--t3]">Годовая цель (книг)</p>
            <div class="flex items-center gap-3">
              <input
                v-model.number="yearlyGoal"
                type="range"
                min="1"
                max="100"
                class="flex-1 accent-[--accent]"
                @change="saveGoal"
              />
              <span class="min-w-[2.5rem] text-center text-[16px] font-bold text-[--t1]">
                {{ yearlyGoal }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Storage & Cache -->
      <div class="card p-5">
        <h3 class="section-label mb-4">
          <span class="flex items-center gap-2">
            <IconHardDrive :size="16" />
            Хранилище
          </span>
        </h3>
        <div class="flex flex-wrap gap-x-8 gap-y-3">
          <div v-if="dl.isNative.value">
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">Скачанные</p>
            <p class="text-[18px] leading-none font-bold text-[--t1]">{{ fmtSize(dl.totalDownloadedSize.value) }}</p>
          </div>
          <div>
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">Локальные книги</p>
            <p class="text-[18px] leading-none font-bold text-[--t1]">{{ localBooks.length }}</p>
          </div>
          <div>
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">Кэш</p>
            <p class="text-[18px] leading-none font-bold text-[--t1]">{{ fmtSize(cacheBytes) }}</p>
          </div>
        </div>
        <button v-if="cacheBytes > 0" class="btn btn-ghost mt-4" @click="clearCache">
          <IconTrash :size="14" />
          Очистить кэш
        </button>
      </div>

      <!-- About -->
      <div class="card p-5">
        <h3 class="section-label mb-4">О приложении</h3>
        <div class="space-y-2 text-[13px]">
          <div class="flex justify-between">
            <span class="text-[--t3]">Версия</span>
            <span class="font-medium text-[--t2]">2.0.0</span>
          </div>
          <div class="flex justify-between">
            <span class="text-[--t3]">Книг в каталоге</span>
            <span class="font-medium text-[--t2]">343</span>
          </div>
          <div class="flex justify-between">
            <span class="text-[--t3]">Платформа</span>
            <span class="font-medium text-[--t2]">Web</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
