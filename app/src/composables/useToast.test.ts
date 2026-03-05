import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useToast } from './useToast'

describe('useToast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // Clear any existing toasts
    const t = useToast()
    t.toasts.value = []
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('add() creates a toast with unique ID', () => {
    const t = useToast()
    t.add('msg1')
    t.add('msg2')
    expect(t.toasts.value).toHaveLength(2)
    expect(t.toasts.value[0]!.id).not.toBe(t.toasts.value[1]!.id)
  })

  it('remove() filters out toast by ID', () => {
    const t = useToast()
    t.add('msg')
    const id = t.toasts.value[0]!.id
    t.remove(id)
    expect(t.toasts.value).toHaveLength(0)
  })

  it('success() sets type to success', () => {
    const t = useToast()
    t.success('done')
    expect(t.toasts.value[0]!.type).toBe('success')
  })

  it('error() sets type to error', () => {
    const t = useToast()
    t.error('fail')
    expect(t.toasts.value[0]!.type).toBe('error')
  })

  it('info() sets type to info', () => {
    const t = useToast()
    t.info('note')
    expect(t.toasts.value[0]!.type).toBe('info')
  })

  it('warning() sets type to warning', () => {
    const t = useToast()
    t.warning('warn')
    expect(t.toasts.value[0]!.type).toBe('warning')
  })

  it('auto-dismisses after 3 seconds', () => {
    const t = useToast()
    t.add('temporary')
    expect(t.toasts.value).toHaveLength(1)
    vi.advanceTimersByTime(3000)
    expect(t.toasts.value).toHaveLength(0)
  })

  it('tracks multiple toasts independently', () => {
    const t = useToast()
    t.add('first')
    vi.advanceTimersByTime(1500)
    t.add('second')
    vi.advanceTimersByTime(1500)
    // First should be dismissed, second still there
    expect(t.toasts.value).toHaveLength(1)
    expect(t.toasts.value[0]!.message).toBe('second')
  })
})
