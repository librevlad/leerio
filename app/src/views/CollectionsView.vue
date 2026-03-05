<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { useBooks } from '../composables/useBooks'
import { useToast } from '../composables/useToast'
import type { Collection } from '../types'
import { IconPlus, IconTrash, IconEdit, IconX, IconCheck, IconBookmark, IconMusic } from '../components/shared/icons'
import EmptyState from '../components/shared/EmptyState.vue'

const toast = useToast()
const { books, load: loadBooks } = useBooks()

const collections = ref<Collection[]>([])
const loading = ref(true)
const showCreate = ref(false)
const editIdx = ref<number | null>(null)

// Form state
const formName = ref('')
const formDesc = ref('')
const formBooks = ref<string[]>([])

async function loadCollections() {
  loading.value = true
  try {
    collections.value = await api.getCollections()
  } catch {
    toast.error('Ошибка загрузки коллекций')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  formName.value = ''
  formDesc.value = ''
  formBooks.value = []
  editIdx.value = null
  showCreate.value = true
}

function openEdit(idx: number) {
  const c = collections.value[idx]!
  formName.value = c.name
  formDesc.value = c.description
  formBooks.value = [...c.books]
  editIdx.value = idx
  showCreate.value = true
}

function closeForm() {
  showCreate.value = false
  editIdx.value = null
}

function toggleBook(title: string) {
  const i = formBooks.value.indexOf(title)
  if (i >= 0) {
    formBooks.value.splice(i, 1)
  } else {
    formBooks.value.push(title)
  }
}

async function save() {
  if (!formName.value.trim()) {
    toast.error('Введите название')
    return
  }
  try {
    if (editIdx.value !== null) {
      await api.updateCollection(editIdx.value, formName.value.trim(), formBooks.value, formDesc.value.trim())
      toast.success('Коллекция обновлена')
    } else {
      await api.createCollection(formName.value.trim(), formBooks.value, formDesc.value.trim())
      toast.success('Коллекция создана')
    }
    closeForm()
    await loadCollections()
  } catch {
    toast.error('Ошибка сохранения')
  }
}

async function remove(idx: number) {
  if (!confirm(`Удалить коллекцию "${collections.value[idx]!.name}"?`)) return
  try {
    await api.deleteCollection(idx)
    toast.success('Удалено')
    await loadCollections()
  } catch {
    toast.error('Ошибка удаления')
  }
}

onMounted(async () => {
  await Promise.all([loadCollections(), loadBooks()])
})
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="page-title">Коллекции</h1>
        <p class="mt-1 text-[13px] text-[--t3]">
          {{ collections.length > 0 ? `${collections.length} коллекций` : 'Группируйте книги по темам' }}
        </p>
      </div>
      <button class="btn btn-primary flex items-center gap-1.5 px-4 py-2 text-[12px] font-semibold" @click="openCreate">
        <IconPlus :size="14" />
        Создать
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 3" :key="i" class="skeleton h-24 rounded-xl" />
    </div>

    <!-- Empty -->
    <EmptyState
      v-else-if="!collections.length && !showCreate"
      title="Нет коллекций"
      description="Создайте коллекцию, чтобы группировать книги по темам"
      action-label="Создать коллекцию"
      @action="openCreate"
    />

    <!-- Collections list -->
    <div v-else-if="!showCreate" class="space-y-3">
      <div v-for="(col, idx) in collections" :key="idx" class="card p-4">
        <div class="mb-2 flex items-start justify-between">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <IconBookmark :size="16" class="flex-shrink-0 text-[--accent]" />
              <h3 class="truncate text-[14px] font-semibold text-[--t1]">{{ col.name }}</h3>
            </div>
            <p v-if="col.description" class="mt-1 line-clamp-2 text-[12px] text-[--t3]">{{ col.description }}</p>
          </div>
          <div class="ml-3 flex flex-shrink-0 gap-1">
            <button
              class="rounded-lg p-1.5 text-[--t3] transition-colors hover:bg-white/5 hover:text-[--t2]"
              @click="openEdit(idx)"
            >
              <IconEdit :size="14" />
            </button>
            <button
              class="rounded-lg p-1.5 text-[--t3] transition-colors hover:bg-red-500/15 hover:text-red-400"
              @click="remove(idx)"
            >
              <IconTrash :size="14" />
            </button>
          </div>
        </div>
        <div v-if="col.books.length" class="flex flex-wrap gap-1.5">
          <span
            v-for="book in col.books"
            :key="book"
            class="max-w-[200px] truncate rounded-md px-2 py-0.5 text-[11px] font-medium text-[--t3]"
            style="background: rgba(255, 255, 255, 0.05)"
          >
            {{ book }}
          </span>
        </div>
        <p v-else class="flex items-center gap-1 text-[12px] text-[--t3]">
          <IconMusic :size="12" />
          Пусто
        </p>
      </div>
    </div>

    <!-- Create/Edit form -->
    <div v-if="showCreate" class="card p-5">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="text-[16px] font-semibold text-[--t1]">
          {{ editIdx !== null ? 'Редактировать' : 'Новая коллекция' }}
        </h2>
        <button
          class="rounded-lg p-1.5 text-[--t3] transition-colors hover:bg-white/5 hover:text-[--t2]"
          @click="closeForm"
        >
          <IconX :size="16" />
        </button>
      </div>

      <div class="mb-4">
        <label class="mb-1.5 block text-[12px] font-medium text-[--t2]">Название</label>
        <input v-model="formName" class="input w-full" placeholder="Моя подборка..." @keyup.enter="save" />
      </div>

      <div class="mb-4">
        <label class="mb-1.5 block text-[12px] font-medium text-[--t2]">Описание</label>
        <input v-model="formDesc" class="input w-full" placeholder="Необязательно..." />
      </div>

      <div class="mb-5">
        <label class="mb-2 block text-[12px] font-medium text-[--t2]">
          Книги
          <span v-if="formBooks.length" class="text-[--t3]">({{ formBooks.length }})</span>
        </label>
        <div class="max-h-60 space-y-1 overflow-y-auto">
          <button
            v-for="book in books"
            :key="book.id"
            class="flex w-full cursor-pointer items-center gap-2.5 rounded-lg border-0 bg-transparent px-2.5 py-2 text-left transition-colors hover:bg-white/[0.03]"
            :class="formBooks.includes(book.title) ? 'text-[--accent]' : 'text-[--t2]'"
            @click="toggleBook(book.title)"
          >
            <span
              class="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border"
              :class="
                formBooks.includes(book.title) ? 'border-[--accent] bg-[--accent]' : 'border-[--border] bg-transparent'
              "
            >
              <IconCheck v-if="formBooks.includes(book.title)" :size="10" class="text-black" />
            </span>
            <span class="truncate text-[13px]">{{ book.title }}</span>
            <span class="ml-auto flex-shrink-0 text-[11px] text-[--t3]">{{ book.author }}</span>
          </button>
        </div>
      </div>

      <div class="flex gap-2">
        <button class="btn btn-primary flex-1" @click="save">
          {{ editIdx !== null ? 'Сохранить' : 'Создать' }}
        </button>
        <button class="btn btn-ghost" @click="closeForm">Отмена</button>
      </div>
    </div>
  </div>
</template>
