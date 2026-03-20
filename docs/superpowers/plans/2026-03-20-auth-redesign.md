# Auth Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full auth redesign: email registration with verification, password reset, visual upgrade of login page, while preserving Google OAuth.

**Architecture:** Backend adds 4 new endpoints + verification_codes table + Resend email. Frontend rewrites LoginView with tab-based form (login/register/forgot/verify). useAuth composable gets 4 new methods.

**Tech Stack:** FastAPI, SQLite, Resend API (email), Vue 3, TypeScript

**Spec:** `docs/superpowers/specs/2026-03-20-auth-redesign.md`

---

## File Structure

### Create:
- `server/email.py` — Resend email sending (send_verification, send_reset)
- `server/tests/test_auth_registration.py` — backend auth tests

### Modify:
- `server/db.py` — add verification_codes table, register_user(), verify/invalidate code functions, add `active` column
- `server/api.py` — add 4 new auth endpoints (register, verify-email, forgot-password, reset-password)
- `app/src/views/LoginView.vue` — complete rewrite with tabs, forms, animations
- `app/src/composables/useAuth.ts` — add register(), verifyEmail(), forgotPassword(), resetPassword()
- `app/src/api.ts` — add 4 auth API methods
- `app/src/i18n/locales/ru.ts` — add registration/verification/reset translations
- `app/src/i18n/locales/en.ts` — same
- `app/src/i18n/locales/uk.ts` — same

---

## Task 1: Database — verification_codes table + register_user

**Files:**
- Modify: `server/db.py`

- [ ] **Step 1: Add verification_codes table to schema**

In the `_init_db()` function (after existing CREATE TABLE statements), add:

```python
cur.execute("""
    CREATE TABLE IF NOT EXISTS verification_codes (
        email TEXT NOT NULL,
        code TEXT NOT NULL,
        type TEXT NOT NULL,
        attempts INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        expires_at TEXT NOT NULL
    )
""")
```

- [ ] **Step 2: Add register_user function**

```python
def register_user(email: str, name: str, password: str) -> str:
    """Create inactive user with hashed password. Returns user_id."""
    user_id = secrets.token_hex(8)
    salt = secrets.token_hex(16)
    pw_hash = f"{salt}:{hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100_000).hex()}"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO users (user_id, email, name, password_hash, role, plan, active) VALUES (?, ?, ?, ?, 'user', 'free', 0)",
            (user_id, email, name, pw_hash),
        )
    return user_id
```

- [ ] **Step 3: Add activate_user function**

```python
def activate_user(email: str):
    with _connect() as conn:
        conn.execute("UPDATE users SET active = 1 WHERE email = ?", (email,))
```

- [ ] **Step 4: Add verification code functions**

```python
def create_verification_code(email: str, code_type: str) -> str:
    """Generate 6-digit code, store in DB, return code."""
    code = str(secrets.randbelow(900000) + 100000)
    expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    with _connect() as conn:
        # Clean up expired codes
        conn.execute("DELETE FROM verification_codes WHERE expires_at < datetime('now')")
        # Delete existing codes of same type for this email
        conn.execute("DELETE FROM verification_codes WHERE email = ? AND type = ?", (email, code_type))
        conn.execute(
            "INSERT INTO verification_codes (email, code, type, expires_at) VALUES (?, ?, ?, ?)",
            (email, code, code_type, expires),
        )
    return code

def verify_code(email: str, code: str, code_type: str) -> bool:
    """Check code validity. Increments attempts. Returns True if valid."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT code, attempts FROM verification_codes WHERE email = ? AND type = ? AND expires_at > datetime('now')",
            (email, code_type),
        ).fetchone()
        if not row:
            return False
        if row[1] >= 5:  # Max attempts
            return False
        if row[0] != code:
            conn.execute(
                "UPDATE verification_codes SET attempts = attempts + 1 WHERE email = ? AND type = ?",
                (email, code_type),
            )
            return False
        # Valid — delete code
        conn.execute("DELETE FROM verification_codes WHERE email = ? AND type = ?", (email, code_type))
        return True

def update_user_password(email: str, password: str):
    salt = secrets.token_hex(16)
    pw_hash = f"{salt}:{hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100_000).hex()}"
    with _connect() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE email = ?", (pw_hash, email))
```

