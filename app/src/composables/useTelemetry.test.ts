import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useTracking } from './useTelemetry'

let sendBeaconMock: ReturnType<typeof vi.fn>
let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-03-20T12:00:00.000Z'))

  sendBeaconMock = vi.fn().mockReturnValue(true)
  vi.stubGlobal('navigator', { sendBeacon: sendBeaconMock })

  fetchMock = vi.fn().mockResolvedValue(new Response())
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('useTelemetry', () => {
  it('track() sends event via sendBeacon when available', () => {
    const { track } = useTracking()
    track('book_played')

    expect(sendBeaconMock).toHaveBeenCalledOnce()
    expect(sendBeaconMock).toHaveBeenCalledWith(
      '/api/telemetry',
      expect.any(Blob),
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('track() falls back to fetch when sendBeacon is not available', () => {
    vi.stubGlobal('navigator', { sendBeacon: undefined })

    const { track } = useTracking()
    track('resume_clicked')

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledWith('/api/telemetry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: expect.stringContaining('"event":"resume_clicked"'),
      keepalive: true,
    })
  })

  it('track() includes event name and timestamp in payload', () => {
    const { track } = useTracking()
    track('onboarding_started')

    const blob: Blob = sendBeaconMock.mock.calls[0][1]
    expect(blob).toBeInstanceOf(Blob)
    expect(blob.type).toBe('application/json')

    // Verify via fetch fallback for easier payload inspection
    vi.stubGlobal('navigator', { sendBeacon: undefined })
    const { track: track2 } = useTracking()
    track2('onboarding_started')

    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body.event).toBe('onboarding_started')
    expect(body.ts).toBe('2026-03-20T12:00:00.000Z')
  })

  it('track() includes extra data in payload', () => {
    vi.stubGlobal('navigator', { sendBeacon: undefined })

    const { track } = useTracking()
    track('book_played', { bookId: 'abc-123', duration: 42 })

    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body.event).toBe('book_played')
    expect(body.bookId).toBe('abc-123')
    expect(body.duration).toBe(42)
  })

  it('track() never throws even if sendBeacon/fetch fails', () => {
    sendBeaconMock.mockImplementation(() => { throw new Error('beacon broken') })

    const { track } = useTracking()
    expect(() => track('paywall_shown')).not.toThrow()

    vi.stubGlobal('navigator', { sendBeacon: undefined })
    fetchMock.mockImplementation(() => { throw new Error('fetch broken') })

    const { track: track2 } = useTracking()
    expect(() => track2('upgrade_clicked')).not.toThrow()
  })
})
