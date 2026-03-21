import { describe, it, expect, vi, beforeEach } from 'vitest'

let mountedCb: (() => void) | null = null
let unmountedCb: (() => void) | null = null

vi.mock('vue', async () => {
  const actual = await vi.importActual('vue')
  return {
    ...actual,
    onMounted: vi.fn((cb: () => void) => {
      mountedCb = cb
    }),
    onUnmounted: vi.fn((cb: () => void) => {
      unmountedCb = cb
    }),
  }
})

import { usePullToRefresh } from './usePullToRefresh'

function createTouchEvent(type: string, clientY: number): Event {
  const event = new Event(type, { bubbles: true })
  ;(event as unknown as Record<string, unknown>).touches = [{ clientY }]
  return event
}

describe('usePullToRefresh', () => {
  let onRefresh: ReturnType<typeof vi.fn>

  beforeEach(() => {
    mountedCb = null
    unmountedCb = null
    onRefresh = vi.fn(() => Promise.resolve())

    // Ensure scrollTop is 0 (at top of page)
    Object.defineProperty(document.documentElement, 'scrollTop', {
      value: 0,
      writable: true,
      configurable: true,
    })
  })

  function mount(refreshFn?: () => Promise<void>) {
    const result = usePullToRefresh((refreshFn ?? onRefresh) as () => Promise<void>)
    expect(mountedCb).toBeTypeOf('function')
    mountedCb!()
    return result
  }

  it('pullProgress updates on pull down from top', () => {
    const { pullProgress } = mount()

    document.dispatchEvent(createTouchEvent('touchstart', 100))
    document.dispatchEvent(createTouchEvent('touchmove', 140))

    // delta = 40, threshold = 80 → progress = 0.5
    expect(pullProgress.value).toBe(0.5)
  })

  it('pullProgress caps at 1', () => {
    const { pullProgress } = mount()

    document.dispatchEvent(createTouchEvent('touchstart', 100))
    document.dispatchEvent(createTouchEvent('touchmove', 300))

    // delta = 200, threshold = 80 → Math.min(200/80, 1) = 1
    expect(pullProgress.value).toBe(1)
  })

  it('triggers refresh when pulled past threshold and released', async () => {
    mount()

    document.dispatchEvent(createTouchEvent('touchstart', 100))
    document.dispatchEvent(createTouchEvent('touchmove', 200))
    document.dispatchEvent(new Event('touchend', { bubbles: true }))

    // Allow async onTouchEnd to run
    await vi.waitFor(() => {
      expect(onRefresh).toHaveBeenCalledTimes(1)
    })
  })

  it('does not trigger refresh when pulled less than threshold', async () => {
    mount()

    document.dispatchEvent(createTouchEvent('touchstart', 100))
    document.dispatchEvent(createTouchEvent('touchmove', 130))
    document.dispatchEvent(new Event('touchend', { bubbles: true }))

    // pullProgress = 30/80 = 0.375, which is < 1
    await Promise.resolve()
    expect(onRefresh).not.toHaveBeenCalled()
  })

  it('refreshing flag is true during refresh', async () => {
    let resolveRefresh: () => void
    const slowRefresh = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveRefresh = resolve
        }),
    )

    const { refreshing } = mount(slowRefresh)

    document.dispatchEvent(createTouchEvent('touchstart', 100))
    document.dispatchEvent(createTouchEvent('touchmove', 200))
    document.dispatchEvent(new Event('touchend', { bubbles: true }))

    // Allow the async handler to start
    await vi.waitFor(() => {
      expect(refreshing.value).toBe(true)
    })

    // Resolve the refresh
    resolveRefresh!()
    await vi.waitFor(() => {
      expect(refreshing.value).toBe(false)
    })
  })

  it('does not start pull when scrolled down', () => {
    const { pullProgress } = mount()

    // Simulate being scrolled down
    Object.defineProperty(document.documentElement, 'scrollTop', {
      value: 200,
      configurable: true,
    })

    document.dispatchEvent(createTouchEvent('touchstart', 100))
    document.dispatchEvent(createTouchEvent('touchmove', 200))

    expect(pullProgress.value).toBe(0)
  })

  it('upward pull cancels pulling state', () => {
    const { pullProgress } = mount()

    document.dispatchEvent(createTouchEvent('touchstart', 200))
    // Move down first
    document.dispatchEvent(createTouchEvent('touchmove', 240))
    expect(pullProgress.value).toBe(0.5)

    // Then move above start point (upward)
    document.dispatchEvent(createTouchEvent('touchmove', 190))
    expect(pullProgress.value).toBe(0)
  })

  it('removes event listeners on unmount', () => {
    mount()
    const removeSpy = vi.spyOn(document, 'removeEventListener')

    expect(unmountedCb).toBeTypeOf('function')
    unmountedCb!()

    const removedEvents = removeSpy.mock.calls.map((c) => c[0])
    expect(removedEvents).toContain('touchstart')
    expect(removedEvents).toContain('touchmove')
    expect(removedEvents).toContain('touchend')
  })
})
