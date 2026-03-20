import { test as setup, expect } from '@playwright/test'

const email = process.env.E2E_EMAIL || 'librevlad@gmail.com'
const password = process.env.E2E_PASSWORD || 'librevlad@gmail.com'

setup('authenticate', async ({ page }) => {
  // Skip onboarding for E2E tests
  await page.goto('/login')
  await page.evaluate(() => localStorage.setItem('leerio_onboarded', '1'))

  await page.locator('input[type="email"]').fill(email)
  await page.locator('input[type="password"]').fill(password)
  await page.locator('button[type="submit"]:has-text("Войти")').click()

  await expect(page).toHaveURL('/library', { timeout: 10_000 })

  await page.context().storageState({ path: 'e2e/.auth/storageState.json' })
})
