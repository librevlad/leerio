import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL || 'http://localhost:5173'
const isCI = !!process.env.CI
const isExternal = !!process.env.E2E_BASE_URL

export default defineConfig({
  testDir: './e2e/tests',
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  workers: isCI ? 1 : undefined,
  reporter: isCI ? 'github' : 'html',
  timeout: 30_000,

  use: {
    baseURL,
    locale: 'ru-RU',
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
    storageState: 'e2e/.auth/storageState.json',
  },

  projects: [
    {
      name: 'setup',
      testDir: './e2e',
      testMatch: /auth\.setup\.ts/,
      use: { storageState: { cookies: [], origins: [] } },
    },
    {
      name: 'desktop-chrome',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
      dependencies: ['setup'],
    },
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'], viewport: { width: 375, height: 812 } },
      dependencies: ['setup'],
    },
  ],

  ...(isExternal
    ? {}
    : {
        webServer: [
          {
            command: 'cd .. && python -m uvicorn server.api:app --host 0.0.0.0 --port 8000',
            port: 8000,
            reuseExistingServer: true,
            timeout: 30_000,
          },
          {
            command: 'npm run dev',
            port: 5173,
            reuseExistingServer: true,
            timeout: 30_000,
          },
        ],
      }),
})
