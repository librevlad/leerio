import { test, expect } from '../fixtures'

test.describe('Audio player', { tag: '@needs-books' }, () => {
  async function navigateToBookAndListen(page: import('@playwright/test').Page) {
    await page.goto('/library')
    await expect(page.locator('a.card.card-hover').first()).toBeVisible({ timeout: 15_000 })
    await page.locator('a.card.card-hover').first().click()
    await expect(page).toHaveURL(/\/book\//, { timeout: 10_000 })
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
  }

  test('listen button shows player', async ({ page, takeScreenshot }) => {
    await navigateToBookAndListen(page)
    const listenBtn = page.locator('button.btn-primary').first()
    await expect(listenBtn).toBeVisible()
    await listenBtn.click()

    // Player section should appear
    await expect(page.locator('text=Плеер')).toBeVisible({ timeout: 10_000 })
    await takeScreenshot('player-active')
  })

  test('player shows track info', async ({ page }) => {
    await navigateToBookAndListen(page)
    await page.locator('button.btn-primary').first().click()
    await expect(page.locator('text=Плеер')).toBeVisible({ timeout: 10_000 })

    // Track info is displayed
    const trackInfo = page.locator('text=/Трек \\d+/')
    await expect(trackInfo).toBeVisible()
  })

  test('play/pause button exists', async ({ page }) => {
    await navigateToBookAndListen(page)
    await page.locator('button.btn-primary').first().click()
    await expect(page.locator('text=Плеер')).toBeVisible({ timeout: 10_000 })

    // Large play/pause button
    const playBtn = page.locator('button.flex.h-14.w-14')
    await expect(playBtn).toBeVisible()
  })

  test('speed control button exists', async ({ page, takeScreenshot }) => {
    await navigateToBookAndListen(page)
    await page.locator('button.btn-primary').first().click()
    await expect(page.locator('text=Плеер')).toBeVisible({ timeout: 10_000 })

    // Speed button shows current speed
    const speedBtn = page.locator('button:has-text("x")')
    await expect(speedBtn.first()).toBeVisible()
    await takeScreenshot('player-controls')
  })

  test('track list is visible', async ({ page, takeScreenshot }) => {
    await navigateToBookAndListen(page)
    await page.locator('button.btn-primary').first().click()
    await expect(page.locator('text=Плеер')).toBeVisible({ timeout: 10_000 })

    await expect(page.locator('text=Треки')).toBeVisible()
    await takeScreenshot('player-tracklist')
  })

  test('MiniPlayer appears on navigation away', async ({ page, takeScreenshot }) => {
    await navigateToBookAndListen(page)
    await page.locator('button.btn-primary').first().click()
    await expect(page.locator('text=Плеер')).toBeVisible({ timeout: 10_000 })

    // Navigate away via client-side routing (preserves SPA state)
    const sidebarLink = page.locator('aside a:has-text("Библиотека")')
    const bottomNavLink = page.locator('nav.fixed.bottom-0 a[href="/library"]')
    const navLink = (await sidebarLink.isVisible().catch(() => false)) ? sidebarLink : bottomNavLink
    await navLink.click()
    await expect(page).toHaveURL('/library', { timeout: 10_000 })

    // MiniPlayer should be visible at bottom
    const miniPlayer = page.locator('.fixed.bottom-\\[60px\\],.fixed.md\\:bottom-0').first()
    await expect(miniPlayer).toBeVisible({ timeout: 5_000 })
    await takeScreenshot('mini-player')
  })

  test('sleep timer button exists', async ({ page }) => {
    await navigateToBookAndListen(page)
    await page.locator('button.btn-primary').first().click()
    await expect(page.locator('text=Плеер')).toBeVisible({ timeout: 10_000 })

    // Moon icon button for sleep timer
    const sleepBtn = page
      .locator('button')
      .filter({ has: page.locator('svg') })
      .last()
    await expect(sleepBtn).toBeVisible()
  })
})
