# Block B — Player UI Improvements

## Goal

Redesign FullscreenPlayer for a more polished look, update skip intervals to -15s/+30s in all player UI, ensure MiniPlayer doesn't overlap content, and audit chapter switching for race conditions.

## Changes

### 1. FullscreenPlayer Redesign

File: `app/src/components/player/FullscreenPlayer.vue`

**Header**: Replace book title with "Сейчас играет" label (uppercase, small, muted text). Keep minimize and book-page buttons.

**Cover**: Increase `max-w-[280px]` → `max-w-[320px]`. Strengthen shadow (`shadow-2xl` → add deeper shadow).

**Track info**: Show **book title** large (16px, bold) instead of track filename. Below: author + chapter counter in one line (e.g. "Автор · Глава 1 из 24").

**Seek bar**: Add a visible thumb circle (12px, accent color) at current position. Show remaining time with minus sign (e.g. "-8:16") on the right instead of total duration.

**Main controls**: Replace `IconRewind15` and `IconForward15` icons with circular buttons containing text labels "-15" and "+30". Style: 40x40 rounded-full, `bg-white/5`, text `font-bold text-sm`. Keep prev/next track and play/pause as-is.

**Secondary controls**: Add text labels below each icon — "Скорость" / speed value, "Сон" / timer value, "Закладка", "Звук". Use small column layout per button.

### 2. Skip Intervals → +30s Forward

All player components call `skipForward(30)` instead of `skipForward()` (default 15):

- `MiniPlayer.vue`: `skipForward()` → `skipForward(30)`, update aria-label
- `FullscreenPlayer.vue`: `skipForward()` → `skipForward(30)`
- `AudioPlayer.vue`: `skipForward()` → `skipForward(30)`

Backward skip stays at 15s (default). Keyboard shortcut (Right Arrow in App.vue) stays at default 15s for precise navigation.

### 3. MiniPlayer Stability

- Verify `mobile-bottom-pad-player` class provides enough padding (currently 140px + safe area — should be sufficient)
- No structural changes needed — existing padding system already handles player overlap

### 4. Chapter Switching Audit

File: `app/src/composables/usePlayer.ts`

Add a guard in `playTrack()` to prevent double invocation:

```ts
async function playTrack(index: number) {
  if (!currentBook.value || index < 0 || index >= tracks.value.length) return
  if (isLoading.value) return  // prevent double-tap race condition
  // ... rest
}
```

Verify `ended` → `nextTrack()` → `playTrack()` chain doesn't cause issues when tracks switch quickly.

### 5. Icon Changes

File: `app/src/components/shared/icons.ts`

No new icons needed — skip buttons switch from icon-based to text-based circular buttons ("-15" / "+30" as text in a styled div).

Remove `IconRewind15` and `IconForward15` imports from FullscreenPlayer (keep in MiniPlayer if still using icons there, or switch MiniPlayer to text too).

**MiniPlayer approach**: Keep icons for compactness but update forward icon label. Actually, MiniPlayer is compact — switch to "-15"/"+30" text labels would be too small. Keep `IconRewind15` icon for -15s. For +30s, create `IconForward30` in icons.ts (same SVG path structure as Forward15 but with "30" text).

## Files Modified

- `app/src/components/player/FullscreenPlayer.vue` — visual redesign + skip 30s
- `app/src/components/player/MiniPlayer.vue` — skip 30s + new icon
- `app/src/components/player/AudioPlayer.vue` — skip 30s
- `app/src/components/shared/icons.ts` — add IconForward30
- `app/src/composables/usePlayer.ts` — playTrack guard

## Not In Scope

- Component rewrites or new components
- Backend changes
- New composables
- Keyboard shortcut changes (stays at 15s default)

## Testing

- Visual: verify FullscreenPlayer layout on mobile and desktop
- Visual: verify MiniPlayer doesn't overlap page content
- Functional: verify +30s skip works in all player components
- Functional: rapid chapter switching doesn't cause double audio
- Unit: existing tests cover skipForward with custom seconds
