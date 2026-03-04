<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const { loginWithGoogle } = useAuth()
const error = ref('')
const loading = ref(false)

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
  // Load Google Identity Services SDK
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
      shape: 'pill',
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
      error.value = 'Регистрация недоступна для этого аккаунта. Обратитесь к администратору.'
    } else {
      error.value = msg
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-dvh min-h-screen items-center justify-center px-4" style="background: var(--bg)">
    <div class="w-full max-w-sm text-center">
      <div class="mb-8 flex items-center justify-center gap-3">
        <img src="/logo.png" alt="Leerio" class="h-10 w-10 rounded-xl object-contain" />
        <span class="text-[24px] font-bold tracking-tight text-[--t1]">Leerio</span>
      </div>

      <p class="mb-8 text-[14px] text-[--t2]">Войдите, чтобы продолжить</p>

      <div class="flex justify-center">
        <div id="google-signin-btn" />
      </div>

      <div v-if="loading" class="mt-6 text-[13px] text-[--t3]">Вход...</div>
      <div v-if="error" class="mt-6 text-[13px] text-red-400">{{ error }}</div>

      <p class="mt-12 text-[11px] text-[--t3] opacity-50">Leerio v1.0</p>
    </div>
  </div>
</template>
