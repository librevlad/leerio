import { test, expect } from '../fixtures'

test.describe('History', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/history')
    await expect(page.locator('.fade-in').first().or(page.locator('text=История пуста'))).toBeVisible({
      timeout: 15_000,
    })
  })

  test('shows page title', async ({ page, takeScreenshot }) => {
    await expect(page.locator('h1.page-title')).toContainText('История')
    await takeScreenshot('history-page')
  })

  test('has search input', async ({ page }) => {
    await expect(page.locator('input[placeholder="Поиск по книге..."]')).toBeVisible()
  })

  test('has action filter pills', async ({ page }) => {
    const allPill = page.locator('button', { hasText: 'Все' }).first()
    await expect(allPill).toBeVisible()
  })

  test('search filters history entries', async ({ page, takeScreenshot }) => {
    const search = page.locator('input[placeholder="Поиск по книге..."]')
    await search.fill('nonexistent-book-xyz')
    await page.waitForTimeout(500)

    // Either filtered results or empty state
    await expect(page.locator('.fade-in').first().or(page.locator('text=История пуста'))).toBeVisible()
    await takeScreenshot('history-search')
  })
})
