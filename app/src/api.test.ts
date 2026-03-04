import { describe, it, expect, beforeEach } from 'vitest'
import { getServerUrl, setServerUrl, audioUrl, coverUrl } from './api'

describe('getServerUrl / setServerUrl', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns empty string by default', () => {
    expect(getServerUrl()).toBe('')
  })

  it('stores and retrieves a URL', () => {
    setServerUrl('http://localhost:8000')
    expect(getServerUrl()).toBe('http://localhost:8000')
  })

  it('strips trailing slashes', () => {
    setServerUrl('http://localhost:8000///')
    expect(getServerUrl()).toBe('http://localhost:8000')
  })

  it('clears on empty string', () => {
    setServerUrl('http://localhost:8000')
    setServerUrl('')
    expect(getServerUrl()).toBe('')
  })
})

describe('audioUrl', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('uses relative path when no server set', () => {
    expect(audioUrl('book-1', 2)).toBe('/api/audio/book-1/2')
  })

  it('uses server URL when set', () => {
    setServerUrl('http://myserver:8000')
    expect(audioUrl('book-1', 0)).toBe('http://myserver:8000/api/audio/book-1/0')
  })
})

describe('coverUrl', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('uses relative path when no server set', () => {
    expect(coverUrl('book-1')).toBe('/api/books/book-1/cover')
  })

  it('uses server URL when set', () => {
    setServerUrl('http://myserver:8000')
    expect(coverUrl('book-1')).toBe('http://myserver:8000/api/books/book-1/cover')
  })
})
