import { test, expect } from '../fixtures'

test.describe('Book detail', { tag: '@needs-books' }, () => {
  let bookUrl: string

  test.beforeEach(async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('a.card.card-hover').first()).toBeVisible({ timeout: 15_000 })
    const firstCard = page.locator('a.card.card-hover').first()
    bookUrl = (await firstCard.getAttribute('href')) || '/library'
    await page.goto(bookUrl)
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
  })

  test('displays book info', async ({ page, takeScreenshot }) => {
    await expect(page.locator('h1:visible').first()).toBeVisible()
    await takeScreenshot('book-detail')
  })

  test('shows back button', async ({ page }) => {
    await expect(page.locator('button:has-text("Назад")')).toBeVisible()
  })

  test('back button navigates away', async ({ page }) => {
    await page.locator('button:has-text("Назад")').click()
    await expect(page).not.toHaveURL(bookUrl, { timeout: 5_000 })
  })

  test('shows listen button', async ({ page }) => {
    const listenBtn = page.locator('button.btn-primary').first()
    await expect(listenBtn).toBeVisible()
    const text = await listenBtn.textContent()
    expect(text).toMatch(/Слушать|Продолжить/)
  })
})
