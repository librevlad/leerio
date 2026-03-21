<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { version } from '../../package.json'

const router = useRouter()
const { t } = useI18n()
const auth = useAuth()

type AuthView = 'login' | 'register' | 'verify-email' | 'forgot-step1' | 'forgot-step2' | 'forgot-step3'
const view = ref<AuthView>('login')

const email = ref('')
const password = ref('')
const name = ref('')
const confirmPassword = ref('')
const verifyCode = ref('')
const forgotCode = ref('')
const newPassword = ref('')
const confirmNewPassword = ref('')
const error = ref('')
const loading = ref(false)
const resendCooldown = ref(0)
let resendTimer: ReturnType<typeof setInterval> | null = null

// Password strength
function getStrength(pw: string): 'weak' | 'medium' | 'strong' {
  if (pw.length < 8) return 'weak'
  const checks = [/[a-z]/, /[A-Z]/, /\d/, /[^a-zA-Z0-9]/].filter((r) => r.test(pw)).length
  if (pw.length >= 12 && checks >= 3) return 'strong'
  if (pw.length >= 8 && checks >= 2) return 'medium'
  return 'weak'
}

const strength = computed(() => getStrength(password.value))
const strengthLabel = computed(() =>
  t(`login.strength${strength.value.charAt(0).toUpperCase() + strength.value.slice(1)}`),
)
const strengthTextClass = computed(
  () =>
    ({
      weak: 'text-red-400',
      medium: 'text-yellow-400',
      strong: 'text-green-400',
    })[strength.value],
)

function strengthColor(index: number) {
  const s = strength.value
  if (s === 'weak') return index === 0 ? 'bg-red-400' : 'bg-white/[0.06]'
  if (s === 'medium') return index <= 1 ? 'bg-yellow-400' : 'bg-white/[0.06]'
  return 'bg-green-400'
}

function switchTo(v: AuthView) {
  view.value = v
  error.value = ''
}

function startResendCooldown() {
  resendCooldown.value = 60
  if (resendTimer) clearInterval(resendTimer)
  resendTimer = setInterval(() => {
    resendCooldown.value--
    if (resendCooldown.value <= 0 && resendTimer) {
      clearInterval(resendTimer)
      resendTimer = null
    }
  }, 1000)
}

// Handlers
async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.loginWithPassword(email.value, password.value)
    router.push('/library')
  } catch (e) {
    error.value = e instanceof Error ? e.message.replace(/^\d+:\s*/, '') : String(e)
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  error.value = ''
  loading.value = true
  try {
    await auth.register(name.value, email.value, password.value)
    view.value = 'verify-email'
    startResendCooldown()
  } catch (e) {
    error.value = e instanceof Error ? e.message.replace(/^\d+:\s*/, '') : String(e)
  } finally {
    loading.value = false
  }
}

async function handleVerify() {
  error.value = ''
  loading.value = true
  try {
    await auth.verifyEmail(email.value, verifyCode.value)
    router.push('/library')
  } catch (e) {
    error.value = e instanceof Error ? e.message.replace(/^\d+:\s*/, '') : String(e)
  } finally {
    loading.value = false
  }
}

async function handleResend() {
  try {
    await auth.register(name.value, email.value, password.value)
    startResendCooldown()
    error.value = ''
  } catch (e) {
    error.value = e instanceof Error ? e.message.replace(/^\d+:\s*/, '') : String(e)
  }
}

async function handleForgotSend() {
  error.value = ''
  loading.value = true
  try {
    await auth.forgotPassword(email.value)
    view.value = 'forgot-step2'
  } catch (e) {
    error.value = e instanceof Error ? e.message.replace(/^\d+:\s*/, '') : String(e)
  } finally {
    loading.value = false
  }
}

function handleForgotVerify() {
  view.value = 'forgot-step3'
}

async function handleResetPassword() {
  error.value = ''
  loading.value = true
  try {
    await auth.resetPassword(email.value, forgotCode.value, newPassword.value)
    router.push('/library')
  } catch (e) {
    error.value = e instanceof Error ? e.message.replace(/^\d+:\s*/, '') : String(e)
  } finally {
    loading.value = false
  }
}

// Google OAuth
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: Record<string, unknown>) => void
          renderButton: (el: HTMLElement, config: Record<string, unknown>) => void
        }
      }
    }
  }
}

