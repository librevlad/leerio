<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../../api'
import { useToast } from '../../composables/useToast'
import { useTrello } from '../../composables/useTrello'
import { useConstants } from '../../composables/useConstants'
import { useAuth } from '../../composables/useAuth'
import StarRating from '../shared/StarRating.vue'
import ConfirmDialog from '../shared/ConfirmDialog.vue'
import type { BookStatusValue } from '../../types'

const props = defineProps<{
  bookId: string
  cardId?: string
  status?: string
  bookStatus?: BookStatusValue
  title: string
  author?: string
  category?: string
}>()
const emit = defineEmits<{ moved: []; cardCreated: [cardId: string]; statusChanged: [] }>()

const toast = useToast()
const { createCard } = useTrello()
const { constants, load: loadConstants } = useConstants()
const { isAdmin } = useAuth()
const showDoneDialog = ref(false)
const showRejectDialog = ref(false)
const doneRating = ref(0)
const loading = ref(false)
const creating = ref(false)

loadConstants()

// ── Admin: Trello actions ──

async function move(target: string, rating = 0) {
  if (!props.cardId) {
    toast.warning('Нет карточки Trello')
    return
  }
  loading.value = true
  try {
    await api.moveCard(props.cardId, target, rating)
    toast.success(`→ ${target}`)
    emit('moved')
  } catch (e: unknown) {
    toast.error(e instanceof Error ? e.message : 'Ошибка')
  } finally {
    loading.value = false
  }
}

async function markDone() {
  await move('Прочитано', doneRating.value)
  showDoneDialog.value = false
}

async function reject() {
  await move('Забраковано')
  showRejectDialog.value = false
}

async function handleCreateCard() {
  creating.value = true
  try {
    const name = props.author ? `${props.author} - ${props.title}` : props.title
    const label =
      props.category && constants.value?.folder_to_label
        ? (constants.value.folder_to_label[props.category] ?? undefined)
        : undefined
    const cardId = await createCard(name, 'Прочесть', label)
    if (cardId) {
      emit('cardCreated', cardId)
    }
  } finally {
    creating.value = false
  }
}

const actions = [
  { key: 'listen', target: 'В процессе', label: 'Слушать', hide: 'В процессе', style: 'ghost' },
  { key: 'phone', target: 'В телефоне', label: 'На телефон', hide: 'В телефоне', style: 'ghost' },
  { key: 'pause', target: 'На Паузе', label: 'Пауза', hide: 'На Паузе', style: 'ghost' },
]

// ── Regular user: simple status buttons ──

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

    <!-- Admin mode: Trello actions -->
    <template v-if="isAdmin">
      <div v-if="!cardId" class="space-y-3">
        <div class="flex items-center gap-3 rounded-xl px-3 py-2.5" style="background: rgba(255, 255, 255, 0.02)">
          <div
            class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg"
            style="background: rgba(250, 204, 21, 0.1)"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="text-yellow-400"
            >
              <path
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
              />
            </svg>
          </div>
          <div>
            <p class="text-[12px] font-medium text-[--t2]">Нет привязки к Trello</p>
            <p class="text-[10px] text-[--t3]">Создайте карточку, чтобы управлять книгой</p>
          </div>
        </div>
        <button class="btn btn-ghost w-full" :disabled="creating" @click="handleCreateCard">
          {{ creating ? 'Создание...' : 'Создать карточку' }}
        </button>
      </div>
      <div v-else class="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
        <template v-for="a in actions" :key="a.key">
          <button
            v-if="status !== a.hide"
            class="btn btn-ghost justify-center"
            :disabled="loading"
            @click="move(a.target)"
          >
            {{ a.label }}
          </button>
        </template>
        <button class="btn btn-primary justify-center" :disabled="loading" @click="showDoneDialog = true">
          Прослушано
        </button>
        <button class="btn btn-danger justify-center" :disabled="loading" @click="showRejectDialog = true">
          Забраковать
        </button>
      </div>
    </template>

    <!-- Regular user mode: simple status buttons -->
    <template v-else>
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
    </template>

    <Teleport to="body">
      <Transition name="dialog">
        <div
          v-if="showDoneDialog"
          class="fixed inset-0 z-50 flex items-center justify-center p-4"
          @click.self="showDoneDialog = false"
        >
          <div class="dialog-overlay fixed inset-0" />
          <div class="dialog-panel relative z-10 w-full max-w-sm p-7">
            <h3 class="mb-1 text-[16px] font-bold text-[--t1]">Прослушано!</h3>
            <p class="mb-5 text-[13px] text-[--t2]">Оцените книгу:</p>
            <div class="mb-6 flex justify-center">
              <StarRating v-model="doneRating" size="lg" />
            </div>
            <div class="flex justify-end gap-2">
              <button class="btn btn-ghost" @click="showDoneDialog = false">Отмена</button>
              <button class="btn btn-primary" @click="markDone">Готово</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <ConfirmDialog
      :show="showRejectDialog"
      title="Забраковать?"
      :message="`Отправить «${title}» в забракованные?`"
      confirm-text="Забраковать"
      confirm-class="!bg-red-600 hover:!bg-red-500 !text-white !shadow-none"
      @confirm="reject"
      @cancel="showRejectDialog = false"
    />
  </div>
</template>
