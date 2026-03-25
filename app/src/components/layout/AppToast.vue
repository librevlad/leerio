<script setup lang="ts">
import { useToast } from '../../composables/useToast'

const { toasts, remove } = useToast()

const colorMap: Record<string, string> = {
  success: 'border-[--success]/20',
  error: 'border-[--error]/20',
  info: 'border-[--info]/20',
  warning: 'border-[--warning]/20',
}
</script>

<template>
  <div
    class="fixed right-4 bottom-20 left-4 z-50 flex max-w-sm flex-col gap-2.5 md:right-5 md:bottom-5 md:left-auto md:ml-auto"
  >
    <TransitionGroup name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="cursor-pointer rounded-2xl border px-4 py-3 backdrop-blur-xl"
        :class="colorMap[toast.type] || colorMap.info"
        style="
          background: rgba(17, 17, 25, 0.9);
          box-shadow:
            0 12px 40px rgba(0, 0, 0, 0.5),
            0 0 0 1px rgba(255, 255, 255, 0.05);
        "
        @click="remove(toast.id)"
      >
        <p class="m-0 text-[13px] font-medium text-[--t1]">{{ toast.message }}</p>
      </div>
    </TransitionGroup>
  </div>
</template>
