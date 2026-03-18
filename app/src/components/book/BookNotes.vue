<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDebounceFn } from '@vueuse/core'
import { api } from '../../api'
import { useToast } from '../../composables/useToast'
import { useLocalData } from '../../composables/useLocalData'
import { useAuth } from '../../composables/useAuth'

const { t } = useI18n()
const props = defineProps<{ bookId: string; title: string; note: string }>()
const toast = useToast()
const local = useLocalData()
const { isLoggedIn } = useAuth()

const text = ref(props.note)
const saving = ref(false)

// Load from local first, then use prop (server) as fallback
onMounted(async () => {
  const localNote = await local.getNote(props.bookId)
  if (localNote !== undefined) text.value = localNote
})

watch(
  () => props.note,
  (v) => {
    // Only update from server if we don't have local data
    if (v && !text.value) text.value = v
  },
)

const save = useDebounceFn(async (val: string) => {
  saving.value = true
  try {
    // Always save locally
    await local.setNote(props.bookId, val)
    // Sync to server if logged in
    if (isLoggedIn.value) {
      await api.setNote(props.bookId, val)
    }
  } catch {
    toast.error(t('book.noteSaveError'))
  } finally {
    saving.value = false
  }
}, 800)
</script>

<template>
  <div class="card p-5">
    <div class="mb-3 flex items-center justify-between">
      <h3 class="section-label">{{ t('book.notes') }}</h3>
      <Transition name="toast">
        <span v-if="saving" class="text-[11px] font-medium text-[--accent] opacity-70">
          {{ t('book.noteSaving') }}</span
        >
      </Transition>
    </div>
    <textarea
      v-model="text"
      rows="4"
      :placeholder="t('book.addNote')"
      class="input-field w-full resize-y p-3.5 text-[13px] leading-relaxed"
      @input="save(text)"
    />
  </div>
</template>
