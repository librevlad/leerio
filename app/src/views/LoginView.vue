<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuth } from '../composables/useAuth'
import { version } from '../../package.json'

const router = useRouter()
const { t } = useI18n()
const { loginWithGoogle, loginWithPassword } = useAuth()
const error = ref('')
const loading = ref(false)
const email = ref('')
const password = ref('')

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
    handleGoogleCallback?: (response: { credential: string }) => void
  }
}

onMounted(() => {
  const script = document.createElement('script')
  script.src = 'https://accounts.google.com/gsi/client'
  script.async = true
  script.defer = true
  script.onload = initializeGsi
  document.head.appendChild(script)
})

function initializeGsi() {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
  if (!clientId || !window.google) return

  window.google.accounts.id.initialize({
    client_id: clientId,
    callback: handleCredentialResponse,
  })

  const buttonDiv = document.getElementById('google-signin-btn')
  if (buttonDiv) {
    window.google.accounts.id.renderButton(buttonDiv, {
      theme: 'filled_black',
      size: 'large',
      width: 300,
      text: 'signin_with',
      shape: 'rectangular',
      logo_alignment: 'left',
    })
  }
}

async function handleCredentialResponse(response: { credential: string }) {
  loading.value = true
  error.value = ''
  try {
    await loginWithGoogle(response.credential)
    router.push('/')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : 'Login failed'
    if (msg.includes('403')) {
      error.value = t('login.registrationClosed')
    } else {
      error.value = msg
    }
  } finally {
    loading.value = false
  }
}

async function handlePasswordLogin() {
  if (!email.value || !password.value) return
  loading.value = true
  error.value = ''
  try {
    await loginWithPassword(email.value, password.value)
    router.push('/')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : 'Login failed'
    if (msg.includes('401')) {
      error.value = t('login.invalidCredentials')
    } else {
      error.value = msg
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="relative flex min-h-dvh min-h-screen items-center justify-center px-4" style="background: var(--bg)">
    <!-- Subtle radial glow -->
    <div
      class="pointer-events-none absolute inset-0"
      style="background: radial-gradient(ellipse 60% 50% at 50% 40%, rgba(232, 146, 58, 0.06) 0%, transparent 70%)"
    />

    <div class="relative w-full max-w-sm">
      <!-- Logo -->
      <div class="mb-10 flex items-center justify-center gap-3">
        <img src="/logo.png" alt="Leerio" class="h-11 w-11 rounded-xl" />
        <span class="text-[26px] font-bold tracking-tight text-[--t1]">Leerio</span>
      </div>

      <!-- Card -->
      <div class="card p-7 text-center">
        <p class="mb-6 text-[14px] text-[--t2]">{{ t('login.subtitle') }}</p>

        <!-- Email/Password form -->
        <form class="mb-5 space-y-3" @submit.prevent="handlePasswordLogin">
          <input
            v-model="email"
            type="email"
            placeholder="Email"
            autocomplete="email"
            class="input-field w-full px-4 py-2.5"
          />
          <input
            v-model="password"
            type="password"
            :placeholder="t('login.password')"
            autocomplete="current-password"
            class="input-field w-full px-4 py-2.5"
          />
          <button
            type="submit"
            :disabled="loading || !email || !password"
            class="btn btn-primary w-full justify-center py-2.5"
          >
            {{ t('login.signIn') }}
          </button>
        </form>

        <div class="mb-5 flex items-center gap-3">
          <div class="h-px flex-1 bg-[--border]" />
          <span class="text-[11px] text-[--t3]">{{ t('login.or') }}</span>
          <div class="h-px flex-1 bg-[--border]" />
        </div>

        <div class="flex justify-center">
          <div id="google-signin-btn" />
        </div>

        <p class="mt-4 text-center text-[12px] text-[--t3]">
          {{ t('login.noAccount') }}
        </p>

        <div v-if="loading" class="mt-5 text-[13px] text-[--t3]">{{ t('login.loading') }}</div>
        <div v-if="error" class="mt-5 text-[13px] text-red-400">{{ error }}</div>
      </div>

      <p class="mt-10 text-center text-[11px] text-[--t3] opacity-40">Leerio v{{ version }}</p>
    </div>
  </div>
</template>
