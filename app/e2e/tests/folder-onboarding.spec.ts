/**
 * APK Folder Onboarding E2E Tests
 *
 * Tests the full folder onboarding feature:
 * - Onboarding step 2 redesign (scan/files/folder buttons)
 * - FAB + popup menu in library
 * - ScanResultsView with checkboxes
 * - fs: books in MyLibrary and BookDetail
 * - Cloud upload paywall for free users
 * - YouTube import view
 * - Platform detection (web vs native)
 */
import { test, expect } from '../fixtures'

// ── Helper: inject fs: books into localStorage ──────────────────────
const FS_BOOKS_KEY = 'leerio_fs_books'

function makeFsBook(name: string, trackCount: number) {
  const tracks = Array.from({ length: trackCount }, (_, i) => ({
    index: i,
    filename: `${String(i + 1).padStart(2, '0')}.mp3`,
    path: `Audiobooks/${name}/${String(i + 1).padStart(2, '0')}.mp3`,
    duration: 300 + i * 60,
  }))
  return {
    id: `fs:${name}`,
    title: name.includes(' - ') ? name.split(' - ').slice(1).join(' - ') : name,
    author: name.includes(' - ') ? name.split(' - ')[0] : '',
    folderPath: `Audiobooks/${name}`,
    tracks,
    sizeBytes: trackCount * 5_000_000,
    synced: false,
    addedAt: new Date().toISOString(),
  }
}

async function injectFsBooks(page: import('@playwright/test').Page) {
  const books = {
    'fs:Толстой - Война и мир': makeFsBook('Толстой - Война и мир', 12),
    'fs:Булгаков - Мастер и Маргарита': makeFsBook('Булгаков - Мастер и Маргарита', 8),
    'fs:Simple Audiobook': makeFsBook('Simple Audiobook', 3),
  }
  await page.evaluate((data) => localStorage.setItem('leerio_fs_books', JSON.stringify(data)), books)
}

// ══════════════════════════════════════════════════════════════════════
// ONBOARDING
// ══════════════════════════════════════════════════════════════════════

test.describe('Onboarding Step 2', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test('web: shows files + folder buttons, no scan button', async ({ page }) => {
    await page.goto('/welcome')
    await expect(page.locator('button:has-text("Продолжить")')).toBeVisible({ timeout: 10_000 })
    await page.locator('button:has-text("Продолжить")').click()

    // Step 2 visible
    await expect(page.locator('text=Добавь свои книги')).toBeVisible({ timeout: 5_000 })

    // Files and folder buttons visible
    await expect(page.locator('button:has-text("Выбрать файлы")')).toBeVisible()
    await expect(page.locator('button:has-text("Указать папку")')).toBeVisible()

    // Scan button should NOT be visible on web (not native)
    await expect(page.locator('button:has-text("Сканировать устройство")')).not.toBeVisible()

    // Skip link visible
    await expect(page.locator('button:has-text("Пропустить")')).toBeVisible()
  })

  test('skip onboarding navigates to library', async ({ page }) => {
    await page.goto('/welcome')
    await page.locator('button:has-text("Продолжить")').click()
    await expect(page.locator('text=Добавь свои книги')).toBeVisible({ timeout: 5_000 })

    // Click skip
    await page.locator('button:has-text("Пропустить")').click()

    // Step 3
    await expect(page.getByRole('heading', { name: 'Библиотека готова' })).toBeVisible({
      timeout: 5_000,
    })
  })

  test('back button returns to step 1', async ({ page }) => {
    await page.goto('/welcome')
    await page.locator('button:has-text("Продолжить")').click()
    await expect(page.locator('text=Добавь свои книги')).toBeVisible({ timeout: 5_000 })

    await page.locator('button:has-text("Назад")').click()
    await expect(page.locator('text=Твоя аудиобиблиотека')).toBeVisible({ timeout: 5_000 })
  })

  test('files button primary on web (accent style)', async ({ page }) => {
    await page.goto('/welcome')
    await page.locator('button:has-text("Продолжить")').click()
    await expect(page.locator('text=Добавь свои книги')).toBeVisible({ timeout: 5_000 })

    // On web, files button should have accent gradient (inline style)
    const filesBtn = page.locator('button:has-text("Выбрать файлы")')
    const style = await filesBtn.getAttribute('style')
    expect(style).toContain('gradient-accent')
  })
})