- [ ] **Step 5: Add `active` column to users table**

In `_init_db()`, after the users CREATE TABLE, add migration:
```python
try:
    cur.execute("ALTER TABLE users ADD COLUMN active INTEGER DEFAULT 1")
except Exception:
    pass  # Column already exists
```

- [ ] **Step 6: Update verify_user_password to check active status**

Find existing `verify_user_password` and add active check:
```python
# After fetching user, before password check:
if not row["active"]:
    return None  # Inactive users can't login
```

- [ ] **Step 7: Verify + commit**

```bash
cd /e/leerio && python -c "from server.db import _init_db; _init_db(); print('OK')"
git commit -m "feat: add verification_codes table and registration DB functions"
```

---

## Task 2: Email sending via Resend

**Files:**
- Create: `server/email.py`

- [ ] **Step 1: Create email.py**

```python
"""Email sending via Resend API."""
import os
import logging
import httpx

logger = logging.getLogger("leerio.email")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = "Leerio <noreply@leerio.app>"


async def send_email(to: str, subject: str, body: str) -> bool:
    if not RESEND_API_KEY:
        logger.info(f"[DEV] Email to {to}: {subject} — {body}")
        return True
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={"from": FROM_EMAIL, "to": [to], "subject": subject, "text": body},
            )
            if res.status_code >= 400:
                logger.error(f"Resend error {res.status_code}: {res.text[:200]}")
                return False
            return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


async def send_verification_code(to: str, code: str):
    await send_email(to, "Код подтверждения Leerio", f"Ваш код подтверждения: {code}\n\nДействителен 15 минут.")


async def send_reset_code(to: str, code: str):
    await send_email(to, "Сброс пароля Leerio", f"Код для сброса пароля: {code}\n\nДействителен 15 минут.")
```

- [ ] **Step 2: Verify + commit**

```bash
cd /e/leerio && python -c "from server.email import send_email; print('OK')"
git commit -m "feat: add Resend email sending module"
```

---

## Task 3: Backend — 4 new auth endpoints

**Files:**
- Modify: `server/api.py`

- [ ] **Step 1: Add register endpoint (after existing auth endpoints ~line 471)**

```python
class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

@app.post("/api/auth/register")
async def auth_register(body: RegisterRequest):
    name = body.name.strip()
    email = body.email.strip().lower()
    password = body.password

    if not name or len(name) > 100:
        raise HTTPException(400, "Name is required (max 100 chars)")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) or len(email) > 255:
        raise HTTPException(400, "Invalid email format")
    if len(password) < 8 or len(password) > 128:
        raise HTTPException(400, "Password must be 8-128 characters")

    existing = db.get_user_by_email(email)
    if existing and existing.get("active", 1):
        raise HTTPException(409, "Email already registered")

    # Create or update inactive user
    if existing:
        db.update_user_password(email, password)
    else:
        db.register_user(email, name, password)

    code = db.create_verification_code(email, "email_verify")
    from .email import send_verification_code
    await send_verification_code(email, code)

    return {"ok": True}
```

- [ ] **Step 2: Add verify-email endpoint**

```python
class VerifyEmailRequest(BaseModel):
    email: str
    code: str

@app.post("/api/auth/verify-email")
async def auth_verify_email(body: VerifyEmailRequest, response: Response):
    email = body.email.strip().lower()
    if not db.verify_code(email, body.code, "email_verify"):
        raise HTTPException(400, "Invalid or expired code")

    db.activate_user(email)
    user = db.get_user_by_email(email)
    if not user:
        raise HTTPException(400, "User not found")

    set_auth_cookie(response, user["user_id"])
    return {k: user[k] for k in ("user_id", "email", "name", "picture", "role", "plan")}
```

