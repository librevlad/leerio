import { ref, computed } from 'vue'
import type { User } from '../types'

const user = ref<User | null>(null)
const loading = ref(true)
const checked = ref(false)

export function useAuth() {
  const isLoggedIn = computed(() => !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function checkAuth(): Promise<boolean> {
    if (checked.value) return !!user.value
    loading.value = true
    try {
      const res = await fetch('/api/auth/me', { credentials: 'include' })
      if (res.ok) {
        user.value = await res.json()
        return true
      }
      user.value = null
      return false
    } catch {
      user.value = null
      return false
    } finally {
      loading.value = false
      checked.value = true
    }
  }

  async function loginWithGoogle(idToken: string): Promise<User> {
    const res = await fetch('/api/auth/google', {
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
    return data
  }

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
    user.value = null
    checked.value = false
  }

  return {
    user,
    loading,
    isLoggedIn,
    isAdmin,
    checkAuth,
    loginWithGoogle,
    logout,
  }
}
