<script setup lang="ts">
import { ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { api } from '../../api'
import { useToast } from '../../composables/useToast'
import ProgressRing from '../shared/ProgressRing.vue'

const props = defineProps<{ title: string; progress: number }>()
const emit = defineEmits<{ updated: [pct: number] }>()

const toast = useToast()
const pct = ref(props.progress)

watch(
  () => props.progress,
  (v) => {
    pct.value = v
  },
)

const save = useDebounceFn(async (val: number) => {
  try {
    await api.setProgress(props.title, val)
    emit('updated', val)
    toast.success(`Прогресс: ${val}%`)
  } catch {
    toast.error('Не удалось сохранить прогресс')
  }
}, 500)
</script>

<template>
  <div class="card p-5">
    <div class="flex items-center gap-5">
      <!-- Big ring -->
      <div class="flex-shrink-0">
        <ProgressRing :percent="pct" :size="72" :stroke="5" />
      </div>

      <!-- Slider area -->
      <div class="min-w-0 flex-1">
        <div class="mb-1 flex items-center justify-between">
          <h3 class="section-label">Прогресс</h3>
          <span class="gradient-text text-[15px] font-bold">{{ pct }}%</span>
        </div>
        <div class="mt-2">
          <input v-model.number="pct" type="range" min="0" max="100" step="5" class="w-full" @input="save(pct)" />
        </div>
        <div class="mt-1.5 flex justify-between text-[10px] text-[--t3]">
          <span>0%</span>
          <span>50%</span>
          <span>100%</span>
        </div>
      </div>
    </div>
  </div>
</template>
