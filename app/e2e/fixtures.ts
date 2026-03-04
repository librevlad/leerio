import { test as base, expect } from '@playwright/test'
import path from 'path'

type Fixtures = {
  takeScreenshot: (name: string) => Promise<void>
}

export const test = base.extend<Fixtures>({
  takeScreenshot: async ({ page }, use, testInfo) => {
    const fn = async (name: string) => {
      const project = testInfo.project.name
      const filePath = path.join('e2e', 'screenshots', `${project}--${name}.png`)
      await page.screenshot({ path: filePath, fullPage: false })
    }
    await use(fn)
  },
})

export { expect }
