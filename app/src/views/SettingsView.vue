<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useDownloads } from '../composables/useDownloads'
import { useLocalBooks } from '../composables/useLocalBooks'
import { useOfflineCache } from '../composables/useOfflineCache'
import { useAuth } from '../composables/useAuth'
import type { SessionStats } from '../types'
import { IconTrash, IconDownload, IconHardDrive, IconLogout } from '../components/shared/icons'
import { useLocale } from '../composables/useLocale'
import { formatSize } from '../utils/format'
import { version } from '../../package.json'

const router = useRouter()
const { t } = useI18n()
const { currentLocale, setLocale, LOCALES } = useLocale()
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
const totalBooks = ref<number | null>(null)

const speeds = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]

onMounted(async () => {
  const [, settings, streakData, dash] = await Promise.allSettled([
    api.getSessionStats(30).then((s) => (sessionStats.value = s)),
    api.getUserSettings(),
    api.getStreak(),
    api.getDashboard(),
  ])
  if (settings.status === 'fulfilled') {
    yearlyGoal.value = settings.value.yearly_goal
    playbackSpeed.value = settings.value.playback_speed
  }
  if (streakData.status === 'fulfilled') {
    streak.value = streakData.value
  }
  if (dash.status === 'fulfilled') {
    totalBooks.value = dash.value.total_books
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
  return formatSize(bytes, t)
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
    <h1 class="page-title mb-8">{{ t('settings.title') }}</h1>

    <div class="max-w-2xl space-y-5">
      <!-- Profile -->
      <div class="card p-5">
        <h3 class="section-label mb-4">{{ t('settings.profile') }}</h3>
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
              {{ t('settings.admin') }}
            </span>
          </div>
        </div>
        <button class="btn btn-ghost mt-4 text-red-400 hover:text-red-300" @click="handleLogout">
          <IconLogout :size="14" />
          {{ t('settings.logout') }}
        </button>
      </div>

      <!-- Language -->
      <div class="card p-5">
        <h3 class="section-label mb-4">{{ t('settings.language') }}</h3>
        <div class="grid grid-cols-3 gap-2">
          <button
            v-for="locale in LOCALES"
            :key="locale.code"
            class="relative flex flex-col items-center gap-1.5 rounded-xl px-3 py-3.5 text-[13px] font-semibold transition-all duration-200"
            :class="
              currentLocale === locale.code
                ? 'bg-[--accent] text-white shadow-[0_0_20px_rgba(255,138,0,0.25)]'
                : 'bg-white/[0.04] text-[--t2] hover:bg-white/[0.08] hover:text-[--t1]'
            "
            @click="setLocale(locale.code)"
          >
            <span class="text-[22px] leading-none">{{ locale.flag }}</span>
            <span class="text-[12px] font-semibold">{{ locale.label }}</span>
            <span
              v-if="currentLocale === locale.code"
              class="absolute top-2 right-2 h-1.5 w-1.5 rounded-full bg-white/60"
            />
          </button>
        </div>
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
        <h3 class="section-label mb-4">{{ t('settings.statsTitle') }}</h3>
        <div class="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
          <div>
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">{{ t('settings.statTotalHours') }}</p>
            <p class="text-[22px] leading-none font-bold tracking-tight text-[--t1]">
              {{ sessionStats.total_hours.toFixed(1) }}
            </p>
          </div>
          <div>
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">{{ t('settings.statToday') }}</p>
            <p class="text-[22px] leading-none font-bold tracking-tight text-[--t1]">
              {{ sessionStats.today_min
              }}<span class="ml-0.5 text-[12px] text-[--t3]">{{ t('settings.unitMin') }}</span>
            </p>
          </div>
          <div>
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">{{ t('settings.statWeek') }}</p>
            <p class="text-[22px] leading-none font-bold tracking-tight text-[--t1]">
              {{ sessionStats.week_hours.toFixed(1)
              }}<span class="ml-0.5 text-[12px] text-[--t3]">{{ t('settings.unitH') }}</span>
            </p>
          </div>
          <div v-if="sessionStats.peak_hour !== null">
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">{{ t('settings.statPeak') }}</p>
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
            {{ t('settings.downloads') }}
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
                {{ b.tracks.length }} {{ t('plural.track', b.tracks.length) }} ·
                {{ fmtSize(b.totalSize) }}
              </p>
            </div>
            <button
              class="shrink-0 rounded-full p-2 text-[--t3] transition-colors hover:bg-red-500/15 hover:text-red-400"
              :title="t('common.delete')"
              @click="dl.deleteBook(b.bookId)"
            >
              <IconTrash :size="14" />
            </button>
          </div>
          <p class="pt-1 text-[12px] text-[--t3]">
            {{ t('settings.totalSize') }}:
            <span class="font-semibold text-[--t2]">{{ fmtSize(dl.totalDownloadedSize.value) }}</span>
          </p>
          <button
            v-if="dl.downloadedBooks.value.length > 1"
            class="btn btn-ghost mt-2 text-red-400 hover:text-red-300"
            @click="dl.deleteAllBooks()"
          >
            <IconTrash :size="14" />
            {{ t('settings.deleteAllDownloads') }}
          </button>
        </div>

        <p v-else class="text-[12px] text-[--t3]">{{ t('settings.noDownloads') }}</p>
      </div>

      <!-- Listening Streak -->
      <div class="card p-5">
        <h3 class="section-label mb-4">{{ t('settings.streakTitle') }}</h3>
        <div class="flex items-center gap-6">
          <div class="text-center">
            <p
              class="text-[32px] leading-none font-bold tracking-tight"
              :class="streak.current > 0 ? 'text-[--accent]' : 'text-[--t3]'"
            >
              {{ streak.current }}
            </p>
            <p class="mt-1 text-[11px] font-semibold text-[--t3]">
              {{ t('plural.day', streak.current) }}
            </p>
          </div>
          <div class="h-10 w-px" style="background: var(--border)" />
          <div class="text-center">
            <p class="text-[22px] leading-none font-bold tracking-tight text-[--t2]">
              {{ streak.best }}
            </p>
            <p class="mt-1 text-[11px] font-semibold text-[--t3]">{{ t('settings.streakBest') }}</p>
          </div>
        </div>
      </div>

      <!-- Playback Preferences -->
      <div class="card p-5">
        <h3 class="section-label mb-4">{{ t('settings.playback') }}</h3>

        <div class="space-y-5">
          <!-- Default playback speed -->
          <div>
            <p class="mb-2.5 text-[12px] font-semibold text-[--t3]">{{ t('settings.defaultSpeed') }}</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="s in speeds"
                :key="s"
                class="rounded-lg px-3 py-1.5 text-[13px] font-semibold transition-colors"
                :class="
                  playbackSpeed === s ? 'bg-[--accent] text-white' : 'bg-white/[0.06] text-[--t2] hover:bg-white/[0.1]'
                "
                @click="setSpeed(s)"
              >
                {{ s }}x
              </button>
            </div>
          </div>

          <!-- Yearly goal -->
          <div>
            <p class="mb-2.5 text-[12px] font-semibold text-[--t3]">{{ t('settings.yearlyGoal') }}</p>
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
            {{ t('settings.storage') }}
          </span>
        </h3>
        <div class="flex flex-wrap gap-x-8 gap-y-3">
          <div v-if="dl.isNative.value">
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">{{ t('settings.storageDownloaded') }}</p>
            <p class="text-[18px] leading-none font-bold text-[--t1]">{{ fmtSize(dl.totalDownloadedSize.value) }}</p>
          </div>
          <div>
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">{{ t('settings.storageLocal') }}</p>
            <p class="text-[18px] leading-none font-bold text-[--t1]">{{ localBooks.length }}</p>
          </div>
          <div>
            <p class="mb-1 text-[11px] font-semibold text-[--t3]">{{ t('settings.storageCache') }}</p>
            <p class="text-[18px] leading-none font-bold text-[--t1]">{{ fmtSize(cacheBytes) }}</p>
          </div>
        </div>
        <button v-if="cacheBytes > 0" class="btn btn-ghost mt-4" @click="clearCache">
          <IconTrash :size="14" />
          {{ t('settings.clearCache') }}
        </button>
      </div>

      <!-- Keyboard Shortcuts -->
      <div class="card p-5">
        <h3 class="section-label mb-4">{{ t('settings.shortcuts') }}</h3>
        <div class="space-y-2 text-[13px]">
          <div class="flex items-center justify-between">
            <span class="text-[--t3]">{{ t('settings.shortcutPlayPause') }}</span>
            <kbd class="rounded bg-white/[0.06] px-2 py-0.5 font-mono text-[11px] text-[--t2]">Space</kbd>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-[--t3]">{{ t('settings.shortcutForward') }}</span>
            <kbd class="rounded bg-white/[0.06] px-2 py-0.5 font-mono text-[11px] text-[--t2]">&rarr;</kbd>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-[--t3]">{{ t('settings.shortcutBack') }}</span>
            <kbd class="rounded bg-white/[0.06] px-2 py-0.5 font-mono text-[11px] text-[--t2]">&larr;</kbd>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-[--t3]">{{ t('settings.shortcutNext') }}</span>
            <kbd class="rounded bg-white/[0.06] px-2 py-0.5 font-mono text-[11px] text-[--t2]">Shift + &rarr;</kbd>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-[--t3]">{{ t('settings.shortcutPrev') }}</span>
            <kbd class="rounded bg-white/[0.06] px-2 py-0.5 font-mono text-[11px] text-[--t2]">Shift + &larr;</kbd>
          </div>
        </div>
      </div>

      <!-- About -->
      <div class="card p-5">
        <h3 class="section-label mb-4">{{ t('settings.about') }}</h3>
        <div class="space-y-2 text-[13px]">
          <div class="flex justify-between">
            <span class="text-[--t3]">{{ t('settings.aboutVersion') }}</span>
            <span class="font-medium text-[--t2]">{{ version }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-[--t3]">{{ t('settings.aboutBooks') }}</span>
            <span class="font-medium text-[--t2]">{{ totalBooks ?? '—' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-[--t3]">{{ t('settings.aboutPlatform') }}</span>
            <span class="font-medium text-[--t2]">Web</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
