# Aradia UI Simplification Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement task-by-task.

**Goal:** Radical UI simplification — remove everything that doesn't affect playback or book finding.

**Architecture:** Remove nav clutter, dashboard widgets, player decorations. Keep only: Home (resume), Library (find+filter), History (track), Player (listen), Settings (configure).

**Tech Stack:** Vue 3, Tailwind CSS, vue-router

---

### Task 1: Simplify BottomNav — 4 tabs, no More menu

**Files:**
- Modify: `app/src/components/layout/BottomNav.vue`

- [ ] **Step 1:** Replace `authTabs` array with 4 items: Home (/), Library (/library), History (/history), Settings (/settings). Remove My Library tab.
- [ ] **Step 2:** Delete `moreLinks` array entirely.
- [ ] **Step 3:** Delete "More" button and BottomSheet import/usage.
- [ ] **Step 4:** Remove BottomSheet component import.
- [ ] **Step 5:** Verify: `npx vue-tsc --noEmit`

---

### Task 2: Simplify AppSidebar — 4 links

**Files:**
- Modify: `app/src/components/layout/AppSidebar.vue`

- [ ] **Step 1:** Replace `mainLinks` array with 4 items: Home, Library, History, Settings. Remove Collections, Want to Read, Analytics, Upload.
- [ ] **Step 2:** Verify: `npx vue-tsc --noEmit`

---

### Task 3: Remove routes — Collections, Analytics, Upload

**Files:**
- Modify: `app/src/router/index.ts`

- [ ] **Step 1:** Remove route definitions for /collections, /analytics, /upload.
- [ ] **Step 2:** Remove from `routeNavKeyMap` if present.
- [ ] **Step 3:** Verify: `npx vue-tsc --noEmit`

Note: Keep view files for now (they're not imported elsewhere). Route removal makes them dead code.

---

### Task 4: Simplify Dashboard — only Continue Listening

**Files:**
- Modify: `app/src/views/DashboardView.vue`

- [ ] **Step 1:** Remove imports: ActivityHeatmap, YearlyGoal, RecentActivity.
- [ ] **Step 2:** Remove template sections: streak card, yearly goal card, smart recommendation, time investment banner, recently added, activity heatmap, recent activity.
- [ ] **Step 3:** Keep ONLY: greeting + hero card (continue listening) + other active books list.
- [ ] **Step 4:** Increase spacing around hero card for breathing room.
- [ ] **Step 5:** Verify: `npx vue-tsc --noEmit && npx vitest run`

---

### Task 5: Simplify Library — keep categories + status, remove rest

**Files:**
- Modify: `app/src/views/LibraryView.vue`

- [ ] **Step 1:** Remove: language filter flags, sort buttons row, view mode toggle ("By Author"), shuffle button, count badge next to title.
- [ ] **Step 2:** Keep: search input, category pills, status dropdown, book grid, infinite scroll.
- [ ] **Step 3:** Increase card spacing for cleaner grid.
- [ ] **Step 4:** Verify: `npx vue-tsc --noEmit`

---

### Task 6: Simplify Book Detail — cover + play + chapters only

**Files:**
- Modify: `app/src/views/BookDetailView.vue`

- [ ] **Step 1:** Remove: star rating, share button, similar books section.
- [ ] **Step 2:** Remove tabs system — keep only Chapters (inline, no tabs). Remove Notes, Quotes, Tags, About tabs.
- [ ] **Step 3:** Keep: back button, cover, title, author, play button, progress card, chapters list, description (below chapters).
- [ ] **Step 4:** Remove APK prompt from book detail (already in App.vue banner).
- [ ] **Step 5:** Verify: `npx vue-tsc --noEmit`

---

### Task 7: Simplify Player mobile — square cover, no vinyl

**Files:**
- Modify: `app/src/components/player/FullscreenPlayer.vue`

- [ ] **Step 1:** Replace vinyl disc (mobile) with simple rounded square cover (240x240, rounded-2xl).
- [ ] **Step 2:** Remove ambient glow div.
- [ ] **Step 3:** Remove playing indicator dot (the orange dot on vinyl).
- [ ] **Step 4:** Increase spacing between elements.
- [ ] **Step 5:** Remove bookmark button from mobile secondary controls (already removed volume).
- [ ] **Step 6:** Mobile secondary = speed + sleep only.
- [ ] **Step 7:** Verify: `npx vue-tsc --noEmit`

---

### Task 8: Reduce visual noise globally

**Files:**
- Modify: `app/src/components/player/MiniPlayer.vue`
- Modify: `app/src/components/shared/BookCard.vue`

- [ ] **Step 1:** MiniPlayer: remove close (X) button — player stays until book finishes or user navigates away.
- [ ] **Step 2:** BookCard: increase padding, simplify to cover + title only (remove author text on grid cards).
- [ ] **Step 3:** Verify: `npx vue-tsc --noEmit && npx vitest run`

---

### Task 9: Final verification

- [ ] **Step 1:** `cd app && npx vue-tsc --noEmit` — type check
- [ ] **Step 2:** `cd app && npx vitest run` — all tests pass
- [ ] **Step 3:** `cd app && npx prettier --check "src/**/*.{ts,vue}"` — formatting
- [ ] **Step 4:** Commit all changes
- [ ] **Step 5:** Push and verify CI
