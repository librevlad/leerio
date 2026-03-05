<script setup lang="ts">
defineProps<{ open: boolean }>()
defineEmits<{ close: [] }>()
</script>

<template>
  <Teleport to="body">
    <transition name="sheet">
      <div v-if="open" class="fixed inset-0 z-[90]">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="$emit('close')" />

        <!-- Sheet -->
        <div
          class="absolute right-0 bottom-0 left-0 rounded-t-2xl border-t border-[--border]"
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
