# Mobile Adaptation Design

## Problem

Bottom nav has 5 tabs but the app has 9 sections. History, Analytics, Collections, Upload are unreachable on mobile. The "More" tab navigates directly to Settings instead of showing a menu.

## Solution

### A. Bottom Sheet "More" Menu

Replace direct Settings navigation with a bottom sheet overlay listing all secondary pages:

- Загрузить (Upload)
- Коллекции (Collections)
- История (History)
- Аналитика (Analytics)
- Настройки (Settings)

Tap outside or swipe down to close. Each item navigates and closes the sheet.

### B. Bottom Nav Label Refinements

| Before | After |
|--------|-------|
| LibriVox | Найти |
| Ещё (→ Settings) | Ещё (→ sheet) |

### C. Dashboard Responsive Fix

HeroStats grid: `grid-cols-2 sm:grid-cols-3` so stats don't crush on narrow screens.

### D. PWA Manifest

Add `manifest.json` with app name, icons, `display: standalone`, theme color. Add Apple meta tags for iOS standalone mode.

## Non-goals

- No swipe gestures between pages
- No offline-first PWA (service worker)
- No redesign of card layouts
