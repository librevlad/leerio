<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted } from 'vue'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const sheetRef = ref<HTMLElement>()
let previousFocus: HTMLElement | null = null

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => {
  previousFocus = document.activeElement as HTMLElement
  nextTick(() => sheetRef.value?.focus())
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  previousFocus?.focus()
})
</script>

<template>
  <Teleport to="body">
    <transition name="sheet">
      <div v-if="open" class="fixed inset-0 z-[90]">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="$emit('close')" />

        <!-- Sheet -->
        <div
          ref="sheetRef"
          role="dialog"
          aria-modal="true"
          tabindex="-1"
          class="absolute right-0 bottom-0 left-0 rounded-t-2xl border-t border-[--border] outline-none"
          style="background: var(--card-solid)"
        >
          <!-- Handle -->
          <div class="flex justify-center py-3">
            <div class="h-1 w-10 rounded-full bg-white/15" />
          </div>

          <!-- Content -->
          <div class="safe-bottom px-2 pb-4">
            <slot />
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>
