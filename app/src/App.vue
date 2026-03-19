<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, onErrorCaptured } from 'vue'
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
import { IconWifiOff } from './components/shared/icons'

const { t } = useI18n()
const sidebarCollapsed = ref(false)
const player = usePlayer()
const { isPlayerVisible } = player
const downloads = useDownloads()
const { loading: authLoading } = useAuth()
const { isOnline } = useNetwork()
const { load: loadCategories } = useCategories()
useSync()
const route = useRoute()

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
