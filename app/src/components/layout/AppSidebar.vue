<script setup lang="ts">
import { useRoute } from 'vue-router'
import {
  IconHome,
  IconLibrary,
  IconQueue,
  IconHistory,
  IconChart,
  IconSettings,
  IconMenu,
  IconX,
} from '../shared/icons'

defineProps<{ collapsed: boolean }>()
const emit = defineEmits<{ 'update:collapsed': [val: boolean] }>()
const route = useRoute()

const links = [
  { path: '/', label: 'Дашборд', icon: IconHome },
  { path: '/library', label: 'Библиотека', icon: IconLibrary },
  { path: '/queue', label: 'Очередь', icon: IconQueue },
  { path: '/history', label: 'История', icon: IconHistory },
  { path: '/analytics', label: 'Аналитика', icon: IconChart },
  { path: '/settings', label: 'Настройки', icon: IconSettings },
]

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}
</script>

<template>
  <aside
    class="fixed top-0 left-0 z-40 flex h-screen flex-col transition-all duration-300"
    :class="collapsed ? 'w-16' : 'w-56'"
    style="
      background: linear-gradient(180deg, rgba(14, 14, 22, 0.97) 0%, rgba(7, 7, 14, 0.99) 100%);
      backdrop-filter: blur(20px);
      border-right: 1px solid var(--border);
    "
  >
    <div class="flex h-16 items-center gap-3 px-4">
      <button
        class="flex cursor-pointer items-center rounded-xl border-0 bg-transparent p-1.5 text-[--t3] transition-colors hover:text-[--t2]"
        :aria-label="collapsed ? 'Развернуть' : 'Свернуть'"
        @click="emit('update:collapsed', !collapsed)"
      >
        <component :is="collapsed ? IconMenu : IconX" :size="18" />
      </button>
      <div v-if="!collapsed" class="flex items-center gap-2.5">
        <img src="/logo.png" alt="Leerio" class="h-7 w-7 rounded-lg object-contain" />
        <span class="text-[14px] font-bold tracking-tight text-[--t1]">Leerio</span>
      </div>
    </div>

    <nav class="flex flex-1 flex-col gap-0.5 px-2.5 py-3">
      <router-link
        v-for="link in links"
        :key="link.path"
        :to="link.path"
        class="group relative flex items-center gap-3 rounded-xl px-3 py-2.5 no-underline transition-all duration-200"
        :class="isActive(link.path) ? 'text-white' : 'text-[--t3] hover:bg-white/[0.03] hover:text-[--t2]'"
      >
        <span
          v-if="isActive(link.path)"
          class="absolute inset-0 rounded-xl"
          style="background: var(--accent-soft); box-shadow: 0 0 24px rgba(232, 146, 58, 0.06)"
        />
        <span
          v-if="isActive(link.path)"
          class="absolute top-1/2 left-0 h-4 w-[3px] -translate-y-1/2 rounded-r-full"
          style="background: var(--accent)"
        />
        <span class="relative flex w-5 flex-shrink-0 items-center justify-center">
          <component :is="link.icon" :size="18" />
        </span>
        <span v-if="!collapsed" class="relative text-[13px]" :class="isActive(link.path) ? 'font-semibold' : ''">{{
          link.label
        }}</span>
      </router-link>
    </nav>

    <div v-if="!collapsed" class="px-5 py-4 text-[11px] text-[--t3] opacity-30">v1.0</div>
  </aside>
</template>
