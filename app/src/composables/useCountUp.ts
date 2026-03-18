import { ref, watch, type Ref } from 'vue'

/**
 * Animates a number from 0 to target value.
 * Returns a ref with the current display value (string).
 */
export function useCountUp(target: Ref<number | null>, options: { duration?: number; decimals?: number } = {}) {
  const { duration = 600, decimals = 0 } = options
  const display = ref('0')

  watch(
    target,
    (val) => {
      if (val === null || val === undefined) return
      const start = performance.now()
      const from = 0

      function tick(now: number) {
        const elapsed = now - start
        const progress = Math.min(elapsed / duration, 1)
        // ease-out cubic
        const eased = 1 - Math.pow(1 - progress, 3)
        const current = from + (val! - from) * eased
        display.value = decimals > 0 ? current.toFixed(decimals) : String(Math.round(current))
        if (progress < 1) requestAnimationFrame(tick)
      }
      requestAnimationFrame(tick)
    },
    { immediate: true },
  )

  return display
}
