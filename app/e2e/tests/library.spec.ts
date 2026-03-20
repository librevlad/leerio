import { test, expect } from '../fixtures'

test.describe('Library', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('.fade-in').first().or(page.locator('text=Книги не найдены'))).toBeVisible({
      timeout: 15_000,
    })
  })

  test('shows page title', async ({ page, takeScreenshot }) => {
    await expect(page.locator('h1.page-title')).toContainText('Каталог')
    await takeScreenshot('library-page')
  })

  test('displays book grid', { tag: '@needs-books' }, async ({ page }) => {
    const cards = page.locator('a.card.card-hover')
    await expect(cards.first()).toBeVisible()
  })

  test('category pills are displayed', { tag: '@needs-books' }, async ({ page }) => {
    await expect(page.locator('button:has-text("Все")').first()).toBeVisible()
    const categories = ['Бизнес', 'Отношения', 'Саморазвитие', 'Художественная', 'Языки']
    let found = 0
    for (const cat of categories) {
      if (await page.locator(`button:has-text("${cat}")`).isVisible()) found++
    }
    expect(found).toBeGreaterThan(0)
  })

  test('category filter works', async ({ page }) => {
    const firstCategory = page.locator('button:has-text("Бизнес")')
    if (await firstCategory.isVisible()) {
      await firstCategory.click()
      await page.waitForTimeout(300)
      await expect(page.locator('a.card.card-hover').first().or(page.locator('text=Книги не найдены'))).toBeVisible()
    }
  })

  test('clicking book navigates to detail', { tag: '@needs-books' }, async ({ page }) => {
    await page.locator('a.card.card-hover').first().click()
    await expect(page).toHaveURL(/\/book\//, { timeout: 10_000 })
  })
})
