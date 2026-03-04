<script setup lang="ts">
import { useRoute } from 'vue-router'
import { IconHome, IconLibrary, IconQueue, IconHistory, IconSettings } from '../shared/icons'

const route = useRoute()

const tabs = [
  { path: '/', label: 'Главная', icon: IconHome },
  { path: '/library', label: 'Книги', icon: IconLibrary },
  { path: '/queue', label: 'Очередь', icon: IconQueue },
  { path: '/history', label: 'История', icon: IconHistory },
  { path: '/settings', label: 'Ещё', icon: IconSettings },
]

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}
</script>

<template>
  <nav
    class="fixed bottom-0 left-0 right-0 z-50 md:hidden safe-bottom"
    style="background: rgba(7,7,14,0.92); backdrop-filter: blur(24px) saturate(180%); border-top: 1px solid var(--border)"
  >
    <div class="flex items-stretch justify-around h-14">
      <router-link
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        class="flex flex-col items-center justify-center flex-1 gap-0.5 no-underline transition-colors duration-200 relative"
        :class="isActive(tab.path) ? 'text-[--accent-2]' : 'text-[--t3]'"
      >
        <span
          v-if="isActive(tab.path)"
          class="absolute -top-px left-1/2 -translate-x-1/2 w-5 h-0.5 rounded-full"
          style="background: var(--accent)"
        />
        <component :is="tab.icon" :size="20" />
        <span class="text-[10px] font-medium leading-none">{{ tab.label }}</span>
      </router-link>
    </div>
  </nav>
</template>
