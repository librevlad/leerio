<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, coverUrl } from '../api'
import { useBooks } from '../composables/useBooks'
import { useToast } from '../composables/useToast'
import type { Collection, Book } from '../types'
import { IconPlus, IconTrash, IconEdit, IconX, IconCheck, IconBookmark, IconSearch } from '../components/shared/icons'
import EmptyState from '../components/shared/EmptyState.vue'

const { t } = useI18n()
const toast = useToast()
const { books, load: loadBooks } = useBooks()

const collections = ref<Collection[]>([])
const loading = ref(true)
const showCreate = ref(false)
const editId = ref<number | null>(null)
const expandedIdx = ref<number | null>(null)
const coverErrors = reactive(new Set<string>())

// Form state
const formName = ref('')
const formDesc = ref('')
const formBooks = ref<number[]>([])
const bookSearch = ref('')

// Map book IDs to Book objects for covers/links
function bookById(id: number): Book | undefined {
  return books.value.find((b) => b.id === String(id))
}

const filteredBooks = computed(() => {
  const q = bookSearch.value.toLowerCase().trim()
  if (!q) return books.value
  return books.value.filter((b) => b.title.toLowerCase().includes(q) || b.author.toLowerCase().includes(q))
})

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
  bookSearch.value = ''
  editId.value = null
  showCreate.value = true
}

function openEdit(col: Collection) {
  formName.value = col.name
  formDesc.value = col.description
  formBooks.value = [...col.books]
  bookSearch.value = ''
  editId.value = col.id
  showCreate.value = true
}

function closeForm() {
  showCreate.value = false
  editId.value = null
}

function toggleBook(bookId: number) {
  const i = formBooks.value.indexOf(bookId)
  if (i >= 0) {
    formBooks.value.splice(i, 1)
  } else {
    formBooks.value.push(bookId)
  }
}

function toggleExpand(idx: number) {
  expandedIdx.value = expandedIdx.value === idx ? null : idx
}

