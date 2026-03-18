/**
 * Minimal telemetry for retention/conversion tracking.
 *
 * Events are sent to /api/telemetry (POST) as fire-and-forget.
 * Falls back silently — telemetry never blocks UX.
 */

const ENDPOINT = '/api/telemetry'

type TelemetryEvent =
  | 'onboarding_started'
  | 'onboarding_completed'
  | 'resume_clicked'
  | 'upload_started'
  | 'upload_completed'
  | 'paywall_shown'
  | 'upgrade_clicked'
  | 'book_played'

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
        navigator.sendBeacon(ENDPOINT, body)
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

  return { track }
}
