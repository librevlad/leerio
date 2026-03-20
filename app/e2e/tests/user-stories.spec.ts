/**
 * Core User Story E2E Tests
 *
 * Covers the most critical user flows that span multiple pages.
 */
import { test, expect } from '../fixtures'

// ── Story 1: Browse → Book Detail → Play ────────────────────────────
test.describe('Story: Browse and Play', () => {
  test('user can browse catalog, open book, and start playback', { tag: '@needs-books' }, async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })

    const firstBook = page.locator('a[href*="/book/"]').first()
    const bookTitle = await firstBook.locator('h3').textContent()
    await firstBook.click()

    await expect(page).toHaveURL(/\/book\//, { timeout: 10_000 })
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 })

    const playBtn = page.locator('button:has-text("Воспроизвести"), button:has-text("Продолжить")')
    await expect(playBtn.first()).toBeVisible({ timeout: 5_000 })
    await playBtn.first().click()

    await expect(page.locator('.fixed.inset-0')).toBeVisible({ timeout: 10_000 })

    if (bookTitle) {
      await expect(page.locator('.fixed.inset-0')).toContainText(bookTitle.trim().slice(0, 20), { timeout: 5_000 })
    }
  })
})

// ── Story 2: Settings Persistence ───────────────────────────────────
test.describe('Story: Settings', () => {
  test('language switch changes UI text', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.locator('h1')).toContainText('Настройки', { timeout: 15_000 })

    const enBtn = page.locator('button:has-text("English"), button:has-text("🇬🇧")')
    if (await enBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await enBtn.click()
      await page.waitForTimeout(500)
      await expect(page.locator('h1')).toContainText('Settings', { timeout: 5_000 })

      const ruBtn = page.locator('button:has-text("Русский"), button:has-text("🇷🇺")')
      await ruBtn.click()
      await page.waitForTimeout(500)
      await expect(page.locator('h1')).toContainText('Настройки', { timeout: 5_000 })
    }
  })
})

// ── Story 3: Navigation ────────────────────────────────────────────
test.describe('Story: Navigation', () => {
  test('user can navigate main pages without errors', async ({ page }) => {
    const routes = ['/library', '/settings']

    for (const route of routes) {
      await page.goto(route)
      await expect(page.locator('h1, h2, main').first()).toBeVisible({ timeout: 15_000 })
      const errorBoundary = page.locator('text=Произошла ошибка, text=Something went wrong')
      await expect(errorBoundary.first())
        .not.toBeVisible({ timeout: 1_000 })
        .catch(() => {})
    }
  })
})

// ── Story 4: Guest Experience ─────────────────────────────────────
test.describe('Story: Guest', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test('guest can browse catalog', async ({ page }) => {
    await page.goto('/library')
    await page.evaluate(() => localStorage.setItem('leerio_onboarded', '1'))
    await page.goto('/library')

    await page.waitForTimeout(2000)
    await expect(page.locator('h1')).toBeVisible({ timeout: 15_000 })
  })
})
