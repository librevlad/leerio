/**
 * Leerio Pro — a Google Play subscription (monthly or yearly, a free week first).
 *
 * The answer lives on the phone: Play's purchase list, cached in localStorage so Pro holds offline
 * and from the first frame. The free plan's limits apply only while Pro can actually be bought —
 * Play returned a plan — so nobody hits a limit they cannot lift.
 */
import { Capacitor, registerPlugin, type PluginListenerHandle } from '@capacitor/core'
import { computed, readonly, ref } from 'vue'
import { STORAGE } from '../constants/storage'

export const PRO_PRODUCT_ID = 'leerio_pro'
/** Free plan narrates only the first chapter of a book */
export const FREE_NARRATION_CHAPTERS = 1
/** Free plan keeps up to this many books in My Library */
export const FREE_BOOKS = 5

export interface ProPhase {
  /** Formatted by Play in the user's currency, e.g. "14,99 $" */
  price: string
  priceMicros: number
  currency: string
  /** ISO 8601 period: P7D, P1M, P1Y */
  period: string
  cycles: number
}

export interface ProOffer {
  basePlanId: string
  offerId?: string
  phases: ProPhase[]
}

export interface ProPlan {
  offer: ProOffer
  /** Recurring price, e.g. "14,99 $" */
  price: string
  period: string
  /** Free days before the first charge; 0 — no trial for this user */
  trialDays: number
}

export type PurchaseStatus = 'purchased' | 'pending' | 'canceled' | 'owned' | 'unavailable' | 'error'

interface PlayBillingPlugin {
  getOffers(o: { productId: string }): Promise<{ available: boolean; offers?: ProOffer[] }>
  getEntitlement(o: { productId: string }): Promise<{ available: boolean; active?: boolean }>
  purchase(o: { productId: string; basePlanId: string; offerId?: string }): Promise<{
    status: PurchaseStatus
    active: boolean
  }>
  manage(o: { productId: string }): Promise<void>
  addListener(event: 'entitlement', cb: (e: { active: boolean }) => void): Promise<PluginListenerHandle>
}

const PlayBilling = registerPlugin<PlayBillingPlugin>('PlayBilling')

// ── Plans ──────────────────────────────────────────────────────────────

const DAYS: Record<string, number> = { D: 1, W: 7, M: 30, Y: 365 }

/** "P7D" → 7, "P1W" → 7, "P1M" → 30 */
export function periodDays(period: string): number {
  const m = /^P(\d+)([DWMY])$/.exec(period)
  return m ? Number(m[1]) * DAYS[m[2]!]! : 0
}

/** One plan per base plan — with the free trial when Play offers it to this user — yearly first */
export function proPlans(offers: ProOffer[]): ProPlan[] {
  const byBase = new Map<string, ProOffer[]>()
  for (const o of offers) {
    if (!o.phases?.length) continue
    byBase.set(o.basePlanId, [...(byBase.get(o.basePlanId) ?? []), o])
  }
  const plans: ProPlan[] = []
  for (const list of byBase.values()) {
    const trial = list.find((o) => o.phases.some((p) => p.priceMicros === 0))
    const offer = trial ?? list.find((o) => !o.offerId) ?? list[0]!
    const recurring = offer.phases[offer.phases.length - 1]!
    const free = offer.phases.find((p) => p.priceMicros === 0)
    plans.push({
      offer,
      price: recurring.price,
      period: recurring.period,
      trialDays: free ? periodDays(free.period) * Math.max(1, free.cycles) : 0,
    })
  }
  return plans.sort((a, b) => periodDays(b.period) - periodDays(a.period))
}

// ── State ──────────────────────────────────────────────────────────────

function readCache(): { active: boolean; offers: ProOffer[] } {
  try {
    const c = JSON.parse(localStorage.getItem(STORAGE.PRO) || '{}')
    return { active: c.active === true, offers: Array.isArray(c.offers) ? c.offers : [] }
  } catch {
    return { active: false, offers: [] }
  }
}

const cached = readCache()
const isPro = ref(cached.active)
const offers = ref<ProOffer[]>(cached.offers)
const busy = ref(false)

/** Pro can be bought here: Play returned at least one plan */
const canBuy = computed(() => offers.value.length > 0)
/** The free plan's limits are on — only when Pro can lift them */
const limited = computed(() => !isPro.value && canBuy.value)
const plans = computed(() => proPlans(offers.value))

function save() {
  try {
    localStorage.setItem(STORAGE.PRO, JSON.stringify({ active: isPro.value, offers: offers.value }))
  } catch {
    // Storage full or blocked: the answer still holds for this session
  }
}

let refreshOp = 0

/** Play confirmed a purchase: Pro is on, and an answer asked before the purchase must not undo it */
function grant() {
  refreshOp++
  isPro.value = true
  save()
}

let listening = false
function listen() {
  if (listening) return
  listening = true
  void PlayBilling.addListener('entitlement', (e) => {
    if (e.active) grant()
  })
}

/**
 * Asks Play whether Pro is active and what it costs. Offline or no Play: the cached answer stays.
 * Resolves true when Play answered about the purchase, false when it could not be asked.
 */
async function refresh(): Promise<boolean> {
  if (!Capacitor.isNativePlatform()) return false
  listen()
  const op = ++refreshOp
  const productId = PRO_PRODUCT_ID
  const [ent, off] = await Promise.all([
    PlayBilling.getEntitlement({ productId }).catch(() => null),
    PlayBilling.getOffers({ productId }).catch(() => null),
  ])
  const answered = ent?.available === true
  if (op !== refreshOp) return answered
  if (answered) isPro.value = ent.active === true
  if (off?.available) offers.value = off.offers ?? []
  save()
  return answered
}

async function purchase(plan: ProPlan): Promise<PurchaseStatus> {
  if (busy.value) return 'error'
  busy.value = true
  try {
    const r = await PlayBilling.purchase({
      productId: PRO_PRODUCT_ID,
      basePlanId: plan.offer.basePlanId,
      offerId: plan.offer.offerId,
    })
    if (r.active) grant()
    // Already bought on this Google account (e.g. after reinstall): restore it
    if (r.status === 'owned') {
      await refresh()
      return isPro.value ? 'purchased' : 'error'
    }
    return r.status
  } catch {
    return 'error'
  } finally {
    busy.value = false
  }
}

/** "Restore purchase": what Play says — or that Play could not be asked (offline, no Play Store) */
async function restore(): Promise<'active' | 'none' | 'unavailable'> {
  if (!(await refresh())) return 'unavailable'
  return isPro.value ? 'active' : 'none'
}

async function manage(): Promise<void> {
  await PlayBilling.manage({ productId: PRO_PRODUCT_ID }).catch(() => undefined)
}

export function usePro() {
  return {
    isPro: readonly(isPro),
    canBuy,
    limited,
    plans,
    busy: readonly(busy),
    refresh,
    purchase,
    restore,
    manage,
  }
}