- [ ] **Step 3: Add forgot-password endpoint**

```python
class ForgotPasswordRequest(BaseModel):
    email: str

@app.post("/api/auth/forgot-password")
async def auth_forgot_password(body: ForgotPasswordRequest):
    email = body.email.strip().lower()
    user = db.get_user_by_email(email)
    if user and user.get("active", 1):
        code = db.create_verification_code(email, "password_reset")
        from .email import send_reset_code
        await send_reset_code(email, code)
    # Always return ok (don't leak email existence)
    return {"ok": True}
```

- [ ] **Step 4: Add reset-password endpoint**

```python
class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    password: str

@app.post("/api/auth/reset-password")
async def auth_reset_password(body: ResetPasswordRequest, response: Response):
    email = body.email.strip().lower()
    if len(body.password) < 8 or len(body.password) > 128:
        raise HTTPException(400, "Password must be 8-128 characters")

    if not db.verify_code(email, body.code, "password_reset"):
        raise HTTPException(400, "Invalid or expired code")

    db.update_user_password(email, body.password)
    user = db.get_user_by_email(email)
    if user:
        set_auth_cookie(response, user["user_id"])
    return {"ok": True}
```

- [ ] **Step 5: Add imports at top of api.py**

```python
from .auth import set_auth_cookie  # if not already imported
```

- [ ] **Step 6: Verify + commit**

```bash
cd /e/leerio && python -c "from server.api import app; print('OK')"
cd /e/leerio && python -m ruff check server/api.py
git commit -m "feat: add register, verify-email, forgot-password, reset-password endpoints"
```

---

## Task 4: Frontend — API methods + useAuth

**Files:**
- Modify: `app/src/api.ts`
- Modify: `app/src/composables/useAuth.ts`

- [ ] **Step 1: Add auth API methods to api.ts**

In the `api` object, add after the `logout` line:

```typescript
  // Auth
  register: (name: string, email: string, password: string) =>
    post<{ ok: boolean }>('/auth/register', { name, email, password }),
  verifyEmail: (email: string, code: string) =>
    post<User>('/auth/verify-email', { email, code }),
  forgotPassword: (email: string) =>
    post<{ ok: boolean }>('/auth/forgot-password', { email }),
  resetPassword: (email: string, code: string, password: string) =>
    post<{ ok: boolean }>('/auth/reset-password', { email, code, password }),
```

- [ ] **Step 2: Add methods to useAuth.ts**

Add these functions inside `useAuth()`, before the return statement:

```typescript
  async function register(name: string, email: string, password: string): Promise<void> {
    const res = await fetch(apiUrl('/auth/register'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ name, email, password }),
    })
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      let detail = text
      try { const json = JSON.parse(text); if (json.detail) detail = json.detail } catch { /* not JSON */ }
      throw new Error(`${res.status}: ${detail}`)
    }
  }

  async function verifyEmail(email: string, code: string): Promise<User> {
    const res = await fetch(apiUrl('/auth/verify-email'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, code }),
    })
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      let detail = text
      try { const json = JSON.parse(text); if (json.detail) detail = json.detail } catch { /* not JSON */ }
      throw new Error(`${res.status}: ${detail}`)
    }
    const data = await res.json()
    user.value = data
    checked.value = true
    loading.value = false
    try { localStorage.setItem(STORAGE.USER, JSON.stringify(data)) } catch { /* full */ }
    return data
  }

  async function forgotPassword(email: string): Promise<void> {
    const res = await fetch(apiUrl('/auth/forgot-password'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email }),
    })
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      throw new Error(text)
    }
  }

  async function resetPassword(email: string, code: string, password: string): Promise<void> {
    const res = await fetch(apiUrl('/auth/reset-password'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, code, password }),
    })
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      let detail = text
      try { const json = JSON.parse(text); if (json.detail) detail = json.detail } catch { /* not JSON */ }
      throw new Error(`${res.status}: ${detail}`)
    }
  }
```

Add to return object: `register, verifyEmail, forgotPassword, resetPassword`

