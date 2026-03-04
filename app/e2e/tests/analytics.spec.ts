import { test, expect } from '../fixtures'

test.describe('Analytics', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/analytics')
    await expect(page.locator('.fade-in').first().or(page.locator('.skeleton').first())).toBeVisible({
      timeout: 15_000,
    })
  })

  test('shows page title', async ({ page, takeScreenshot }) => {
    await expect(page.locator('h1.page-title')).toContainText('Аналитика')
    await takeScreenshot('analytics-page')
  })

  test('renders chart sections after loading', async ({ page, takeScreenshot }) => {
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
    // Charts rendered as canvas elements
    const canvases = page.locator('canvas')
    await expect(canvases.first()).toBeVisible({ timeout: 10_000 })
    await takeScreenshot('analytics-charts')
  })

  test('shows achievements section', async ({ page }) => {
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
    // Achievements grid is always rendered
    await expect(page.locator('text=Достижения').first()).toBeVisible()
  })

  test('shows top authors section if data exists', async ({ page, takeScreenshot }) => {
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
    const topAuthors = page.locator('text=Топ авторов')
    if (await topAuthors.isVisible().catch(() => false)) {
      await takeScreenshot('analytics-top-authors')
    }
  })
})
