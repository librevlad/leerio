import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { LOCALES, type LocaleCode } from '../i18n'
import { STORAGE } from '../constants/storage'

export function useLocale() {
  const { locale } = useI18n()

  const currentLocale = computed(() => locale.value as LocaleCode)

  function setLocale(code: LocaleCode) {
    locale.value = code
    localStorage.setItem(STORAGE.LOCALE, code)
    document.documentElement.lang = code
  }

  return { currentLocale, setLocale, LOCALES }
}
