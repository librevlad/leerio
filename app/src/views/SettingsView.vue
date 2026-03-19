<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { STORAGE } from '../constants/storage'
import { useDownloads } from '../composables/useDownloads'
import { useLocalBooks } from '../composables/useLocalBooks'
import { useOfflineCache } from '../composables/useOfflineCache'
import { useAuth } from '../composables/useAuth'
import type { SessionStats } from '../types'
import { IconTrash, IconDownload } from '../components/shared/icons'
import { useLocale } from '../composables/useLocale'
import { formatSize } from '../utils/format'
import { useCountUp } from '../composables/useCountUp'
import PaywallModal from '../components/shared/PaywallModal.vue'
import { PLAYBACK_SPEEDS } from '../composables/usePlayer'
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
const showShortcuts = ref(false)
const showPaywall = ref(false)

const speeds = PLAYBACK_SPEEDS

// Count-up animations for stats
const totalHours = computed(() => (sessionStats.value ? sessionStats.value.total_hours : null))
const todayMin = computed(() => (sessionStats.value ? sessionStats.value.today_min : null))
const streakCurrent = computed(() => streak.value.current)
const animHours = useCountUp(totalHours, { duration: 800, decimals: 1 })
const animToday = useCountUp(todayMin, { duration: 600 })
const animStreak = useCountUp(streakCurrent, { duration: 500 })

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
  localStorage.setItem(STORAGE.PLAYBACK_RATE, String(speed))
  await api.updateUserSettings({ playback_speed: speed }).catch(() => {})
}

function fmtSize(bytes: number): string {
  return formatSize(bytes, t)
}

function clearCache() {
  cache.clear()
  cacheBytes.value = 0
}

const loggingOut = ref(false)

