<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuth } from '../../composables/useAuth'
import { usePlayer } from '../../composables/usePlayer'
import { STORAGE } from '../../constants/storage'
import {
  IconHome,
  IconLibrary,
  IconHistory,
  IconSettings,
  IconMenu,
  IconX,
  IconFolder,
  IconUpload,
  IconChart,
  IconQueue,
  IconBookmark,
} from '../shared/icons'

defineProps<{ collapsed: boolean }>()
const emit = defineEmits<{ 'update:collapsed': [val: boolean] }>()
const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { user, isLoggedIn, logout } = useAuth()
const { currentBook, openFullscreen } = usePlayer()

const lastPlayed = ref<{ id: string; title: string; author: string } | null>(null)
onMounted(() => {
  try {
    const raw = localStorage.getItem(STORAGE.LAST_PLAYED)
    if (raw) lastPlayed.value = JSON.parse(raw)
  } catch {
    /* ignore */
  }
})

const sidebarBook = computed(() => {
  if (currentBook.value) return { ...currentBook.value, isPlaying: true }
  if (lastPlayed.value) return { ...lastPlayed.value, isPlaying: false }
  return null
})

const publicLinks = computed(() => [{ path: '/library', label: t('nav.catalog'), icon: IconLibrary }])

const mainLinks = computed(() => [
  { path: '/', label: t('nav.home'), icon: IconHome },
  { path: '/library', label: t('nav.catalog'), icon: IconLibrary },
  { path: '/my-library', label: t('nav.library'), icon: IconFolder },
  { path: '/collections', label: t('nav.collections'), icon: IconQueue },
  { path: '/library?status=want_to_read', label: t('nav.wantToRead'), icon: IconBookmark },
  { path: '/history', label: t('nav.history'), icon: IconHistory },
  { path: '/analytics', label: t('nav.analytics'), icon: IconChart },
  { path: '/upload', label: t('nav.upload'), icon: IconUpload },
])

const navLinks = computed(() => (isLoggedIn.value ? mainLinks.value : publicLinks.value))

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  if (path.includes('?')) {
    const [base, query] = path.split('?')
    return route.path === base && route.fullPath.includes(query!)
  }
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
    :class="collapsed ? 'w-16' : 'w-60'"
    style="background: var(--sidebar); border-right: 1px solid var(--border)"
  >
    <div class="flex h-16 items-center gap-3 px-4">
      <button
        class="flex cursor-pointer items-center rounded-xl border-0 bg-transparent p-1.5 text-[--t3] transition-colors hover:text-[--t2]"
        :aria-label="collapsed ? t('nav.expand') : t('nav.collapse')"
        @click="emit('update:collapsed', !collapsed)"
      >
        <component :is="collapsed ? IconMenu : IconX" :size="18" />
      </button>
      <div v-if="!collapsed" class="flex items-center gap-2.5">
        <img src="/logo.png" alt="Leerio" class="h-7 w-7 rounded-lg" />
        <span class="text-[14px] font-bold tracking-tight text-[--t1]">Leerio</span>
      </div>
    </div>

    <nav class="flex flex-1 flex-col gap-0.5 px-2.5 py-3">
      <router-link
        v-for="link in navLinks"
        :key="link.path"
        :to="link.path"
        :title="collapsed ? link.label : undefined"
        class="group relative flex items-center gap-3 rounded-xl px-3 py-2.5 no-underline transition-all duration-150"
        :class="
          isActive(link.path) ? 'bg-[--card] text-[--accent]' : 'text-[--t3] hover:bg-[--card-hover] hover:text-[--t2]'
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

    <!-- Last played / Now playing -->
    <button
      v-if="sidebarBook"
      class="mx-2.5 mb-2 flex cursor-pointer items-center gap-2.5 rounded-xl border-0 px-3 py-2.5 text-left transition-colors hover:bg-[--card-hover]"
      :style="
        sidebarBook.isPlaying
          ? 'background: rgba(255, 138, 0, 0.06); border: 1px solid rgba(255, 138, 0, 0.1)'
          : 'background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.04)'
      "
      @click="sidebarBook.isPlaying ? openFullscreen() : router.push(`/book/${sidebarBook.id}`)"
    >
      <span v-if="sidebarBook.isPlaying" class="now-playing-bars inline-flex shrink-0 items-end gap-px">
        <span /><span /><span />
      </span>
      <span v-else class="shrink-0 text-[14px]">🎧</span>
      <span v-if="!collapsed" class="min-w-0 flex-1">
        <span class="block truncate text-[12px] font-semibold text-[--t1]">{{ sidebarBook.title }}</span>
        <span class="block truncate text-[10px] text-[--t3]">{{ sidebarBook.author }}</span>
      </span>
    </button>

    <!-- Secondary section -->
    <div class="border-t px-2.5 pt-2 pb-3" style="border-color: var(--border)">
      <!-- Authenticated: settings + user info + logout -->
      <template v-if="isLoggedIn">
        <router-link
          to="/settings"
          :title="collapsed ? t('nav.settings') : undefined"
          class="flex items-center gap-3 rounded-xl px-3 py-2.5 no-underline transition-all duration-150"
          :class="
            isActive('/settings')
              ? 'bg-[--card] text-[--accent]'
              : 'text-[--t3] hover:bg-[--card-hover] hover:text-[--t2]'
          "
        >
          <span class="flex w-5 flex-shrink-0 items-center justify-center">
            <IconSettings :size="18" />
          </span>
          <span v-if="!collapsed" class="text-[13px]" :class="isActive('/settings') ? 'font-semibold' : ''">
            {{ t('nav.settings') }}
          </span>
        </router-link>

        <div v-if="user && !collapsed" class="mt-2 flex items-center gap-2.5 px-3">
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
            <p v-if="user.plan !== 'premium'" class="text-[10px] text-[--t3]">Free</p>
          </div>
        </div>

        <button
          class="mt-1 flex w-full cursor-pointer items-center gap-3 rounded-xl border-0 bg-transparent px-3 py-2 text-[--t3] transition-colors hover:bg-[--card-hover] hover:text-[--t2]"
          :title="collapsed ? t('nav.logout') : undefined"
          :aria-label="t('nav.logout')"
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
          <span v-if="!collapsed" class="text-[12px]">{{ t('nav.logout') }}</span>
        </button>
      </template>

      <!-- Guest: login link -->
      <router-link
        v-else
        to="/login"
        class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-[--accent] no-underline transition-all duration-150 hover:bg-[--card-hover]"
      >
        <span class="flex w-5 flex-shrink-0 items-center justify-center">
          <svg
            width="18"
            height="18"
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
        </span>
        <span v-if="!collapsed" class="text-[13px] font-semibold">{{ t('nav.login') }}</span>
      </router-link>
    </div>
  </aside>
</template>
