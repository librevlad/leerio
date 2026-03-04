<script setup lang="ts">
defineProps<{
  progress: number
  refreshing: boolean
}>()
</script>

<template>
  <div
    v-if="progress > 0 || refreshing"
    class="pointer-events-none fixed top-0 right-0 left-0 z-50 flex justify-center md:hidden"
    :style="{ paddingTop: refreshing ? '12px' : `${progress * 12}px` }"
  >
    <div
      class="flex h-8 w-8 items-center justify-center rounded-full bg-[--card-solid] shadow-lg"
      :style="{ opacity: refreshing ? 1 : progress, transform: `scale(${0.5 + progress * 0.5})` }"
    >
      <div
        class="h-4 w-4 rounded-full border-2 border-[--t3] border-t-[--accent]"
        :class="refreshing ? 'animate-spin' : ''"
        :style="refreshing ? {} : { transform: `rotate(${progress * 360}deg)` }"
      />
    </div>
  </div>
</template>
