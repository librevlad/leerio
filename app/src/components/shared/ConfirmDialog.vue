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
        <div class="dialog-overlay fixed inset-0" />
        <div class="dialog-panel relative z-10 w-full max-w-sm p-6">
          <h3 class="mb-1.5 text-[15px] font-semibold text-[--t1]">{{ title }}</h3>
          <p class="mb-6 text-[13px] leading-relaxed text-[--t2]">{{ message }}</p>
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
