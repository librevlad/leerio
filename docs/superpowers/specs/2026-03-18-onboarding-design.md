# Onboarding Flow — Design Spec

## Goal
3-screen onboarding wizard for first-time users, guiding them to upload audiobooks.

## Trigger
First visit: `localStorage.getItem('leerio_onboarded') !== '1'`
Router redirects `/` → `/welcome`.

## Screens

### Step 1: Value Prop
- Title: "Твоя аудиобиблиотека, наконец организована"
- Subtitle: "Загрузи книги и начни слушать"
- CTA: [Продолжить]

### Step 2: Upload
- Title: "Загрузи свои аудиокниги"
- Drag & drop zone (MP3, M4B, ZIP)
- File picker button as fallback
- Shows uploaded files in realtime
- CTA: [Продолжить] (always enabled)

### Step 3: Done
- Title: "Библиотека готова"
- Subtitle: "Выбери книгу и начни слушать"
- CTA: [Начать слушать] → sets onboarded flag → redirect `/library`

## Files
- Create: `app/src/views/WelcomeView.vue`
- Modify: `app/src/router.ts` (add route + redirect)
- Modify: i18n locales (welcome.* keys)

## Constraints
- No login required
- No blocking if 0 files uploaded
- Dark theme, project design tokens
- i18n: RU/EN/UK
