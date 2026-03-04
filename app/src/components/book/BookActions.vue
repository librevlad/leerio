<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../../api'
import { useToast } from '../../composables/useToast'
import type { BookStatusValue } from '../../types'

const props = defineProps<{
  bookId: string
  bookStatus?: BookStatusValue
  title: string
}>()
const emit = defineEmits<{ statusChanged: [] }>()

const toast = useToast()
const loading = ref(false)

const statusButtons: { status: BookStatusValue; label: string; style: string }[] = [
  { status: 'want_to_read', label: 'Хочу прочесть', style: 'ghost' },
  { status: 'reading', label: 'Слушаю', style: 'ghost' },
  { status: 'paused', label: 'Пауза', style: 'ghost' },
  { status: 'done', label: 'Прослушано', style: 'primary' },
  { status: 'rejected', label: 'Не интересно', style: 'danger' },
]

async function setBookStatus(status: BookStatusValue) {
  loading.value = true
  try {
    await api.setBookStatus(props.bookId, status)
    toast.success(statusButtons.find((s) => s.status === status)?.label || status)
    emit('statusChanged')
  } catch (e: unknown) {
    toast.error(e instanceof Error ? e.message : 'Ошибка')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="card p-5">
    <h3 class="section-label mb-3">Действия</h3>
    <div class="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
      <button
        v-for="sb in statusButtons"
        :key="sb.status"
        class="btn justify-center"
        :class="[
          bookStatus === sb.status ? 'btn-primary !opacity-100' : sb.style === 'danger' ? 'btn-danger' : 'btn-ghost',
        ]"
        :disabled="loading || bookStatus === sb.status"
        @click="setBookStatus(sb.status)"
      >
        {{ sb.label }}
      </button>
    </div>
  </div>
</template>
