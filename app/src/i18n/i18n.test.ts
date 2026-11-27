import { describe, it, expect } from 'vitest'
import en from './locales/en'
import ru from './locales/ru'
import uk from './locales/uk'
import i18n from './index'

function flatKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k
    return typeof v === 'object' && v !== null ? flatKeys(v as Record<string, unknown>, key) : [key]
  })
}

describe('i18n locale key parity', () => {
  const enKeys = new Set(flatKeys(en))
  const ruKeys = new Set(flatKeys(ru))
  const ukKeys = new Set(flatKeys(uk))

  it('ru has all keys from en', () => {
    const missing = [...enKeys].filter((k) => !ruKeys.has(k))
    expect(missing, `Missing in ru: ${missing.join(', ')}`).toEqual([])
  })

  it('uk has all keys from en', () => {
    const missing = [...enKeys].filter((k) => !ukKeys.has(k))
    expect(missing, `Missing in uk: ${missing.join(', ')}`).toEqual([])
  })

  it('en has all keys from ru', () => {
    const missing = [...ruKeys].filter((k) => !enKeys.has(k))
    expect(missing, `Missing in en: ${missing.join(', ')}`).toEqual([])
  })

  it('all locales have the same number of keys', () => {
    expect(enKeys.size).toBe(ruKeys.size)
    expect(enKeys.size).toBe(ukKeys.size)
  })
})

describe('plural forms', () => {
  const t = (locale: 'en' | 'ru' | 'uk', key: string, n: number) => {
    i18n.global.locale.value = locale
    return i18n.global.t(key, n)
  }

  it('counts books, tracks and chapters', () => {
    expect(t('ru', 'scan.addN', 1)).toBe('Добавить 1 книгу')
    expect(t('ru', 'scan.addN', 3)).toBe('Добавить 3 книги')
    expect(t('ru', 'scan.found', 15)).toBe('Найдено 15 книг')
    expect(t('ru', 'scan.tracks', 61)).toBe('61 трек')
    expect(t('uk', 'scan.tracks', 22)).toBe('22 треки')
    expect(t('uk', 'scan.added', 11)).toBe('Додано 11 книг')
    expect(t('en', 'scan.found', 1)).toBe('Found 1 book')
    expect(t('en', 'scan.addN', 2)).toBe('Add 2 books')
    expect(t('ru', 'narrate.chapters', 2)).toBe('2 главы')
    expect(t('ru', 'book.tracks', 2)).toBe('2 трека')
    expect(t('uk', 'book.tracks', 5)).toBe('5 треків')
    expect(t('en', 'book.tracks', 1)).toBe('1 track')
  })
})
