# Block A — Android Media Session & Background Playback

## Goal

Polish Media Session integration so Android shows full media notification (artwork, controls) during audiobook playback. Background playback already works via HTMLAudioElement.

## Current State

`usePlayer.ts` already has:
- `updateMediaSession()` setting title, artist, album
- Action handlers: play, pause, previoustrack, nexttrack, seekto
- HTMLAudioElement continues playing in background (native browser behavior)

**Missing:**
- `artwork` not set in MediaMetadata — no cover in Android notification
- No `seekbackward` / `seekforward` handlers
- No `positionState` updates — Android can't show progress bar in notification

## Changes

### 1. Artwork via Blob URL

In `usePlayer.ts`:

- Add `coverBlobUrl` ref (string | null)
- On `loadBook()`: fetch `/api/books/{id}/cover` → create blob URL via `URL.createObjectURL()`
- On `updateMediaSession()`: pass blob URL in `artwork` array as `[{src, sizes: "512x512", type: "image/png"}]`
- On book change or player close: `URL.revokeObjectURL()` to free memory
- Fallback: if fetch fails, omit artwork (notification still works, just no image)

Why blob URL: Media Session may not send auth cookies when fetching artwork from a protected endpoint. Blob URLs are local and bypass this entirely.

### 2. seekbackward / seekforward Handlers

Add to `updateMediaSession()`:

```ts
navigator.mediaSession.setActionHandler('seekbackward', () => skipBackward(10))
navigator.mediaSession.setActionHandler('seekforward', () => skipForward(30))
```

Intervals: -10s back / +30s forward (Android standard, matches Google Podcasts / Audible behavior). These are independent of the in-app UI skip intervals (-15s / +15s in MiniPlayer).

### 3. Position State

Call `navigator.mediaSession.setPositionState()` at:

- `loadedmetadata` event (duration becomes known)
- `timeupdate` event (throttled — only when position changes by ≥1s)
- `playbackRate` change

Payload:
```ts
navigator.mediaSession.setPositionState({
  duration: audio.duration,
  position: audio.currentTime,
  playbackRate: audio.playbackRate
})
```

This enables the progress bar in Android notification and lock screen.

## Files Modified

- `app/src/composables/usePlayer.ts` — all changes in this single file

## Not In Scope

- Web Lock API — not needed, Media Session keeps process alive
- visibilitychange position save — existing 10s interval sufficient
- New components — none
- Backend changes — none
- UI changes — none (this block is purely about Android notification integration)

## Testing

- Manual: play a book on Android Chrome/PWA, verify notification shows cover + controls
- Manual: verify seekbackward/seekforward buttons work from notification
- Manual: verify progress bar updates in notification
- Unit: mock `navigator.mediaSession` and verify handlers are registered
