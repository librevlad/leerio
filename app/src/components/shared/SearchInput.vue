<script setup lang="ts">
import { ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { IconSearch } from './icons'

const props = withDefaults(defineProps<{
  modelValue: string
  placeholder?: string
}>(), {
  placeholder: 'Поиск...',
})

const emit = defineEmits<{ 'update:modelValue': [val: string] }>()

const local = ref(props.modelValue)

const debouncedEmit = useDebounceFn((val: string) => {
  emit('update:modelValue', val)
}, 300)

watch(local, (val) => debouncedEmit(val))
watch(() => props.modelValue, (val) => { local.value = val })
</script>

<template>
  <div class="relative">
    <span class="absolute left-3 top-1/2 -translate-y-1/2 flex items-center text-[--t3]">
      <IconSearch :size="14" />
    </span>
    <input
      v-model="local"
      type="text"
      :placeholder="placeholder"
      class="input-field w-full pl-9 pr-3 py-2.5"
    />
  </div>
</template>