async function handleLogout() {
  if (loggingOut.value) return
  loggingOut.value = true
  try {
    await logout()
    router.push('/login')
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <div>
    <h1 class="page-title mb-6">{{ t('settings.title') }}</h1>

    <!-- ── Profile Card with gradient border ─────────────────────── -->
    <div class="settings-profile mb-6">
      <!-- Guest prompt -->
      <div v-if="!user" class="flex items-center gap-3.5">
        <div
          class="flex h-12 w-12 shrink-0 items-center justify-center rounded-[14px] text-[18px]"
          style="background: rgba(255, 255, 255, 0.06)"
        >
          👤
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-[14px] font-semibold text-[--t1]">{{ t('settings.guest') }}</p>
          <router-link to="/login" class="text-[12px] font-medium text-[--accent] no-underline hover:text-[--accent-2]">
            {{ t('settings.loginForSync') }}
          </router-link>
        </div>
      </div>
      <!-- Logged in user -->
      <div v-else class="flex items-center gap-3.5">
        <img
          v-if="user.picture"
          :src="user.picture"
          :alt="user.name"
          class="h-12 w-12 rounded-[14px] object-cover"
          referrerpolicy="no-referrer"
        />
        <div
          v-else
          class="flex h-12 w-12 shrink-0 items-center justify-center rounded-[14px] text-[18px] font-bold text-[--card]"
          style="background: var(--gradient-accent)"
        >
          {{ user.name?.charAt(0) || '?' }}
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <p class="text-[16px] font-bold text-[--t1]">{{ user.name }}</p>
            <span v-if="isAdmin" class="rounded bg-[--accent] px-1.5 py-0.5 text-[9px] font-bold text-[--bg]">
              ADMIN
            </span>
          </div>
          <p class="text-[12px] text-[--t2]">{{ user.email }}</p>
        </div>
      </div>

      <!-- Stats bar -->
      <div v-if="statsLoading" class="settings-stat-bar mt-4">
        <div v-for="i in 4" :key="i" class="settings-stat-cell">
          <div class="skeleton h-5 w-10 rounded" />
          <div class="skeleton mt-1 h-2.5 w-12 rounded" />
        </div>
      </div>
      <div v-else-if="sessionStats" class="settings-stat-bar mt-4">
        <div class="settings-stat-cell">
          <p class="settings-stat-num text-[--accent]">{{ animHours }}</p>
          <p class="settings-stat-label">{{ t('settings.unitH') }}</p>
        </div>
        <div class="settings-stat-cell">
          <p class="settings-stat-num">
            {{ animToday }}<span class="text-[11px] text-[--t3]">{{ t('settings.unitMin') }}</span>
          </p>
          <p class="settings-stat-label">{{ t('settings.statToday') }}</p>
        </div>
        <div class="settings-stat-cell">
          <p class="settings-stat-num">
            {{ totalBooks ?? 0 }}<span class="text-[12px] text-[--t3]">/{{ yearlyGoal }}</span>
          </p>
          <p class="settings-stat-label">{{ t('settings.yearlyGoal') }}</p>
        </div>
        <div class="settings-stat-cell">
          <p class="settings-stat-num">🔥 {{ animStreak }}</p>
          <p class="settings-stat-label">
            {{ t('plural.day', streak.current) }}
            <span v-if="streak.best > 0" class="hidden text-[--t3] sm:inline">
              · {{ t('settings.streakBest') }} {{ streak.best }}</span
            >
          </p>
        </div>
        <div v-if="sessionStats.peak_hour !== null" class="settings-stat-cell">
          <p class="settings-stat-num gradient-text">{{ sessionStats.peak_hour }}:00</p>
          <p class="settings-stat-label">{{ t('settings.statPeak') }}</p>
        </div>
      </div>
    </div>

    <!-- ── Settings groups (2-col on desktop) ─────────────────────── -->
    <div class="grid gap-4 md:grid-cols-2">
      <!-- LEFT column -->
      <div class="space-y-4">
        <!-- Playback -->
        <div>
          <p class="settings-group-label">{{ t('settings.playback') }}</p>
          <div class="settings-group">
            <div class="settings-row flex-wrap md:flex-nowrap">
              <span class="settings-row-label shrink-0">{{ t('settings.defaultSpeed') }}</span>
              <div class="flex flex-wrap gap-1.5 md:flex-nowrap">
                <button
                  v-for="s in speeds"
                  :key="s"
                  class="settings-speed-pill"
                  :class="playbackSpeed === s ? 'settings-speed-active' : 'settings-speed-inactive'"
                  @click="setSpeed(s)"
                >
                  {{ s }}x
                </button>
              </div>
            </div>
            <div class="settings-row">
              <span class="settings-row-label">{{ t('settings.yearlyGoal') }}</span>
              <div class="flex items-center gap-3">
                <input
                  v-model.number="yearlyGoal"
                  type="range"
                  min="1"
                  max="100"
                  class="w-36 accent-[--accent]"
                  @change="saveGoal"
                />
                <span class="text-[14px] font-bold text-[--accent]">{{ yearlyGoal }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Language -->
        <div>
          <p class="settings-group-label">{{ t('settings.language') }}</p>
          <div class="settings-group">
            <div class="settings-row">
              <span class="settings-row-label">{{ t('settings.language') }}</span>
              <div class="settings-segment">
                <button
                  v-for="locale in LOCALES"
                  :key="locale.code"
                  class="settings-segment-btn"
                  :class="currentLocale === locale.code ? 'settings-segment-active' : ''"
                  @click="setLocale(locale.code)"
                >
                  {{ locale.flag }} {{ locale.label }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Downloads (native only) -->
        <div v-if="dl.isNative.value">
          <p class="settings-group-label">
            <IconDownload :size="14" class="inline" />
            {{ t('settings.downloads') }}
          </p>
          <div class="settings-group">
            <div v-if="dl.downloadedBooks.value.length" class="space-y-0">
              <div v-for="b in dl.downloadedBooks.value" :key="b.bookId" class="settings-row">
                <div class="min-w-0 flex-1">
                  <p class="truncate text-[13px] font-medium text-[--t1]">{{ b.title }}</p>
                  <p class="text-[11px] text-[--t3]">
                    {{ b.tracks.length }} {{ t('plural.track', b.tracks.length) }} · {{ fmtSize(b.totalSize) }}
                  </p>
                </div>
                <button
                  class="shrink-0 rounded-full p-2 text-[--t3] transition-colors hover:bg-red-500/15 hover:text-red-400"
                  @click="dl.deleteBook(b.bookId)"
                >
                  <IconTrash :size="14" />
                </button>
              </div>
            </div>
            <div v-else class="settings-row">
              <span class="text-[12px] text-[--t3]">{{ t('settings.noDownloads') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- RIGHT column -->
      <div class="space-y-4">
        <!-- Data -->
        <div>
          <p class="settings-group-label">{{ t('settings.storage') }}</p>
          <div class="settings-group">
            <div class="settings-row">
              <span class="settings-row-label">{{ t('settings.storageCache') }}</span>
              <div class="flex items-center gap-2.5">
                <span class="text-[12px] text-[--t3]">{{ fmtSize(cacheBytes) }}</span>
                <button
                  v-if="cacheBytes > 0"
                  class="text-[12px] font-medium text-[--accent] transition-colors hover:text-[--accent-2]"
                  @click="clearCache"
                >
                  {{ t('settings.clearCache') }}
                </button>
              </div>
            </div>
            <div class="settings-row">
              <span class="settings-row-label">{{ t('settings.storageLocal') }}</span>
              <span class="text-[12px] text-[--t3]">{{ localBooks.length }}</span>
            </div>
          </div>
        </div>

        <!-- Shortcuts (collapsible) -->
        <div>
          <p class="settings-group-label">{{ t('settings.shortcuts') }}</p>
          <div class="settings-group">
            <button v-ripple class="settings-row w-full" @click="showShortcuts = !showShortcuts">
              <span class="settings-row-label">{{ t('settings.shortcuts') }}</span>
              <span class="text-[12px] text-[--t3] transition-transform" :class="showShortcuts ? 'rotate-90' : ''"
                >▸</span
              >
            </button>
            <template v-if="showShortcuts">
              <div class="settings-row">
                <span class="text-[12px] text-[--t3]">{{ t('settings.shortcutPlayPause') }}</span>
                <kbd class="settings-kbd">Space</kbd>
              </div>
              <div class="settings-row">
                <span class="text-[12px] text-[--t3]">{{ t('settings.shortcutForward') }}</span>
                <kbd class="settings-kbd">&rarr;</kbd>
              </div>
              <div class="settings-row">
                <span class="text-[12px] text-[--t3]">{{ t('settings.shortcutBack') }}</span>
                <kbd class="settings-kbd">&larr;</kbd>
              </div>
              <div class="settings-row">
                <span class="text-[12px] text-[--t3]">{{ t('settings.shortcutNext') }}</span>
                <kbd class="settings-kbd">Shift + &rarr;</kbd>
              </div>
              <div class="settings-row">
                <span class="text-[12px] text-[--t3]">{{ t('settings.shortcutPrev') }}</span>
                <kbd class="settings-kbd">Shift + &larr;</kbd>
              </div>
            </template>
          </div>
        </div>

        <!-- Plan -->
        <div v-if="user">
          <p class="settings-group-label">{{ t('settings.plan') }}</p>
          <div class="settings-group">
            <div class="settings-row">
              <span class="settings-row-label">{{ t('settings.currentPlan') }}</span>
              <span
                class="rounded px-2 py-0.5 text-[11px] font-bold"
                :class="user.plan === 'premium' ? 'bg-[--accent] text-[--bg]' : 'bg-white/[0.06] text-[--t2]'"
              >
                {{ user.plan === 'premium' ? 'Premium' : 'Free' }}
              </span>
            </div>
            <div v-if="user.plan !== 'premium'" class="settings-row">
              <span class="settings-row-label">{{ t('settings.booksCount') }}</span>
              <span class="text-[12px]" :class="(totalBooks ?? 0) >= 10 ? 'font-bold text-[--accent]' : 'text-[--t3]'"
                >{{ totalBooks ?? 0 }} / 10</span
              >
            </div>
            <div v-if="user.plan !== 'premium'" class="settings-row">
              <button
                v-ripple
                class="w-full rounded-lg py-2 text-[13px] font-semibold text-white"
                style="background: var(--gradient-accent)"
                @click="showPaywall = true"
              >
                {{ t('paywall.upgrade') }}
              </button>
            </div>
            <div v-else class="settings-row">
              <span class="text-[12px] text-emerald-400">{{ t('settings.unlimitedBooks') }}</span>
            </div>
          </div>
        </div>

        <!-- About (inline) -->
        <div>
          <p class="settings-group-label">{{ t('settings.about') }}</p>
          <div class="settings-group">
            <div class="settings-row">
              <span class="settings-row-label">{{ t('settings.aboutVersion') }}</span>
              <span class="text-[12px] text-[--t3]">{{ version }}</span>
            </div>
            <div class="settings-row">
              <span class="settings-row-label">{{ t('settings.aboutBooks') }}</span>
              <span class="text-[12px] text-[--t3]">{{ totalBooks ?? '—' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Logout ─────────────────────────────────────────────── -->
    <div class="mt-6 text-center">
      <button
        class="text-[13px] font-medium text-red-400 transition-colors hover:text-red-300 disabled:opacity-50"
        :disabled="loggingOut"
        @click="handleLogout"
      >
        {{ loggingOut ? '...' : t('settings.logout') }}
      </button>
    </div>

    <PaywallModal :open="showPaywall" @close="showPaywall = false" />
  </div>
</template>

<style scoped>
/* ── Profile card ────────────────────────────────────────────── */
.settings-profile {
  background: linear-gradient(135deg, rgba(255, 138, 0, 0.12), rgba(255, 138, 0, 0.02));
  border: 1px solid rgba(255, 138, 0, 0.2);
  border-radius: 16px;
  padding: 20px;
}

/* ── Stat bar ────────────────────────────────────────────────── */
.settings-stat-bar {
  display: flex;
  background: rgba(0, 0, 0, 0.25);
  border-radius: 12px;
  overflow: hidden;
}

.settings-stat-cell {
  flex: 1;
  padding: 12px 8px;
  text-align: center;
  border-right: 1px solid rgba(255, 255, 255, 0.05);
}

.settings-stat-cell:last-child {
  border-right: none;
}

.settings-stat-num {
  font-size: 18px;
  font-weight: 800;
  line-height: 1;
  color: var(--t1);
}

.settings-stat-label {
  font-size: 9px;
  color: var(--t3);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-top: 4px;
}

/* ── Settings groups (iOS-style rows) ────────────────────────── */
.settings-group-label {
  font-size: 10px;
  color: var(--t3);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 6px;
}

.settings-group {
  background: var(--card);
  border-radius: 14px;
  overflow: hidden;
}

.settings-row {
  padding: 13px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border);
  gap: 12px;
}

.settings-row:last-child {
  border-bottom: none;
}

.settings-row-label {
  font-size: 13px;
  color: var(--t1);
}

/* ── Speed pills ─────────────────────────────────────────────── */
.settings-speed-pill {
  padding: 6px 11px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.15s;
  cursor: pointer;
}

.settings-speed-pill:hover {
  transform: scale(1.05);
}

.settings-speed-active {
  background: var(--gradient-accent);
  color: var(--bg);
  box-shadow: 0 0 14px rgba(255, 138, 0, 0.25);
}

.settings-speed-inactive {
  background: rgba(255, 255, 255, 0.06);
  color: var(--t2);
}

.settings-speed-inactive:hover {
  background: rgba(255, 255, 255, 0.1);
}

/* ── Language segment ────────────────────────────────────────── */
.settings-segment {
  display: flex;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 10px;
  padding: 3px;
}

.settings-segment-btn {
  flex: 1;
  text-align: center;
  padding: 7px 10px;
  font-size: 12px;
  border-radius: 8px;
  color: var(--t3);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.settings-segment-btn:hover {
  color: var(--t2);
}

.settings-segment-active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}

/* ── Keyboard badge ──────────────────────────────────────────── */
.settings-kbd {
  display: inline-block;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 4px;
  padding: 2px 8px;
  font-family: ui-monospace, monospace;
  font-size: 11px;
  color: var(--t2);
}
</style>
