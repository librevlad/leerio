/**
 * Format file size in bytes to human-readable string.
 * Uses KB / MB / GB with consistent decimal places.
 */
export function formatSize(bytes: number, t: (key: string) => string): string {
  if (!isFinite(bytes) || bytes < 0) bytes = 0
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' ' + t('common.kb')
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' ' + t('common.mb')
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' ' + t('common.gb')
}

/**
 * Format megabytes to human-readable string (e.g. 286.15 → "286.1 МБ" or "1.2 ГБ").
 */
export function formatSizeMB(mb: number, t: (key: string) => string): string {
  if (!isFinite(mb) || mb < 0) mb = 0
  if (mb >= 1024) return (mb / 1024).toFixed(1) + ' ' + t('common.gb')
  return mb.toFixed(1) + ' ' + t('common.mb')
}

/**
 * Format remaining listening time from total hours and progress percentage.
 */
export function formatRemaining(totalHours: number, progress: number, t: (key: string) => string): string {
  if (!isFinite(totalHours) || totalHours < 0) totalHours = 0
  if (!isFinite(progress)) progress = 0
  const remaining = totalHours * (1 - Math.min(100, Math.max(0, progress)) / 100)
  if (remaining < 1 / 60) return `< 1 ${t('common.unitMin')}`
  if (remaining < 1) return `${Math.round(remaining * 60)} ${t('common.unitMin')}`
  const h = Math.floor(remaining)
  const m = Math.round((remaining - h) * 60)
  return m > 0 ? `${h}${t('common.unitH')} ${m}${t('common.unitM')}` : `${h}${t('common.unitH')}`
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
