import { test, expect } from '../fixtures'

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('.fade-in').first().or(page.locator('.skeleton').first())).toBeVisible({
      timeout: 15_000,
    })
  })

  test.describe('Desktop sidebar', () => {
    test.skip(({ page }) => {
      const vp = page.viewportSize()
      return !!vp && vp.width < 768
    }, 'Desktop only')

    test('sidebar is visible', async ({ page, takeScreenshot }) => {
      await expect(page.locator('aside')).toBeVisible()
      await takeScreenshot('nav-sidebar')
    })

    test('shows nav links', async ({ page }) => {
      const links = ['Каталог', 'Настройки']
      for (const label of links) {
        await expect(page.locator(`aside a:has-text("${label}")`)).toBeVisible()
      }
    })

    test('navigates to library', async ({ page }) => {
      await page.locator('aside a:has-text("Каталог")').click()
      await expect(page).toHaveURL('/library', { timeout: 10_000 })
    })

    test('collapse toggle works', async ({ page, takeScreenshot }) => {
      const toggle = page.locator('button[aria-label="Свернуть"]')
      if (await toggle.isVisible()) {
        await toggle.click()
        await expect(page.locator('button[aria-label="Развернуть"]')).toBeVisible()
        await takeScreenshot('nav-sidebar-collapsed')
      }
    })
  })

  test.describe('Mobile bottom nav', () => {
    test.skip(({ page }) => {
      const vp = page.viewportSize()
      return !!vp && vp.width >= 768
    }, 'Mobile only')

    test('bottom nav is visible', async ({ page, takeScreenshot }) => {
      const bottomNav = page.locator('nav.fixed.bottom-0').first()
      await expect(bottomNav).toBeVisible()
      await takeScreenshot('nav-mobile')
    })

    test('shows tabs', async ({ page }) => {
      const tabs = ['Каталог', 'Настройки']
      for (const label of tabs) {
        await expect(page.locator(`nav.fixed.bottom-0 >> text=${label}`)).toBeVisible()
      }
    })

    test('navigates via bottom nav', async ({ page }) => {
      await page.locator('nav.fixed.bottom-0 a[href="/library"]').click()
      await expect(page).toHaveURL('/library', { timeout: 10_000 })
    })
  })

  test('route navigation preserves auth', async ({ page }) => {
    const routes = ['/library', '/settings']
    for (const route of routes) {
      await page.goto(route)
      await expect(page).not.toHaveURL(/\/login/, { timeout: 5_000 })
    }
  })
})
