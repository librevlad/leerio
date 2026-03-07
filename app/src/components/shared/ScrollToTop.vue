<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { IconChevronUp } from './icons'

const visible = ref(false)

function onScroll() {
  visible.value = window.scrollY > 400
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onUnmounted(() => window.removeEventListener('scroll', onScroll))
</script>

<template>
  <transition name="toast">
    <button
      v-if="visible"
      class="fixed right-4 bottom-20 z-40 flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-white/10 bg-[--card-solid] text-[--t2] shadow-lg transition-colors hover:bg-white/[0.12] hover:text-[--t1] md:bottom-6"
      title="Наверх"
      @click="scrollToTop"
    >
      <IconChevronUp :size="20" />
    </button>
  </transition>
</template>
