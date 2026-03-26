<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { IconLibrary, IconMusic, IconSettings } from '../shared/icons'
import { useAuth } from '../../composables/useAuth'

const route = useRoute()
const { t } = useI18n()
const { isLoggedIn } = useAuth()

const tabs = computed(() => {
  const base: { path: string; label: string; icon: typeof IconLibrary }[] = [
    { path: '/library', label: t('nav.catalog'), icon: IconLibrary },
  ]
  if (isLoggedIn.value) {
    base.push({ path: '/my-library', label: t('nav.myLibrary'), icon: IconMusic })
  }
  base.push({ path: '/settings', label: t('nav.settings'), icon: IconSettings })
  return base
})

const isActive = (path: string) => route.path.startsWith(path)
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
        <component :is="tab.icon" :size="20" />
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
