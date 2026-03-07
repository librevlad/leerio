import { test, expect } from '../fixtures'

test.use({ storageState: { cookies: [], origins: [] } })

test.describe('Login page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
  })

  test('displays login form with all elements', async ({ page, takeScreenshot }) => {
    await expect(page.locator('img[alt="Leerio"]')).toBeVisible()
    await expect(page.locator('text=Войдите, чтобы продолжить')).toBeVisible()
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]:has-text("Войти")')).toBeVisible()
    await expect(page.locator('text=Leerio v1.0')).toBeVisible()
    await takeScreenshot('login-form')
  })

  test('submit button is disabled when fields are empty', async ({ page }) => {
    const btn = page.locator('button[type="submit"]:has-text("Войти")')
    await expect(btn).toBeDisabled()
  })

  test('submit button is disabled with only email', async ({ page }) => {
    await page.locator('input[type="email"]').fill('test@test.com')
    const btn = page.locator('button[type="submit"]:has-text("Войти")')
    await expect(btn).toBeDisabled()
  })

  test('submit button is enabled when both fields filled', async ({ page }) => {
    await page.locator('input[type="email"]').fill('test@test.com')
    await page.locator('input[type="password"]').fill('password')
    const btn = page.locator('button[type="submit"]:has-text("Войти")')
    await expect(btn).toBeEnabled()
  })

  test('shows error on wrong credentials', async ({ page, takeScreenshot }) => {
    await page.locator('input[type="email"]').fill('wrong@test.com')
    await page.locator('input[type="password"]').fill('wrongpassword')
    await page.locator('button[type="submit"]:has-text("Войти")').click()

    await expect(page.locator('.text-red-400')).toBeVisible({ timeout: 10_000 })
    await takeScreenshot('login-error')
  })

  test('successful login redirects to dashboard', async ({ page }) => {
    const email = process.env.E2E_EMAIL || 'librevlad@gmail.com'
    const password = process.env.E2E_PASSWORD || 'librevlad@gmail.com'

    await page.locator('input[type="email"]').fill(email)
    await page.locator('input[type="password"]').fill(password)
    await page.locator('button[type="submit"]:has-text("Войти")').click()

    await expect(page).toHaveURL('/', { timeout: 10_000 })
  })

  test('unauthenticated user is redirected to login', async ({ page }) => {
    await page.goto('/settings')
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 })
  })
})
