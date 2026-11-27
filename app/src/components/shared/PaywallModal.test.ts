import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const play = {
  getEntitlement: vi.fn(() => Promise.resolve({ available: false })),
  getOffers: vi.fn(() => Promise.resolve({ available: false })),
  purchase: vi.fn(() => Promise.resolve({ status: 'purchased', active: true })),
  manage: vi.fn(),
  addListener: vi.fn(() => Promise.resolve({ remove: vi.fn() })),
}

vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => true },
  registerPlugin: () => play,
}))
vi.mock('../../api', () => ({ api: { getPaymentPlan: vi.fn() } }))
vi.mock('../../composables/useAuth', () => ({ useAuth: () => ({ user: { value: null } }) }))
const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() }
vi.mock('../../composables/useToast', () => ({ useToast: () => toast }))
vi.mock('../../composables/useTelemetry', () => ({ useTracking: () => ({ track: vi.fn() }) }))

const phase = (price: string, micros: number, period: string, cycles = 0) => ({
  price,
  priceMicros: micros,
  currency: 'USD',
  period,
  cycles,
})

/** Plans as Play returned them last time (the cache the app starts from) */
function cachePlans() {
  localStorage.setItem(
    'leerio_pro',
    JSON.stringify({
      active: false,
      offers: [
        { basePlanId: 'monthly', phases: [phase('1,99 $', 1_990_000, 'P1M')] },
        {
          basePlanId: 'yearly',
          offerId: 'trial',
          phases: [phase('Бесплатно', 0, 'P1W', 1), phase('14,99 $', 14_990_000, 'P1Y')],
        },
      ],
    }),
  )
}

async function mountPaywall(reason?: 'books' | 'narration') {
  vi.resetModules()
  localStorage.setItem('leerio_locale', 'ru')
  const { default: i18n } = await import('../../i18n')
  const { default: PaywallModal } = await import('./PaywallModal.vue')
  return mount(PaywallModal, {
    props: { open: true, reason },
    global: { plugins: [i18n], stubs: { teleport: true, transition: false }, directives: { ripple: {} } },
  })
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
})

describe('PaywallModal in the app (Google Play)', () => {
  it('shows the Play plans, yearly with the free week first, and the renewal terms', async () => {
    cachePlans()
    const w = await mountPaywall('books')
    const text = w.text()
    expect(text).toContain('Leerio Pro')
    expect(text).toContain('Бесплатно в библиотеке до 5 книг')
    const plans = w.findAll('button').filter((b) => /в (год|месяц)/.test(b.text()))
    expect(plans.map((b) => b.text())).toEqual([
      expect.stringMatching(/Год.*14,99 \$ в год.*7 дней бесплатно/),
      expect.stringMatching(/Месяц.*1,99 \$ в месяц/),
    ])
    expect(text).toContain('Попробовать бесплатно')
    expect(text).toContain('7 дней бесплатно, затем 14,99 $ в год. Подписка продлевается сама')
  })

  it('buys the chosen plan and closes', async () => {
    cachePlans()
    const w = await mountPaywall('narration')
    expect(w.text()).toContain('Бесплатно озвучивается первая глава')
    await w
      .findAll('button')
      .find((b) => b.text().startsWith('Месяц'))!
      .trigger('click')
    const buy = w.findAll('button').find((b) => b.text() === 'Оформить Pro')!
    await buy.trigger('click')
    await flushPromises()
    expect(play.purchase).toHaveBeenCalledWith({ productId: 'leerio_pro', basePlanId: 'monthly', offerId: undefined })
    expect(toast.success).toHaveBeenCalled()
    expect(w.emitted('close')).toBeTruthy()
  })

  it('says Play is unavailable when there are no plans', async () => {
    const w = await mountPaywall()
    expect(w.text()).toContain('Google Play сейчас недоступен')
    expect(w.findAll('button').some((b) => b.text() === 'Оформить Pro')).toBe(false)
  })
})
