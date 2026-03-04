import { test, expect } from '../fixtures'

test.describe('LibriVox detail', { tag: '@librivox' }, () => {
  test.describe.configure({ retries: 2 })

  test.beforeEach(async ({ page }) => {
    // Search for a book and navigate to its detail
    await page.goto('/discover')
    const search = page.locator('input[placeholder="Поиск по названию..."]')
    await search.fill('adventure')
    await expect(page.locator('a.card').first()).toBeVisible({ timeout: 15_000 })
    await page.locator('a.card').first().click()
    await expect(page).toHaveURL(/\/discover\//, { timeout: 10_000 })
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
  })

  test('shows book title and author', async ({ page, takeScreenshot }) => {
    await expect(page.locator('h1').first()).toBeVisible()
    await takeScreenshot('librivox-detail')
  })

  test('shows cover image or fallback', async ({ page }) => {
    // Book hero card contains either a cover image or an "LV" text fallback
    const heroCard = page.locator('.card').first()
    const cover = heroCard.locator('img').first()
    const fallback = heroCard.locator('text="LV"')
    await expect(cover.or(fallback)).toBeVisible()
  })

  test('shows metadata (language, duration, chapters)', async ({ page }) => {
    // At least one metadata element should be visible
    const chaptersLabel = page.locator('text=/\\d+ глав/')
    await expect(chaptersLabel).toBeVisible({ timeout: 10_000 })
  })

  test('has listen button', async ({ page }) => {
    const listenBtn = page.locator('button.btn-primary').first()
    await expect(listenBtn).toBeVisible()
    const text = await listenBtn.textContent()
    expect(text).toMatch(/Слушать|Продолжить/)
  })

  test('shows chapter list', async ({ page, takeScreenshot }) => {
    await expect(page.locator('text=Главы')).toBeVisible()
    // Should have at least one chapter row — scope to main to avoid sidebar matches
    const chapters = page.locator('main button.w-full.cursor-pointer')
    await expect(chapters.first()).toBeVisible()
    await takeScreenshot('librivox-chapters')
  })

  test('has back button', async ({ page }) => {
    const backBtn = page.locator('button:has-text("Назад")')
    await expect(backBtn).toBeVisible()
    await backBtn.click()
    await expect(page).toHaveURL('/discover', { timeout: 10_000 })
  })

  test('has external LibriVox.org link', async ({ page }) => {
    const link = page.locator('a:has-text("LibriVox.org")')
    await expect(link).toBeVisible()
    await expect(link).toHaveAttribute('target', '_blank')
  })
})
