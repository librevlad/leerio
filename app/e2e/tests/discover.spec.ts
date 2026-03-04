import { test, expect } from '../fixtures'

test.describe('Discover (LibriVox)', { tag: '@librivox' }, () => {
  test.describe.configure({ retries: 2 })

  test.beforeEach(async ({ page }) => {
    await page.goto('/discover')
    await expect(page.locator('h1:has-text("LibriVox")')).toBeVisible({ timeout: 15_000 })
  })

  test('shows title and subtitle', async ({ page, takeScreenshot }) => {
    await expect(page.locator('h1:has-text("LibriVox")')).toBeVisible()
    await expect(page.locator('text=Бесплатные аудиокниги')).toBeVisible()
    await takeScreenshot('discover-page')
  })

  test('has search input', async ({ page }) => {
    await expect(page.locator('input[placeholder="Поиск по названию..."]')).toBeVisible()
  })

  test('displays language filter pills', async ({ page }) => {
    await expect(page.locator('button:has-text("Все")')).toBeVisible()
    await expect(page.locator('button:has-text("English")')).toBeVisible()
    await expect(page.locator('button:has-text("Русский")')).toBeVisible()
  })

  test('shows initial empty state before search', async ({ page, takeScreenshot }) => {
    await expect(page.locator('text=Откройте мир бесплатных аудиокниг')).toBeVisible()
    await takeScreenshot('discover-initial')
  })

  test('search returns results', async ({ page, takeScreenshot }) => {
    const search = page.locator('input[placeholder="Поиск по названию..."]')
    await search.fill('adventure')
    // Wait for API response
    await expect(page.locator('a.card').first()).toBeVisible({ timeout: 15_000 })
    await takeScreenshot('discover-results')
  })

  test('language filter works', async ({ page }) => {
    const search = page.locator('input[placeholder="Поиск по названию..."]')
    await search.fill('love')
    await expect(page.locator('a.card').first()).toBeVisible({ timeout: 15_000 })

    // Click a language filter
    await page.locator('button:has-text("English")').click()
    await page.waitForTimeout(500)
    // Results should still be visible or change
    await expect(page.locator('a.card').first().or(page.locator('text=Ничего не найдено'))).toBeVisible({
      timeout: 15_000,
    })
  })

  test('result cards show metadata', async ({ page }) => {
    const search = page.locator('input[placeholder="Поиск по названию..."]')
    await search.fill('adventure')
    await expect(page.locator('a.card').first()).toBeVisible({ timeout: 15_000 })

    const firstCard = page.locator('a.card').first()
    // Title
    await expect(firstCard.locator('h3')).toBeVisible()
    // Author
    await expect(firstCard.locator('p').first()).toBeVisible()
  })

  test('clicking a result navigates to detail', async ({ page }) => {
    const search = page.locator('input[placeholder="Поиск по названию..."]')
    await search.fill('adventure')
    await expect(page.locator('a.card').first()).toBeVisible({ timeout: 15_000 })

    await page.locator('a.card').first().click()
    await expect(page).toHaveURL(/\/discover\//, { timeout: 10_000 })
  })
})
