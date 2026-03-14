import { ref, onUnmounted } from 'vue'
import { useToast } from './useToast'

const isOnline = ref(navigator.onLine)
const reconnectCallbacks: Array<() => void> = []
let initialized = false

function init() {
  if (initialized) return
  initialized = true

  const toast = useToast()

  window.addEventListener('online', () => {
    isOnline.value = true
    import('../i18n').then((m) => toast.success(m.default.global.t('common.online'))).catch(() => toast.success('Online'))
    reconnectCallbacks.forEach((cb) => cb())
  })

  window.addEventListener('offline', () => {
    isOnline.value = false
  })
}

export function useNetwork() {
  init()

  function onReconnect(callback: () => void) {
    reconnectCallbacks.push(callback)
    onUnmounted(() => {
      const idx = reconnectCallbacks.indexOf(callback)
      if (idx !== -1) reconnectCallbacks.splice(idx, 1)
    })
  }

  return { isOnline, onReconnect }
}
