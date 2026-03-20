<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed, onErrorCaptured } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppSidebar from './components/layout/AppSidebar.vue'
import BottomNav from './components/layout/BottomNav.vue'
import GlobalSearch from './components/layout/GlobalSearch.vue'
import AppToast from './components/layout/AppToast.vue'
import MiniPlayer from './components/player/MiniPlayer.vue'
import ScrollToTop from './components/shared/ScrollToTop.vue'
import FullscreenPlayer from './components/player/FullscreenPlayer.vue'
import { usePlayer } from './composables/usePlayer'
import { useDownloads } from './composables/useDownloads'
import { useAuth } from './composables/useAuth'
import { useNetwork } from './composables/useNetwork'
import { useCategories } from './composables/useCategories'
import { useSync } from './composables/useSync'
import { IconWifiOff, IconX } from './components/shared/icons'
import { STORAGE } from './constants/storage'

const { t } = useI18n()
const sidebarCollapsed = ref(false)
const apkBannerDismissed = ref(localStorage.getItem(STORAGE.APK_DISMISSED) === '1')
const player = usePlayer()
const { isPlayerVisible } = player
const downloads = useDownloads()
const { loading: authLoading } = useAuth()
const { isOnline } = useNetwork()
const { load: loadCategories } = useCategories()
useSync()
const route = useRoute()

const isMobileWeb = computed(() => !downloads.isNative.value && /Android|iPhone|iPad|iPod/i.test(navigator.userAgent))
const showApkBanner = computed(() => isMobileWeb.value && !apkBannerDismissed.value)
function dismissApkBanner() {
  apkBannerDismissed.value = true
  localStorage.setItem(STORAGE.APK_DISMISSED, '1')
}

const isLoginPage = computed(() => route.name === 'login')
const isWelcomePage = computed(() => route.name === 'welcome')
const isPublicPage = computed(() => !!route.meta.public)
const showApp = computed(() => !authLoading.value && !isLoginPage.value && !isWelcomePage.value)

function onKeydown(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement)?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable) return
  if (!player.currentBook.value) return

  switch (e.code) {
    case 'Space':
      e.preventDefault()
      player.togglePlay()
      break
    case 'ArrowRight':
      if (e.shiftKey) {
        player.nextTrack()
      } else {
        player.skipForward()
      }
      break
    case 'ArrowLeft':
      if (e.shiftKey) {
        player.prevTrack()
      } else {
        player.skipBackward()
      }
      break
  }
}

const appError = ref(false)
const appKey = ref(0)

function retryApp() {
  appError.value = false
  appKey.value++
}

onErrorCaptured((err) => {
  console.error('[App] Uncaught component error:', err)
  appError.value = true
  return false
})

// Auto-resume last played book (instant resume — 0 clicks)
let autoResumed = false
watch(
  () => authLoading.value,
  (loading) => {
    if (loading || autoResumed || player.currentBook.value) return
    autoResumed = true
    try {
      const raw = localStorage.getItem(STORAGE.LAST_PLAYED)
      if (!raw) return
      const { id } = JSON.parse(raw) as { id: string }
      if (!id) return
      import('./api').then(({ api }) => {
        api
          .getBook(id)
          .then((book) => {
            if (player.currentBook.value) return // user already started something
            if (route.name === 'login') return // don't auto-resume on login page
            player.loadBook(book)
            player.closeFullscreen() // show MiniPlayer, not fullscreen
          })
          .catch(() => {
            // Book deleted or offline — clear last played so we don't retry on next load
            try { localStorage.removeItem(STORAGE.LAST_PLAYED) } catch { /* ignore */ }
          })
      })
    } catch {
      // corrupted localStorage
    }
  },
  { immediate: true },
)

