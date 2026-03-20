# Auth Redesign — Login/Registration Page

## Summary

Полный редизайн страницы входа: визуальное обновление + email регистрация + подтверждение email + сброс пароля + Google OAuth. Одна страница `/login` с табами "Войти / Создать аккаунт".

---

## Visual Design

**Layout:** Центрированная карточка с glow-эффектом на тёмном фоне. Табы сверху переключают между "Войти" и "Создать аккаунт". Плавные transitions.

**Элементы:**
- CSS-анимация звуковой волны / наушников сверху
- Inline-валидация (зелёная галка / красный крест)
- Password strength indicator при регистрации
- Skeleton loading на Google кнопке пока SDK грузится
- Shake-анимация при ошибке (уже есть)

### Форма "Войти"
- Email input
- Password input + ссылка "Забыли пароль?" справа
- Кнопка "Войти" (accent gradient)
- Разделитель "или"
- Google OAuth кнопка
- Текст: "Нет аккаунта? Создать" (клик переключает таб)

### Форма "Создать аккаунт"
- Name input
- Email input
- Password input + strength indicator (weak/medium/strong)
- Confirm password input
- Кнопка "Создать аккаунт"
- Разделитель "или"
- Google OAuth кнопка
- Текст: "Уже есть аккаунт? Войти"

### Форма "Забыли пароль" (вместо формы, не отдельная страница)
- Step 1: Email → "Отправить код"
- Step 2: 6-digit code input → "Подтвердить"
- Step 3: New password + confirm → "Сбросить пароль"
- Ссылка "Назад к входу"

### Email Verification (после регистрации)
- Экран: "Проверьте почту" + 6-digit code input
- Кнопка "Подтвердить"
- Ссылка "Отправить код повторно" (cooldown 60 сек)
- Ссылка "Назад"

---

## Backend API

### Новые эндпоинты

#### `POST /api/auth/register`
```json
Request: { "name": "Vlad", "email": "vlad@example.com", "password": "mypassword" }
Response: { "ok": true }
Errors: 400 (validation), 409 (email exists), 429 (rate limit)
```
- Валидация: name not empty, email format, password >= 8 chars
- Hash password (текущий pbkdf2 алгоритм из db.py)
- Create user (active=false)
- Generate 6-digit code → save to `verification_codes`
- Send code via Resend API
- Rate limit: 3/min

#### `POST /api/auth/verify-email`
```json
Request: { "email": "vlad@example.com", "code": "123456" }
Response: { "user_id": "...", "email": "...", "name": "...", ... }
Errors: 400 (invalid/expired code), 429 (too many attempts)
```
- Validate code against `verification_codes` table
- Activate user (active=true)
- Delete code
- Set auth cookie
- Return user object

#### `POST /api/auth/forgot-password`
```json
Request: { "email": "vlad@example.com" }
Response: { "ok": true }
Errors: 429 (rate limit)
```
- Always return `{ ok: true }` (don't leak whether email exists)
- If email exists: generate code → save → send via Resend
- Rate limit: 3/min

#### `POST /api/auth/reset-password`
```json
Request: { "email": "vlad@example.com", "code": "123456", "password": "newpassword" }
Response: { "ok": true }
Errors: 400 (invalid code, weak password), 429
```
- Validate code
- Hash new password
- Update user
- Delete code
- Set auth cookie

### Database Changes

New table:
```sql
CREATE TABLE IF NOT EXISTS verification_codes (
    email TEXT NOT NULL,
    code TEXT NOT NULL,
    type TEXT NOT NULL,  -- 'email_verify' or 'password_reset'
    attempts INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
```

User table changes:
- Add column `active INTEGER DEFAULT 1` (existing users = active)
- Add column `password_hash TEXT` (nullable, for email-registered users)
- Google OAuth users: active=1, password_hash=NULL

### Email via Resend

**Config:** `RESEND_API_KEY` env var. If not set, skip email (dev mode logs code to console).

**Send function:**
```python
async def send_email(to: str, subject: str, body: str):
    key = os.getenv("RESEND_API_KEY")
    if not key:
        logger.info(f"[DEV] Email to {to}: {body}")
        return
    async with httpx.AsyncClient() as client:
        await client.post("https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}"},
            json={"from": "Leerio <noreply@leerio.app>", "to": to, "subject": subject, "text": body})
```

**Templates (plain text):**
- Verification: "Ваш код подтверждения: {code}. Действителен 15 минут."
- Password reset: "Код для сброса пароля: {code}. Действителен 15 минут."

### Verification Codes

- 6-digit random (`secrets.randbelow(900000) + 100000`)
- TTL: 15 минут
- Max 5 attempts per code → code invalidated
- Max 3 codes per email per hour → rate limit
- Code deleted after successful use
- Cleanup: expired codes deleted on each new code generation

### Validation Rules

| Field | Rule |
|-------|------|
| name | Not empty, max 100 chars |
| email | Valid format (regex), max 255 chars |
| password | Min 8 chars, max 128 chars |
| confirm | Must match password (client-side only) |

### Existing Login Changes

- `POST /api/auth/login`: add check `if not user.active: return 403 "Email not verified"`
- Google OAuth: auto-activates users (no email verification needed)

---

## Frontend

### Files to modify
- `app/src/views/LoginView.vue` — complete rewrite

### Composable changes
- `app/src/composables/useAuth.ts` — add `register()`, `verifyEmail()`, `forgotPassword()`, `resetPassword()`

### API changes
- `app/src/api.ts` — add 4 new auth endpoints

### i18n
- Add translation keys for all new strings in ru/en/uk

### State machine

```
idle → login | register | forgot-password | verify-email

login:
  submit → loading → success (redirect) | error

register:
  submit → loading → verify-email | error

verify-email:
  submit → loading → success (redirect) | error
  resend → cooldown (60s)

forgot-password:
  step1 (email) → loading → step2 (code) | error
  step2 (code) → loading → step3 (new password) | error
  step3 (password) → loading → success (redirect) | error
```

### Password Strength Indicator

```typescript
function getStrength(password: string): 'weak' | 'medium' | 'strong' {
  if (password.length < 8) return 'weak'
  const has = {
    lower: /[a-z]/.test(password),
    upper: /[A-Z]/.test(password),
    digit: /\d/.test(password),
    special: /[^a-zA-Z0-9]/.test(password),
  }
  const score = Object.values(has).filter(Boolean).length
  if (password.length >= 12 && score >= 3) return 'strong'
  if (password.length >= 8 && score >= 2) return 'medium'
  return 'weak'
}
```

Visual: colored bar (red/yellow/green) under password field.

---

## What We Don't Change

- Google OAuth flow — works as-is
- JWT cookie mechanism — same 30-day httpOnly cookie
- useAuth composable structure — just add new methods
- Onboarding flow — stays the same (after login redirect)
- Admin/allowlist — still works for Google OAuth

---

## Testing

- Unit: password strength function
- Unit: useAuth new methods (register, verify, forgot, reset) with API mocks
- Unit: backend endpoints (register → verify flow, forgot → reset flow)
- Edge cases: expired codes, wrong codes, duplicate emails, inactive user login
- E2E: register → verify email → login → logout → forgot password → reset → login
