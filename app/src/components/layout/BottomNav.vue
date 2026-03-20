<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { IconHome, IconLibrary, IconHistory, IconSettings } from '../shared/icons'
import { usePlayer } from '../../composables/usePlayer'
import { useAuth } from '../../composables/useAuth'

const route = useRoute()
const { t } = useI18n()
const { isPlayerVisible } = usePlayer()
const { isLoggedIn } = useAuth()

const authTabs = computed(() => [
  { path: '/', label: t('nav.home'), icon: IconHome },
  { path: '/library', label: t('nav.catalog'), icon: IconLibrary },
  { path: '/history', label: t('nav.history'), icon: IconHistory },
  { path: '/settings', label: t('nav.settings'), icon: IconSettings },
])

const guestTabs = computed(() => [{ path: '/library', label: t('nav.catalog'), icon: IconLibrary }])

const tabs = computed(() => (isLoggedIn.value ? authTabs.value : guestTabs.value))

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
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

      <!-- Login button (guest) -->
      <router-link
        v-if="!isLoggedIn"
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
        <span class="text-[10px] leading-none font-medium">{{ t('nav.login') }}</span>
      </router-link>
    </div>
  </nav>
</template>
