<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../../api'
import { useToast } from '../../composables/useToast'
import { useLocalData } from '../../composables/useLocalData'
import { useAuth } from '../../composables/useAuth'
import type { Quote } from '../../types'
import { IconX } from '../shared/icons'

const { t } = useI18n()
const props = defineProps<{ bookTitle: string; bookAuthor: string }>()
const toast = useToast()
const local = useLocalData()
const { isLoggedIn } = useAuth()

const allQuotes = ref<Quote[]>([])
const loading = ref(true)
const newText = ref('')
const adding = ref(false)

const quotes = computed(() => allQuotes.value.filter((q) => q.book === props.bookTitle))

onMounted(async () => {
  try {
    // Load local quotes first
    const localQuotes = await local.getQuotes()
    if (localQuotes.length) allQuotes.value = localQuotes

    // Merge with server if logged in
    if (isLoggedIn.value) {
      const serverQuotes = await api.getQuotes()
      allQuotes.value = serverQuotes
    }
  } catch {
    /* use local data */
  } finally {
    loading.value = false
  }
})

async function addQuote() {
  const text = newText.value.trim()
  if (!text) return
  adding.value = true
  try {
    const quote = await local.addQuote({
      text,
      book: props.bookTitle,
      author: props.bookAuthor,
      ts: new Date().toISOString(),
    })
    allQuotes.value.push(quote)
    if (isLoggedIn.value) {
      await api.addQuote(text, props.bookTitle, props.bookAuthor)
    }
    newText.value = ''
    toast.success(t('book.quoteAdded'))
  } catch {
    toast.error(t('book.quoteAddError'))
  } finally {
    adding.value = false
  }
}

async function removeQuote(quoteId: number) {
  try {
    await local.deleteQuote(quoteId)
    allQuotes.value = allQuotes.value.filter((q) => q.id !== quoteId)
    if (isLoggedIn.value) {
      await api.deleteQuote(quoteId)
    }
  } catch {
    toast.error(t('book.quoteDeleteError'))
  }
}
</script>

<template>
  <div class="card p-5">
    <h3 class="section-label mb-3">{{ t('book.quotes') }}</h3>

    <div v-if="loading" class="space-y-2">
      <div class="skeleton h-12 rounded-xl" />
    </div>

    <div v-else>
      <!-- Existing quotes -->
      <div v-if="quotes.length" class="mb-3 space-y-2">
        <div
          v-for="q in quotes"
          :key="q.id"
          class="group relative rounded-xl px-4 py-3 text-[13px] leading-relaxed text-[--t2] italic"
          style="background: rgba(232, 146, 58, 0.05); border-left: 2px solid var(--accent)"
        >
          <button
            class="absolute top-2 right-2 cursor-pointer border-0 bg-transparent p-0.5 text-[--t3] opacity-0 transition-opacity group-hover:opacity-100 hover:text-red-400"
            :aria-label="t('book.deleteQuoteAria')"
            @click="removeQuote(q.id)"
          >
            <IconX :size="12" />
          </button>
          "{{ q.text }}"
          <p v-if="q.ts" class="mt-1 text-[10px] text-[--t3] not-italic">
            {{ new Date(q.ts).toLocaleDateString('ru', { day: 'numeric', month: 'short' }) }}
          </p>
        </div>
      </div>

      <!-- Add new quote -->
      <div class="flex gap-2">
        <textarea
          v-model="newText"
          rows="2"
          :placeholder="t('book.addQuote')"
          class="input-field flex-1 resize-none px-3.5 py-2.5 text-[12px]"
          @keydown.ctrl.enter="addQuote"
        />
        <button class="btn btn-ghost flex-shrink-0 self-end" :disabled="adding || !newText.trim()" @click="addQuote">
          {{ adding ? t('book.adding') : t('book.add') }}
        </button>
      </div>
    </div>
  </div>
</template>
