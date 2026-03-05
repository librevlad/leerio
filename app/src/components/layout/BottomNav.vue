<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IconHome,
  IconLibrary,
  IconFolder,
  IconMenu,
  IconUpload,
  IconBookmark,
  IconHistory,
  IconChart,
  IconSettings,
} from '../shared/icons'
import BottomSheet from './BottomSheet.vue'

const route = useRoute()
const router = useRouter()
const showMore = ref(false)

const tabs = [
  { path: '/', label: 'Главная', icon: IconHome },
  { path: '/library', label: 'Каталог', icon: IconLibrary },
  { path: '/my-library', label: 'Моя', icon: IconFolder },
]

const moreLinks = [
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
        <component :is="tab.icon" :size="20" />
        <span class="text-[10px] leading-none font-medium">{{ tab.label }}</span>
      </router-link>

      <!-- More button -->
      <button
        class="relative flex flex-1 cursor-pointer flex-col items-center justify-center gap-0.5 border-0 bg-transparent transition-colors duration-200"
        :class="showMore || isMoreActive ? 'text-[--accent]' : 'text-[--t3]'"
        @click="showMore = !showMore"
      >
        <IconMenu :size="20" />
        <span class="text-[10px] leading-none font-medium">Ещё</span>
      </button>
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
