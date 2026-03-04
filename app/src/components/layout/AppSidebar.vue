<script setup lang="ts">
import { useRoute } from 'vue-router'
import { IconHome, IconLibrary, IconQueue, IconHistory, IconChart, IconSettings, IconMenu, IconX } from '../shared/icons'

const props = defineProps<{ collapsed: boolean }>()
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
    class="fixed left-0 top-0 h-screen z-40 transition-all duration-300 flex flex-col"
    :class="collapsed ? 'w-16' : 'w-56'"
    style="background: linear-gradient(180deg, rgba(14,14,22,0.97) 0%, rgba(7,7,14,0.99) 100%); backdrop-filter: blur(20px); border-right: 1px solid var(--border)"
  >
    <div class="flex items-center h-16 px-4 gap-3">
      <button
        class="text-[--t3] hover:text-[--t2] transition-colors cursor-pointer bg-transparent border-0 p-1.5 flex items-center rounded-xl"
        :aria-label="collapsed ? 'Развернуть' : 'Свернуть'"
        @click="emit('update:collapsed', !collapsed)"
      >
        <component :is="collapsed ? IconMenu : IconX" :size="18" />
      </button>
      <div v-if="!collapsed" class="flex items-center gap-2.5">
        <img src="/logo.png" alt="Leerio" class="w-7 h-7 rounded-lg object-contain" />
        <span class="text-[14px] font-bold text-[--t1] tracking-tight">Leerio</span>
      </div>
    </div>

    <nav class="flex-1 py-3 flex flex-col gap-0.5 px-2.5">
      <router-link
        v-for="link in links"
        :key="link.path"
        :to="link.path"
        class="relative flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 no-underline group"
        :class="isActive(link.path)
          ? 'text-white'
          : 'text-[--t3] hover:text-[--t2] hover:bg-white/[0.03]'"
      >
        <span
          v-if="isActive(link.path)"
          class="absolute inset-0 rounded-xl"
          style="background: var(--accent-soft); box-shadow: 0 0 24px rgba(232,146,58,0.06)"
        />
        <span
          v-if="isActive(link.path)"
          class="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 rounded-r-full"
          style="background: var(--accent)"
        />
        <span class="relative w-5 flex-shrink-0 flex items-center justify-center">
          <component :is="link.icon" :size="18" />
        </span>
        <span
          v-if="!collapsed"
          class="relative text-[13px]"
          :class="isActive(link.path) ? 'font-semibold' : ''"
        >{{ link.label }}</span>
      </router-link>
    </nav>

    <div v-if="!collapsed" class="px-5 py-4 text-[11px] text-[--t3] opacity-30">
      v1.0
    </div>
  </aside>
</template>
