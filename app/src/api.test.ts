import { describe, it, expect } from 'vitest'
import { audioUrl, coverUrl } from './api'

describe('audioUrl', () => {
  it('uses relative path', () => {
    expect(audioUrl('book-1', 2)).toBe('/api/audio/book-1/2')
  })
})

describe('coverUrl', () => {
  it('uses relative path', () => {
    expect(coverUrl('book-1')).toBe('/api/books/book-1/cover')
  })
})
