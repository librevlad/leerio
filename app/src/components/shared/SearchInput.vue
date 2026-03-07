<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { IconSearch } from './icons'

const props = withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
  }>(),
  {
    placeholder: 'Поиск...',
  },
)

const emit = defineEmits<{ 'update:modelValue': [val: string] }>()

const local = ref(props.modelValue)
const inputRef = ref<HTMLInputElement>()
const focused = ref(false)

const debouncedEmit = useDebounceFn((val: string) => {
  emit('update:modelValue', val)
}, 300)

watch(local, (val) => debouncedEmit(val))
watch(
  () => props.modelValue,
  (val) => {
    local.value = val
  },
)

function onKeydown(e: KeyboardEvent) {
  if (e.key === '/' && !focused.value) {
    const tag = (e.target as HTMLElement)?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable) return
    e.preventDefault()
    inputRef.value?.focus()
  }
  if (e.key === 'Escape' && focused.value) {
    inputRef.value?.blur()
  }
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="relative">
    <span class="absolute top-1/2 left-3 flex -translate-y-1/2 items-center text-[--t3]">
      <IconSearch :size="14" />
    </span>
    <input
      ref="inputRef"
      v-model="local"
      type="text"
      :placeholder="placeholder"
      class="input-field w-full py-2.5 pr-9 pl-9"
      @focus="focused = true"
      @blur="focused = false"
    />
    <kbd
      v-if="!focused && !local"
      class="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[10px] leading-none font-medium text-[--t3]"
    >
      /
    </kbd>
  </div>
</template>
