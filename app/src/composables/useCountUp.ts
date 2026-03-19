import { ref, watch, onScopeDispose, type Ref } from 'vue'

/**
 * Animates a number from 0 to target value.
 * Returns a ref with the current display value (string).
 */
export function useCountUp(target: Ref<number | null>, options: { duration?: number; decimals?: number } = {}) {
  const { duration = 600, decimals = 0 } = options
  const display = ref('0')
  let rafId: number | null = null

  function cancel() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  }

  watch(
    target,
    (val) => {
      cancel()
      if (val === null || val === undefined) return
      const start = performance.now()

      function tick(now: number) {
        const elapsed = now - start
        const progress = Math.min(elapsed / duration, 1)
        const eased = 1 - Math.pow(1 - progress, 3)
        const current = val! * eased
        display.value = decimals > 0 ? current.toFixed(decimals) : String(Math.round(current))
        if (progress < 1) rafId = requestAnimationFrame(tick)
        else rafId = null
      }
      rafId = requestAnimationFrame(tick)
    },
    { immediate: true },
  )

  onScopeDispose(cancel)

  return display
}
