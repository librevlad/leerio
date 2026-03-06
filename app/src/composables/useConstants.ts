import { ref } from 'vue'
import { api } from '../api'
import type { Constants } from '../types'

const constants = ref<Constants | null>(null)
const loading = ref(false)

export function useConstants() {
  async function load() {
    if (constants.value || loading.value) return
    loading.value = true
    try {
      constants.value = await api.getConstants()
    } catch {
      // Fallback defaults
      constants.value = {
        categories: [],
        status_style: {},
        action_styles: {},
        action_labels: {},
        list_to_status: {},
        label_to_folder: {},
        folder_to_label: {},
      }
    } finally {
      loading.value = false
    }
  }

  return { constants, load }
}
