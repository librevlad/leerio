/**
 * Format file size in bytes to human-readable string.
 * Uses KB / MB / GB with consistent decimal places.
 */
export function formatSize(bytes: number, t: (key: string) => string): string {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' ' + t('common.kb')
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' ' + t('common.mb')
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' ' + t('common.gb')
}

/**
 * Format megabytes to human-readable string (e.g. 286.15 → "286.1 МБ" or "1.2 ГБ").
 */
export function formatSizeMB(mb: number, t: (key: string) => string): string {
  if (mb >= 1024) return (mb / 1024).toFixed(1) + ' ' + t('common.gb')
  return mb.toFixed(1) + ' ' + t('common.mb')
}

/**
 * Format track filename to readable chapter name.
 * Numeric-only filenames (e.g. "0101.mp3") → "Глава 1" via i18n.
 * Other filenames → strip extension.
 */
export function trackDisplayName(
  filename: string,
  index: number,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  const name = filename.replace(/\.\w+$/, '')
  if (/^\d+$/.test(name)) return t('book.chapterN', { n: index + 1 })
  return name
}
