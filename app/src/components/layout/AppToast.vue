<script setup lang="ts">
import { useToast } from '../../composables/useToast'

const { toasts, remove } = useToast()

const colorMap: Record<string, string> = {
  success: 'border-emerald-500/20',
  error: 'border-red-500/20',
  info: 'border-blue-500/20',
  warning: 'border-amber-500/20',
}
</script>

<template>
  <div class="fixed bottom-20 md:bottom-5 right-4 md:right-5 left-4 md:left-auto z-50 flex flex-col gap-2.5 max-w-sm md:ml-auto">
    <TransitionGroup name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="px-4 py-3 rounded-2xl border cursor-pointer backdrop-blur-xl"
        :class="colorMap[toast.type] || colorMap.info"
        style="background: rgba(17,17,25,0.9); box-shadow: 0 12px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05)"
        @click="remove(toast.id)"
      >
        <p class="text-[13px] m-0 text-[--t1] font-medium">{{ toast.message }}</p>
      </div>
    </TransitionGroup>
  </div>
</template>
