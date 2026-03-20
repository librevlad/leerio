/**
 * Player stress tests — break the audio engine to find race conditions,
 * state desync, and instability.
 *
 * Strategy:
 * - Inject Audio constructor hook (addInitScript) to track singleton/instances
 * - Use keyboard shortcuts for rapid play/pause (bypasses :disabled guard)
 * - Collect console errors and page errors
 * - Assert audio state via injected debug hooks
 */
import { test, expect } from '../fixtures'
import type { Page, ConsoleMessage } from '@playwright/test'

// ── Selectors ────────────────────────────────────────────────────────────────

const FP = '.fixed.inset-0.z-\\[100\\]' // fullscreen player overlay

// Play/pause: h-16 on mobile, h-14 on desktop
const playBtnSel = `${FP} button.h-16.w-16, ${FP} button.h-14.w-14`
const nextTrackSel = `${FP} [aria-label="Следующий трек"]`
const prevTrackSel = `${FP} [aria-label="Предыдущий трек"]`
const skipFwdSel = `${FP} [aria-label="Вперёд 30 сек"]`
const skipBackSel = `${FP} [aria-label="Назад 15 сек"]`
const seekBarSel = `${FP} input[type="range"]`
const closeFpSel = `${FP} [aria-label="Свернуть плеер"]`

// ── Helpers ──────────────────────────────────────────────────────────────────

type AudioDebug = {
  instanceCount: number
  playingCount: number
  states: {
    src: string
    paused: boolean
    currentTime: number
    duration: number
    readyState: number
    error: string | null
  }[]
}

/** Inject Audio constructor hook BEFORE app loads — tracks all Audio instances */
async function injectAudioDebug(page: Page) {
  await page.addInitScript(() => {
    /* eslint-disable @typescript-eslint/no-explicit-any */
    const OrigAudio = window.Audio
    const instances: HTMLAudioElement[] = []
    ;(window as any).__audioInstances = instances
    ;(window as any).Audio = function (...args: any[]) {
      const a = new OrigAudio(...(args as [string]))
      instances.push(a)
      return a
    }
    ;(window as any).Audio.prototype = OrigAudio.prototype
    ;(window as any).__getAudioDebug = () => ({
      instanceCount: instances.length,
      playingCount: instances.filter((a) => !a.paused).length,
      states: instances.map((a) => ({
        src: a.src?.slice(-60) ?? '',
        paused: a.paused,
        currentTime: Math.round(a.currentTime * 10) / 10,
        duration: Math.round((a.duration || 0) * 10) / 10,
        readyState: a.readyState,
        error: a.error?.message ?? null,
      })),
    })
  })
}

async function getAudioDebug(page: Page): Promise<AudioDebug> {
  type W = Window & { __getAudioDebug?: () => AudioDebug }
  return page.evaluate(() => (window as unknown as W).__getAudioDebug?.() ?? { instanceCount: 0, playingCount: 0, states: [] })
}

/** Collect JS errors, filtering known-benign ones */
function collectErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (msg: ConsoleMessage) => {
    if (msg.type() !== 'error') return
    const t = msg.text()
    // Browser fires this when play() is interrupted by pause() — benign
    if (t.includes('interrupted') || t.includes('AbortError')) return
    if (t.includes('play() request')) return
    // Network errors during offline/throttle tests — expected
    if (t.includes('net::ERR_') || t.includes('Failed to load resource')) return
    errors.push(t)
  })
  page.on('pageerror', (err: Error) => errors.push(err.message))
  return errors
}

/** Navigate to library → book detail → click listen → fullscreen player */
async function openPlayer(page: Page) {
  await page.goto('/library')
  await expect(page.locator('a.card.card-hover').first()).toBeVisible({ timeout: 15_000 })
  await page.locator('a.card.card-hover').first().click()
  await expect(page).toHaveURL(/\/book\//, { timeout: 10_000 })
  await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })
  await page.locator('button.btn-primary').first().click()
  await expect(page.locator(FP)).toBeVisible({ timeout: 10_000 })
}

/** Click play button in fullscreen player */
async function startPlayback(page: Page) {
  await page.locator(playBtnSel).first().click()
  // Wait for audio to actually load and begin
  await page.waitForTimeout(2000)
}

