import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api', () => ({
  api: { getCategories: vi.fn() },
}))

import { useCategories } from './useCategories'
import { api } from '../api'

const mockCategories = [
  { id: 1, name: 'Бизнес', color: '#f59e0b', gradient: 'linear-gradient(135deg, #f59e0b, #d97706)', sort_order: 1 },
  { id: 2, name: 'Языки', color: '#3b82f6', gradient: 'linear-gradient(135deg, #3b82f6, #2563eb)', sort_order: 2 },
]

describe('useCategories', () => {
  beforeEach(() => {
    vi.mocked(api.getCategories).mockReset()
    const c = useCategories()
    c.categories.value = []
  })

  it('color() returns category color', () => {
    const c = useCategories()
    c.categories.value = [...mockCategories]
    expect(c.color('Бизнес')).toBe('#f59e0b')
  })

  it('color() returns FALLBACK_COLOR for unknown category', () => {
    const c = useCategories()
    c.categories.value = [...mockCategories]
    expect(c.color('Несуществующая')).toBe(c.FALLBACK_COLOR)
  })

  it('gradient() returns category gradient', () => {
    const c = useCategories()
    c.categories.value = [...mockCategories]
    expect(c.gradient('Языки')).toBe('linear-gradient(135deg, #3b82f6, #2563eb)')
  })

  it('gradient() returns FALLBACK_GRADIENT for unknown category', () => {
    const c = useCategories()
    c.categories.value = [...mockCategories]
    expect(c.gradient('Несуществующая')).toBe(c.FALLBACK_GRADIENT)
  })
})

describe('useCategories load()', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('load() calls API and sets categories', async () => {
    vi.doMock('../api', () => ({
      api: { getCategories: vi.fn().mockResolvedValue(mockCategories) },
    }))
    const { useCategories: freshUseCategories } = await import('./useCategories')
    const { api: freshApi } = await import('../api')

    const c = freshUseCategories()
    await c.load()
    expect(freshApi.getCategories).toHaveBeenCalledOnce()
    expect(c.categories.value).toEqual(mockCategories)
  })

  it('load() skips if already loaded', async () => {
    const mockFn = vi.fn().mockResolvedValue(mockCategories)
    vi.doMock('../api', () => ({
      api: { getCategories: mockFn },
    }))
    const { useCategories: freshUseCategories } = await import('./useCategories')

    const c = freshUseCategories()
    await c.load()
    await c.load()
    expect(mockFn).toHaveBeenCalledOnce()
  })

  it('load() keeps existing categories on error', async () => {
    const existing = [mockCategories[0]!]
    vi.doMock('../api', () => ({
      api: { getCategories: vi.fn().mockRejectedValue(new Error('network')) },
    }))
    const { useCategories: freshUseCategories } = await import('./useCategories')

    const c = freshUseCategories()
    c.categories.value = existing
    await c.load()
    expect(c.categories.value).toEqual(existing)
  })
})
