import { describe, it, expect } from 'vitest'
import en from './locales/en'
import ru from './locales/ru'
import uk from './locales/uk'

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
