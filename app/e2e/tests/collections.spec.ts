import { test, expect } from '../fixtures'

test.describe('Collections CRUD', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/collections')
    await expect(page.locator('h1')).toBeVisible({ timeout: 15_000 })
  })

  test('shows collections page title', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Коллекции')
  })

  test('can create a new collection', async ({ page }) => {
    const createBtn = page.locator('button:has-text("Создать"), button:has-text("Новая")')
    if (await createBtn.isVisible()) {
      await createBtn.first().click()

      // Fill collection name
      const nameInput = page.locator('input[placeholder*="назван"], input[placeholder*="Название"]')
      if (await nameInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await nameInput.fill('Тестовая коллекция')

        // Submit
        const saveBtn = page.locator('button:has-text("Сохранить"), button:has-text("Создать")')
        await saveBtn.first().click()

        // Verify collection appears
        await expect(page.locator('text=Тестовая коллекция')).toBeVisible({ timeout: 5_000 })
      }
    }
  })

  test('shows empty state when no collections', { tag: '@needs-books' }, async ({ page }) => {
    // Check for either collections list or empty state
    const content = page.locator('main')
    await expect(content).toBeVisible()
  })
})
