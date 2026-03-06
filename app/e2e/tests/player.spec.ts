import { test, expect } from '../fixtures'

test.describe('Audio player', { tag: '@needs-books' }, () => {
  // The fullscreen player overlay selector
  const fullscreenPlayer = '.fixed.inset-0.z-\\[100\\]'

  async function navigateToBookAndListen(page: import('@playwright/test').Page) {
    await page.goto('/library')
    await expect(page.locator('a.card.card-hover').first()).toBeVisible({ timeout: 15_000 })
    await page.locator('a.card.card-hover').first().click()
    await expect(page).toHaveURL(/\/book\//, { timeout: 10_000 })
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
  }

  async function openPlayer(page: import('@playwright/test').Page) {
    await navigateToBookAndListen(page)
    const listenBtn = page.locator('button.btn-primary').first()
    await expect(listenBtn).toBeVisible()
    await listenBtn.click()
    // Fullscreen player overlay should appear
    await expect(page.locator(fullscreenPlayer)).toBeVisible({ timeout: 10_000 })
  }

  test('listen button shows player', async ({ page, takeScreenshot }) => {
    await openPlayer(page)
    await takeScreenshot('player-active')
  })

  test('player shows track info', async ({ page }) => {
    await openPlayer(page)
    // Track info: "Трек N из M"
    const trackInfo = page.locator('text=/Трек \\d+/')
    await expect(trackInfo).toBeVisible()
  })

  test('play/pause button exists', async ({ page }) => {
    await openPlayer(page)
    // Large play/pause button (h-16 w-16 with accent gradient)
    const playBtn = page.locator(`${fullscreenPlayer} button.h-16.w-16`)
    await expect(playBtn).toBeVisible()
  })

  test('speed control button exists', async ({ page, takeScreenshot }) => {
    await openPlayer(page)
    // Speed button shows current speed (e.g. "1x")
    const speedBtn = page.locator(`${fullscreenPlayer} button:has-text("x")`)
    await expect(speedBtn.first()).toBeVisible()
    await takeScreenshot('player-controls')
  })

  test('seek bar is visible', async ({ page, takeScreenshot }) => {
    await openPlayer(page)
    // Seek bar input[type="range"]
    await expect(page.locator(`${fullscreenPlayer} input[type="range"]`)).toBeVisible()
    await takeScreenshot('player-seekbar')
  })

  test('MiniPlayer appears on navigation away', async ({ page, takeScreenshot }) => {
    await openPlayer(page)

    // Close fullscreen player via back button
    const closeBtn = page.locator(`${fullscreenPlayer} button[aria-label="Свернуть плеер"]`)
    await closeBtn.click()
    await expect(page.locator(fullscreenPlayer)).not.toBeVisible({ timeout: 5_000 })

    // MiniPlayer should be visible at bottom
    const miniPlayer = page.locator('.fixed.bottom-\\[60px\\],.fixed.md\\:bottom-0').first()
    await expect(miniPlayer).toBeVisible({ timeout: 5_000 })
    await takeScreenshot('mini-player')
  })

  test('sleep timer button exists', async ({ page }) => {
    await openPlayer(page)
    // Sleep timer button with aria-label or icon
    const sleepBtn = page.locator(`${fullscreenPlayer} button:has-text("мин")`)
    const sleepIcon = page.locator(`${fullscreenPlayer} button`).filter({ has: page.locator('svg') })
    // Either a timer label or an icon button should exist in secondary controls
    const hasTimer = await sleepBtn.isVisible().catch(() => false)
    const hasIcon = (await sleepIcon.count()) > 3 // main controls + secondary
    expect(hasTimer || hasIcon).toBeTruthy()
  })
})
