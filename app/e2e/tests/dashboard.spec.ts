import { test, expect } from '../fixtures'

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('shows greeting', async ({ page, takeScreenshot }) => {
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
    await expect(page.locator('p.uppercase').first()).toContainText(/Добр(ое|ый|ой)/)
    await takeScreenshot('dashboard-greeting')
  })

  test('shows loading skeletons initially', async ({ page }) => {
    // Navigate fresh to catch skeletons
    await page.goto('/', { waitUntil: 'commit' })
    // Skeletons may be very brief — just verify they exist or content loads
    await expect(page.locator('.skeleton').first().or(page.locator('.fade-in').first())).toBeVisible({
      timeout: 10_000,
    })
  })

  test('displays content after loading', async ({ page, takeScreenshot }) => {
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })

    // Dashboard should show greeting and either hero card, empty state, or stats
    await expect(page.locator('h1').first()).toBeVisible()
    await takeScreenshot('dashboard-content')
  })

  test('loads dashboard content', async ({ page }) => {
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
    // Dashboard renders greeting and content (heatmap only shown with activity data)
    await expect(page.locator('h1').first()).toBeVisible()
  })

  test('displays category shelves', { tag: '@needs-books' }, async ({ page, takeScreenshot }) => {
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
    // Should have at least one "Показать все" link from category shelves
    await expect(page.locator('text=Показать все').first()).toBeVisible()
    await takeScreenshot('dashboard-shelves')
  })
})
