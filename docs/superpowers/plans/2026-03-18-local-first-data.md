# Local-First Data Layer — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Leerio work fully without login/internet — local-first data with optional cloud sync.

**Architecture:** Replace server-first data flow with IndexedDB as primary store. All reads/writes go to IndexedDB first, then sync to server when online + logged in. Auth guards become optional — unauthenticated users get full local functionality.

**Tech Stack:** IndexedDB (via idb-keyval), existing Vue composables, existing offline queue/cache

---

## Chunk 1: Local Data Store

### Task 1: IndexedDB wrapper for user data

**Files:**
- Create: `app/src/composables/useLocalData.ts`
- Test: `app/src/composables/useLocalData.test.ts`

The composable provides get/set/delete for all user data types using IndexedDB:
- `bookStatus(bookId)` — get/set/delete
- `bookmarks(bookId)` — get/add/remove
- `notes(bookId)` — get/set/delete
- `tags(bookId)` — get/set
- `quotes()` — get/add/delete
- `collections()` — get/add/update/delete
- `playbackPosition(bookId)` — get/set
- `progress(bookId)` — get/set
- `settings()` — get/set
- `rating(bookId)` — get/set

All operations are synchronous-feeling (return cached refs) with async IndexedDB writes behind the scenes.

### Task 2: Wire composable to existing API layer

**Files:**
- Modify: `app/src/api.ts` — `get()` reads from local first, `post/put/del` writes to local + queues server sync
- Modify: `app/src/composables/useOfflineCache.ts` — migrate to use IndexedDB via useLocalData

## Chunk 2: Optional Auth

### Task 3: Make login optional

**Files:**
- Modify: `app/src/router.ts` — remove auth requirement, make all routes accessible
- Modify: `app/src/App.vue` — show app layout for unauthenticated users
- Modify: `app/src/views/DashboardView.vue` — work with local data when not logged in
- Modify: `app/src/composables/useAuth.ts` — add `isGuest` computed

### Task 4: Guest-friendly UI

**Files:**
- Modify key views — show "Login for sync" prompt instead of redirect
- Modify: `app/src/components/layout/AppSidebar.vue` — guest avatar + login link
- Modify: `app/src/components/layout/BottomNav.vue` — accessible without auth

## Chunk 3: Background Sync

### Task 5: Sync engine

**Files:**
- Create: `app/src/composables/useSync.ts` — pull server data into local, push local changes to server
- Modify: `app/src/composables/useOfflineQueue.ts` — integrate with sync engine

### Task 6: Conflict resolution

Simple last-write-wins with timestamps. Server data wins on first sync, local wins on subsequent offline edits.
