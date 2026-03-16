<script setup lang="ts">
import type { Component } from 'vue'
import { IconInbox } from './icons'

defineProps<{
  title: string
  description?: string
  actionLabel?: string
  icon?: Component
}>()

defineEmits<{ action: [] }>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-24 text-center select-none">
    <span class="mb-5 text-[--t3] opacity-40">
      <component :is="icon ?? IconInbox" :size="56" />
    </span>
    <h3 class="mb-1 text-[14px] font-medium text-[--t2]">{{ title }}</h3>
    <p v-if="description" class="max-w-xs text-[13px] text-[--t3]">{{ description }}</p>
    <button v-if="actionLabel" class="btn btn-ghost mt-5" @click="$emit('action')">
      {{ actionLabel }}
    </button>
  </div>
</template>
