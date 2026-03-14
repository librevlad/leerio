/**
 * Russian pluralization: picks the correct word form based on count.
 * Usage: plural(n, 'книга', 'книги', 'книг') → "книга" / "книги" / "книг"
 *
 * Note: this is intentionally separate from the slavicPluralRule in i18n/index.ts.
 * slavicPluralRule is used by vue-i18n's t('key', count) pipe syntax (returns an index 0/1/2),
 * while this helper returns the actual word form directly — useful in templates where
 * inline pluralization with explicit forms is simpler than defining i18n message keys.
 */
export function plural(n: number, one: string, few: string, many: string): string {
  const abs = Math.abs(n)
  const mod10 = abs % 10
  const mod100 = abs % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few
  return many
}
