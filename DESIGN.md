# Design System — Leerio

## Product Context
- **What this is:** Audiobook player for personal audiobook libraries (BYO files + public domain catalog)
- **Who it's for:** People who download/own audiobooks and want a modern player with cloud sync
- **Space/industry:** Audiobooks — competing with Smart AudioBook Player, Audible, Storytel, Audiobookshelf
- **Project type:** PWA + Android app (dark-first, mobile-first)

## Aesthetic Direction
- **Direction:** Industrial/Utilitarian + Luxury — cinematic darkness with warm lamp light
- **Decoration level:** Intentional — orange glow as light source, not decoration for its own sake
- **Mood:** Like listening in a dark cinema with a warm reading lamp. The covers glow against deep black. Controls are precise and functional. Nothing competes with the book.
- **Differentiation:** Deep black (#0b0b0f) is darker than Spotify (#121212), making covers pop. Orange accent is unique in the category (Spotify=green, Audible=blue, Storytel=red).

## Typography
- **Display/Hero:** Satoshi (700, 900) — geometric, modern, excellent Cyrillic. Used for page titles, book titles, hero text
- **Body/UI:** DM Sans (400, 500, 600) — clean, readable, tabular-nums for timers and stats
- **UI/Labels:** DM Sans 500 — same as body for consistency
- **Data/Tables:** DM Sans (tabular-nums) — aligned numbers in player, stats, progress
- **Code/Time:** JetBrains Mono (400, 500) — player timestamps, track counters
- **Loading:** Satoshi via api.fontshare.com, DM Sans + JetBrains Mono via Google Fonts
- **Scale:**
  - 11px — captions, labels, badges
  - 12px — secondary text, timestamps
  - 13-14px — body text, UI elements
  - 16px — section labels
  - 18-20px — page titles
  - 24-32px — hero headings
  - 48px — display (landing only)

## Color
- **Approach:** Restrained — 1 accent (orange) + neutrals. Orange = warm, analog, like a tube amplifier
- **Surfaces:**
  - `--bg: #0b0b0f` — deep black background
  - `--card: #121218` — card/elevated surface
  - `--card-hover: #16161d` — interactive hover
  - `--card-solid: #121218` — opaque card (overlays)
  - `--sidebar: #0e0e14` — navigation sidebar
  - `--pill: rgba(255,255,255,0.06)` — filter pills, tags
- **Borders:**
  - `--border: #1f1f26` — default border
  - `--border-light: rgba(255,255,255,0.1)` — subtle separators
- **Text:**
  - `--t1: #ffffff` — primary text (headings, important)
  - `--t2: #a1a1aa` — secondary text (descriptions, metadata)
  - `--t3: #505068` — muted text (captions, timestamps, labels)
- **Accent:**
  - `--accent: #ff8a00` — primary action, active states, focus rings
  - `--accent-2: #ffaa40` — lighter accent for gradients
  - `--accent-soft: rgba(255,138,0,0.12)` — accent backgrounds
  - `--gradient-accent: linear-gradient(135deg, #ff8a00, #e07000)` — primary buttons
  - `--gradient-bar: linear-gradient(90deg, #ff8a00, #ffaa40, #ffc878)` — progress bars
  - `--bg-glow: radial-gradient(ellipse 80% 60% at 50% -10%, rgba(255,138,0,0.06), transparent 70%)` — ambient glow
- **Semantic:**
  - Success: `#22c55e` — completed, downloaded, synced
  - Warning: `#f59e0b` — paused, attention needed
  - Error: `#ef4444` — failed, destructive actions
  - Info: `#3b82f6` — loading, informational
- **Dark mode:** This IS the dark mode. No light theme planned.

## Spacing
- **Base unit:** 4px
- **Density:** Comfortable — generous padding for touch targets
- **Scale:** 2xs(2) xs(4) sm(8) md(16) lg(24) xl(32) 2xl(48) 3xl(64)
- **Touch targets:** Minimum 44px height for interactive elements
- **Content padding:** px-4 (16px) mobile, px-6 (24px) desktop

## Layout
- **Approach:** Grid-disciplined — strict grid, cards, clean lines
- **Grid:** 1 column (mobile), 2-3 columns (tablet), 3-4 columns (desktop) for book cards
- **Sidebar:** 240px fixed on desktop, hidden on mobile (bottom nav replaces)
- **Max content width:** 1280px
- **Border radius:**
  - sm: 4px — pills, badges, small chips
  - md: 8px — buttons, inputs, tags
  - lg: 12px — cards, modals, panels
  - xl: 16px — fullscreen player, large containers
  - full: 9999px — avatars, play button

## Motion
- **Approach:** Intentional — micro-animations on buttons, smooth player transitions
- **Easing:** enter(ease-out) exit(ease-in) move(ease-in-out)
- **Duration:** micro(50-100ms) short(150-250ms) medium(250-400ms) long(400-700ms)
- **Specific:**
  - Button press: scale(0.97) 100ms
  - Card hover: translateY(-2px) 150ms
  - Fullscreen player: slide-up 300ms ease-out
  - Mini player: height transition 200ms
  - Page transitions: fade 150ms
  - Ripple effect: 400ms radial expand
- **Reduce motion:** Respect `prefers-reduced-motion` — disable all transforms, keep opacity transitions

## Category Colors
Each book category has its own gradient for card backgrounds:
- Бизнес: `linear-gradient(135deg, #92400e, #d97706)`
- Отношения: `linear-gradient(135deg, #9d174d, #db2777)`
- Саморазвитие: `linear-gradient(135deg, #9a5c16, #E8923A)`
- Художественная: `linear-gradient(135deg, #155e75, #0891b2)`
- Языки: `linear-gradient(135deg, #064e3b, #059669)`

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-24 | Initial design system created | Formalized existing organic design from CLAUDE.md + code. Research: Spotify, Audible, Smart ABP, Storytel |
| 2026-03-24 | Satoshi as display font | Geometric, modern, excellent Cyrillic — differentiates from Inter/system used by all competitors |
| 2026-03-24 | DM Sans as body font | Clean, readable, tabular-nums for player timers — better than system font for brand consistency |
| 2026-03-24 | Deep black #0b0b0f | Darker than Spotify #121212 — cinematic, covers pop against the background |
| 2026-03-24 | Orange accent #ff8a00 | Unique in category (Spotify=green, Audible=blue, Storytel=red). Warm, analog, lamp-like |
| 2026-03-24 | Semantic colors added | success/warning/error/info for consistent status communication across the app |
