import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import i18n from '../i18n'
import LoginView from './LoginView.vue'

const auth = vi.hoisted(() => ({ loginWithPassword: vi.fn() }))
vi.mock('../composables/useAuth', () => ({ useAuth: () => auth }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn(), back: vi.fn() }) }))
// The template's /logo.png is a file of public/, which the test runner cannot load
vi.mock('/logo.png', () => ({ default: '/logo.png' }))

async function signIn(reject: unknown) {
  auth.loginWithPassword.mockRejectedValueOnce(reject)
  const w = mount(LoginView, { global: { plugins: [i18n], mocks: { $router: { back: vi.fn() } } } })
  await w.find('input[type="email"]').setValue('me@example.com')
  await w.find('input[type="password"]').setValue('secret123')
  await w.find('form').trigger('submit')
  await flushPromises()
  return w
}

describe('LoginView: what a failed sign-in says', () => {
  beforeEach(() => {
    auth.loginWithPassword.mockReset()
    i18n.global.locale.value = 'ru'
    // Google's script is already "loaded": the view does not reach for the network
    window.google = { accounts: { id: { initialize: vi.fn(), renderButton: vi.fn() } } }
  })

  it('no server: a plain sentence, not "Failed to fetch"', async () => {
    const w = await signIn(new TypeError('Failed to fetch'))
    expect(w.text()).toContain('Нет связи с сервером Leerio')
    expect(w.text()).not.toContain('Failed to fetch')
  })

  it('a proxy error page (502) reads the same, without its HTML', async () => {
    const w = await signIn(new Error('502: <html><body>Bad Gateway</body></html>'))
    expect(w.text()).toContain('Нет связи с сервером Leerio')
    expect(w.text()).not.toContain('Bad Gateway')
  })

  it("the server's own answer is shown as it is", async () => {
    const w = await signIn(new Error('401: Неверный email или пароль'))
    expect(w.text()).toContain('Неверный email или пароль')
    expect(w.text()).not.toContain('401')
  })

  it('no English on the Russian screen', async () => {
    const w = await signIn(new Error('401: x'))
    expect(w.text()).not.toContain('Back')
    expect(w.text()).toContain('Назад')
  })
})
