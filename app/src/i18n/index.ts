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
 */
function slavicPluralRule(choice: number): number {
  const abs = Math.abs(choice)
  const mod10 = abs % 10
  const mod100 = abs % 100
  if (mod10 === 1 && mod100 !== 11) return 0
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 1
  return 2
}

const savedLocale = (localStorage.getItem('leerio_locale') as LocaleCode) || 'ru'

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'ru',
  pluralRules: {
    ru: slavicPluralRule,
    uk: slavicPluralRule,
  },
  messages: { en, ru, uk },
})

export default i18n
