<script setup lang="ts">
import { ref } from 'vue'
import { IconStar, IconStarOutline } from './icons'

const props = defineProps<{
  modelValue: number
  readonly?: boolean
  size?: string
}>()
const emit = defineEmits<{ 'update:modelValue': [val: number] }>()

const hoverValue = ref(0)

function onClick(star: number) {
  if (props.readonly) return
  emit('update:modelValue', star === props.modelValue ? 0 : star)
}
</script>

<template>
  <div class="flex gap-1 select-none" :class="readonly ? '' : 'cursor-pointer'">
    <span
      v-for="star in 5"
      :key="star"
      class="transition-colors duration-150 flex items-center"
      :class="(hoverValue || modelValue) >= star ? 'text-amber-500/70' : 'text-[--t3]'"
      @click="onClick(star)"
      @mouseenter="!readonly && (hoverValue = star)"
      @mouseleave="hoverValue = 0"
    >
      <component
        :is="(hoverValue || modelValue) >= star ? IconStar : IconStarOutline"
        :size="size === 'lg' ? 28 : 18"
      />
    </span>
  </div>
</template>
