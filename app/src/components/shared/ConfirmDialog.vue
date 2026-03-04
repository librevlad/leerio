<script setup lang="ts">
defineProps<{
  show: boolean
  title: string
  message: string
  confirmText?: string
  confirmClass?: string
}>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()
</script>

<template>
  <Teleport to="body">
    <Transition name="dialog">
      <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center p-4" @click.self="emit('cancel')">
        <div class="fixed inset-0 dialog-overlay" />
        <div class="dialog-panel p-6 max-w-sm w-full relative z-10">
          <h3 class="text-[15px] font-semibold mb-1.5 text-[--t1]">{{ title }}</h3>
          <p class="text-[13px] leading-relaxed mb-6 text-[--t2]">{{ message }}</p>
          <div class="flex justify-end gap-2">
            <button class="btn btn-ghost" @click="emit('cancel')">Отмена</button>
            <button class="btn btn-primary" :class="confirmClass" @click="emit('confirm')">
              {{ confirmText || 'Подтвердить' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
