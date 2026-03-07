<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { api, coverUrl } from '../../api'
import type { SimilarBook } from '../../types'
import { useCategories } from '../../composables/useCategories'

const props = defineProps<{ bookId: string }>()

const similar = ref<SimilarBook[]>([])
const loading = ref(true)
const coverErrors = reactive(new Set<string>())
const { gradient: catGradient } = useCategories()

onMounted(async () => {
  if (props.bookId.startsWith('ub:') || props.bookId.startsWith('lb:')) {
    loading.value = false
    return
  }
  try {
    similar.value = await api.getSimilar(props.bookId)
  } catch {
    /* ignore */
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-if="loading" class="card p-5">
    <div class="skeleton mb-4 h-4 w-28 rounded-lg" />
    <div class="flex gap-3 overflow-hidden">
      <div v-for="i in 4" :key="i" class="skeleton h-44 w-28 shrink-0 rounded-xl" />
    </div>
  </div>
  <div v-else-if="similar.length" class="card p-5">
    <h3 class="section-label mb-4">Похожие книги</h3>
    <div class="scrollbar-hide -mx-1 flex gap-3 overflow-x-auto px-1 pb-1">
      <router-link
        v-for="book in similar"
        :key="book.id"
        :to="`/book/${book.id}`"
        class="group flex w-[120px] shrink-0 flex-col no-underline transition-transform hover:scale-[1.02]"
      >
        <!-- Cover -->
        <div
          class="mb-2 h-[160px] w-full overflow-hidden rounded-lg shadow-md"
          :style="!(book.has_cover && !coverErrors.has(book.id)) ? { background: catGradient(book.category) } : {}"
        >
          <img
            v-if="book.has_cover && !coverErrors.has(book.id)"
            :src="coverUrl(book.id)"
            :alt="book.title"
            class="h-full w-full object-cover"
            @error="coverErrors.add(book.id)"
          />
        </div>
        <p
          class="line-clamp-2 text-[12px] leading-tight font-semibold text-[--t2] transition-colors group-hover:text-[--t1]"
          :title="book.title"
        >
          {{ book.title }}
        </p>
        <p v-if="book.author" class="mt-0.5 truncate text-[11px] text-[--t3]" :title="book.author">
          {{ book.author }}
        </p>
      </router-link>
    </div>
  </div>
</template>
