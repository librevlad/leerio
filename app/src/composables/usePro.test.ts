import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ProOffer } from './usePro'

const play = {
  getEntitlement: vi.fn(),
  getOffers: vi.fn(),
  purchase: vi.fn(),
  manage: vi.fn(),
  addListener: vi.fn(() => Promise.resolve({ remove: vi.fn() })),
}
let native = true

vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => native },
  registerPlugin: () => play,
}))

const phase = (price: string, micros: number, period: string, cycles = 0) => ({
  price,
  priceMicros: micros,
  currency: 'USD',
  period,
  cycles,
})

const yearly: ProOffer = { basePlanId: 'yearly', phases: [phase('$14.99', 14_990_000, 'P1Y')] }
const yearlyTrial: ProOffer = {
  basePlanId: 'yearly',
  offerId: 'trial',
  phases: [phase('Free', 0, 'P1W', 1), phase('$14.99', 14_990_000, 'P1Y')],
}
const monthly: ProOffer = { basePlanId: 'monthly', phases: [phase('$1.99', 1_990_000, 'P1M')] }

/** Fresh module: state is read from localStorage on import */
async function load() {
  vi.resetModules()
  return import('./usePro')
}

beforeEach(() => {
  localStorage.clear()
  native = true
  vi.clearAllMocks()
})

describe('proPlans', () => {
  it('offers one plan per base plan, the trial when there is one, yearly first', async () => {
    const { proPlans } = await load()
    const plans = proPlans([monthly, yearly, yearlyTrial])
    expect(plans.map((p) => p.offer.basePlanId)).toEqual(['yearly', 'monthly'])
    expect(plans[0]).toMatchObject({ price: '$14.99', period: 'P1Y', trialDays: 7, offer: { offerId: 'trial' } })
    expect(plans[1]).toMatchObject({ price: '$1.99', period: 'P1M', trialDays: 0 })
  })

  it('falls back to the base offer when the trial is not offered to this user', async () => {
    const { proPlans } = await load()
    expect(proPlans([yearly])[0]).toMatchObject({ trialDays: 0, offer: { basePlanId: 'yearly' } })
  })

  it('reads ISO periods', async () => {
    const { periodDays } = await load()
    expect(periodDays('P7D')).toBe(7)
    expect(periodDays('P1W')).toBe(7)
    expect(periodDays('P1Y')).toBe(365)
    expect(periodDays('weird')).toBe(0)
  })
})

describe('free plan limits', () => {
  it('are off while Pro cannot be bought', async () => {
    const { usePro } = await load()
    const pro = usePro()
    expect(pro.isPro.value).toBe(false)
    expect(pro.canBuy.value).toBe(false)
    expect(pro.limited.value).toBe(false)
  })

  it('are on when Play sells Pro and it is not active', async () => {
    localStorage.setItem('leerio_pro', JSON.stringify({ active: false, offers: [monthly] }))
    const { usePro } = await load()
    expect(usePro().limited.value).toBe(true)
  })

  it('are off for Pro, from the cache, before Play answers', async () => {
    localStorage.setItem('leerio_pro', JSON.stringify({ active: true, offers: [monthly] }))
    const { usePro } = await load()
    expect(usePro().isPro.value).toBe(true)
    expect(usePro().limited.value).toBe(false)
  })
})

describe('refresh', () => {
  it('takes the entitlement and the plans from Play and caches them', async () => {
    play.getEntitlement.mockResolvedValue({ available: true, active: true })
    play.getOffers.mockResolvedValue({ available: true, offers: [yearly, monthly] })
    const { usePro } = await load()
    const pro = usePro()
    await pro.refresh()
    expect(pro.isPro.value).toBe(true)
    expect(pro.plans.value).toHaveLength(2)
    expect(JSON.parse(localStorage.getItem('leerio_pro')!)).toMatchObject({ active: true })
  })

  it('keeps the cached answer when Play is unavailable (offline, no Play Store)', async () => {
    localStorage.setItem('leerio_pro', JSON.stringify({ active: true, offers: [monthly] }))
    play.getEntitlement.mockResolvedValue({ available: false })
    play.getOffers.mockRejectedValue(new Error('no Play'))
    const { usePro } = await load()
    const pro = usePro()
    await pro.refresh()
    expect(pro.isPro.value).toBe(true)
    expect(pro.canBuy.value).toBe(true)
  })

  it('turns Pro off when Play says the subscription ended', async () => {
    localStorage.setItem('leerio_pro', JSON.stringify({ active: true, offers: [monthly] }))
    play.getEntitlement.mockResolvedValue({ available: true, active: false })
    play.getOffers.mockResolvedValue({ available: true, offers: [monthly] })
    const { usePro } = await load()
    const pro = usePro()
    await pro.refresh()
    expect(pro.isPro.value).toBe(false)
    expect(pro.limited.value).toBe(true)
  })

  it('does nothing on the web', async () => {
    native = false
    const { usePro } = await load()
    await usePro().refresh()
    expect(play.getEntitlement).not.toHaveBeenCalled()
  })
})

describe('purchase', () => {
  it('turns Pro on when Play confirms', async () => {
    play.purchase.mockResolvedValue({ status: 'purchased', active: true })
    const { usePro, proPlans } = await load()
    const pro = usePro()
    expect(await pro.purchase(proPlans([monthly])[0]!)).toBe('purchased')
    expect(pro.isPro.value).toBe(true)
    expect(play.purchase).toHaveBeenCalledWith({ productId: 'leerio_pro', basePlanId: 'monthly', offerId: undefined })
  })

  it('restores a subscription this Google account already owns', async () => {
    play.purchase.mockResolvedValue({ status: 'owned', active: false })
    play.getEntitlement.mockResolvedValue({ available: true, active: true })
    play.getOffers.mockResolvedValue({ available: true, offers: [monthly] })
    const { usePro, proPlans } = await load()
    const pro = usePro()
    expect(await pro.purchase(proPlans([monthly])[0]!)).toBe('purchased')
    expect(pro.isPro.value).toBe(true)
  })

  it('stays free when the user cancels', async () => {
    play.purchase.mockResolvedValue({ status: 'canceled', active: false })
    const { usePro, proPlans } = await load()
    const pro = usePro()
    expect(await pro.purchase(proPlans([monthly])[0]!)).toBe('canceled')
    expect(pro.isPro.value).toBe(false)
  })
})