// ══════════════════════════════════════════════════════════════════════
// FAB + POPUP
// ══════════════════════════════════════════════════════════════════════

test.describe('FAB in Library', () => {
  test('FAB button is visible in library', async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })

    // FAB button (fixed, round, with +)
    const fab = page.locator('button.fixed.rounded-full')
    await expect(fab).toBeVisible()
  })

  test('FAB click opens popup with menu items', async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })

    const fab = page.locator('button.fixed.rounded-full')
    await fab.click()

    // Popup visible with menu items
    await expect(page.locator('text=Файлы')).toBeVisible({ timeout: 3_000 })
    await expect(page.locator('text=Папка')).toBeVisible()
    await expect(page.locator('text=Озвучить текст')).toBeVisible()

    // On web: Scan and YouTube should NOT be visible
    await expect(page.locator('button:has-text("Сканировать")')).not.toBeVisible()
  })

  test('FAB popup has overlay that closes on click', async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })

    const fab = page.locator('button.fixed.rounded-full')
    await fab.click()
    await expect(page.locator('text=Файлы')).toBeVisible({ timeout: 3_000 })

    // Click overlay to close
    await page.locator('.fixed.inset-0.bg-black\\/50').click()
    await expect(page.locator('text=Файлы')).not.toBeVisible({ timeout: 3_000 })
  })

  test('FAB rotates when open (rotate-45 class)', async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })

    const fab = page.locator('button.fixed.rounded-full')
    await fab.click()

    // FAB should have rotate-45 class when open
    await expect(fab).toHaveClass(/rotate-45/)
  })

  test('TTS menu item navigates to /upload', async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })

    const fab = page.locator('button.fixed.rounded-full')
    await fab.click()
    await page.locator('button:has-text("Озвучить текст")').click()

    await expect(page).toHaveURL(/\/upload/, { timeout: 5_000 })
  })

  test('Files menu item navigates to /upload', async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })

    const fab = page.locator('button.fixed.rounded-full')
    await fab.click()

    // Click "Файлы" in popup (not in category pills)
    await page.locator('[style*="card-solid"] button:has-text("Файлы")').click()

    await expect(page).toHaveURL(/\/upload/, { timeout: 5_000 })
  })
})

// ══════════════════════════════════════════════════════════════════════
// SCAN RESULTS
// ══════════════════════════════════════════════════════════════════════

test.describe('Scan Results View', () => {
  test('shows empty state on web (no native scanner)', async ({ page }) => {
    await page.goto('/scan-results')
    await expect(page.locator('text=Найдено 0 книг')).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('text=Аудиокниги не найдены')).toBeVisible()
    await expect(page.locator('text=Попробуйте указать папку вручную')).toBeVisible()
  })

  test('back button works', async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })

    await page.goto('/scan-results')
    await expect(page.locator('text=Найдено 0 книг')).toBeVisible({ timeout: 10_000 })

    await page.goBack()
    await expect(page).toHaveURL(/\/library/, { timeout: 5_000 })
  })
})

// ══════════════════════════════════════════════════════════════════════
// FS: BOOKS IN MY LIBRARY
// ══════════════════════════════════════════════════════════════════════

test.describe('fs: books in My Library', () => {
  test('injected fs: books appear in my library', async ({ page }) => {
    await page.goto('/my-library')
    await injectFsBooks(page)
    await page.reload()

    await expect(page.locator('text=Моя библиотека')).toBeVisible({ timeout: 10_000 })

    // fs: books should appear
    await expect(page.locator('text=Война и мир')).toBeVisible({ timeout: 5_000 })
    await expect(page.locator('text=Мастер и Маргарита')).toBeVisible()
    await expect(page.locator('text=Simple Audiobook')).toBeVisible()
  })

  test('local filter shows only fs: books', async ({ page }) => {
    await page.goto('/my-library')
    await injectFsBooks(page)
    await page.reload()

    await expect(page.locator('text=Моя библиотека')).toBeVisible({ timeout: 10_000 })

    // Click "Локальные" filter
    await page.locator('button:has-text("Локальные")').click()
    await page.waitForTimeout(300)

    // fs: books visible
    await expect(page.locator('text=Война и мир')).toBeVisible()

    // Uploaded books should NOT be visible
    await expect(page.locator('text=Загружено').first()).not.toBeVisible({ timeout: 2_000 })
  })
})