async function save() {
  if (!formName.value.trim()) {
    toast.error('Введите название')
    return
  }
  try {
    if (editId.value !== null) {
      await api.updateCollection(editId.value, formName.value.trim(), formBooks.value, formDesc.value.trim())
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

async function remove(col: Collection) {
  if (!confirm(t('collections.deleteConfirm', { name: col.name }))) return
  try {
    await api.deleteCollection(col.id)
    toast.success('Удалено')
    expandedIdx.value = null
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
        <h1 class="page-title">{{ t('collections.title') }}</h1>
        <p class="mt-1 text-[13px] text-[--t3]">
          {{
            collections.length > 0
              ? `${collections.length} ${t('plural.collection', collections.length)}`
              : t('collections.groupHint')
          }}
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
      :title="t('collections.emptyTitle')"
      :description="t('collections.emptyDesc')"
      :action-label="t('collections.emptyAction')"
      @action="openCreate"
    />

    <!-- Collections list -->
    <div v-else-if="!showCreate" class="space-y-4">
      <div v-for="(col, idx) in collections" :key="col.id" class="card card-hover overflow-hidden">
        <!-- Collection header — clickable to expand -->
        <button
          class="flex w-full cursor-pointer items-center gap-4 border-0 bg-transparent p-4 text-left transition-colors hover:bg-white/[0.02]"
          @click="toggleExpand(idx)"
        >
          <!-- Cover stack preview -->
          <div class="relative h-14 w-14 flex-shrink-0">
            <template v-if="col.books.length">
              <div
                v-for="(bookId, i) in col.books.slice(0, 3)"
                :key="bookId"
                class="absolute overflow-hidden rounded-lg shadow-md"
                :style="{
                  width: '40px',
                  height: '40px',
                  top: i * 4 + 'px',
                  left: i * 6 + 'px',
                  zIndex: 3 - i,
                }"
              >
                <img
                  v-if="bookById(bookId)?.has_cover && !coverErrors.has(String(bookId))"
                  :src="coverUrl(bookById(bookId)!.id)"
                  :alt="bookById(bookId)?.title ?? ''"
                  class="h-full w-full object-cover"
                  @error="coverErrors.add(String(bookId))"
                />
                <div
                  v-else
                  class="flex h-full w-full items-center justify-center text-[12px] font-bold text-white/50"
                  style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%)"
                >
                  {{ (bookById(bookId)?.title ?? '?').charAt(0) }}
                </div>
              </div>
            </template>
            <div
              v-else
              class="flex h-14 w-14 items-center justify-center rounded-xl"
              style="background: rgba(255, 255, 255, 0.04)"
            >
              <IconBookmark :size="20" class="text-[--t3]" />
            </div>
          </div>

          <!-- Info -->
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <h3 class="truncate text-[14px] font-semibold text-[--t1]">{{ col.name }}</h3>
              <span
                class="flex-shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-medium text-[--t3]"
                style="background: rgba(255, 255, 255, 0.05)"
              >
                {{ col.books.length }}
              </span>
            </div>
            <p v-if="col.description" class="mt-0.5 line-clamp-1 text-[12px] text-[--t3]">{{ col.description }}</p>
          </div>

          <!-- Actions -->
          <div class="ml-2 flex flex-shrink-0 gap-1" @click.stop>
            <button
              class="rounded-lg p-2 text-[--t3] transition-colors hover:bg-white/5 hover:text-[--t2]"
              :aria-label="t('collections.editAriaLabel')"
              @click="openEdit(col)"
            >
              <IconEdit :size="14" />
            </button>
            <button
              class="rounded-lg p-2 text-[--t3] transition-colors hover:bg-red-500/15 hover:text-red-400"
              :aria-label="t('collections.deleteAriaLabel')"
              @click="remove(col)"
            >
              <IconTrash :size="14" />
            </button>
          </div>

          <!-- Chevron -->
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="flex-shrink-0 text-[--t3] transition-transform duration-200"
            :class="expandedIdx === idx ? 'rotate-180' : ''"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>

        <!-- Expanded: book grid -->
        <div v-if="expandedIdx === idx" class="border-t px-4 pt-4 pb-4" style="border-color: var(--border)">
          <div v-if="col.books.length" class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <router-link
              v-for="bookId in col.books"
              :key="bookId"
              :to="bookById(bookId) ? `/book/${bookById(bookId)!.id}` : '#'"
              class="group flex items-center gap-3 rounded-xl p-2.5 no-underline transition-colors hover:bg-white/[0.04]"
            >
              <div class="h-12 w-12 flex-shrink-0 overflow-hidden rounded-lg">
                <img
                  v-if="bookById(bookId)?.has_cover && !coverErrors.has(String(bookId))"
                  :src="coverUrl(bookById(bookId)!.id)"
                  :alt="bookById(bookId)?.title ?? ''"
                  class="h-full w-full object-cover"
                  @error="coverErrors.add(String(bookId))"
                />
                <div
                  v-else
                  class="flex h-full w-full items-center justify-center text-[14px] font-bold text-white/50"
                  style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%)"
                >
                  {{ (bookById(bookId)?.title ?? '?').charAt(0) }}
                </div>
              </div>
              <div class="min-w-0">
                <p class="line-clamp-2 text-[12px] font-medium text-[--t2] transition-colors group-hover:text-[--t1]">
                  {{ bookById(bookId)?.title ?? 'Неизвестная книга' }}
                </p>
                <p v-if="bookById(bookId)" class="mt-0.5 line-clamp-1 text-[11px] text-[--t3]">
                  {{ bookById(bookId)!.author }}
                </p>
              </div>
            </router-link>
          </div>
          <p v-else class="py-4 text-center text-[13px] text-[--t3]">{{ t('collections.noBooksInCollection') }}</p>
        </div>
      </div>
    </div>

    <!-- Create/Edit form (dialog overlay) -->
    <Teleport to="body">
      <transition name="dialog">
        <div
          v-if="showCreate"
          class="dialog-overlay fixed inset-0 z-50 flex items-center justify-center p-4"
          @click.self="closeForm"
        >
          <div
            class="dialog-panel flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden sm:max-h-[90vh]"
            @click.stop
          >
            <!-- Sticky header -->
            <div class="flex items-center justify-between px-6 pt-6 pb-4 sm:px-6 sm:pt-6">
              <h2 class="text-[18px] font-bold text-[--t1]">
                {{ editId !== null ? t('collections.editCollection') : t('collections.newCollection') }}
              </h2>
              <button
                class="rounded-lg p-1.5 text-[--t3] transition-colors hover:bg-white/5 hover:text-[--t2]"
                @click="closeForm"
              >
                <IconX :size="18" />
              </button>
            </div>

            <!-- Scrollable body -->
            <div class="flex-1 overflow-y-auto px-6">
              <div class="mb-4">
                <label class="mb-1.5 block text-[12px] font-medium text-[--t2]">{{ t('collections.labelName') }}</label>
                <input
                  v-model="formName"
                  class="input-field w-full px-3.5 py-2.5"
                  :placeholder="t('collections.placeholderName')"
                  @keyup.enter="save"
                />
              </div>

              <div class="mb-4">
                <label class="mb-1.5 block text-[12px] font-medium text-[--t2]">{{ t('collections.labelDesc') }}</label>
                <input v-model="formDesc" class="input-field w-full px-3.5 py-2.5" :placeholder="t('collections.placeholderDesc')" />
              </div>

              <div class="mb-2">
                <label class="mb-2 block text-[12px] font-medium text-[--t2]">
                  Книги
                  <span v-if="formBooks.length" class="text-[--accent]">({{ formBooks.length }})</span>
                </label>

                <!-- Search -->
                <div class="relative mb-2">
                  <IconSearch
                    :size="14"
                    class="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-[--t3]"
                  />
                  <input
                    v-model="bookSearch"
                    class="input-field w-full py-2 pr-3 pl-8 text-[13px]"
                    :placeholder="t('collections.searchBooks')"
                  />
                </div>

                <!-- Selected books preview -->
                <div v-if="formBooks.length && !bookSearch" class="mb-2 flex flex-wrap gap-1.5">
                  <span
                    v-for="bookId in formBooks"
                    :key="bookId"
                    class="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-[--accent]"
                    style="background: var(--accent-soft)"
                  >
                    {{
                      (() => {
                        const t = bookById(bookId)?.title ?? 'Книга #' + bookId
                        return t.length > 25 ? t.slice(0, 25) + '...' : t
                      })()
                    }}
                    <button
                      class="ml-0.5 cursor-pointer border-0 bg-transparent p-0 text-[--accent] hover:text-white"
                      @click="toggleBook(bookId)"
                    >
                      <IconX :size="10" />
                    </button>
                  </span>
                </div>

                <!-- Book list -->
                <div
                  class="max-h-48 space-y-0.5 overflow-y-auto rounded-lg border p-1 sm:max-h-56"
                  style="border-color: var(--border)"
                >
                  <button
                    v-for="book in filteredBooks"
                    :key="book.id"
                    class="flex w-full cursor-pointer items-center gap-2.5 rounded-lg border-0 bg-transparent px-2.5 py-2 text-left transition-colors hover:bg-white/[0.04]"
                    :class="formBooks.includes(Number(book.id)) ? 'text-[--accent]' : 'text-[--t2]'"
                    @click="toggleBook(Number(book.id))"
                  >
                    <span
                      class="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border"
                      :class="
                        formBooks.includes(Number(book.id))
                          ? 'border-[--accent] bg-[--accent]'
                          : 'border-[--border] bg-transparent'
                      "
                    >
                      <IconCheck v-if="formBooks.includes(Number(book.id))" :size="10" class="text-black" />
                    </span>
                    <div class="h-7 w-7 flex-shrink-0 overflow-hidden rounded">
                      <img
                        v-if="book.has_cover && !coverErrors.has(book.id)"
                        :src="coverUrl(book.id)"
                        :alt="book.title"
                        class="h-full w-full object-cover"
                        @error="coverErrors.add(book.id)"
                      />
                      <div
                        v-else
                        class="flex h-full w-full items-center justify-center text-[9px] font-bold text-white/40"
                        style="background: rgba(255, 255, 255, 0.06)"
                      >
                        {{ book.title.charAt(0) }}
                      </div>
                    </div>
                    <span class="min-w-0 flex-1 truncate text-[13px]">{{ book.title }}</span>
                    <span v-if="book.author" class="ml-auto hidden flex-shrink-0 text-[11px] text-[--t3] sm:inline">{{
                      book.author
                    }}</span>
                  </button>
                  <p v-if="!filteredBooks.length" class="py-4 text-center text-[12px] text-[--t3]">Ничего не найдено</p>
                </div>
              </div>
            </div>

            <!-- Sticky footer -->
            <div class="flex gap-2 px-6 pt-4 pb-6">
              <button class="btn btn-primary flex-1" @click="save">
                {{ editId !== null ? t('collections.save') : t('collections.create') }}
              </button>
              <button class="btn btn-ghost" @click="closeForm">{{ t('collections.cancel') }}</button>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>
  </div>
</template>
