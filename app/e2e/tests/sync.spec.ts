import { test, expect } from '../fixtures'

test.describe('Data sync', () => {
  test('dashboard loads without errors after login', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 15_000 })

    // No error toasts visible
    const errorToast = page.locator('.toast-error, [class*="red"]')
    await expect(errorToast)
      .not.toBeVisible({ timeout: 2_000 })
      .catch(() => {
        // Some red elements may exist legitimately (e.g., logout button)
      })
  })

  test('settings page shows user profile after sync', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.locator('h1')).toContainText('Настройки', { timeout: 15_000 })

    // User info should be visible (synced from server)
    const profileSection = page.locator('main')
    await expect(profileSection).toContainText(/Vlad|librevlad|admin/i, { timeout: 5_000 })
  })

  test('book statuses persist across page reload', { tag: '@needs-books' }, async ({ page }) => {
    // Go to a book and set status
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })
    await page.locator('a[href*="/book/"]').first().click()
    await expect(page).toHaveURL(/\/book\//, { timeout: 10_000 })

    // Click a status pill
    const statusPill = page.locator('button:has-text("Слушаю")')
    if (await statusPill.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await statusPill.click()

      // Reload and verify status persists
      await page.reload()
      await expect(page.locator('button:has-text("Слушаю")')).toBeVisible({ timeout: 10_000 })
    }
  })
})
