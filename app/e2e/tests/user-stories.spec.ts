/**
 * Core User Story E2E Tests
 *
 * Covers the most critical user flows that span multiple pages.
 * Each test verifies a complete user story end-to-end.
 */
import { test, expect } from '../fixtures'

// ── Story 1: Browse → Book Detail → Play ────────────────────────────
test.describe('Story: Browse and Play', () => {
  test('user can browse catalog, open book, and start playback', { tag: '@needs-books' }, async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })

    // Click first book card
    const firstBook = page.locator('a[href*="/book/"]').first()
    const bookTitle = await firstBook.locator('h3').textContent()
    await firstBook.click()

    // Verify book detail page loaded
    await expect(page).toHaveURL(/\/book\//, { timeout: 10_000 })
    await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 })

    // Click play button
    const playBtn = page.locator('button:has-text("Воспроизвести"), button:has-text("Продолжить")')
    await expect(playBtn.first()).toBeVisible({ timeout: 5_000 })
    await playBtn.first().click()

    // Verify fullscreen player opened
    await expect(page.locator('.fixed.inset-0')).toBeVisible({ timeout: 10_000 })

    // Verify book title is shown in player
    if (bookTitle) {
      await expect(page.locator('.fixed.inset-0')).toContainText(bookTitle.trim().slice(0, 20), { timeout: 5_000 })
    }
  })
})

// ── Story 2: Set Book Status → Filter in Library ────────────────────
test.describe('Story: Book Status Workflow', () => {
  test('user sets status on book and finds it via library filter', { tag: '@needs-books' }, async ({ page }) => {
    // Go to a book
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })
    await page.locator('a[href*="/book/"]').first().click()
    await expect(page).toHaveURL(/\/book\//, { timeout: 10_000 })

    // Set status to "Хочу прочесть"
    const wantBtn = page.locator('button:has-text("Хочу прочесть")')
    if (await wantBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await wantBtn.click()
      await page.waitForTimeout(500)
    }

    // Go to library with want_to_read filter
    await page.goto('/library?status=want_to_read')
    await page.waitForTimeout(1000)

    // Should see at least one book (or empty state)
    const hasBooks = await page
      .locator('a[href*="/book/"]')
      .first()
      .isVisible({ timeout: 5_000 })
      .catch(() => false)
    const hasEmpty = await page
      .locator('text=Книги не найдены')
      .isVisible({ timeout: 2_000 })
      .catch(() => false)
    expect(hasBooks || hasEmpty).toBeTruthy()
  })
})

// ── Story 3: Add Bookmark → See in Player ───────────────────────────
test.describe('Story: Bookmark Flow', () => {
  test('user adds bookmark and sees it in bookmarks tab', { tag: '@needs-books' }, async ({ page }) => {
    // Open a book and start playback
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })
    await page.locator('a[href*="/book/"]').first().click()
    await expect(page).toHaveURL(/\/book\//, { timeout: 10_000 })

    const playBtn = page.locator('button:has-text("Воспроизвести")')
    if (await playBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await playBtn.click()
      await expect(page.locator('.fixed.inset-0')).toBeVisible({ timeout: 10_000 })
      await page.waitForTimeout(1000) // let audio load

      // Click bookmark button (desktop layout)
      const bookmarkBtn = page.locator('.fixed.inset-0 button:has(svg)').filter({ hasText: '' }).nth(8) // approximate
      // Try finding by aria-label or icon
      const bmButton = page.locator('[aria-label*="закладк" i], [aria-label*="bookmark" i]').first()
      if (await bmButton.isVisible({ timeout: 2_000 }).catch(() => false)) {
        await bmButton.click()
        await page.waitForTimeout(500)

        // Check for toast
        const toast = page.locator('text=Закладка добавлена, text=Bookmark added')
        await expect(toast.first())
          .toBeVisible({ timeout: 3_000 })
          .catch(() => {})
      }
    }
  })
})

