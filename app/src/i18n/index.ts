import { createI18n } from 'vue-i18n'
import en from './locales/en'
import ru from './locales/ru'
import uk from './locales/uk'

export type LocaleCode = 'en' | 'ru' | 'uk'

export const LOCALES: { code: LocaleCode; label: string; flag: string }[] = [
  { code: 'en', label: 'English', flag: '🇬🇧' },
  { code: 'ru', label: 'Русский', flag: '🇷🇺' },
  { code: 'uk', label: 'Українська', flag: '🇺🇦' },
]

/**
 * Slavic plural rule for Russian and Ukrainian.
 * Returns 0 (one), 1 (few), or 2 (many).
 *
 * Used by vue-i18n's built-in t('key', count) pluralization.
 * For inline template pluralization with explicit word forms, use utils/plural.ts instead.
 */
function slavicPluralRule(choice: number): number {
  const abs = Math.abs(choice)
  const mod10 = abs % 10
  const mod100 = abs % 100
  if (mod10 === 1 && mod100 !== 11) return 0
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 1
  return 2
}

import { STORAGE } from '../constants/storage'

function detectLocale(): LocaleCode {
  const saved = localStorage.getItem(STORAGE.LOCALE) as LocaleCode | null
  if (saved && ['en', 'ru', 'uk'].includes(saved)) return saved
  const lang = navigator.language?.toLowerCase() || ''
  let detected: LocaleCode = 'en'
  if (lang.startsWith('ru')) detected = 'ru'
  else if (lang.startsWith('uk')) detected = 'uk'
  // Persist detected locale so subsequent page reloads are stable
  localStorage.setItem(STORAGE.LOCALE, detected)
  return detected
}

const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en',
  pluralRules: {
    ru: slavicPluralRule,
    uk: slavicPluralRule,
  },
  messages: { en, ru, uk },
})

export default i18n
