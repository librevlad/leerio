import { describe, it, expect } from 'vitest'
import { formatSize, formatSizeMB, formatRemaining, trackDisplayName } from './format'

const t = (key: string) => {
  const map: Record<string, string> = {
    'common.kb': 'КБ',
    'common.mb': 'МБ',
    'common.gb': 'ГБ',
    'common.unitMin': 'мин',
    'common.unitH': 'ч',
    'common.unitM': 'м',
  }
  return map[key] ?? key
}

const tChapter = (key: string, params?: Record<string, unknown>) => {
  if (key === 'book.chapterN') return `Глава ${params?.n}`
  return key
}

describe('formatSize', () => {
  it('formats bytes to KB', () => {
    expect(formatSize(512, t)).toBe('1 КБ')
    expect(formatSize(500 * 1024, t)).toBe('500 КБ')
  })

  it('formats bytes to MB', () => {
    expect(formatSize(5 * 1024 * 1024, t)).toBe('5.0 МБ')
    expect(formatSize(150.5 * 1024 * 1024, t)).toBe('150.5 МБ')
  })

  it('formats bytes to GB', () => {
    expect(formatSize(2 * 1024 * 1024 * 1024, t)).toBe('2.0 ГБ')
  })

  it('treats negative bytes as 0', () => {
    expect(formatSize(-1024, t)).toBe('0 КБ')
  })

  it('treats NaN as 0', () => {
    expect(formatSize(NaN, t)).toBe('0 КБ')
  })

  it('treats Infinity as 0', () => {
    expect(formatSize(Infinity, t)).toBe('0 КБ')
  })
})

describe('formatSizeMB', () => {
  it('formats MB', () => {
    expect(formatSizeMB(286.15, t)).toBe('286.1 МБ')
  })

  it('formats GB when >= 1024 MB', () => {
    expect(formatSizeMB(1500, t)).toBe('1.5 ГБ')
  })

  it('treats negative MB as 0', () => {
    expect(formatSizeMB(-50, t)).toBe('0.0 МБ')
  })

  it('treats NaN as 0', () => {
    expect(formatSizeMB(NaN, t)).toBe('0.0 МБ')
  })
})

describe('formatRemaining', () => {
  it('formats hours and minutes', () => {
    expect(formatRemaining(10, 50, t)).toBe('5ч')
  })

  it('formats minutes only when < 1 hour', () => {
    expect(formatRemaining(1, 50, t)).toBe('30 мин')
  })

  it('returns < 1 min for very small remaining', () => {
    expect(formatRemaining(0.01, 99, t)).toBe('< 1 мин')
  })

  it('handles 0% progress', () => {
    expect(formatRemaining(2, 0, t)).toBe('2ч')
  })

  it('includes minutes when not round hours', () => {
    expect(formatRemaining(3, 0, t)).toBe('3ч')
    expect(formatRemaining(2.5, 0, t)).toBe('2ч 30м')
  })

  it('treats negative totalHours as 0', () => {
    expect(formatRemaining(-5, 50, t)).toBe('< 1 мин')
  })

  it('treats NaN totalHours as 0', () => {
    expect(formatRemaining(NaN, 50, t)).toBe('< 1 мин')
  })

  it('clamps progress to 0-100', () => {
    expect(formatRemaining(10, 150, t)).toBe('< 1 мин')
    expect(formatRemaining(10, -50, t)).toBe('10ч')
  })
})

describe('trackDisplayName', () => {
  it('strips file extension', () => {
    expect(trackDisplayName('Chapter 1.mp3', 0, tChapter)).toBe('Chapter 1')
    expect(trackDisplayName('intro.m4a', 0, tChapter)).toBe('intro')
  })

  it('converts numeric filenames to chapter names', () => {
    expect(trackDisplayName('0001.mp3', 0, tChapter)).toBe('Глава 1')
    expect(trackDisplayName('05.mp3', 4, tChapter)).toBe('Глава 5')
  })

  it('preserves non-numeric filenames', () => {
    expect(trackDisplayName('My Chapter.mp3', 0, tChapter)).toBe('My Chapter')
  })
})
