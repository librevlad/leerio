<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IconHome, IconLibrary, IconFolder, IconMenu, IconUpload, IconHistory, IconSettings } from '../shared/icons'
import BottomSheet from './BottomSheet.vue'
import { usePlayer } from '../../composables/usePlayer'
import { useAuth } from '../../composables/useAuth'

const route = useRoute()
const router = useRouter()
const showMore = ref(false)
const { isPlayerVisible } = usePlayer()
const { isLoggedIn } = useAuth()

const authTabs = [
  { path: '/', label: 'Главная', icon: IconHome },
  { path: '/library', label: 'Каталог', icon: IconLibrary },
  { path: '/my-library', label: 'Моя', icon: IconFolder },
]

const guestTabs = [{ path: '/library', label: 'Каталог', icon: IconLibrary }]

const tabs = computed(() => (isLoggedIn.value ? authTabs : guestTabs))

const moreLinks = [
  { path: '/history', label: 'История', icon: IconHistory },
  { path: '/upload', label: 'Загрузить', icon: IconUpload },
  { path: '/settings', label: 'Настройки', icon: IconSettings },
]

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

const isMoreActive = computed(() => moreLinks.some((l) => isActive(l.path)))

function goTo(path: string) {
  showMore.value = false
  router.push(path)
}
</script>

<template>
  <nav
    class="safe-bottom fixed right-0 bottom-0 left-0 z-50 md:hidden"
    style="
      background: rgba(7, 7, 14, 0.92);
      backdrop-filter: blur(24px) saturate(180%);
      border-top: 1px solid var(--border);
    "
  >
    <div class="flex h-14 items-stretch justify-around">
      <router-link
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        class="relative flex flex-1 flex-col items-center justify-center gap-0.5 no-underline transition-colors duration-200"
        :class="isActive(tab.path) ? 'text-[--accent]' : 'text-[--t3]'"
      >
        <span class="relative">
          <component :is="tab.icon" :size="20" />
          <span
            v-if="tab.path === '/' && isPlayerVisible"
            class="absolute -top-0.5 -right-1 h-2 w-2 rounded-full bg-[--accent]"
            style="box-shadow: 0 0 6px rgba(232, 146, 58, 0.5)"
          />
        </span>
        <span class="text-[10px] leading-none font-medium">{{ tab.label }}</span>
      </router-link>

      <!-- More button (auth) -->
      <button
        v-if="isLoggedIn"
        class="relative flex flex-1 cursor-pointer flex-col items-center justify-center gap-0.5 border-0 bg-transparent transition-colors duration-200"
        :class="showMore || isMoreActive ? 'text-[--accent]' : 'text-[--t3]'"
        @click="showMore = !showMore"
      >
        <IconMenu :size="20" />
        <span class="text-[10px] leading-none font-medium">Ещё</span>
      </button>
      <!-- Login button (guest) -->
      <router-link
        v-else
        to="/login"
        class="relative flex flex-1 flex-col items-center justify-center gap-0.5 text-[--accent] no-underline"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
          <polyline points="10 17 15 12 10 7" />
          <line x1="15" y1="12" x2="3" y2="12" />
        </svg>
        <span class="text-[10px] leading-none font-medium">Войти</span>
      </router-link>
    </div>
  </nav>

  <BottomSheet :open="showMore" @close="showMore = false">
    <button
      v-for="link in moreLinks"
      :key="link.path"
      class="flex w-full cursor-pointer items-center gap-3.5 rounded-xl border-0 bg-transparent px-4 py-3 text-left transition-colors hover:bg-white/[0.04]"
      :class="isActive(link.path) ? 'text-[--accent]' : 'text-[--t2]'"
      @click="goTo(link.path)"
    >
      <component :is="link.icon" :size="20" />
      <span class="text-[14px] font-medium">{{ link.label }}</span>
    </button>
  </BottomSheet>
</template>