- [ ] **Step 3: Type check + test + commit**

```bash
cd /e/leerio/app && npx vue-tsc --noEmit && npx vitest run
git commit -m "feat: add auth API methods and useAuth registration functions"
```

---

## Task 5: i18n translations

**Files:**
- Modify: `app/src/i18n/locales/ru.ts`, `en.ts`, `uk.ts`

- [ ] **Step 1: Add keys to all 3 locale files**

In the `login` section:

**Russian:**
```typescript
tabLogin: 'Войти',
tabRegister: 'Создать аккаунт',
name: 'Имя',
namePlaceholder: 'Как вас зовут?',
confirmPassword: 'Подтвердите пароль',
register: 'Создать аккаунт',
forgotPassword: 'Забыли пароль?',
hasAccount: 'Уже есть аккаунт?',
backToLogin: 'Назад к входу',
// Verification
verifyTitle: 'Проверьте почту',
verifySubtitle: 'Мы отправили код на {email}',
verifyCode: 'Код подтверждения',
verifyCodePlaceholder: '123456',
verify: 'Подтвердить',
resendCode: 'Отправить повторно',
resendCooldown: 'Повторно через {n} сек',
// Forgot password
forgotTitle: 'Сброс пароля',
forgotSubtitle: 'Введите email для получения кода',
sendCode: 'Отправить код',
enterCode: 'Введите код',
newPassword: 'Новый пароль',
confirmNewPassword: 'Подтвердите пароль',
resetPassword: 'Сбросить пароль',
resetSuccess: 'Пароль изменён!',
// Validation
passwordTooShort: 'Минимум 8 символов',
passwordsDoNotMatch: 'Пароли не совпадают',
emailInvalid: 'Некорректный email',
nameRequired: 'Введите имя',
// Strength
strengthWeak: 'Слабый',
strengthMedium: 'Средний',
strengthStrong: 'Надёжный',
```

English and Ukrainian — same keys, translated values.

- [ ] **Step 2: Commit**

```bash
git commit -m "feat: add auth registration/verification translations"
```

---

## Task 6: LoginView.vue — complete rewrite

**Files:**
- Modify: `app/src/views/LoginView.vue` (175 lines → ~400 lines)

- [ ] **Step 1: Rewrite with tab-based auth form**

The new LoginView has a state machine:
```typescript
type AuthView = 'login' | 'register' | 'verify-email' | 'forgot-password'
const view = ref<AuthView>('login')
```

Each view is a section with `v-if="view === '...'"`.

Key features:
- Tabs "Войти / Создать аккаунт" at top
- Inline validation (email format, password length, passwords match)
- Password strength indicator (weak/medium/strong colored bar)
- Google OAuth button in both login and register views
- Forgot password: 3-step flow (email → code → new password)
- Email verification: code input + resend button with 60s cooldown
- Smooth transitions between views
- All errors shown inline with shake animation
- Loading states on all buttons

The subagent implementing this task should read the full spec at `docs/superpowers/specs/2026-03-20-auth-redesign.md` for visual details.

- [ ] **Step 2: Type check + visual test**

```bash
cd /e/leerio/app && npx vue-tsc --noEmit
```

Open `http://localhost:5173/login` and verify all 4 views work.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: redesign login page with registration and password reset"
```

---

## Task 7: Integration test

- [ ] **Step 1: Run full test suite**

```bash
cd /e/leerio/app && npx vitest run && npx vue-tsc --noEmit && npx eslint src/
```

- [ ] **Step 2: Manual E2E flow**

1. Go to `/login` → see login form
2. Click "Создать аккаунт" → see registration form
3. Fill name + email + password → click register
4. See verification code screen → enter code (from server console in dev)
5. Account created → redirected to library
6. Logout → login with email/password → works
7. Click "Забыли пароль?" → enter email → get code → reset → login with new password
8. Google OAuth → still works

- [ ] **Step 3: Final commit**

```bash
git commit -m "feat: auth redesign — complete implementation"
```
