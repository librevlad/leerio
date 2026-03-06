<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../../composables/useAuth'
import {
  IconHome,
  IconLibrary,
  IconHistory,
  IconChart,
  IconSettings,
  IconMenu,
  IconX,
  IconFolder,
  IconUpload,
  IconBookmark,
} from '../shared/icons'

defineProps<{ collapsed: boolean }>()
const emit = defineEmits<{ 'update:collapsed': [val: boolean] }>()
const route = useRoute()
const router = useRouter()
const { user, logout } = useAuth()

const links = [
  { path: '/', label: 'Главная', icon: IconHome },
  { path: '/library', label: 'Каталог', icon: IconLibrary },
  { path: '/my-library', label: 'Моя библиотека', icon: IconFolder },
  { path: '/upload', label: 'Загрузить', icon: IconUpload },
  { path: '/collections', label: 'Коллекции', icon: IconBookmark },
  { path: '/history', label: 'История', icon: IconHistory },
  { path: '/analytics', label: 'Аналитика', icon: IconChart },
  { path: '/settings', label: 'Настройки', icon: IconSettings },
]

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

async function handleLogout() {
  await logout()
  router.push('/login')
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
        <img src="/logo.svg" alt="Leerio" class="h-7 w-7 rounded-lg" />
        <span class="text-[14px] font-bold tracking-tight text-[--t1]">Leerio</span>
      </div>
    </div>

    <nav class="flex flex-1 flex-col gap-0.5 px-2.5 py-3">
      <router-link
        v-for="link in links"
        :key="link.path"
        :to="link.path"
        :title="collapsed ? link.label : undefined"
        class="group relative flex items-center gap-3 rounded-xl px-3 py-2.5 no-underline transition-all duration-200"
        :class="
          isActive(link.path)
            ? 'bg-white/[0.08] text-[--t1] shadow-[inset_3px_0_0_var(--accent)]'
            : 'text-[--t3] hover:bg-white/[0.03] hover:text-[--t2]'
        "
      >
        <span class="flex w-5 flex-shrink-0 items-center justify-center">
          <component :is="link.icon" :size="18" />
        </span>
        <span v-if="!collapsed" class="text-[13px]" :class="isActive(link.path) ? 'font-semibold' : ''">{{
          link.label
        }}</span>
      </router-link>
    </nav>

    <!-- User section at bottom -->
    <div class="border-t px-3 py-3" style="border-color: var(--border)">
      <div v-if="user && !collapsed" class="mb-2 flex items-center gap-2.5 px-1">
        <img
          v-if="user.picture"
          :src="user.picture"
          :alt="user.name"
          class="h-7 w-7 rounded-full object-cover"
          referrerpolicy="no-referrer"
        />
        <div
          v-else
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-[--t2]"
          style="background: rgba(255, 255, 255, 0.08)"
        >
          {{ user.name?.charAt(0) || '?' }}
        </div>
        <div class="min-w-0 flex-1">
          <p class="truncate text-[12px] font-medium text-[--t2]">{{ user.name }}</p>
          <p class="truncate text-[10px] text-[--t3]">{{ user.email }}</p>
        </div>
      </div>
      <button
        class="flex w-full cursor-pointer items-center gap-3 rounded-xl border-0 bg-transparent px-3 py-2 text-[--t3] transition-colors hover:bg-white/[0.03] hover:text-[--t2]"
        :title="collapsed ? 'Выйти' : undefined"
        aria-label="Выйти"
        @click="handleLogout"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
          <polyline points="16 17 21 12 16 7" />
          <line x1="21" y1="12" x2="9" y2="12" />
        </svg>
        <span v-if="!collapsed" class="text-[12px]">Выйти</span>
      </button>
    </div>
  </aside>
</template>