// ══════════════════════════════════════════════════════════════════════
// FS: BOOK DETAIL
// ══════════════════════════════════════════════════════════════════════

test.describe('fs: Book Detail', () => {
  test('renders book detail for fs: book from localStorage', async ({ page }) => {
    await page.goto('/library')
    await injectFsBooks(page)

    await page.goto('/book/fs:Толстой - Война и мир')
    await expect(page.locator('h1:has-text("Война и мир")')).toBeVisible({ timeout: 10_000 })

    // "On device" badge
    await expect(page.locator('text=На устройстве')).toBeVisible()
  })

  test('shows cloud upload button for fs: books', async ({ page }) => {
    await page.goto('/library')
    await injectFsBooks(page)

    await page.goto('/book/fs:Толстой - Война и мир')
    await expect(page.locator('h1:has-text("Война и мир")')).toBeVisible({ timeout: 10_000 })

    // Cloud upload button visible
    await expect(page.locator('button:has-text("Загрузить в облако")')).toBeVisible()
    // Hint text
    await expect(page.locator('text=Sync между устройствами')).toBeVisible()
  })

  test('cloud upload triggers paywall for free user', async ({ page }) => {
    await page.goto('/library')
    await injectFsBooks(page)

    await page.goto('/book/fs:Толстой - Война и мир')
    await expect(page.locator('h1:has-text("Война и мир")')).toBeVisible({ timeout: 10_000 })

    await page.locator('button:has-text("Загрузить в облако")').click()

    // Paywall modal should appear
    await expect(page.getByRole('button', { name: /Premium/ })).toBeVisible({ timeout: 5_000 })
  })

  test('synced fs: book shows "In cloud" badge', async ({ page }) => {
    // Inject a synced book
    const syncedBook = makeFsBook('Synced Book', 5)
    syncedBook.synced = true
    await page.goto('/library')
    await page.evaluate(
      ([key, data]) => localStorage.setItem(key, JSON.stringify(data)),
      [FS_BOOKS_KEY, { 'fs:Synced Book': syncedBook }] as const,
    )

    await page.goto('/book/fs:Synced Book')
    await expect(page.locator('h1:has-text("Synced Book")')).toBeVisible({ timeout: 10_000 })

    // Should show "В облаке" badge, NOT upload button
    await expect(page.locator('text=В облаке')).toBeVisible()
    await expect(page.locator('button:has-text("Загрузить в облако")')).not.toBeVisible()
  })

  test('fs: book not found redirects to library', async ({ page }) => {
    await page.goto('/book/fs:NonExistent')
    await expect(page).toHaveURL(/\/library/, { timeout: 10_000 })
  })

  test('play button works for fs: book (attempts playback)', async ({ page }) => {
    await page.goto('/library')
    await injectFsBooks(page)

    await page.goto('/book/fs:Булгаков - Мастер и Маргарита')
    await expect(page.locator('h1:has-text("Мастер и Маргарита")')).toBeVisible({ timeout: 10_000 })

    const playBtn = page.locator('button:has-text("Воспроизвести")')
    await expect(playBtn).toBeVisible()
    await playBtn.click()

    // Fullscreen player should open (even if audio fails on web - no actual files)
    await expect(page.locator('.fixed.inset-0')).toBeVisible({ timeout: 10_000 })
  })
})

// ══════════════════════════════════════════════════════════════════════
// YOUTUBE IMPORT VIEW
// ══════════════════════════════════════════════════════════════════════

test.describe('YouTube Import View', () => {
  test('renders with URL input and Find button', async ({ page }) => {
    await page.goto('/youtube-import')
    await expect(page.locator('h1:has-text("YouTube")')).toBeVisible({ timeout: 10_000 })

    const urlInput = page.locator('input[type="url"]')
    await expect(urlInput).toBeVisible()
    await expect(urlInput).toHaveAttribute('placeholder', /youtube/)

    const findBtn = page.locator('button:has-text("Найти")')
    await expect(findBtn).toBeVisible()
    await expect(findBtn).toBeDisabled() // disabled when URL is empty
  })

  test('Find button enables when URL is entered', async ({ page }) => {
    await page.goto('/youtube-import')
    await expect(page.locator('h1:has-text("YouTube")')).toBeVisible({ timeout: 10_000 })

    await page.locator('input[type="url"]').fill('https://youtube.com/watch?v=test')
    const findBtn = page.locator('button:has-text("Найти")')
    await expect(findBtn).toBeEnabled()
  })

  test('back button navigates back', async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('a[href*="/book/"]').first()).toBeVisible({ timeout: 15_000 })

    await page.goto('/youtube-import')
    await expect(page.locator('h1:has-text("YouTube")')).toBeVisible({ timeout: 10_000 })

    await page.goBack()
    await expect(page).toHaveURL(/\/library/, { timeout: 5_000 })
  })
})

