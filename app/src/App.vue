<script setup lang="ts">
import { ref, onMounted } from 'vue'
import AppSidebar from './components/layout/AppSidebar.vue'
import BottomNav from './components/layout/BottomNav.vue'
import AppToast from './components/layout/AppToast.vue'
import MiniPlayer from './components/player/MiniPlayer.vue'
import { usePlayer } from './composables/usePlayer'
import { useDownloads } from './composables/useDownloads'

const sidebarCollapsed = ref(false)
const { isPlayerVisible } = usePlayer()
const downloads = useDownloads()

onMounted(() => {
  downloads.init()
})
</script>

<template>
  <div class="flex min-h-screen min-h-dvh">
    <AppSidebar v-model:collapsed="sidebarCollapsed" class="hidden md:flex" />
    <main
      class="flex-1 transition-all duration-300 overflow-y-auto scroll-smooth"
      :class="[
        sidebarCollapsed ? 'md:ml-16' : 'md:ml-56',
      ]"
    >
      <div
        class="max-w-7xl mx-auto px-4 py-5 md:px-8 md:py-8 md:pb-8"
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
    <BottomNav />
    <AppToast />
  </div>
</template>
