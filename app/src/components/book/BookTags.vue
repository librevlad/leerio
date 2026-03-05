<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../../api'
import { useToast } from '../../composables/useToast'
import { IconX } from '../shared/icons'

const props = defineProps<{ bookId: string; title: string; tags: string[] }>()
const emit = defineEmits<{ updated: [tags: string[]] }>()

const toast = useToast()
const currentTags = ref<string[]>([...props.tags])
const allTags = ref<string[]>([])
const input = ref('')
const showSuggestions = ref(false)

onMounted(async () => {
  try {
    allTags.value = await api.getAllTags()
  } catch {
    /* ignore */
  }
})

const suggestions = () => {
  if (!input.value) return allTags.value.filter((t) => !currentTags.value.includes(t)).slice(0, 5)
  const q = input.value.toLowerCase()
  return allTags.value.filter((t) => t.toLowerCase().includes(q) && !currentTags.value.includes(t)).slice(0, 5)
}

async function addTag(tag: string) {
  const t = tag.trim()
  if (!t || currentTags.value.includes(t)) return
  currentTags.value.push(t)
  input.value = ''
  showSuggestions.value = false
  await save()
}

async function removeTag(tag: string) {
  currentTags.value = currentTags.value.filter((t) => t !== tag)
  await save()
}

function hideSuggestions() {
  globalThis.setTimeout(() => {
    showSuggestions.value = false
  }, 200)
}

async function save() {
  try {
    await api.setTags(props.bookId, currentTags.value)
    emit('updated', currentTags.value)
  } catch {
    toast.error('Не удалось сохранить теги')
  }
}
</script>

<template>
  <div class="card p-5">
    <h3 class="section-label mb-3">Теги</h3>

    <div v-if="currentTags.length" class="mb-3 flex flex-wrap gap-1.5">
      <span
        v-for="tag in currentTags"
        :key="tag"
        class="group inline-flex items-center gap-1 rounded-full px-3 py-1 text-[11px] font-medium text-[--accent-2] transition-all duration-200"
        style="background: var(--accent-soft); border: 1px solid rgba(232, 146, 58, 0.15)"
      >
        {{ tag }}
        <button
          class="flex cursor-pointer items-center border-0 bg-transparent p-0 text-[--accent-2] opacity-0 transition-all group-hover:opacity-100 hover:text-red-400"
          @click="removeTag(tag)"
        >
          <IconX :size="11" />
        </button>
      </span>
    </div>

    <div class="relative">
      <input
        v-model="input"
        type="text"
        placeholder="Добавить тег..."
        class="input-field w-full px-3.5 py-2 text-[12px]"
        @focus="showSuggestions = true"
        @blur="hideSuggestions"
        @keydown.enter="addTag(input)"
      />
      <div
        v-if="showSuggestions && suggestions().length"
        class="absolute top-full right-0 left-0 z-10 mt-1.5 overflow-hidden rounded-xl"
        style="
          background: var(--card-solid);
          border: 1px solid var(--border-light);
          box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
        "
      >
        <button
          v-for="s in suggestions()"
          :key="s"
          class="block w-full cursor-pointer border-0 bg-transparent px-3.5 py-2.5 text-left text-[12px] text-[--t2] transition-colors hover:bg-white/5 hover:text-[--t1]"
          @mousedown="addTag(s)"
        >
          {{ s }}
        </button>
      </div>
    </div>
  </div>
</template>
