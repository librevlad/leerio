<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { IconChevronUp } from './icons'

const { t } = useI18n()

const visible = ref(false)
let mainEl: HTMLElement | null = null

function onScroll() {
  if (mainEl) {
    visible.value = mainEl.scrollTop > 400
  }
}

function scrollToTop() {
  if (mainEl) {
    mainEl.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

onMounted(() => {
  mainEl = document.querySelector('main')
  if (mainEl) {
    mainEl.addEventListener('scroll', onScroll, { passive: true })
  }
})
onUnmounted(() => {
  if (mainEl) {
    mainEl.removeEventListener('scroll', onScroll)
  }
})
</script>

<template>
  <transition name="toast">
    <button
      v-if="visible"
      class="fixed right-4 bottom-20 z-40 flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-white/10 bg-[--card-solid] text-[--t2] shadow-lg transition-colors hover:bg-white/[0.12] hover:text-[--t1] md:bottom-6"
      :title="t('common.toTop')"
      @click="scrollToTop"
    >
      <IconChevronUp :size="20" />
    </button>
  </transition>
</template>
