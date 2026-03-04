import { ref } from 'vue'
import { api } from '../api'
import type { AnalyticsData, Achievement } from '../types'

const data = ref<AnalyticsData | null>(null)
const achievements = ref<Achievement[]>([])
const loading = ref(false)

export function useAnalytics() {
  async function load() {
    loading.value = true
    try {
      const [analytics, badges] = await Promise.all([
        api.getAnalytics(),
        api.getAchievements(),
      ])
      data.value = analytics
      achievements.value = badges
    } catch {
      data.value = null
      achievements.value = []
    } finally {
      loading.value = false
    }
  }

  return { data, achievements, loading, load }
}
