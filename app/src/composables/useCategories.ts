import { ref, computed } from 'vue'
import { api } from '../api'
import type { Category } from '../types'

const categories = ref<Category[]>([])
const loaded = ref(false)

const FALLBACK_COLOR = '#94a3b8'
const FALLBACK_GRADIENT = 'linear-gradient(135deg, #334155 0%, #64748b 100%)'

export function useCategories() {
  async function load() {
    if (loaded.value) return
    try {
      categories.value = await api.getCategories()
      loaded.value = true
    } catch {
      /* keep existing */
    }
  }

  const byName = computed(() => {
    const map: Record<string, Category> = {}
    for (const c of categories.value) map[c.name] = c
    return map
  })

  function color(name: string): string {
    return byName.value[name]?.color ?? FALLBACK_COLOR
  }

  function gradient(name: string): string {
    return byName.value[name]?.gradient ?? FALLBACK_GRADIENT
  }

  return { categories, load, color, gradient, FALLBACK_COLOR, FALLBACK_GRADIENT }
}