// ══════════════════════════════════════════════════════════════════════
// DATA PERSISTENCE
// ══════════════════════════════════════════════════════════════════════

test.describe('fs: data persistence', () => {
  test('fs: books survive page reload', async ({ page }) => {
    await page.goto('/library')
    await injectFsBooks(page)

    // Verify data in localStorage
    const data = await page.evaluate((key) => localStorage.getItem(key), FS_BOOKS_KEY)
    expect(data).toBeTruthy()
    const parsed = JSON.parse(data!)
    expect(Object.keys(parsed)).toHaveLength(3)

    // Reload and verify still there
    await page.reload()
    const afterReload = await page.evaluate((key) => localStorage.getItem(key), FS_BOOKS_KEY)
    expect(afterReload).toBeTruthy()
    expect(JSON.parse(afterReload!)).toEqual(parsed)
  })

  test('fs: books have correct structure', async ({ page }) => {
    await page.goto('/library')
    await injectFsBooks(page)

    const data = JSON.parse((await page.evaluate((key) => localStorage.getItem(key), FS_BOOKS_KEY))!)
    const book = data['fs:Толстой - Война и мир']

    expect(book.id).toBe('fs:Толстой - Война и мир')
    expect(book.title).toBe('Война и мир')
    expect(book.author).toBe('Толстой')
    expect(book.folderPath).toBe('Audiobooks/Толстой - Война и мир')
    expect(book.tracks).toHaveLength(12)
    expect(book.sizeBytes).toBeGreaterThan(0)
    expect(book.synced).toBe(false)
    expect(book.addedAt).toBeTruthy()

    // Track structure
    const track = book.tracks[0]
    expect(track.index).toBe(0)
    expect(track.filename).toBe('01.mp3')
    expect(track.path).toContain('Audiobooks/')
    expect(track.duration).toBeGreaterThan(0)
  })
})

// ══════════════════════════════════════════════════════════════════════
// CLOUD SYNC API
// ══════════════════════════════════════════════════════════════════════

test.describe('Cloud sync endpoint', () => {
  test('returns 403 for free user', async ({ request }) => {
    const response = await request.post('/api/user/books/cloud-sync', {
      multipart: {
        title: 'Test',
        files: {
          name: 'test.mp3',
          mimeType: 'audio/mpeg',
          buffer: Buffer.from('fake audio data'),
        },
      },
    })
    // Free user should get 403
    expect(response.status()).toBe(403)
    const body = await response.json()
    expect(body.detail?.error || body.error).toBe('premium_required')
  })
})

// ══════════════════════════════════════════════════════════════════════
// EDGE CASES
// ══════════════════════════════════════════════════════════════════════

test.describe('Edge cases', () => {
  test('empty fs: books localStorage shows no local books', async ({ page }) => {
    await page.goto('/my-library')
    await page.evaluate((key) => localStorage.setItem(key, '{}'), FS_BOOKS_KEY)
    await page.reload()

    await expect(page.locator('text=Моя библиотека')).toBeVisible({ timeout: 10_000 })
    await page.locator('button:has-text("Локальные")').click()

    // No local books should be shown
    const items = page.locator('a[href*="/book/fs:"]')
    await expect(items).toHaveCount(0, { timeout: 3_000 })
  })

  test('corrupted fs: localStorage handled gracefully', async ({ page }) => {
    await page.goto('/my-library')
    await page.evaluate((key) => localStorage.setItem(key, 'not json'), FS_BOOKS_KEY)
    await page.reload()

    // Should not crash, page should load
    await expect(page.locator('text=Моя библиотека')).toBeVisible({ timeout: 10_000 })
  })

  test('onboarding redirect works for new users', async ({ page, context }) => {
    // Clear all storage
    await context.clearCookies()
    await page.goto('/library')
    await page.evaluate(() => localStorage.clear())
    await page.reload()

    // Should redirect to /welcome
    await expect(page).toHaveURL(/\/welcome/, { timeout: 10_000 })
  })
})
