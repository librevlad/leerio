<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../../api'
import { useToast } from '../../composables/useToast'
import type { BookStatusValue } from '../../types'

const props = defineProps<{
  bookId: string
  bookStatus?: BookStatusValue
}>()
const emit = defineEmits<{ statusChanged: [] }>()

const toast = useToast()
const loading = ref(false)

const statuses: { value: BookStatusValue; label: string }[] = [
  { value: 'want_to_read', label: 'Хочу прочесть' },
  { value: 'reading', label: 'Слушаю' },
  { value: 'paused', label: 'На паузе' },
  { value: 'done', label: 'Прослушано' },
  { value: 'rejected', label: 'Не интересно' },
]

async function setStatus(e: Event) {
  const value = (e.target as HTMLSelectElement).value as BookStatusValue | ''
  if (!value) {
    // Clear status
    loading.value = true
    try {
      await api.removeBookStatus(props.bookId)
      emit('statusChanged')
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Ошибка')
    } finally {
      loading.value = false
    }
    return
  }
  loading.value = true
  try {
    await api.setBookStatus(props.bookId, value)
    emit('statusChanged')
  } catch (err: unknown) {
    toast.error(err instanceof Error ? err.message : 'Ошибка')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <select
    class="input-field cursor-pointer px-3 py-2.5 text-[13px]"
    :value="bookStatus || ''"
    :disabled="loading"
    @change="setStatus"
  >
    <option value="">Без статуса</option>
    <option v-for="s in statuses" :key="s.value" :value="s.value">
      {{ s.label }}
    </option>
  </select>
</template>
