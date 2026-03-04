<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../../api'
import type { SimilarBook } from '../../types'
import CategoryBadge from '../shared/CategoryBadge.vue'

const props = defineProps<{ bookId: string }>()

const similar = ref<SimilarBook[]>([])
const loading = ref(true)

const coverGradient: Record<string, string> = {
  'Бизнес':         'linear-gradient(135deg, #92400e 0%, #d97706 100%)',
  'Отношения':      'linear-gradient(135deg, #9d174d 0%, #db2777 100%)',
  'Саморазвитие':   'linear-gradient(135deg, #5b21b6 0%, #7c3aed 100%)',
  'Художественная': 'linear-gradient(135deg, #155e75 0%, #0891b2 100%)',
  'Языки':          'linear-gradient(135deg, #064e3b 0%, #059669 100%)',
}
const fallbackGradient = 'linear-gradient(135deg, #1e1b4b 0%, #4338ca 100%)'

onMounted(async () => {
  try {
    similar.value = await api.getSimilar(props.bookId)
  } catch { /* ignore */ }
  finally { loading.value = false }
})
</script>

<template>
  <div v-if="loading" class="card p-5">
    <div class="skeleton h-4 w-28 mb-4 rounded-lg" />
    <div class="space-y-2.5">
      <div v-for="i in 3" :key="i" class="skeleton h-14 rounded-xl" />
    </div>
  </div>
  <div v-else-if="similar.length" class="card p-5">
    <h3 class="section-label mb-4">Похожие книги</h3>
    <div class="space-y-2">
      <router-link
        v-for="book in similar"
        :key="book.id"
        :to="`/book/${book.id}`"
        class="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/[0.04] transition-all no-underline group"
      >
        <!-- Mini gradient swatch -->
        <div
          class="w-9 h-9 rounded-lg flex-shrink-0"
          :style="{ background: coverGradient[book.category] || fallbackGradient }"
        />
        <div class="flex-1 min-w-0">
          <p class="text-[12px] font-semibold truncate text-[--t2] group-hover:text-[--t1] transition-colors" :title="book.title">
            {{ book.title }}
          </p>
          <p class="text-[11px] truncate text-[--t3]" :title="book.author">{{ book.author }}</p>
        </div>
        <CategoryBadge :category="book.category" />
      </router-link>
    </div>
  </div>
</template>
