<script setup lang="ts">
import { ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { api } from '../../api'
import { useToast } from '../../composables/useToast'

const props = defineProps<{ title: string; note: string }>()
const toast = useToast()

const text = ref(props.note)
const saving = ref(false)

watch(() => props.note, (v) => { text.value = v })

const save = useDebounceFn(async (val: string) => {
  saving.value = true
  try {
    await api.setNote(props.title, val)
  } catch {
    toast.error('Не удалось сохранить заметку')
  } finally {
    saving.value = false
  }
}, 800)
</script>

<template>
  <div class="card p-5">
    <div class="flex items-center justify-between mb-3">
      <h3 class="section-label">Заметки</h3>
      <Transition name="toast">
        <span v-if="saving" class="text-[11px] text-[--accent] font-medium opacity-70">
          Сохранение...
        </span>
      </Transition>
    </div>
    <textarea
      v-model="text"
      rows="4"
      placeholder="Добавить заметку..."
      class="input-field w-full p-3.5 text-[13px] resize-y leading-relaxed"
      @input="save(text)"
    />
  </div>
</template>
