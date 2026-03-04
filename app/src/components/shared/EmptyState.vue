<script setup lang="ts">
import { IconInbox } from './icons'

defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-24 text-center select-none">
    <span class="mb-5 text-[--t3] opacity-30">
      <IconInbox :size="56" />
    </span>
    <h3 class="text-[14px] font-medium mb-1 text-[--t2]">{{ title }}</h3>
    <p v-if="description" class="text-[13px] max-w-xs text-[--t3]">{{ description }}</p>
  </div>
</template>
