<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { api, coverUrl } from '../../api'
import type { SimilarBook } from '../../types'
import CategoryBadge from '../shared/CategoryBadge.vue'

const props = defineProps<{ bookId: string }>()

const similar = ref<SimilarBook[]>([])
const loading = ref(true)
const coverErrors = reactive(new Set<string>())

const coverGradient: Record<string, string> = {
  Бизнес: 'linear-gradient(135deg, #92400e 0%, #d97706 100%)',
  Личные: 'linear-gradient(135deg, #4c1d95 0%, #7c3aed 100%)',
  Отношения: 'linear-gradient(135deg, #9d174d 0%, #db2777 100%)',
  Саморазвитие: 'linear-gradient(135deg, #9a5c16 0%, #E8923A 100%)',
  Художественная: 'linear-gradient(135deg, #155e75 0%, #0891b2 100%)',
  Языки: 'linear-gradient(135deg, #064e3b 0%, #059669 100%)',
}
const fallbackGradient = 'linear-gradient(135deg, #1e1b4b 0%, #4338ca 100%)'

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
        class="group flex items-center gap-3 rounded-xl px-3 py-2.5 no-underline transition-all hover:bg-white/[0.04]"
      >
        <!-- Mini cover or gradient swatch -->
        <div
          class="h-9 w-9 flex-shrink-0 overflow-hidden rounded-lg"
          :style="
            !(book.has_cover && !coverErrors.has(book.id))
              ? { background: coverGradient[book.category] || fallbackGradient }
              : {}
          "
        >
          <img
            v-if="book.has_cover && !coverErrors.has(book.id)"
            :src="coverUrl(book.id)"
            :alt="book.title"
            class="h-full w-full object-cover"
            @error="coverErrors.add(book.id)"
          />
        </div>
        <div class="min-w-0 flex-1">
          <p
            class="truncate text-[12px] font-semibold text-[--t2] transition-colors group-hover:text-[--t1]"
            :title="book.title"
          >
            {{ book.title }}
          </p>
          <p v-if="book.author" class="truncate text-[11px] text-[--t3]" :title="book.author">
            {{ book.author }}
          </p>
        </div>
        <CategoryBadge :category="book.category" />
      </router-link>
    </div>
  </div>
</template>
