import { ref, onMounted, onUnmounted } from 'vue'

export function usePullToRefresh(onRefresh: () => Promise<void>) {
  const refreshing = ref(false)
  const pullProgress = ref(0) // 0-1, visible pull indicator

  let startY = 0
  let pulling = false
  const threshold = 80

  function getScrollTop(): number {
    const main = document.querySelector('main')
    return main ? main.scrollTop : document.documentElement.scrollTop
  }

  function onTouchStart(e: TouchEvent) {
    const touch = e.touches[0]
    if (touch && getScrollTop() <= 0 && !refreshing.value) {
      startY = touch.clientY
      pulling = true
      pullProgress.value = 0
    }
  }

  function onTouchMove(e: TouchEvent) {
    if (!pulling || refreshing.value) return
    const touch = e.touches[0]
    if (!touch) return
    const delta = touch.clientY - startY
    if (delta > 0) {
      pullProgress.value = Math.min(delta / threshold, 1)
    } else {
      pulling = false
      pullProgress.value = 0
    }
  }

  async function onTouchEnd() {
    if (!pulling) return
    if (pullProgress.value >= 1 && !refreshing.value) {
      refreshing.value = true
      pullProgress.value = 1
      try {
        await onRefresh()
      } finally {
        refreshing.value = false
      }
    }
    pulling = false
    pullProgress.value = 0
  }

  onMounted(() => {
    document.addEventListener('touchstart', onTouchStart, { passive: true })
    document.addEventListener('touchmove', onTouchMove, { passive: true })
    document.addEventListener('touchend', onTouchEnd)
  })

  onUnmounted(() => {
    document.removeEventListener('touchstart', onTouchStart)
    document.removeEventListener('touchmove', onTouchMove)
    document.removeEventListener('touchend', onTouchEnd)
  })

  return { refreshing, pullProgress }
}
