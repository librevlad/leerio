import { describe, it, expect } from 'vitest'
import { dotColor } from './useStatusColors'

describe('dotColor', () => {
  it('has entries for all action types', () => {
    const expected = ['inbox', 'listen', 'phone', 'done', 'pause', 'reject', 'relisten', 'move', 'undo', 'delete']
    for (const key of expected) {
      expect(dotColor[key]).toBeDefined()
    }
  })

  it('all values are Tailwind bg- classes', () => {
    for (const value of Object.values(dotColor)) {
      expect(value).toMatch(/^bg-/)
    }
  })
})