const googleBtnRef = ref<HTMLElement | null>(null)

function initializeGsi() {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
  if (!clientId || !window.google?.accounts?.id) return

  window.google.accounts.id.initialize({
    client_id: clientId,
    callback: handleCredentialResponse,
  })

  if (googleBtnRef.value) {
    window.google.accounts.id.renderButton(googleBtnRef.value, {
      theme: 'filled_black',
      size: 'large',
      text: 'signin_with',
      width: '100%',
    })
  }
}

async function handleCredentialResponse(response: { credential: string }) {
  error.value = ''
  loading.value = true
  try {
    await auth.loginWithGoogle(response.credential)
    router.push('/library')
  } catch (e) {
    error.value = e instanceof Error ? e.message.replace(/^\d+:\s*/, '') : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (window.google?.accounts?.id) {
    initializeGsi()
    return
  }
  const existing = document.querySelector('script[src*="accounts.google.com/gsi/client"]')
  if (existing) {
    existing.addEventListener('load', initializeGsi, { once: true })
    return
  }
  const script = document.createElement('script')
  script.src = 'https://accounts.google.com/gsi/client'
  script.async = true
  script.onload = initializeGsi
  document.head.appendChild(script)
})
</script>

<template>
  <div
    class="flex min-h-screen items-center justify-center px-4"
    style="background: radial-gradient(ellipse at center top, rgba(232, 146, 58, 0.08), transparent 60%)"
  >
    <div class="w-full max-w-sm">
      <!-- Logo -->
      <div class="mb-8 text-center">
        <img src="/logo.png" alt="Leerio" class="mx-auto h-12 w-12 rounded-xl" />
        <h1 class="mt-3 text-[22px] font-bold text-[--t1]">Leerio</h1>
      </div>

      <!-- Card -->
      <div
        class="rounded-2xl border border-white/[0.06] px-6 py-6"
        style="background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(20px)"
      >
        <!-- Tabs (only for login/register views) -->
        <div
          v-if="view === 'login' || view === 'register'"
          class="mb-5 flex rounded-lg p-0.5"
          style="background: rgba(255, 255, 255, 0.04)"
        >
          <button
            class="flex-1 rounded-md py-2 text-[13px] font-medium transition-all"
            :class="view === 'login' ? 'bg-white/[0.08] text-[--t1]' : 'text-[--t3]'"
            @click="switchTo('login')"
          >
            {{ t('login.tabLogin') }}
          </button>
          <button
            class="flex-1 rounded-md py-2 text-[13px] font-medium transition-all"
            :class="view === 'register' ? 'bg-white/[0.08] text-[--t1]' : 'text-[--t3]'"
            @click="switchTo('register')"
          >
            {{ t('login.tabRegister') }}
          </button>
        </div>

        <!-- Error -->
        <div v-if="error" class="shake mb-4 rounded-lg bg-red-500/10 px-3 py-2 text-[12px] text-red-400">
          {{ error }}
        </div>

        <!-- LOGIN VIEW -->
        <form v-if="view === 'login'" class="space-y-4" @submit.prevent="handleLogin">
          <div>
            <input
              v-model="email"
              type="email"
              :placeholder="t('login.email')"
              autocomplete="email"
              class="input-field w-full px-3.5 py-2.5"
            />
          </div>
          <div>
            <input
              v-model="password"
              type="password"
              :placeholder="t('login.password')"
              autocomplete="current-password"
              class="input-field w-full px-3.5 py-2.5"
            />
            <button
              type="button"
              class="mt-1.5 cursor-pointer border-0 bg-transparent p-0 text-[11px] text-[--accent]"
              @click="switchTo('forgot-step1')"
            >
              {{ t('login.forgotPassword') }}
            </button>
          </div>
          <button type="submit" class="btn-primary w-full py-2.5" :disabled="!email || !password || loading">
            {{ loading ? t('login.loading') : t('login.signIn') }}
          </button>
        </form>

        <!-- REGISTER VIEW -->
        <form v-if="view === 'register'" class="space-y-4" @submit.prevent="handleRegister">
          <div>
            <input
              v-model="name"
              type="text"
              :placeholder="t('login.namePlaceholder')"
              autocomplete="name"
              class="input-field w-full px-3.5 py-2.5"
            />
            <p v-if="name.length > 0 && !name.trim()" class="mt-1 text-[11px] text-red-400">
              {{ t('login.nameRequired') }}
            </p>
          </div>
          <div>
            <input
              v-model="email"
              type="email"
              :placeholder="t('login.email')"
              autocomplete="email"
              class="input-field w-full px-3.5 py-2.5"
            />
          </div>
          <div>
            <input
              v-model="password"
              type="password"
              :placeholder="t('login.password')"
              autocomplete="new-password"
              class="input-field w-full px-3.5 py-2.5"
            />
            <!-- Strength bar -->
            <div v-if="password.length > 0" class="mt-1.5 flex items-center gap-2">
              <div class="flex flex-1 gap-1">
                <div class="h-1 flex-1 rounded-full" :class="strengthColor(0)" />
                <div class="h-1 flex-1 rounded-full" :class="strengthColor(1)" />
                <div class="h-1 flex-1 rounded-full" :class="strengthColor(2)" />
              </div>
              <span class="text-[10px]" :class="strengthTextClass">{{ strengthLabel }}</span>
            </div>
          </div>
          <div>
            <input
              v-model="confirmPassword"
              type="password"
              :placeholder="t('login.confirmPassword')"
              autocomplete="new-password"
              class="input-field w-full px-3.5 py-2.5"
            />
            <p v-if="confirmPassword && password !== confirmPassword" class="mt-1 text-[11px] text-red-400">
              {{ t('login.passwordsDoNotMatch') }}
            </p>
          </div>
          <button
            type="submit"
            class="btn-primary w-full py-2.5"
            :disabled="!name.trim() || !email || password.length < 8 || password !== confirmPassword || loading"
          >
            {{ loading ? t('login.registering') : t('login.register') }}
          </button>
        </form>

        <!-- VERIFY EMAIL VIEW -->
        <div v-if="view === 'verify-email'" class="space-y-4">
          <div class="text-center">
            <div class="mb-2 text-[32px]">&#x1F4E7;</div>
            <h2 class="text-[16px] font-bold text-[--t1]">{{ t('login.verifyTitle') }}</h2>
            <p class="mt-1 text-[12px] text-[--t3]">{{ t('login.verifySubtitle', { email }) }}</p>
          </div>
          <input
            v-model="verifyCode"
            type="text"
            inputmode="numeric"
            maxlength="6"
            :placeholder="t('login.verifyCodePlaceholder')"
            class="input-field w-full px-3.5 py-2.5 text-center text-[18px] tracking-[0.3em]"
            @keydown.enter="handleVerify"
          />
          <button
            class="btn-primary w-full py-2.5"
            :disabled="verifyCode.length !== 6 || loading"
            @click="handleVerify"
          >
            {{ loading ? '...' : t('login.verify') }}
          </button>
          <div class="text-center">
            <button
              v-if="resendCooldown <= 0"
              class="cursor-pointer border-0 bg-transparent text-[12px] text-[--accent]"
              @click="handleResend"
            >
              {{ t('login.resendCode') }}
            </button>
            <span v-else class="text-[12px] text-[--t3]">{{ t('login.resendCooldown', { n: resendCooldown }) }}</span>
          </div>
          <button
            class="w-full cursor-pointer border-0 bg-transparent text-center text-[12px] text-[--t3] hover:text-[--t2]"
            @click="switchTo('login')"
          >
            {{ t('login.backToLogin') }}
          </button>
        </div>

        <!-- FORGOT PASSWORD STEP 1: Enter email -->
        <form v-if="view === 'forgot-step1'" class="space-y-4" @submit.prevent="handleForgotSend">
          <div class="mb-2 text-center">
            <h2 class="text-[16px] font-bold text-[--t1]">{{ t('login.forgotTitle') }}</h2>
            <p class="mt-1 text-[12px] text-[--t3]">{{ t('login.forgotSubtitle') }}</p>
          </div>
          <input
            v-model="email"
            type="email"
            :placeholder="t('login.email')"
            class="input-field w-full px-3.5 py-2.5"
          />
          <button type="submit" class="btn-primary w-full py-2.5" :disabled="!email || loading">
            {{ loading ? '...' : t('login.sendCode') }}
          </button>
          <button
            type="button"
            class="w-full cursor-pointer border-0 bg-transparent text-center text-[12px] text-[--t3] hover:text-[--t2]"
            @click="switchTo('login')"
          >
            {{ t('login.backToLogin') }}
          </button>
        </form>

        <!-- FORGOT PASSWORD STEP 2: Enter code -->
        <form v-if="view === 'forgot-step2'" class="space-y-4" @submit.prevent="handleForgotVerify">
          <div class="mb-2 text-center">
            <h2 class="text-[16px] font-bold text-[--t1]">{{ t('login.enterCode') }}</h2>
            <p class="mt-1 text-[12px] text-[--t3]">{{ t('login.verifySubtitle', { email }) }}</p>
          </div>
          <input
            v-model="forgotCode"
            type="text"
            inputmode="numeric"
            maxlength="6"
            :placeholder="t('login.verifyCodePlaceholder')"
            class="input-field w-full px-3.5 py-2.5 text-center text-[18px] tracking-[0.3em]"
          />
          <button type="submit" class="btn-primary w-full py-2.5" :disabled="forgotCode.length !== 6 || loading">
            {{ loading ? '...' : t('login.verify') }}
          </button>
          <button
            type="button"
            class="w-full cursor-pointer border-0 bg-transparent text-center text-[12px] text-[--t3] hover:text-[--t2]"
            @click="switchTo('forgot-step1')"
          >
            {{ t('login.backToLogin') }}
          </button>
        </form>

        <!-- FORGOT PASSWORD STEP 3: New password -->
        <form v-if="view === 'forgot-step3'" class="space-y-4" @submit.prevent="handleResetPassword">
          <div class="mb-2 text-center">
            <h2 class="text-[16px] font-bold text-[--t1]">{{ t('login.newPassword') }}</h2>
          </div>
          <input
            v-model="newPassword"
            type="password"
            :placeholder="t('login.newPassword')"
            class="input-field w-full px-3.5 py-2.5"
          />
          <input
            v-model="confirmNewPassword"
            type="password"
            :placeholder="t('login.confirmNewPassword')"
            class="input-field w-full px-3.5 py-2.5"
          />
          <p v-if="confirmNewPassword && newPassword !== confirmNewPassword" class="text-[11px] text-red-400">
            {{ t('login.passwordsDoNotMatch') }}
          </p>
          <button
            type="submit"
            class="btn-primary w-full py-2.5"
            :disabled="newPassword.length < 8 || newPassword !== confirmNewPassword || loading"
          >
            {{ loading ? '...' : t('login.resetPassword') }}
          </button>
        </form>

        <!-- Google OAuth divider + button (show in login and register) -->
        <template v-if="view === 'login' || view === 'register'">
          <div class="my-5 flex items-center gap-3">
            <div class="h-px flex-1 bg-white/[0.06]" />
            <span class="text-[11px] text-[--t3]">{{ t('login.or') }}</span>
            <div class="h-px flex-1 bg-white/[0.06]" />
          </div>
          <div ref="googleBtnRef" id="google-signin-btn" />
          <!-- Toggle text -->
          <p class="mt-4 text-center text-[12px] text-[--t3]">
            <template v-if="view === 'login'">
              {{ t('login.noAccount') }}
              <button
                class="cursor-pointer border-0 bg-transparent p-0 font-semibold text-[--accent]"
                @click="switchTo('register')"
              >
                {{ t('login.tabRegister') }}
              </button>
            </template>
            <template v-else>
              {{ t('login.hasAccount') }}
              <button
                class="cursor-pointer border-0 bg-transparent p-0 font-semibold text-[--accent]"
                @click="switchTo('login')"
              >
                {{ t('login.tabLogin') }}
              </button>
            </template>
          </p>
        </template>
      </div>

      <!-- Version -->
      <p class="mt-6 text-center text-[11px] text-[--t3]/50">Leerio v{{ version }}</p>
    </div>
  </div>
</template>

<style scoped>
.shake {
  animation: shake 0.4s ease-in-out;
}

@keyframes shake {
  0%,
  100% {
    transform: translateX(0);
  }
  25% {
    transform: translateX(-6px);
  }
  75% {
    transform: translateX(6px);
  }
}
</style>
