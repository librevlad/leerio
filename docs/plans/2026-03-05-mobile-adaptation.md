# Mobile Adaptation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make all app sections accessible on mobile via a "More" bottom sheet, fix responsive issues, add PWA manifest.

**Architecture:** Add a BottomSheet component triggered by the "More" tab in BottomNav. Fix HeroStats grid breakpoint. Add manifest.json for PWA install prompt.

**Tech Stack:** Vue 3, Tailwind CSS, TypeScript

---

### Task 1: Create BottomSheet component

**Files:**
- Create: `app/src/components/layout/BottomSheet.vue`

**Step 1: Create the component**

```vue
<script setup lang="ts">
defineProps<{ open: boolean }>()
defineEmits<{ close: [] }>()
</script>

<template>
  <Teleport to="body">
    <transition name="sheet">
      <div v-if="open" class="fixed inset-0 z-[90]" @click.self="$emit('close')">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="$emit('close')" />

        <!-- Sheet -->
        <div class="absolute right-0 bottom-0 left-0 rounded-t-2xl border-t border-[--border]"
          style="background: var(--card-solid)"
        >
          <!-- Handle -->
          <div class="flex justify-center py-3">
            <div class="h-1 w-10 rounded-full bg-white/15" />
          </div>

          <!-- Content -->
          <div class="safe-bottom px-2 pb-4">
            <slot />
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>
```

**Step 2: Verify type-check**

Run: `cd app && npx vue-tsc -b`
Expected: no errors

**Step 3: Commit**

```bash
git add app/src/components/layout/BottomSheet.vue
git commit -m "feat: add BottomSheet component for mobile menus"
```

---

### Task 2: Wire BottomSheet into BottomNav "More" tab

**Files:**
- Modify: `app/src/components/layout/BottomNav.vue`

**Step 1: Update BottomNav to show sheet instead of navigating to settings**

Replace the entire file content with:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IconHome,
  IconLibrary,
  IconFolder,
  IconSearch,
  IconMenu,
  IconUpload,
  IconBookmark,
  IconHistory,
  IconChart,
  IconSettings,
} from '../shared/icons'
import BottomSheet from './BottomSheet.vue'

const route = useRoute()
const router = useRouter()
const showMore = ref(false)

const tabs = [
  { path: '/', label: 'Главная', icon: IconHome },
  { path: '/library', label: 'Каталог', icon: IconLibrary },
  { path: '/my-library', label: 'Моя', icon: IconFolder },
  { path: '/discover', label: 'Найти', icon: IconSearch },
]

const moreLinks = [
  { path: '/upload', label: 'Загрузить', icon: IconUpload },
  { path: '/collections', label: 'Коллекции', icon: IconBookmark },
  { path: '/history', label: 'История', icon: IconHistory },
  { path: '/analytics', label: 'Аналитика', icon: IconChart },
  { path: '/settings', label: 'Настройки', icon: IconSettings },
]

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

const isMoreActive = moreLinks.some((l) => isActive(l.path))

function goTo(path: string) {
  showMore.value = false
  router.push(path)
}
</script>

<template>
  <nav
    class="safe-bottom fixed right-0 bottom-0 left-0 z-50 md:hidden"
    style="
      background: rgba(7, 7, 14, 0.92);
      backdrop-filter: blur(24px) saturate(180%);
      border-top: 1px solid var(--border);
    "
  >
    <div class="flex h-14 items-stretch justify-around">
      <router-link
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        class="relative flex flex-1 flex-col items-center justify-center gap-0.5 no-underline transition-colors duration-200"
        :class="isActive(tab.path) ? 'text-[--accent]' : 'text-[--t3]'"
      >
        <component :is="tab.icon" :size="20" />
        <span class="text-[10px] leading-none font-medium">{{ tab.label }}</span>
      </router-link>

      <!-- More button -->
      <button
        class="relative flex flex-1 cursor-pointer flex-col items-center justify-center gap-0.5 border-0 bg-transparent transition-colors duration-200"
        :class="showMore || isMoreActive ? 'text-[--accent]' : 'text-[--t3]'"
        @click="showMore = !showMore"
      >
        <IconMenu :size="20" />
        <span class="text-[10px] leading-none font-medium">Ещё</span>
      </button>
    </div>
  </nav>

  <BottomSheet :open="showMore" @close="showMore = false">
    <button
      v-for="link in moreLinks"
      :key="link.path"
      class="flex w-full cursor-pointer items-center gap-3.5 rounded-xl border-0 bg-transparent px-4 py-3 text-left transition-colors hover:bg-white/[0.04]"
      :class="isActive(link.path) ? 'text-[--accent]' : 'text-[--t2]'"
      @click="goTo(link.path)"
    >
      <component :is="link.icon" :size="20" />
      <span class="text-[14px] font-medium">{{ link.label }}</span>
    </button>
  </BottomSheet>
