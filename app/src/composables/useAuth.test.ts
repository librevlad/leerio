vi.mock('../api', () => ({
  apiUrl: vi.fn((p: string) => '/api' + p),
}))

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAuth } from './useAuth'

const mockUser = {
  user_id: '1',
  email: 'test@example.com',
  name: 'Test User',
  picture: 'https://example.com/pic.jpg',
  role: 'user' as const,
}

const mockAdmin = {
  ...mockUser,
  user_id: '2',
  role: 'admin' as const,
}

function mockFetch(response: Partial<Response> & { json?: () => Promise<unknown>; text?: () => Promise<string> }) {
  const fn = vi.fn().mockResolvedValue({
    ok: response.ok ?? true,
    status: response.status ?? 200,
    statusText: response.statusText ?? 'OK',
    json: response.json ?? (() => Promise.resolve({})),
    text: response.text ?? (() => Promise.resolve('')),
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

beforeEach(async () => {
  vi.restoreAllMocks()
  localStorage.clear()
  // Reset singleton state via logout()
  const auth = useAuth()
  // Force user to null and checked to false by calling logout
  // First stub fetch so logout's fetch doesn't throw
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
  await auth.logout()
  auth.loading.value = true
})

describe('useAuth', () => {
  describe('computed properties', () => {
    it('isLoggedIn is false when no user', () => {
      const { isLoggedIn } = useAuth()
      expect(isLoggedIn.value).toBe(false)
    })

    it('isLoggedIn is true when user is set', () => {
      const { user, isLoggedIn } = useAuth()
      user.value = mockUser
      expect(isLoggedIn.value).toBe(true)
    })

    it('isGuest is true when no user', () => {
      const { isGuest } = useAuth()
      expect(isGuest.value).toBe(true)
    })

    it('isGuest is false when user is set', () => {
      const { user, isGuest } = useAuth()
      user.value = mockUser
      expect(isGuest.value).toBe(false)
    })

    it('isAdmin is false for regular user', () => {
      const { user, isAdmin } = useAuth()
      user.value = mockUser
      expect(isAdmin.value).toBe(false)
    })

    it('isAdmin is true for admin user', () => {
      const { user, isAdmin } = useAuth()
      user.value = mockAdmin
      expect(isAdmin.value).toBe(true)
    })
  })

  describe('checkAuth()', () => {
    it('fetches user and caches to localStorage on success', async () => {
      mockFetch({ ok: true, json: () => Promise.resolve(mockUser) })

      const { checkAuth, user } = useAuth()
      const result = await checkAuth()

      expect(result).toBe(true)
      expect(user.value).toEqual(mockUser)
      expect(localStorage.getItem('leerio_user')).toBe(JSON.stringify(mockUser))
    })

    it('returns false on 401 response', async () => {
      mockFetch({ ok: false, status: 401 })

      const { checkAuth, user } = useAuth()
      const result = await checkAuth()

      expect(result).toBe(false)
      expect(user.value).toBeNull()
    })

    it('falls back to cached user from localStorage on network error', async () => {
      localStorage.setItem('leerio_user', JSON.stringify(mockUser))
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

      const { checkAuth, user } = useAuth()
      const result = await checkAuth()

      expect(result).toBe(true)
      expect(user.value).toEqual(mockUser)
    })

    it('returns false on network error with no cached user', async () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

      const { checkAuth, user } = useAuth()
      const result = await checkAuth()

      expect(result).toBe(false)
      expect(user.value).toBeNull()
    })

    it('returns immediately without fetch when already checked', async () => {
      // First call: set user
      const fetch1 = mockFetch({ ok: true, json: () => Promise.resolve(mockUser) })
      const auth = useAuth()
      await auth.checkAuth()
      expect(fetch1).toHaveBeenCalledTimes(1)

      // Second call: should not fetch again
      const fetch2 = mockFetch({ ok: true, json: () => Promise.resolve(mockUser) })
      const result = await auth.checkAuth()
      expect(result).toBe(true)
      expect(fetch2).not.toHaveBeenCalled()
    })

    it('deduplicates concurrent calls', async () => {
      const fetchFn = mockFetch({ ok: true, json: () => Promise.resolve(mockUser) })

      const auth = useAuth()
      const [r1, r2, r3] = await Promise.all([auth.checkAuth(), auth.checkAuth(), auth.checkAuth()])

      expect(r1).toBe(true)
      expect(r2).toBe(true)
      expect(r3).toBe(true)
      expect(fetchFn).toHaveBeenCalledTimes(1)
    })

    it('sets loading to false after check', async () => {
      mockFetch({ ok: true, json: () => Promise.resolve(mockUser) })

      const auth = useAuth()
      expect(auth.loading.value).toBe(true)
      await auth.checkAuth()
      expect(auth.loading.value).toBe(false)
    })
  })

  describe('loginWithGoogle()', () => {
    it('sets user and caches to localStorage on success', async () => {
      const fetchFn = mockFetch({ ok: true, json: () => Promise.resolve(mockUser) })

      const { loginWithGoogle, user } = useAuth()
      const result = await loginWithGoogle('google-id-token-123')

      expect(result).toEqual(mockUser)
      expect(user.value).toEqual(mockUser)
      expect(localStorage.getItem('leerio_user')).toBe(JSON.stringify(mockUser))
      expect(fetchFn).toHaveBeenCalledWith(
        '/api/auth/google',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ id_token: 'google-id-token-123' }),
        }),
      )
    })

    it('throws with detail message on error', async () => {
      mockFetch({
        ok: false,
        status: 403,
        text: () => Promise.resolve(JSON.stringify({ detail: 'Account disabled' })),
      })

      const { loginWithGoogle } = useAuth()
      await expect(loginWithGoogle('bad-token')).rejects.toThrow('403: Account disabled')
    })

    it('throws with raw text when response is not JSON', async () => {
      mockFetch({
        ok: false,
        status: 500,
        text: () => Promise.resolve('Internal Server Error'),
      })

      const { loginWithGoogle } = useAuth()
      await expect(loginWithGoogle('bad-token')).rejects.toThrow('500: Internal Server Error')
    })
  })

  describe('loginWithPassword()', () => {
    it('sets user and caches to localStorage on success', async () => {
      const fetchFn = mockFetch({ ok: true, json: () => Promise.resolve(mockUser) })

      const { loginWithPassword, user } = useAuth()
      const result = await loginWithPassword('test@example.com', 'password123')

      expect(result).toEqual(mockUser)
      expect(user.value).toEqual(mockUser)
      expect(localStorage.getItem('leerio_user')).toBe(JSON.stringify(mockUser))
      expect(fetchFn).toHaveBeenCalledWith(
        '/api/auth/login',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'test@example.com', password: 'password123' }),
        }),
      )
    })

    it('throws with JSON detail on error', async () => {
      mockFetch({
        ok: false,
        status: 401,
        text: () => Promise.resolve(JSON.stringify({ detail: 'Invalid credentials' })),
      })

      const { loginWithPassword } = useAuth()
      await expect(loginWithPassword('bad@email.com', 'wrong')).rejects.toThrow('401: Invalid credentials')
    })

    it('throws with raw text when detail is missing', async () => {
      mockFetch({
        ok: false,
        status: 400,
        text: () => Promise.resolve('Bad Request'),
      })

      const { loginWithPassword } = useAuth()
      await expect(loginWithPassword('bad@email.com', '')).rejects.toThrow('400: Bad Request')
    })
  })

  describe('logout()', () => {
    it('clears user and localStorage', async () => {
      // First login
      mockFetch({ ok: true, json: () => Promise.resolve(mockUser) })
      const auth = useAuth()
      await auth.loginWithPassword('test@example.com', 'pass')
      expect(auth.user.value).toEqual(mockUser)
      expect(localStorage.getItem('leerio_user')).toBeTruthy()

      // Now logout
      mockFetch({ ok: true })
      await auth.logout()

      expect(auth.user.value).toBeNull()
      expect(auth.isLoggedIn.value).toBe(false)
      expect(auth.isGuest.value).toBe(true)
      expect(localStorage.getItem('leerio_user')).toBeNull()
    })

    it('clears user even if fetch fails', async () => {
      // Login first
      mockFetch({ ok: true, json: () => Promise.resolve(mockUser) })
      const auth = useAuth()
      await auth.loginWithPassword('test@example.com', 'pass')

      // Logout with network error
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Network error')))
      await auth.logout()

      expect(auth.user.value).toBeNull()
      expect(localStorage.getItem('leerio_user')).toBeNull()
    })

    it('resets checked so next checkAuth fetches again', async () => {
      // Login
      mockFetch({ ok: true, json: () => Promise.resolve(mockUser) })
      const auth = useAuth()
      await auth.checkAuth()

      // Logout
      mockFetch({ ok: true })
      await auth.logout()

      // checkAuth should fetch again (not return cached)
      const fetchFn = mockFetch({ ok: false, status: 401 })
      const result = await auth.checkAuth()

      expect(fetchFn).toHaveBeenCalledTimes(1)
      expect(result).toBe(false)
    })
  })
})
