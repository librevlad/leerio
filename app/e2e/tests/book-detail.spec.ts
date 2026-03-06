import { test, expect } from '../fixtures'

test.describe('Book detail', { tag: '@needs-books' }, () => {
  let bookUrl: string

  test.beforeEach(async ({ page }) => {
    // Navigate to library, click first book
    await page.goto('/library')
    await expect(page.locator('a.card.card-hover').first()).toBeVisible({ timeout: 15_000 })
    const firstCard = page.locator('a.card.card-hover').first()
    bookUrl = (await firstCard.getAttribute('href')) || '/library'
    await page.goto(bookUrl)
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
  })

  test('displays book info card', async ({ page, takeScreenshot }) => {
    // Title and author visible (two h1 elements: mobile + desktop, pick the visible one)
    await expect(page.locator('h1:visible').first()).toBeVisible()
    await takeScreenshot('book-detail')
  })

  test('shows back button', async ({ page }) => {
    const backBtn = page.locator('button:has-text("Назад")')
    await expect(backBtn).toBeVisible()
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

  test('shows status pills', async ({ page, takeScreenshot }) => {
    // Status is now shown as pill buttons (e.g. "Хочу прочесть", "Слушаю", etc.)
    const statusPill = page.locator('button:has-text("Хочу прочесть"), button:has-text("Слушаю")')
    await expect(statusPill.first()).toBeVisible()
    await takeScreenshot('book-detail-actions')
  })

  test('shows notes section', async ({ page }) => {
    await expect(page.locator('text=Заметки')).toBeVisible()
    await expect(page.locator('textarea[placeholder="Добавить заметку..."]')).toBeVisible()
  })

  test('shows tags section', async ({ page }) => {
    await expect(page.locator('text=Теги')).toBeVisible()
    await expect(page.locator('input[placeholder="Добавить тег..."]')).toBeVisible()
  })

  test('shows metadata (size, files, duration)', async ({ page, takeScreenshot }) => {
    // Metadata is shown in responsive layouts (mobile: md:hidden, desktop: hidden md:block)
    // Check that book info section contains metadata text in the page
    const pageContent = await page.textContent('body')
    const hasSize = pageContent?.includes('МБ') ?? false
    const hasFiles = pageContent?.includes('Файлов') ?? false
    const hasDuration = pageContent?.includes('Длительность') ?? false
    expect(hasSize || hasFiles || hasDuration).toBeTruthy()
    await takeScreenshot('book-detail-meta')
  })
})
