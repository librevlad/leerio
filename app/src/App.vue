<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './components/layout/AppSidebar.vue'
import BottomNav from './components/layout/BottomNav.vue'
import AppToast from './components/layout/AppToast.vue'
import MiniPlayer from './components/player/MiniPlayer.vue'
import FullscreenPlayer from './components/player/FullscreenPlayer.vue'
import { usePlayer } from './composables/usePlayer'
import { useDownloads } from './composables/useDownloads'
import { useAuth } from './composables/useAuth'
import { useNetwork } from './composables/useNetwork'
import { IconWifiOff } from './components/shared/icons'

const sidebarCollapsed = ref(false)
const { isPlayerVisible } = usePlayer()
const downloads = useDownloads()
const { loading: authLoading, isLoggedIn } = useAuth()
const { isOnline } = useNetwork()
const route = useRoute()

const isLoginPage = computed(() => route.name === 'login')
const showApp = computed(() => !authLoading.value && isLoggedIn.value && !isLoginPage.value)

onMounted(() => {
  downloads.init()
})
</script>

<template>
  <!-- Auth loading spinner -->
  <div
    v-if="authLoading && !isLoginPage"
    class="flex min-h-dvh min-h-screen items-center justify-center"
    style="background: var(--bg)"
  >
    <div class="text-center">
      <div class="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-[--t3] border-t-[--accent]" />
      <p class="text-[13px] text-[--t3]">Загрузка...</p>
    </div>
  </div>

  <!-- Login page (no sidebar/nav) -->
  <router-view v-else-if="isLoginPage" />

  <!-- Authenticated app layout -->
  <div v-else-if="showApp" class="flex min-h-dvh min-h-screen">
    <AppSidebar v-model:collapsed="sidebarCollapsed" class="hidden md:flex" />
    <main
      class="flex-1 overflow-y-auto scroll-smooth transition-all duration-300"
      :class="[sidebarCollapsed ? 'md:ml-16' : 'md:ml-56']"
    >
      <!-- Offline banner -->
      <transition name="toast">
        <div
          v-if="!isOnline"
          class="flex items-center justify-center gap-2 px-4 py-1.5 text-[12px] font-medium text-amber-200"
          style="background: rgba(217, 119, 6, 0.15); border-bottom: 1px solid rgba(217, 119, 6, 0.2)"
        >
          <IconWifiOff :size="14" />
          Офлайн — доступны только скачанные книги
        </div>
      </transition>

      <div
        class="mx-auto max-w-7xl px-4 py-5 md:px-8 md:py-8 md:pb-8"
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
    <AppToast />
  </div>
</template>
