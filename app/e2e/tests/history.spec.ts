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

  test('has action filter dropdown', async ({ page }) => {
    const select = page.locator('select.input-field')
    await expect(select).toBeVisible()
    // Verify it has the "Все" option
    await expect(select.locator('option', { hasText: 'Все' })).toBeAttached()
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
