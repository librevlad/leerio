<script setup lang="ts">
import { ref } from 'vue'
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
const loading = ref(false)

const statuses: {
  value: BookStatusValue
  label: string
  color: string
  activeBg: string
  activeBorder: string
  activeText: string
  dot: string
}[] = [
  {
    value: 'want_to_read',
    label: 'Хочу прочесть',
    color: 'bg-slate-400',
    activeBg: 'bg-slate-500/15',
    activeBorder: 'border-slate-500/30',
    activeText: 'text-slate-300',
    dot: 'bg-slate-400',
  },
  {
    value: 'reading',
    label: 'Слушаю',
    color: 'bg-purple-400',
    activeBg: 'bg-purple-500/15',
    activeBorder: 'border-purple-500/30',
    activeText: 'text-purple-400',
    dot: 'bg-purple-400',
  },
  {
    value: 'paused',
    label: 'На паузе',
    color: 'bg-amber-400',
    activeBg: 'bg-amber-500/15',
    activeBorder: 'border-amber-500/30',
    activeText: 'text-amber-400',
    dot: 'bg-amber-400',
  },
  {
    value: 'done',
    label: 'Прослушано',
    color: 'bg-emerald-400',
    activeBg: 'bg-emerald-500/15',
    activeBorder: 'border-emerald-500/30',
    activeText: 'text-emerald-400',
    dot: 'bg-emerald-400',
  },
  {
    value: 'rejected',
    label: 'Не интересно',
    color: 'bg-red-400',
    activeBg: 'bg-red-500/15',
    activeBorder: 'border-red-500/30',
    activeText: 'text-red-400',
    dot: 'bg-red-400',
  },
]

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
    toast.error(err instanceof Error ? err.message : 'Ошибка')
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
    toast.error(err instanceof Error ? err.message : 'Ошибка')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="scrollbar-hide flex items-center gap-2 overflow-x-auto">
    <button
      v-for="s in statuses"
      :key="s.value"
      class="inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full border px-3.5 py-2 text-[12px] font-semibold transition-all"
      :class="
        bookStatus === s.value
          ? [s.activeBg, s.activeBorder, s.activeText]
          : 'border-transparent bg-white/[0.04] text-[--t3] hover:bg-white/[0.06] hover:text-[--t2]'
      "
      :disabled="loading"
      @click="selectStatus(s.value)"
    >
      <span class="h-1.5 w-1.5 rounded-full" :class="s.dot" />
      {{ s.label }}
    </button>
    <button
      v-if="bookStatus"
      class="inline-flex shrink-0 cursor-pointer items-center justify-center rounded-full border border-transparent bg-white/[0.04] p-1.5 text-[--t3] transition-all hover:bg-red-500/10 hover:text-red-400"
      :disabled="loading"
      title="Убрать статус"
      @click="clearStatus"
    >
      <IconX :size="14" />
    </button>
  </div>
</template>
