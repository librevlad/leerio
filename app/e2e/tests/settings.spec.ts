import { test, expect } from '../fixtures'

test.describe('Settings', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings')
    await expect(page.locator('h1.page-title')).toContainText('Настройки', { timeout: 15_000 })
  })

  test('shows page title', async ({ page, takeScreenshot }) => {
    await expect(page.locator('h1.page-title')).toContainText('Настройки')
    await takeScreenshot('settings-page')
  })

  test('displays profile info', async ({ page }) => {
    const main = page.locator('main')
    await expect(main.locator('text=Профиль')).toBeVisible()
    // User email should be visible
    await expect(main.locator('text=@').first()).toBeVisible()
  })

  test('shows admin badge for admin user', async ({ page, takeScreenshot }) => {
    const adminBadge = page.locator('text=Администратор')
    // Seed user is admin
    await expect(adminBadge).toBeVisible()
    await takeScreenshot('settings-admin')
  })

  test('displays categories section', async ({ page }) => {
    await expect(page.locator('text=Категории')).toBeVisible()
  })

  test('shows system info', async ({ page }) => {
    await expect(page.locator('text=О системе')).toBeVisible()
    await expect(page.locator('text=v1.0')).toBeVisible()
  })

  test('has logout button', async ({ page, takeScreenshot }) => {
    const logoutBtn = page.locator('main button:has-text("Выйти")')
    await expect(logoutBtn).toBeVisible()
    await takeScreenshot('settings-logout')
  })
})