onMounted(() => {
  downloads.init()
  loadCategories()
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <!-- Error boundary fallback -->
  <div
    v-if="appError"
    class="flex min-h-dvh min-h-screen flex-col items-center justify-center gap-4"
    style="background: var(--bg)"
  >
    <p class="text-[16px] font-semibold text-[--t1]">{{ t('common.errorOccurred') }}</p>
    <button
      class="rounded-lg px-4 py-2 text-[13px] font-semibold text-white"
      style="background: var(--gradient-accent)"
      @click="retryApp"
    >
      {{ t('common.retry') }}
    </button>
  </div>

  <!-- Auth loading spinner (skip for public pages) -->
  <div
    v-if="authLoading && !isLoginPage && !isPublicPage"
    class="flex min-h-dvh min-h-screen items-center justify-center"
    style="background: var(--bg)"
  >
    <div class="text-center">
      <div class="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-[--t3] border-t-[--accent]" />
      <p class="text-[13px] text-[--t3]">{{ t('common.loading') }}</p>
    </div>
  </div>

  <!-- Login / Welcome page (no sidebar/nav) -->
  <router-view v-else-if="isLoginPage || isWelcomePage" />

  <!-- App layout -->
  <div v-else-if="showApp" :key="appKey" class="flex min-h-dvh min-h-screen">
    <AppSidebar v-model:collapsed="sidebarCollapsed" class="hidden md:flex" />
    <main
      class="flex-1 overflow-y-auto scroll-smooth transition-all duration-300"
      :class="[sidebarCollapsed ? 'md:ml-16' : 'md:ml-60']"
    >
      <!-- Global search header (desktop) -->
      <div
        class="sticky top-0 z-30 hidden items-center justify-end px-8 py-3 md:flex"
        style="background: rgba(11, 11, 15, 0.8); backdrop-filter: blur(12px)"
      >
        <GlobalSearch />
      </div>

      <!-- Mobile search -->
      <div class="px-4 pt-3 md:hidden">
        <GlobalSearch />
      </div>

      <!-- Offline banner -->
      <transition name="toast">
        <div
          v-if="!isOnline"
          class="flex items-center justify-center gap-2 px-4 py-1.5 text-[12px] font-medium text-amber-200"
          style="background: rgba(217, 119, 6, 0.15); border-bottom: 1px solid rgba(217, 119, 6, 0.2)"
        >
          <IconWifiOff :size="14" />
          {{ t('common.offlineMsg') }}
        </div>
      </transition>

      <!-- APK install banner (mobile web only) -->
      <div
        v-if="showApkBanner"
        class="flex items-center gap-3 px-4 py-2.5"
        style="background: rgba(232, 146, 58, 0.1); border-bottom: 1px solid rgba(232, 146, 58, 0.15)"
      >
        <img src="/logo.png" alt="" class="h-8 w-8 rounded-lg" />
        <div class="min-w-0 flex-1">
          <p class="text-[12px] font-semibold text-[--t1]">{{ t('book.installApp') }}</p>
          <p class="text-[10px] text-[--t3]">{{ t('book.installAppHint') }}</p>
        </div>
        <a
          href="https://github.com/librevlad/leerio/releases/download/latest-apk/leerio.apk"
          class="shrink-0 rounded-lg border-0 px-3 py-1.5 text-[12px] font-bold text-white no-underline"
          style="background: var(--gradient-accent)"
        >
          APK
        </a>
        <button
          class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-0 bg-transparent text-[--t3] hover:text-[--t1]"
          @click="dismissApkBanner"
        >
          <IconX :size="14" />
        </button>
      </div>

      <div
        class="mx-auto px-4 py-5 md:px-8 md:py-8 md:pb-8"
        style="max-width: 1400px"
        :class="isPlayerVisible ? 'mobile-bottom-pad-player' : 'mobile-bottom-pad'"
      >
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
    <MiniPlayer />
    <Teleport to="body">
      <FullscreenPlayer />
    </Teleport>
    <BottomNav />
    <ScrollToTop />
    <AppToast />
  </div>
</template>