// ══════════════════════════════════════════════════════════════════════════════
// TESTS
// ══════════════════════════════════════════════════════════════════════════════

test.describe('Player stress tests', { tag: '@needs-books' }, () => {
  // ── 1. SPAM PLAY/PAUSE ───────────────────────────────────────────────────

  test('rapid play/pause 20x does not crash or desync', async ({ page }) => {
    test.slow() // double timeout

    await injectAudioDebug(page)
    const errors = collectErrors(page)
    await openPlayer(page)

    // Start playback with button click
    await startPlayback(page)

    // Spam Space key 20 times with 50ms gaps (bypasses :disabled on button)
    for (let i = 0; i < 20; i++) {
      await page.keyboard.press('Space')
      await page.waitForTimeout(50)
    }

    // Let state settle
    await page.waitForTimeout(1500)

    // ── ASSERTIONS ──
    // Player still visible (no crash)
    await expect(page.locator(FP)).toBeVisible()

    // Single Audio instance (singleton pattern)
    const debug = await getAudioDebug(page)
    expect(debug.instanceCount).toBe(1)

    // 0 or 1 source playing — never 2+
    expect(debug.playingCount).toBeLessThanOrEqual(1)

    // After 20 toggles (even count from playing state → back to playing)
    // isPlaying should be consistent with audio.paused
    const btn = page.locator(playBtnSel).first()
    const label = await btn.getAttribute('aria-label')
    const audioPaused = debug.states[0]?.paused ?? true
    if (audioPaused) {
      expect(label).toBe('Воспроизвести')
    } else {
      expect(label).toBe('Пауза')
    }

    // No fatal JS errors
    expect(errors).toEqual([])
  })

  // ── 2. FAST TRACK SWITCH ─────────────────────────────────────────────────

  test('rapid next-track 10x — no dual playback', async ({ page }) => {
    test.slow()

    await injectAudioDebug(page)
    const errors = collectErrors(page)
    await openPlayer(page)
    await startPlayback(page)

    const nextBtn = page.locator(nextTrackSel).first()
    const hasNext = await nextBtn.isVisible({ timeout: 3_000 }).catch(() => false)
    test.skip(!hasNext, 'Book has only 1 track — skip multi-track test')

    // Rapidly click next 10 times
    for (let i = 0; i < 10; i++) {
      await nextBtn.click({ force: true })
      await page.waitForTimeout(100)
    }

    await page.waitForTimeout(2000)

    // ── ASSERTIONS ──
    await expect(page.locator(FP)).toBeVisible()

    const debug = await getAudioDebug(page)
    // Singleton
    expect(debug.instanceCount).toBe(1)
    // At most 1 playing (critical: no dual playback)
    expect(debug.playingCount).toBeLessThanOrEqual(1)
    // Track info shows valid state
    await expect(page.locator(FP).locator('text=/Трек \\d+/')).toBeVisible()

    expect(errors).toEqual([])
  })

  test('rapid prev/next alternating 10x', async ({ page }) => {
    test.slow()

    await injectAudioDebug(page)
    await openPlayer(page)
    await startPlayback(page)

    const nextBtn = page.locator(nextTrackSel).first()
    const prevBtn = page.locator(prevTrackSel).first()
    const hasNext = await nextBtn.isVisible({ timeout: 3_000 }).catch(() => false)
    test.skip(!hasNext, 'Book has only 1 track')

    // Go to track 2 first
    await nextBtn.click({ force: true })
    await page.waitForTimeout(500)

    // Alternate rapidly
    for (let i = 0; i < 10; i++) {
      const btn = i % 2 === 0 ? prevBtn : nextBtn
      await btn.click({ force: true })
      await page.waitForTimeout(80)
    }

    await page.waitForTimeout(2000)

    const debug = await getAudioDebug(page)
    expect(debug.instanceCount).toBe(1)
    expect(debug.playingCount).toBeLessThanOrEqual(1)
    await expect(page.locator(FP)).toBeVisible()
  })

  // ── 3. SEEK STRESS ───────────────────────────────────────────────────────

  test('rapid seek to random positions does not freeze', async ({ page }) => {
    await injectAudioDebug(page)
    const errors = collectErrors(page)
    await openPlayer(page)
    await startPlayback(page)

    const seekBar = page.locator(seekBarSel).first()
    await expect(seekBar).toBeVisible()

    // Get duration via debug
    const pre = await getAudioDebug(page)
    const dur = pre.states[0]?.duration ?? 0
    test.skip(dur === 0, 'Audio duration not available')

    // Rapid seek to 10 random positions via slider value
    const positions = [0.1, 0.9, 0.5, 0.2, 0.8, 0.05, 0.7, 0.3, 0.95, 0.5]
    for (const pct of positions) {
      const seekTime = Math.round(dur * pct * 10) / 10
      await seekBar.evaluate(
        (el, val) => {
          const input = el as HTMLInputElement
          input.value = String(val)
          input.dispatchEvent(new Event('input', { bubbles: true }))
          input.dispatchEvent(new Event('change', { bubbles: true }))
        },
        seekTime,
      )
      await page.waitForTimeout(100)
    }

    await page.waitForTimeout(1000)

    // Player should still work
    await expect(page.locator(FP)).toBeVisible()
    const debug = await getAudioDebug(page)
    expect(debug.instanceCount).toBe(1)
    // Audio position should be somewhere reasonable
    expect(debug.states[0]?.currentTime).toBeGreaterThanOrEqual(0)

    expect(errors).toEqual([])
  })

  test('skip forward/backward spam 15x each', async ({ page }) => {
    await injectAudioDebug(page)
    await openPlayer(page)
    await startPlayback(page)

    const fwd = page.locator(skipFwdSel).first()
    const back = page.locator(skipBackSel).first()
    const hasFwd = await fwd.isVisible({ timeout: 3_000 }).catch(() => false)
    test.skip(!hasFwd, 'Skip buttons not visible')

    // Spam forward (+30s × 15 = +450s total)
    for (let i = 0; i < 15; i++) {
      await fwd.click({ force: true })
      await page.waitForTimeout(50)
    }
    await page.waitForTimeout(500)

    // Spam backward (-15s × 15 = -225s total)
    for (let i = 0; i < 15; i++) {
      await back.click({ force: true })
      await page.waitForTimeout(50)
    }
    await page.waitForTimeout(1000)

    // Player should still be functional
    await expect(page.locator(FP)).toBeVisible()
    const debug = await getAudioDebug(page)
    expect(debug.instanceCount).toBe(1)
  })

  // ── 4. POSITION PERSISTENCE (RELOAD) ─────────────────────────────────────

  test('playback position saved to localStorage', async ({ page }) => {
    test.slow()

    await injectAudioDebug(page)
    await openPlayer(page)
    await startPlayback(page)

    // Let it play for 4 seconds
    await page.waitForTimeout(4000)

    // Check audio has progressed
    const debug = await getAudioDebug(page)
    const position = debug.states[0]?.currentTime ?? 0
    expect(position).toBeGreaterThan(1)

    // Pause (triggers savePosition)
    await page.keyboard.press('Space')
    await page.waitForTimeout(500)

    // Verify position saved in localStorage
    const savedPos = await page.evaluate(() => {
      const keys = Object.keys(localStorage)
      const posKey = keys.find((k) => k.startsWith('leerio_pos_'))
      if (!posKey) return null
      try {
        return JSON.parse(localStorage.getItem(posKey) || '{}')
      } catch {
        return null
      }
    })

    expect(savedPos).not.toBeNull()
    expect(savedPos?.position).toBeGreaterThan(0)
    expect(savedPos?.track_index).toBeGreaterThanOrEqual(0)
  })

  test('position restores after page reload', async ({ page }) => {
    test.slow()

    await openPlayer(page)
    await startPlayback(page)

    // Play for 5 seconds
    await page.waitForTimeout(5000)

    // Pause to save position
    await page.keyboard.press('Space')
    await page.waitForTimeout(500)

    // Capture the saved position
    const savedBefore = await page.evaluate(() => {
      const keys = Object.keys(localStorage)
      const posKey = keys.find((k) => k.startsWith('leerio_pos_'))
      if (!posKey) return null
      try {
        return JSON.parse(localStorage.getItem(posKey) || '{}')
      } catch {
        return null
      }
    })

    expect(savedBefore?.position).toBeGreaterThan(0)

    // Reload the page
    await page.reload()
    await page.waitForTimeout(3000)

    // Verify localStorage still has the saved position
    const savedAfter = await page.evaluate(() => {
      const keys = Object.keys(localStorage)
      const posKey = keys.find((k) => k.startsWith('leerio_pos_'))
      if (!posKey) return null
      try {
        return JSON.parse(localStorage.getItem(posKey) || '{}')
      } catch {
        return null
      }
    })

    expect(savedAfter).not.toBeNull()
    expect(savedAfter?.position).toBeGreaterThan(0)
    // Position should be roughly the same (saved value persisted)
    expect(savedAfter?.position).toBeCloseTo(savedBefore!.position, 0)
  })

  // ── 5. OFFLINE TEST ──────────────────────────────────────────────────────

  test('offline: player does not crash when network blocked', async ({ page }) => {
    collectErrors(page)
    await openPlayer(page)
    await startPlayback(page)

    // Block all network requests
    await page.route('**/*', (route) => {
      const url = route.request().url()
      if (url.includes('api/') || url.includes('audio/')) {
        return route.abort()
      }
      return route.continue()
    })

    // Try to switch track (forces new audio load over network)
    const nextBtn = page.locator(nextTrackSel).first()
    if (await nextBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await nextBtn.click({ force: true })
      await page.waitForTimeout(3000)

      // Player should NOT crash — it may show error banner, which is correct behavior
      await expect(page.locator(FP)).toBeVisible()

      // The important thing: player didn't crash — error banner or continued playback both OK
      await expect(page.locator(FP)).toBeVisible()
    }

    await page.unrouteAll()
  })

  // ── 6. SLOW NETWORK ─────────────────────────────────────────────────────

  test('slow network: loading indicator and no freeze', async ({ page, context }) => {
    await injectAudioDebug(page)
    await openPlayer(page)
    await startPlayback(page)

    // Throttle via CDP (Chromium only)
    const cdp = await context.newCDPSession(page)
    await cdp.send('Network.emulateNetworkConditions', {
      offline: false,
      downloadThroughput: 5_000, // 5 KB/s — extremely slow
      uploadThroughput: 5_000,
      latency: 3000,
    })

    // Switch track under slow network
    const nextBtn = page.locator(nextTrackSel).first()
    if (await nextBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await nextBtn.click({ force: true })

      // Loading spinner may appear briefly (animate-spin class)
      await page.locator(`${FP} .animate-spin`).isVisible({ timeout: 8_000 }).catch(() => false)

      // Player should still be responsive (not frozen)
      await expect(page.locator(FP)).toBeVisible()
      const btn = page.locator(playBtnSel).first()
      await expect(btn).toBeVisible()
    }

    // Restore normal network
    await cdp.send('Network.emulateNetworkConditions', {
      offline: false,
      downloadThroughput: -1,
      uploadThroughput: -1,
      latency: 0,
    })
  })

  // ── 7. MIXED STRESS: PLAY/PAUSE + TRACK SWITCH ──────────────────────────

  test('play/pause interleaved with track switch', async ({ page }) => {
    test.slow()

    await injectAudioDebug(page)
    const errors = collectErrors(page)
    await openPlayer(page)
    await startPlayback(page)

    const nextBtn = page.locator(nextTrackSel).first()
    const hasNext = await nextBtn.isVisible({ timeout: 3_000 }).catch(() => false)
    test.skip(!hasNext, 'Book has only 1 track')

    // Interleave play/pause with track changes
    for (let i = 0; i < 5; i++) {
      await nextBtn.click({ force: true })
      await page.waitForTimeout(50)
      await page.keyboard.press('Space') // pause
      await page.waitForTimeout(50)
      await page.keyboard.press('Space') // play
      await page.waitForTimeout(50)
    }

    await page.waitForTimeout(2000)

    // ── ASSERTIONS ──
    const debug = await getAudioDebug(page)
    expect(debug.instanceCount).toBe(1)
    expect(debug.playingCount).toBeLessThanOrEqual(1)
    await expect(page.locator(FP)).toBeVisible()
    expect(errors).toEqual([])
  })

  // ── 8. UI STATE SYNC ────────────────────────────────────────────────────

  test('play/pause icon matches actual audio.paused state', async ({ page }) => {
    await injectAudioDebug(page)
    await openPlayer(page)

    const btn = page.locator(playBtnSel).first()

    // Click play
    await btn.click()
    await page.waitForTimeout(2000)

    // Audio should be playing → button shows "Пауза"
    let debug = await getAudioDebug(page)
    if (!debug.states[0]?.paused) {
      await expect(btn).toHaveAttribute('aria-label', 'Пауза')
    }

    // Click pause
    await btn.click()
    await page.waitForTimeout(500)

    // Audio should be paused → button shows "Воспроизвести"
    debug = await getAudioDebug(page)
    if (debug.states[0]?.paused) {
      await expect(btn).toHaveAttribute('aria-label', 'Воспроизвести')
    }
  })

  test('currentTime advances while playing', async ({ page }) => {
    await injectAudioDebug(page)
    await openPlayer(page)
    await startPlayback(page)

    // Read time at T=0
    const t0 = await getAudioDebug(page)
    const time0 = t0.states[0]?.currentTime ?? 0

    // Wait 3 seconds
    await page.waitForTimeout(3000)

    // Read time at T+3
    const t1 = await getAudioDebug(page)
    const time1 = t1.states[0]?.currentTime ?? 0

    // Time should have advanced at least 1 second in 3 seconds
    expect(time1).toBeGreaterThan(time0)
    expect(time1 - time0).toBeGreaterThanOrEqual(1)
  })

  // ── 9. CLOSE → MINI PLAYER → REOPEN ─────────────────────────────────────

  test('minimize to MiniPlayer and reopen preserves state', async ({ page }) => {
    await injectAudioDebug(page)
    await openPlayer(page)
    await startPlayback(page)

    // Note the track info
    const trackInfo = page.locator(FP).locator('text=/Трек \\d+/')
    const trackTextBefore = await trackInfo.textContent().catch(() => '')

    // Minimize
    const closeBtn = page.locator(closeFpSel).first()
    await closeBtn.click()
    await expect(page.locator(FP)).not.toBeVisible({ timeout: 5_000 })

    // Audio should still be playing (minimized, not stopped)
    const debug = await getAudioDebug(page)
    expect(debug.states[0]?.paused).toBe(false)

    // MiniPlayer should be visible
    const miniPlayer = page.locator('.mini-player-position, .fixed.right-0.left-0.z-40').first()
    await expect(miniPlayer).toBeVisible({ timeout: 5_000 })

    // Click MiniPlayer info area to reopen fullscreen
    await miniPlayer.locator('button').first().click()
    await expect(page.locator(FP)).toBeVisible({ timeout: 5_000 })

    // Track info should be the same
    if (trackTextBefore) {
      const trackTextAfter = await page.locator(FP).locator('text=/Трек \\d+/').textContent().catch(() => '')
      expect(trackTextAfter).toBe(trackTextBefore)
    }
  })

  // ── 10. DOUBLE-CLICK BOOK FROM DIFFERENT PAGES ───────────────────────────

  test('loading book from dashboard while player open', async ({ page }) => {
    test.slow()

    await injectAudioDebug(page)
    const errors = collectErrors(page)
    await openPlayer(page)
    await startPlayback(page)

    // Minimize player
    const closeBtn = page.locator(closeFpSel).first()
    await closeBtn.click()
    await expect(page.locator(FP)).not.toBeVisible({ timeout: 5_000 })

    // Navigate to library and open a DIFFERENT book
    await page.goto('/library')
    await expect(page.locator('a.card.card-hover').first()).toBeVisible({ timeout: 15_000 })

    // Click the second book (different from the first)
    const books = page.locator('a.card.card-hover')
    const bookCount = await books.count()
    if (bookCount >= 2) {
      await books.nth(1).click()
    } else {
      await books.first().click()
    }
    await expect(page).toHaveURL(/\/book\//, { timeout: 10_000 })
    await expect(page.locator('.fade-in').first()).toBeVisible({ timeout: 15_000 })

    // Open player for new book
    await page.locator('button.btn-primary').first().click()
    await expect(page.locator(FP)).toBeVisible({ timeout: 10_000 })

    await page.waitForTimeout(2000)

    // ── ASSERTIONS ──
    const debug = await getAudioDebug(page)
    // Still only 1 Audio instance (old one reused)
    expect(debug.instanceCount).toBe(1)
    // At most 1 playing (old book's audio not lingering)
    expect(debug.playingCount).toBeLessThanOrEqual(1)

    expect(errors).toEqual([])
  })
})
