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

- Add `coverBlobUrl` ref (string | null) and `coverMimeType` ref (string)
- On `loadBook()`: resolve cover URL by book type:
  - **Catalog books**: `coverUrl(id)` → `/api/books/{id}/cover`
  - **User books** (`ub:` prefix): `userBookCoverUrl(slug)` → `/api/user/books/{slug}/cover`
  - **Local books** (`lb:` prefix): get cover from IndexedDB via `useLocalBooks()` composable
- Fetch the cover → read `Content-Type` from response headers → create blob URL via `URL.createObjectURL()`
- On `updateMediaSession()`: pass blob URL in `artwork` array as `[{src, sizes: "512x512", type: mimeType}]`
- **Skip artwork** if response Content-Type is `image/svg+xml` (placeholder) — Android Chrome does not reliably render SVG in media notifications; no image is better than a broken image
- On book change: `URL.revokeObjectURL(coverBlobUrl.value)` before loading new cover
- On `closePlayer()`: `URL.revokeObjectURL(coverBlobUrl.value)` before nulling state
- Fallback: if fetch fails (including CORS failure on S3 redirect), omit artwork

Why blob URL: Media Session may not send auth cookies when fetching artwork from a protected endpoint. Blob URLs are local and bypass this entirely.

**Note on S3 redirects**: For catalog books, the cover endpoint may return a 302 redirect to an S3 presigned URL (`ams1.vultrobjects.com`). `fetch()` follows redirects automatically. If S3 CORS headers are missing, the fetch will fail — the fallback (omit artwork) handles this gracefully.

### 2. seekbackward / seekforward Handlers

Add to `updateMediaSession()`:

```ts
navigator.mediaSession.setActionHandler('seekbackward', (details) => {
  skipBackward(details.seekOffset ?? 10)
})
navigator.mediaSession.setActionHandler('seekforward', (details) => {
  skipForward(details.seekOffset ?? 30)
})
```

Uses `details.seekOffset` from the platform when provided, falls back to -10s / +30s (Android standard, matches Google Podcasts / Audible). These are independent of the in-app UI skip intervals (-15s / +15s in MiniPlayer).

### 3. Position State

Call `navigator.mediaSession.setPositionState()` on specific events (NOT on `timeupdate` — that causes notification progress bar stutter on some Android devices):

- `loadedmetadata` — duration becomes known
- `play` — playback starts
- `pause` — playback pauses
- `seeked` — user seeks to new position
- `ratechange` — playback speed changes

The browser extrapolates position between updates using the reported playback rate.

Payload:
```ts
navigator.mediaSession.setPositionState({
  duration: audio.duration,
  position: audio.currentTime,
  playbackRate: audio.playbackRate
})
```

Extract as helper `updatePositionState()` and call from relevant event handlers in `ensureAudio()`.

## Files Modified

- `app/src/composables/usePlayer.ts` — all changes in this single file

## Not In Scope

- Web Lock API — not needed, Media Session keeps process alive
- visibilitychange position save — existing 10s interval sufficient
- New components — none
- Backend changes — none
- UI changes — none (this block is purely about Android notification integration)

## Testing

- Manual: play a catalog book on Android Chrome/PWA, verify notification shows cover + controls
- Manual: play a user book, verify artwork appears
- Manual: verify seekbackward/seekforward buttons work from notification
- Manual: verify progress bar updates in notification
- Manual: verify book with no cover shows notification without broken image
- Manual: verify cover updates when switching books
- Unit: mock `navigator.mediaSession` and verify handlers are registered
