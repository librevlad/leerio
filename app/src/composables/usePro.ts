/**
 * Leerio Pro entitlement — $1.99/month or $14.99/year through Google Play.
 *
 * Play Billing is not wired yet, so everyone is on the free plan. When it lands, set `isPro`
 * here from the billing client (purchase / restore); callers already read it.
 */
import { readonly, ref } from 'vue'

/** Free plan narrates only the first chapter of a book */
export const FREE_NARRATION_CHAPTERS = 1

const isPro = ref(false)

export function usePro() {
  return { isPro: readonly(isPro) }
}
