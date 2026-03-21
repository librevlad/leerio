import { ref, computed } from 'vue'
import type { User } from '../types'
import { apiUrl } from '../api'
import { STORAGE } from '../constants/storage'

const user = ref<User | null>(null)
const loading = ref(true)
const checked = ref(false)
let checkPromise: Promise<boolean> | null = null
let checkAbort: AbortController | null = null

export function useAuth() {
  const isLoggedIn = computed(() => !!user.value)
  const isGuest = computed(() => !user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function checkAuth(): Promise<boolean> {
    if (checked.value) return !!user.value
    if (checkPromise) return checkPromise
    checkAbort = new AbortController()
    checkPromise = (async () => {
      loading.value = true
      try {
        const res = await fetch(apiUrl('/auth/me'), {
          credentials: 'include',
          signal: checkAbort!.signal,
        })
        if (res.ok) {
          user.value = await res.json()
          try {
            localStorage.setItem(STORAGE.USER, JSON.stringify(user.value))
          } catch {
            /* full */
          }
          return true
        }
        // Don't overwrite user if a login completed while we were fetching
        if (!user.value) {
          user.value = null
        }
        return !!user.value
      } catch (e) {
        if (e instanceof DOMException && e.name === 'AbortError') {
          // Login cancelled this check — return current state
          return !!user.value
        }
        // Offline — try cached user
        try {
          const cached = localStorage.getItem(STORAGE.USER)
          if (cached) {
            user.value = JSON.parse(cached)
            return true
          }
        } catch {
          /* parse error */
        }
        if (!user.value) {
          user.value = null
        }
        return false
      } finally {
        loading.value = false
        checked.value = true
        checkPromise = null
        checkAbort = null
      }
    })()
    return checkPromise
  }

  function cancelPendingCheck() {
    if (checkAbort) {
      checkAbort.abort()
      checkAbort = null
    }
    checkPromise = null
  }

  async function loginWithGoogle(idToken: string): Promise<User> {
    cancelPendingCheck()
    const res = await fetch(apiUrl('/auth/google'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ id_token: idToken }),
    })
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      let detail = text
      try {
        const json = JSON.parse(text)
        if (json.detail) detail = json.detail
      } catch {
        /* not JSON */
      }
      throw new Error(`${res.status}: ${detail}`)
    }
    const data = await res.json()
    user.value = data
    checked.value = true
    loading.value = false
    try {
      localStorage.setItem(STORAGE.USER, JSON.stringify(data))
    } catch {
      /* full */
    }
    return data
  }

  async function loginWithPassword(email: string, password: string): Promise<User> {
    cancelPendingCheck()
    const res = await fetch(apiUrl('/auth/login'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      let detail = text
      try {
        const json = JSON.parse(text)
        if (json.detail) detail = json.detail
      } catch {
        /* not JSON */
      }
      throw new Error(`${res.status}: ${detail}`)
    }
    const data = await res.json()
    user.value = data
    checked.value = true
    loading.value = false
    try {
      localStorage.setItem(STORAGE.USER, JSON.stringify(data))
    } catch {
      /* full */
    }
    return data
  }

  async function logout() {
    try {
      await fetch(apiUrl('/auth/logout'), { method: 'POST', credentials: 'include' })
    } catch {
      /* network error — still clear local state */
    }
    user.value = null
    checked.value = false
    localStorage.removeItem(STORAGE.USER)
  }

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
      try {
        const json = JSON.parse(text)
        if (json.detail) detail = json.detail
      } catch {
        /* not JSON */
      }
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
      try {
        const json = JSON.parse(text)
        if (json.detail) detail = json.detail
      } catch {
        /* not JSON */
      }
      throw new Error(`${res.status}: ${detail}`)
    }
    const data = await res.json()
    user.value = data
    checked.value = true
    loading.value = false
    try {
      localStorage.setItem(STORAGE.USER, JSON.stringify(data))
    } catch {
      /* full */
    }
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
      try {
        const json = JSON.parse(text)
        if (json.detail) detail = json.detail
      } catch {
        /* not JSON */
      }
      throw new Error(`${res.status}: ${detail}`)
    }
  }

  return {
    user,
    loading,
    isLoggedIn,
    isGuest,
    isAdmin,
    checkAuth,
    loginWithGoogle,
    loginWithPassword,
    logout,
    register,
    verifyEmail,
    forgotPassword,
    resetPassword,
  }
}
