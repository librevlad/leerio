<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../../api'
import { useToast } from '../../composables/useToast'
import { IconX } from '../shared/icons'

const props = defineProps<{ title: string; tags: string[] }>()
const emit = defineEmits<{ updated: [tags: string[]] }>()

const toast = useToast()
const currentTags = ref<string[]>([...props.tags])
const allTags = ref<string[]>([])
const input = ref('')
const showSuggestions = ref(false)

onMounted(async () => {
  try {
    allTags.value = await api.getAllTags()
  } catch { /* ignore */ }
})

const suggestions = () => {
  if (!input.value) return allTags.value.filter(t => !currentTags.value.includes(t)).slice(0, 5)
  const q = input.value.toLowerCase()
  return allTags.value.filter(t => t.toLowerCase().includes(q) && !currentTags.value.includes(t)).slice(0, 5)
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
  currentTags.value = currentTags.value.filter(t => t !== tag)
  await save()
}

function hideSuggestions() {
  globalThis.setTimeout(() => { showSuggestions.value = false }, 200)
}

async function save() {
  try {
    await api.setTags(props.title, currentTags.value)
    emit('updated', currentTags.value)
  } catch {
    toast.error('Не удалось сохранить теги')
  }
}
</script>

<template>
  <div class="card p-5">
    <h3 class="section-label mb-3">Теги</h3>

    <div v-if="currentTags.length" class="flex flex-wrap gap-1.5 mb-3">
      <span
        v-for="tag in currentTags"
        :key="tag"
        class="group inline-flex items-center gap-1 px-3 py-1 text-[11px] font-medium rounded-full text-[--accent-2] transition-all duration-200"
        style="background: var(--accent-soft); border: 1px solid rgba(232,146,58,0.15)"
      >
        {{ tag }}
        <button
          class="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all cursor-pointer bg-transparent border-0 p-0 flex items-center text-[--accent-2]"
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
        class="absolute top-full left-0 right-0 mt-1.5 rounded-xl overflow-hidden z-10"
        style="background: var(--card-solid); border: 1px solid var(--border-light); box-shadow: 0 12px 40px rgba(0,0,0,0.5)"
      >
        <button
          v-for="s in suggestions()"
          :key="s"
          class="block w-full text-left px-3.5 py-2.5 text-[12px] hover:bg-white/5 transition-colors cursor-pointer bg-transparent border-0 text-[--t2] hover:text-[--t1]"
          @mousedown="addTag(s)"
        >
          {{ s }}
        </button>
      </div>
    </div>
  </div>
</template>
