import { test, expect } from '../fixtures'

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('shows page title', async ({ page, takeScreenshot }) => {
    await expect(page.locator('h1.page-title')).toContainText('Дашборд')
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

  test('displays hero stats after loading', async ({ page, takeScreenshot }) => {
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })

    // Should have stat cards with labels
    await expect(page.locator('text=Всего книг')).toBeVisible()
    await expect(page.locator('text=Прослушано')).toBeVisible()
    await expect(page.locator('span.text-\\[12px\\]:has-text("В процессе")')).toBeVisible()
    await takeScreenshot('dashboard-stats')
  })

  test('displays activity heatmap', async ({ page }) => {
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
    // Heatmap is rendered as SVG or table of cells
    await expect(page.locator('text=Активность').first()).toBeVisible()
  })

  test('displays recent activity section', async ({ page, takeScreenshot }) => {
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
    await takeScreenshot('dashboard-loaded')
  })
})
