import { describe, it, expect, vi, beforeEach } from 'vitest'

let capturedOnUnmounted: (() => void) | null = null

vi.mock('vue', () => ({
  ref: (v: unknown) => ({ value: v }),
  onUnmounted: (cb: () => void) => {
    capturedOnUnmounted = cb
  },
}))

vi.mock('./useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  }),
}))

vi.mock('../i18n', () => ({
  default: {
    global: {
      t: (key: string) => key,
    },
  },
}))

describe('useNetwork', () => {
  beforeEach(() => {
    capturedOnUnmounted = null
    vi.resetModules()
    vi.restoreAllMocks()
  })

  it('isOnline reflects navigator.onLine initially', async () => {
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
    const { useNetwork } = await import('./useNetwork')
    const { isOnline } = useNetwork()
    expect(isOnline.value).toBe(true)
  })

  it('dispatching online event sets isOnline to true', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
    const { useNetwork } = await import('./useNetwork')
    const { isOnline } = useNetwork()
    expect(isOnline.value).toBe(false)

    window.dispatchEvent(new Event('online'))
    expect(isOnline.value).toBe(true)
  })

  it('dispatching offline event sets isOnline to false', async () => {
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
    const { useNetwork } = await import('./useNetwork')
    const { isOnline } = useNetwork()
    expect(isOnline.value).toBe(true)

    window.dispatchEvent(new Event('offline'))
    expect(isOnline.value).toBe(false)
  })

  it('onReconnect callbacks are called on online event', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
    const { useNetwork } = await import('./useNetwork')
    const { onReconnect } = useNetwork()

    const cb = vi.fn()
    onReconnect(cb)

    window.dispatchEvent(new Event('online'))
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('onReconnectPermanent adds permanent callbacks', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
    const { useNetwork, onReconnectPermanent } = await import('./useNetwork')
    useNetwork() // init

    const cb = vi.fn()
    onReconnectPermanent(cb)

    window.dispatchEvent(new Event('online'))
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('init() only runs once (singleton behavior)', async () => {
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
    const addEventSpy = vi.spyOn(window, 'addEventListener')

    const { useNetwork } = await import('./useNetwork')
    useNetwork()
    const callsAfterFirst = addEventSpy.mock.calls.length
    useNetwork()
    expect(addEventSpy.mock.calls.length).toBe(callsAfterFirst)
  })

  it('onReconnect callback is removed on unmount', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
    const { useNetwork } = await import('./useNetwork')
    const { onReconnect } = useNetwork()

    const cb = vi.fn()
    onReconnect(cb)

    // Simulate component unmount
    expect(capturedOnUnmounted).toBeTypeOf('function')
    capturedOnUnmounted!()

    window.dispatchEvent(new Event('online'))
    expect(cb).not.toHaveBeenCalled()
  })
})