</template>
```

**Step 2: Verify type-check and lint**

Run: `cd app && npx vue-tsc -b && npx eslint src/components/layout/BottomNav.vue`
Expected: no errors

**Step 3: Commit**

```bash
git add app/src/components/layout/BottomNav.vue
git commit -m "feat: bottom nav 'More' tab opens sheet with all sections"
```

---

### Task 3: Add CSS transition for BottomSheet

**Files:**
- Modify: `app/src/style.css` (append after fullscreen-player transition block, ~line 506)

**Step 1: Add sheet transition styles**

Append after the `.fullscreen-player-leave-to` rule (after line 506):

```css
/* -- Bottom sheet transition ------------------------------------------ */

.sheet-enter-active {
  transition: opacity 0.25s ease;
}
.sheet-enter-active > :last-child {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.sheet-leave-active {
  transition: opacity 0.2s ease;
}
.sheet-leave-active > :last-child {
  transition: transform 0.2s ease;
}
.sheet-enter-from {
  opacity: 0;
}
.sheet-enter-from > :last-child {
  transform: translateY(100%);
}
.sheet-leave-to {
  opacity: 0;
}
.sheet-leave-to > :last-child {
  transform: translateY(100%);
}
```

**Step 2: Commit**

```bash
git add app/src/style.css
git commit -m "feat: add bottom sheet slide-up transition"
```

---

### Task 4: Fix HeroStats responsive grid

**Files:**
- Modify: `app/src/components/dashboard/HeroStats.vue:18`

**Step 1: Change grid breakpoint**

Change line 18 from:
```html
<div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
```
to:
```html
<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4">
```

This gives 2-column layout on phones (3rd stat wraps to second row) and 3-column on sm+.

**Step 2: Verify type-check**

Run: `cd app && npx vue-tsc -b`
Expected: no errors

**Step 3: Commit**

```bash
git add app/src/components/dashboard/HeroStats.vue
git commit -m "fix: dashboard stats grid 2-col on mobile, 3-col on sm+"
```

---

### Task 5: Add PWA manifest

**Files:**
- Create: `app/public/manifest.json`
- Modify: `app/index.html:5` (add manifest link)

**Step 1: Create manifest.json**

```json
{
  "name": "Leerio",
  "short_name": "Leerio",
  "description": "Менеджер аудиокниг",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#07070e",
  "theme_color": "#07070e",
  "icons": [
    {
      "src": "/logo.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

**Step 2: Add manifest link to index.html**

After the `<link rel="apple-touch-icon" ...>` line (line 6), add:
```html
<link rel="manifest" href="/manifest.json" />
```

**Step 3: Commit**

```bash
git add app/public/manifest.json app/index.html
git commit -m "feat: add PWA manifest for install-to-home-screen"
```

---

### Task 6: Verify everything

**Step 1: Full type-check + lint + test**

Run: `cd app && npx vue-tsc -b && npx eslint src/ && npx prettier --check src/ && npx vitest run`
Expected: all pass

**Step 2: Build check**

Run: `cd app && npx vite build`
Expected: successful build

**Step 3: Push and verify CI**

```bash
git push
gh run watch --exit-status
```
Expected: CI green

---

## Verification checklist

- [ ] All 9 sections accessible on mobile (via 4 tabs + More sheet)
- [ ] "More" sheet opens/closes with animation
- [ ] Dashboard stats don't crush on 320px screens
- [ ] PWA install prompt available on mobile browsers
- [ ] Desktop sidebar unchanged
- [ ] CI passes
