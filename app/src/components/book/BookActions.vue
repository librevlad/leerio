<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../../api'
import { useToast } from '../../composables/useToast'
import { IconX } from '../shared/icons'
import type { BookStatusValue } from '../../types'

const props = defineProps<{
  bookId: string
  bookStatus?: BookStatusValue
}>()
const emit = defineEmits<{ statusChanged: [] }>()

const toast = useToast()
const { t } = useI18n()
const loading = ref(false)


const statuses = computed<{ value: BookStatusValue; label: string }[]>(() => [
  { value: 'want_to_read', label: t('book.actionWantToRead') },
  { value: 'reading', label: t('book.actionListening') },
  { value: 'paused', label: t('book.actionPaused') },
  { value: 'done', label: t('book.actionDone') },
  { value: 'rejected', label: t('book.actionRejected') },
])

async function selectStatus(value: BookStatusValue) {
  if (loading.value) return
  loading.value = true
  try {
    if (props.bookStatus === value) {
      await api.removeBookStatus(props.bookId)
    } else {
      await api.setBookStatus(props.bookId, value)
    }
    emit('statusChanged')
  } catch (err: unknown) {
    toast.error(err instanceof Error ? err.message : t('common.error'))
  } finally {
    loading.value = false
  }
}

async function clearStatus() {
  if (loading.value) return
  loading.value = true
  try {
    await api.removeBookStatus(props.bookId)
    emit('statusChanged')
  } catch (err: unknown) {
    toast.error(err instanceof Error ? err.message : t('common.error'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="scrollbar-hide fade-mask-r flex items-center gap-2 overflow-x-auto">
    <button
      v-for="s in statuses"
      :key="s.value"
      class="inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border px-3.5 py-2 text-[12px] font-medium transition-colors"
      :class="
        bookStatus === s.value
          ? 'border-[--accent]/20 bg-[--accent-soft] text-[--accent]'
          : 'border-white/[0.08] bg-white/[0.04] text-[--t2] hover:bg-white/[0.06] hover:text-[--t1]'
      "
      :disabled="loading"
      @click="selectStatus(s.value)"
    >
      {{ s.label }}
    </button>
    <button
      v-if="bookStatus"
      class="inline-flex shrink-0 cursor-pointer items-center justify-center rounded-lg border border-transparent bg-white/[0.04] p-1.5 text-[--t3] transition-colors hover:bg-red-500/10 hover:text-red-400"
      :disabled="loading"
      :title="t('book.removeStatus')"
      @click="clearStatus"
    >
      <IconX :size="14" />
    </button>
  </div>
</template>
