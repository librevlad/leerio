import { test, expect } from '../fixtures'

test.use({ storageState: { cookies: [], origins: [] } })

test.describe('Login page', () => {
  test.beforeEach(async ({ page }) => {
    // Set onboarded flag before navigating — otherwise router redirects to /welcome
    await page.goto('/login')
    await page.evaluate(() => localStorage.setItem('leerio_onboarded', '1'))
    await page.goto('/login')
  })

  test('displays login form with all elements', async ({ page, takeScreenshot }) => {
    await expect(page.locator('img[alt="Leerio"]')).toBeVisible()
    await expect(page.locator('input[type="email"], input[placeholder*="Email"]').first()).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('button:has-text("Войти")').first()).toBeVisible()
    await expect(page.locator('text=/Leerio v\\d/')).toBeVisible()
    await takeScreenshot('login-form')
  })

  test('submit button is disabled when fields are empty', async ({ page }) => {
    const btn = page.locator('form button:has-text("Войти")')
    await expect(btn).toBeDisabled()
  })

  test('submit button is disabled with only email', async ({ page }) => {
    await page.locator('input[placeholder*="Email"]').fill('test@test.com')
    const btn = page.locator('form button:has-text("Войти")')
    await expect(btn).toBeDisabled()
  })

  test('submit button is enabled when both fields filled', async ({ page }) => {
    await page.locator('input[placeholder*="Email"]').fill('test@test.com')
    await page.locator('input[type="password"]').fill('password')
    const btn = page.locator('form button:has-text("Войти")')
    await expect(btn).toBeEnabled()
  })

  test('shows error on wrong credentials', async ({ page, takeScreenshot }) => {
    await page.locator('input[placeholder*="Email"]').fill('wrong@test.com')
    await page.locator('input[type="password"]').fill('wrongpassword')
    await page.locator('form button:has-text("Войти")').click()

    await expect(page.locator('.text-red-400')).toBeVisible({ timeout: 10_000 })
    await takeScreenshot('login-error')
  })

  test('successful login redirects to dashboard', async ({ page }) => {
    const email = process.env.E2E_EMAIL || 'librevlad@gmail.com'
    const password = process.env.E2E_PASSWORD || 'librevlad@gmail.com'

    // Skip onboarding
    await page.evaluate(() => localStorage.setItem('leerio_onboarded', '1'))

    await page.locator('input[placeholder*="Email"]').fill(email)
    await page.locator('input[type="password"]').fill(password)
    await page.locator('form button:has-text("Войти")').click()

    await expect(page).toHaveURL('/library', { timeout: 10_000 })
  })

  test('unauthenticated user can access settings (guest mode)', async ({ page }) => {
    // Skip onboarding
    await page.goto('/settings')
    await page.evaluate(() => localStorage.setItem('leerio_onboarded', '1'))
    await page.goto('/settings')
    // No redirect — guests can use the app
    await expect(page).toHaveURL('/settings', { timeout: 10_000 })
  })
})
