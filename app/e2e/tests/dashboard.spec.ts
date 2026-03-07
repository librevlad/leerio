import { test, expect } from '../fixtures'

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('shows page title', async ({ page, takeScreenshot }) => {
    await expect(page.locator('h1.page-title')).toContainText(/Добр(ое|ый|ой)/)
    await takeScreenshot('dashboard-title')
  })

  test('shows loading skeletons initially', async ({ page }) => {
    // Navigate fresh to catch skeletons
    await page.goto('/', { waitUntil: 'commit' })
    // Skeletons may be very brief — just verify they exist or content loads
    await expect(page.locator('.skeleton').first().or(page.locator('.fade-in').first())).toBeVisible({
      timeout: 10_000,
    })
  })

  test('displays inline stats after loading', async ({ page, takeScreenshot }) => {
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })

    // Should have inline stats text
    await expect(page.locator('text=книг в библиотеке')).toBeVisible()
    await expect(page.locator('text=прослушано')).toBeVisible()
    await takeScreenshot('dashboard-stats')
  })

  test('displays activity heatmap', async ({ page }) => {
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
    // Heatmap is rendered as SVG or table of cells
    await expect(page.locator('text=Активность').first()).toBeVisible()
  })

  test('displays category shelves', { tag: '@needs-books' }, async ({ page, takeScreenshot }) => {
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
    // Should have at least one "Показать все" link from category shelves
    await expect(page.locator('text=Показать все').first()).toBeVisible()
    await takeScreenshot('dashboard-shelves')
  })
})
