<script setup lang="ts">
import { useRoute } from 'vue-router'
import { IconHome, IconLibrary, IconSettings, IconSearch, IconFolder } from '../shared/icons'

const route = useRoute()

const tabs = [
  { path: '/', label: 'Главная', icon: IconHome },
  { path: '/library', label: 'Каталог', icon: IconLibrary },
  { path: '/my-library', label: 'Моя', icon: IconFolder },
  { path: '/discover', label: 'LibriVox', icon: IconSearch },
  { path: '/settings', label: 'Ещё', icon: IconSettings },
]

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
        :class="isActive(tab.path) ? 'text-[--accent-2]' : 'text-[--t3]'"
      >
        <span
          v-if="isActive(tab.path)"
          class="absolute -top-px left-1/2 h-0.5 w-5 -translate-x-1/2 rounded-full"
          style="background: var(--accent)"
        />
        <component :is="tab.icon" :size="20" />
        <span class="text-[10px] leading-none font-medium">{{ tab.label }}</span>
      </router-link>
    </div>
  </nav>
</template>
