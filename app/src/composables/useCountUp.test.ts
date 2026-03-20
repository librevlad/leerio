import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick, effectScope } from 'vue'
import { useCountUp } from './useCountUp'

describe('useCountUp', () => {
  let rafCallbacks: ((time: number) => void)[]
  let currentTime: number
  let rafIdCounter: number

  beforeEach(() => {
    rafCallbacks = []
    currentTime = 0
    rafIdCounter = 0

    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn((cb: (time: number) => void) => {
        rafCallbacks.push(cb)
        return ++rafIdCounter
      }),
    )
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    vi.stubGlobal('performance', { now: () => currentTime })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  function flushRaf(time: number) {
    currentTime = time
    const cbs = [...rafCallbacks]
    rafCallbacks = []
    cbs.forEach((cb) => cb(time))
  }

  function runAnimationToEnd(duration: number) {
    // Run enough frames to complete the animation, starting from currentTime
    const startAt = currentTime
    for (let t = startAt + 16; t <= startAt + duration + 16; t += 16) {
      flushRaf(t)
    }
  }

  it('starts at "0" when target is null', async () => {
    const scope = effectScope()
    let display: ReturnType<typeof useCountUp> | undefined

    scope.run(() => {
      const target = ref<number | null>(null)
      display = useCountUp(target)
    })

    await nextTick()
    expect(display!.value).toBe('0')
    scope.stop()
  })

  it('animates toward target value', async () => {
    const scope = effectScope()
    let display: ReturnType<typeof useCountUp> | undefined

    scope.run(() => {
      const target = ref<number | null>(100)
      display = useCountUp(target, { duration: 600 })
    })

    await nextTick()

    // First frame at partial time — should be between 0 and 100
    flushRaf(300)
    const midValue = Number(display!.value)
    expect(midValue).toBeGreaterThan(0)
    expect(midValue).toBeLessThan(100)

    scope.stop()
  })

  it('reaches exact target at end of animation', async () => {
    const scope = effectScope()
    let display: ReturnType<typeof useCountUp> | undefined

    scope.run(() => {
      const target = ref<number | null>(42)
      display = useCountUp(target, { duration: 600 })
    })

    await nextTick()
    runAnimationToEnd(600)

    expect(display!.value).toBe('42')
    scope.stop()
  })

  it('supports decimal display', async () => {
    const scope = effectScope()
    let display: ReturnType<typeof useCountUp> | undefined

    scope.run(() => {
      const target = ref<number | null>(3.14)
      display = useCountUp(target, { duration: 600, decimals: 2 })
    })

    await nextTick()
    runAnimationToEnd(600)

    expect(display!.value).toBe('3.14')
    scope.stop()
  })

  it('cancels previous animation when target changes', async () => {
    const scope = effectScope()
    const target = ref<number | null>(100)
    let display: ReturnType<typeof useCountUp> | undefined

    scope.run(() => {
      display = useCountUp(target, { duration: 600 })
    })

    await nextTick()

    // Start animating toward 100
    flushRaf(300)
    const cancelSpy = vi.mocked(cancelAnimationFrame)
    const callsBefore = cancelSpy.mock.calls.length

    // Change target — should cancel previous animation
    target.value = 200
    await nextTick()

    expect(cancelSpy.mock.calls.length).toBeGreaterThan(callsBefore)

    // Complete new animation
    runAnimationToEnd(600)
    expect(display!.value).toBe('200')

    scope.stop()
  })

  it('cancels animation on scope dispose', async () => {
    const scope = effectScope()

    scope.run(() => {
      const target = ref<number | null>(100)
      useCountUp(target, { duration: 600 })
    })

    await nextTick()

    // Partially animate
    flushRaf(100)

    const cancelSpy = vi.mocked(cancelAnimationFrame)
    const callsBefore = cancelSpy.mock.calls.length

    scope.stop()

    expect(cancelSpy.mock.calls.length).toBeGreaterThan(callsBefore)
  })

  it('does nothing when target changes to null', async () => {
    const scope = effectScope()
    const target = ref<number | null>(50)
    let display: ReturnType<typeof useCountUp> | undefined

    scope.run(() => {
      display = useCountUp(target, { duration: 600 })
    })

    await nextTick()
    runAnimationToEnd(600)
    expect(display!.value).toBe('50')

    const rafSpy = vi.mocked(requestAnimationFrame)
    const callsBefore = rafSpy.mock.calls.length

    target.value = null
    await nextTick()

    // No new requestAnimationFrame calls for null target
    expect(rafSpy.mock.calls.length).toBe(callsBefore)
    scope.stop()
  })
})
