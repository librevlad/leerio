import { test, expect } from '../fixtures'

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
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

    test('shows all nav links', async ({ page }) => {
      const links = ['Дашборд', 'Каталог', 'Моя библиотека', 'Загрузить', 'История', 'Аналитика', 'Настройки']
      for (const label of links) {
        await expect(page.locator(`aside a:has-text("${label}")`)).toBeVisible()
      }
    })

    test('highlights active link', async ({ page }) => {
      // Dashboard should be active on /
      const dashLink = page.locator('aside a[href="/"]')
      await expect(dashLink).toHaveClass(/text-\[--t1\]/)
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

    test('shows user info', async ({ page }) => {
      // User section in sidebar
      const userSection = page.locator('aside').locator('text=@').first()
      await expect(userSection).toBeVisible()
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

    test('shows all tabs', async ({ page }) => {
      const tabs = ['Главная', 'Каталог', 'Моя', 'Найти', 'Ещё']
      for (const label of tabs) {
        await expect(page.locator(`nav.fixed.bottom-0 >> text=${label}`)).toBeVisible()
      }
    })

    test('highlights active tab', async ({ page }) => {
      // On dashboard, "Главная" should be active
      const homeTab = page.locator('nav.fixed.bottom-0 a[href="/"]')
      await expect(homeTab).toHaveClass(/text-\[--accent\]/)
    })

    test('navigates via bottom nav', async ({ page }) => {
      await page.locator('nav.fixed.bottom-0 a[href="/library"]').click()
      await expect(page).toHaveURL('/library', { timeout: 10_000 })
    })
  })

  test('route navigation preserves auth', async ({ page }) => {
    const routes = ['/library', '/history', '/analytics', '/settings']
    for (const route of routes) {
      await page.goto(route)
      // Should not redirect to login
      await expect(page).not.toHaveURL(/\/login/, { timeout: 5_000 })
    }
  })
})
