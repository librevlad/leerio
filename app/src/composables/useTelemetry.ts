/**
 * Minimal telemetry for retention/conversion tracking.
 *
 * Events are sent to /api/telemetry (POST) as fire-and-forget.
 * Falls back silently — telemetry never blocks UX.
 */

import { Capacitor } from '@capacitor/core'

const ENDPOINT = Capacitor.isNativePlatform() ? 'https://app.leerio.app/api/telemetry' : '/api/telemetry'

type TelemetryEvent =
  | 'onboarding_started'
  | 'onboarding_completed'
  | 'resume_clicked'
  | 'upload_started'
  | 'upload_completed'
  | 'upload_failed'
  | 'paywall_shown'
  | 'upgrade_clicked'
  | 'book_played'
  | 'scan_completed'
  | 'scan_books_added'
  | 'player_play'
  | 'player_pause'
  | 'player_error'
  | 'player_load_book'
  | 'time_to_first_audio'
  | 'session_active'

// Track time to first audio play per session
const pageLoadTime = Date.now()
let firstAudioTracked = false

export function useTracking() {
  function track(event: TelemetryEvent, data?: Record<string, unknown>) {
    try {
      const payload = {
        event,
        ts: new Date().toISOString(),
        ...data,
      }
      const body = JSON.stringify(payload)
      if (navigator.sendBeacon) {
        navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'application/json' }))
      } else {
        fetch(ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body,
          keepalive: true,
        }).catch(() => {})
      }
    } catch {
      // Telemetry never throws
    }
  }

  function trackFirstAudio() {
    if (firstAudioTracked) return
    firstAudioTracked = true
    const seconds = Math.round((Date.now() - pageLoadTime) / 1000)
    track('time_to_first_audio', { seconds })
  }

  return { track, trackFirstAudio }
}
