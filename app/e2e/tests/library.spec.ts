import { test, expect } from '../fixtures'

test.describe('Library', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/library')
    // Wait for content to load
    await expect(page.locator('.fade-in').first().or(page.locator('text=Книги не найдены'))).toBeVisible({
      timeout: 15_000,
    })
  })

  test('shows page title and book count', async ({ page, takeScreenshot }) => {
    await expect(page.locator('h1.page-title')).toContainText('Библиотека')
    await expect(page.locator('main').locator('text=/\\d+ кни/')).toBeVisible()
    await takeScreenshot('library-page')
  })

  test('displays book grid with cards', { tag: '@needs-books' }, async ({ page }) => {
    const cards = page.locator('a.card.card-hover')
    await expect(cards.first()).toBeVisible()

    // Each card has title and author
    const firstCard = cards.first()
    await expect(firstCard.locator('h3')).toBeVisible()
    await expect(firstCard.locator('p').first()).toBeVisible()
  })

  test('search input filters books', async ({ page, takeScreenshot }) => {
    const search = page.locator('input.input-field[type="text"]')
    await expect(search).toBeVisible()

    const cardsBefore = await page.locator('a.card.card-hover').count()
    await search.fill('test-nonexistent-book-xyz')
    // Wait for debounce
    await page.waitForTimeout(500)

    // Either fewer cards or empty state
    const cardsAfter = await page.locator('a.card.card-hover').count()
    const emptyVisible = await page.locator('text=Книги не найдены').isVisible()
    expect(cardsAfter < cardsBefore || emptyVisible).toBeTruthy()
    await takeScreenshot('library-search')
  })

  test('category pills are displayed', { tag: '@needs-books' }, async ({ page }) => {
    await expect(page.locator('button:has-text("Все")')).toBeVisible()
    // Check for at least one category
    const categories = ['Бизнес', 'Отношения', 'Саморазвитие', 'Художественная', 'Языки']
    let found = 0
    for (const cat of categories) {
      if (await page.locator(`button:has-text("${cat}")`).isVisible()) found++
    }
    expect(found).toBeGreaterThan(0)
  })

  test('sort options are visible', async ({ page }) => {
    await expect(page.locator('text=Сортировка:')).toBeVisible()
    await expect(page.locator('button:has-text("Название")')).toBeVisible()
    await expect(page.locator('button:has-text("Автор")')).toBeVisible()
  })

  test('category filter changes book list', async ({ page }) => {
    const firstCategory = page.locator('button:has-text("Бизнес")')
    if (await firstCategory.isVisible()) {
      await firstCategory.click()
      await page.waitForTimeout(300)
      // Should still show books or empty state
      await expect(page.locator('a.card.card-hover').first().or(page.locator('text=Книги не найдены'))).toBeVisible()
    }
  })

  test('empty state shows reset button', async ({ page, takeScreenshot }) => {
    const search = page.locator('input.input-field[type="text"]')
    await search.fill('zzzznonexistent12345')
    await page.waitForTimeout(500)

    const emptyState = page.locator('text=Книги не найдены')
    if (await emptyState.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await expect(page.locator('button:has-text("Сбросить фильтры")')).toBeVisible()
      await takeScreenshot('library-empty')
    }
  })

  test('clicking a book card navigates to detail', { tag: '@needs-books' }, async ({ page }) => {
    const firstCard = page.locator('a.card.card-hover').first()
    await expect(firstCard).toBeVisible()
    await firstCard.click()
    await expect(page).toHaveURL(/\/book\//, { timeout: 10_000 })
  })
})