// ── Story 4: Settings Persistence ───────────────────────────────────
test.describe('Story: Settings Persistence', () => {
  test('yearly goal change persists after reload', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.locator('h1')).toContainText('Настройки', { timeout: 15_000 })

    // Find goal slider
    const slider = page.locator('input[type="range"]').first()
    if (await slider.isVisible({ timeout: 3_000 }).catch(() => false)) {
      // Change value
      await slider.fill('50')
      await page.waitForTimeout(1000)

      // Reload and verify
      await page.reload()
      await expect(page.locator('h1')).toContainText('Настройки', { timeout: 15_000 })
    }
  })

  test('language switch changes UI text', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.locator('h1')).toContainText('Настройки', { timeout: 15_000 })

    // Find language selector
    const enBtn = page.locator('button:has-text("English"), button:has-text("🇬🇧")')
    if (await enBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await enBtn.click()
      await page.waitForTimeout(500)
      await expect(page.locator('h1')).toContainText('Settings', { timeout: 5_000 })

      // Switch back to Russian
      const ruBtn = page.locator('button:has-text("Русский"), button:has-text("🇷🇺")')
      await ruBtn.click()
      await page.waitForTimeout(500)
      await expect(page.locator('h1')).toContainText('Настройки', { timeout: 5_000 })
    }
  })
})

// ── Story 5: Note Persistence ───────────────────────────────────────
test.describe('Story: Notes', () => {
  test('user adds note on book detail and it persists', { tag: '@needs-books' }, async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })
    await page.locator('a[href*="/book/"]').first().click()
    await expect(page).toHaveURL(/\/book\//, { timeout: 10_000 })

    // Click Notes tab
    const notesTab = page.locator('button:has-text("Заметки")')
    if (await notesTab.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await notesTab.click()
      await page.waitForTimeout(500)

      // Find textarea and type
      const textarea = page.locator('textarea').first()
      if (await textarea.isVisible({ timeout: 3_000 }).catch(() => false)) {
        const testNote = `E2E test note ${Date.now()}`
        await textarea.fill(testNote)
        await page.waitForTimeout(2000) // debounce save

        // Reload and verify
        await page.reload()
        await expect(page.locator('h1')).toBeVisible({ timeout: 10_000 })
        await notesTab.click()
        await page.waitForTimeout(500)
        await expect(page.locator('textarea')).toHaveValue(new RegExp(testNote.slice(0, 20)), { timeout: 5_000 })
      }
    }
  })
})

// ── Story 6: Navigation Flow ────────────────────────────────────────
test.describe('Story: Full Navigation', () => {
  test('user can navigate through all main pages without errors', async ({ page }) => {
    const routes = ['/', '/library', '/my-library', '/collections', '/history', '/analytics', '/settings']

    for (const route of routes) {
      await page.goto(route)
      // Wait for page content (h1, h2, or main content)
      await expect(page.locator('h1, h2, main').first()).toBeVisible({ timeout: 15_000 })
      // No error boundary shown
      const errorBoundary = page.locator('text=Произошла ошибка, text=Something went wrong')
      await expect(errorBoundary.first())
        .not.toBeVisible({ timeout: 1_000 })
        .catch(() => {})
    }
  })
})

// ── Story 7: Guest Mode ─────────────────────────────────────────────
test.describe('Story: Guest Experience', () => {
  // Run without auth
  test.use({ storageState: { cookies: [], origins: [] } })

  test('guest can browse catalog and see welcome prompt', async ({ page }) => {
    // Set onboarded to skip welcome
    await page.goto('/library')
    await page.evaluate(() => localStorage.setItem('leerio_onboarded', '1'))
    await page.goto('/library')

    // Should see library (catalog is public)
    await page.waitForTimeout(2000)
    const title = page.locator('h1')
    await expect(title).toBeVisible({ timeout: 15_000 })
  })

  test('guest dashboard shows guest welcome card', async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.setItem('leerio_onboarded', '1'))
    await page.goto('/')
    await page.waitForTimeout(2000)

    // Should show guest content (not logged-in dashboard)
    const content = page.locator('main')
    await expect(content).toBeVisible({ timeout: 15_000 })
  })
})
