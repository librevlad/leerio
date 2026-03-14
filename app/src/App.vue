<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
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
import { IconWifiOff } from './components/shared/icons'

const { t } = useI18n()
const sidebarCollapsed = ref(false)
const player = usePlayer()
const { isPlayerVisible } = player
const downloads = useDownloads()
const { loading: authLoading, isLoggedIn } = useAuth()
const { isOnline } = useNetwork()
const { load: loadCategories } = useCategories()
const route = useRoute()

const isLoginPage = computed(() => route.name === 'login')
const isPublicPage = computed(() => !!route.meta.public)
const showApp = computed(
  () => (!authLoading.value || isPublicPage.value) && (isLoggedIn.value || isPublicPage.value) && !isLoginPage.value,
)

// PWA install prompt
interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}
const deferredPrompt = ref<BeforeInstallPromptEvent | null>(null)
const showInstallBanner = ref(false)

function handleBeforeInstallPrompt(e: Event) {
  e.preventDefault()
  deferredPrompt.value = e
  if (!localStorage.getItem('pwa-install-dismissed')) {
    showInstallBanner.value = true
  }
}

async function installPwa() {
  if (!deferredPrompt.value) return
  deferredPrompt.value.prompt()
  const result = await deferredPrompt.value.userChoice
  if (result.outcome === 'accepted') {
    showInstallBanner.value = false
  }
  deferredPrompt.value = null
}

function dismissInstall() {
  showInstallBanner.value = false
  localStorage.setItem('pwa-install-dismissed', '1')
}

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

onMounted(() => {
  downloads.init()
  loadCategories()
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
})
</script>

<template>
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

  <!-- Login page (no sidebar/nav) -->
  <router-view v-else-if="isLoginPage" />

  <!-- Authenticated app layout -->
  <div v-else-if="showApp" class="flex min-h-dvh min-h-screen">
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

    <!-- PWA Install Banner -->
    <div
      v-if="showInstallBanner"
      class="fixed right-0 bottom-16 left-0 z-50 flex items-center justify-between gap-3 border-t border-white/10 px-4 py-3 backdrop-blur-xl md:bottom-4 md:left-auto md:right-4 md:w-80 md:rounded-xl md:border"
      style="background: var(--card)"
    >
      <div class="min-w-0">
        <p class="text-[13px] font-semibold text-[--t1]">{{ t('common.installTitle') }}</p>
        <p class="text-[11px] text-[--t3]">{{ t('common.installDesc') }}</p>
      </div>
      <div class="flex shrink-0 gap-2">
        <button class="rounded-lg px-3 py-1.5 text-[12px] text-[--t3]" @click="dismissInstall">{{ t('common.later') }}</button>
        <button class="rounded-lg px-3 py-1.5 text-[12px] font-semibold text-white" style="background: var(--gradient-accent)" @click="installPwa">{{ t('common.install') }}</button>
      </div>
    </div>
  </div>
</template>
