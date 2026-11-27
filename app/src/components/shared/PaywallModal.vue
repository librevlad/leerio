<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Capacitor } from '@capacitor/core'
import { api } from '../../api'
import { useAuth } from '../../composables/useAuth'
import { useToast } from '../../composables/useToast'
import { useTracking } from '../../composables/useTelemetry'
import { usePro, FREE_BOOKS, type ProPlan } from '../../composables/usePro'

declare global {
  interface Window {
    Paddle?: {
      Environment: { set: (env: string) => void }
      Initialize: (opts: { token: string }) => void
      Checkout: {
        open: (opts: {
          items: { priceId: string; quantity: number }[]
          customer?: { email: string }
          customData?: Record<string, string>
          settings?: { theme: string; displayMode: string; successUrl?: string }
        }) => void
      }
    }
  }
}

const props = defineProps<{ open: boolean; bookCount?: number; reason?: 'books' | 'narration' }>()
const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()
const { user } = useAuth()
const toast = useToast()
const { track } = useTracking()

// ── Google Play (the app) ──────────────────────────────────────────────

/** In the app Pro is a Google Play subscription; Paddle below is the web's server plan */
const native = Capacitor.isNativePlatform()
const pro = usePro()
const chosenBase = ref('')
const chosen = computed<ProPlan | undefined>(
  () => pro.plans.value.find((p) => p.offer.basePlanId === chosenBase.value) ?? pro.plans.value[0],
)

const why = computed(() =>
  props.reason === 'books'
    ? t('pro.whyBooks', { n: FREE_BOOKS })
    : props.reason === 'narration'
      ? t('pro.whyNarration')
      : t('pro.why'),
)

/** "14,99 $ в год" */
function priceLabel(plan: ProPlan): string {
  const key = { P1Y: 'pro.perYear', P1M: 'pro.perMonth', P1W: 'pro.perWeek' }[plan.period]
  return key ? t(key, { price: plan.price }) : plan.price
}

function periodName(plan: ProPlan): string {
  const key = { P1Y: 'pro.year', P1M: 'pro.month', P1W: 'pro.week' }[plan.period]
  return key ? t(key) : plan.period
}

async function buy() {
  const plan = chosen.value
  if (!plan || pro.busy.value) return
  track('upgrade_clicked')
  const status = await pro.purchase(plan)
  if (status === 'purchased') {
    toast.success(t('pro.thanks'))
    emit('close')
  } else if (status === 'pending') {
    toast.info(t('pro.pending'))
    emit('close')
  } else if (status === 'unavailable') {
    toast.error(t('pro.unavailable'))
  } else if (status === 'error' || status === 'owned') {
    toast.error(t('pro.failed'))
  }
}

async function restore() {
  const result = await pro.restore()
  if (result === 'active') {
    toast.success(t('pro.restored'))
    emit('close')
  } else if (result === 'unavailable') {
    // Offline or no Play Store: not "no purchase" — Play simply could not be asked
    toast.error(t('pro.unavailable'))
  } else {
    toast.info(t('pro.notFound'))
  }
}

watch(
  () => props.open,
  (v) => {
    if (!v) return
    track('paywall_shown')
    // Prices may have changed in Play Console
    if (native) void pro.refresh()
  },
)
const priceId = ref('')
const clientToken = ref('')
const freeLimit = ref(10)
const loading = ref(false)

defineExpose({ freeLimit })

onMounted(async () => {
  if (native) return
  try {
    const data = await api.getPaymentPlan()
    priceId.value = data.price_id || ''
    clientToken.value = data.client_token || ''
    if (data.free_limit) freeLimit.value = data.free_limit
  } catch {
    /* optional */
  }
})

function openCheckout() {
  track('upgrade_clicked')
  if (!priceId.value) {
    toast.error('Payment not configured')
    return
  }

  if (!window.Paddle) {
    if (loading.value) return // prevent double-click during script load
    loading.value = true
    const script = document.createElement('script')
    script.src = 'https://cdn.paddle.com/paddle/v2/paddle.js'
    script.onload = () => {
      loading.value = false
      openCheckout()
    }
    script.onerror = () => {
      loading.value = false
      toast.error('Payment system unavailable')
    }
    document.head.appendChild(script)
    return
  }

  // Initialize Paddle SDK if client token available
  if (clientToken.value) {
    window.Paddle.Initialize({ token: clientToken.value })
  }

  loading.value = true
  window.Paddle.Checkout.open({
    items: [{ priceId: priceId.value, quantity: 1 }],
    customer: user.value?.email ? { email: user.value.email } : undefined,
    customData: user.value?.email ? { email: user.value.email } : undefined,
    settings: {
      theme: 'dark',
      displayMode: 'overlay',
      successUrl: `${window.location.origin}/settings?upgraded=1`,
    },
  })
  loading.value = false
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <transition name="dialog">
      <div v-if="open" class="fixed inset-0 z-[200] flex items-center justify-center p-4" @click.self="emit('close')">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" />
        <div
          class="relative w-full max-w-sm rounded-2xl p-6 text-center"
          style="background: var(--card); border: 1px solid var(--border)"
        >
          <div
            class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl text-[32px]"
            style="background: var(--accent-soft)"
          >
            📚
          </div>

          <!-- App: Leerio Pro through Google Play -->
          <template v-if="native">
            <h2 class="text-[18px] font-extrabold text-(--t1)">{{ t('pro.title') }}</h2>
            <p class="mt-2 text-[13px] text-(--t2)">{{ why }}</p>

            <div class="mt-5 space-y-2 text-left">
              <div class="flex items-center gap-2.5 rounded-lg px-3 py-2" style="background: rgba(255, 255, 255, 0.03)">
                <span class="text-[14px]">✔</span>
                <span class="text-[13px] text-(--t2)">{{ t('pro.benefitBooks') }}</span>
              </div>
              <div class="flex items-center gap-2.5 rounded-lg px-3 py-2" style="background: rgba(255, 255, 255, 0.03)">
                <span class="text-[14px]">✔</span>
                <span class="text-[13px] text-(--t2)">{{ t('pro.benefitNarration') }}</span>
              </div>
            </div>

            <div v-if="pro.plans.value.length" class="mt-5 space-y-2">
              <button
                v-for="plan in pro.plans.value"
                :key="plan.offer.basePlanId"
                class="flex w-full items-center justify-between rounded-xl border px-4 py-3 text-left transition-colors"
                :class="
                  chosen?.offer.basePlanId === plan.offer.basePlanId
                    ? 'border-(--accent) bg-white/[0.05]'
                    : 'border-(--border) bg-white/[0.02]'
                "
                @click="chosenBase = plan.offer.basePlanId"
              >
                <span>
                  <span class="block text-[14px] font-semibold text-(--t1)">{{ periodName(plan) }}</span>
                  <span class="block text-[12px] text-(--t3)">{{ priceLabel(plan) }}</span>
                </span>
                <span v-if="plan.trialDays" class="text-[11px] font-semibold text-(--accent)">
                  {{ t('pro.trial', plan.trialDays) }}
                </span>
              </button>
            </div>
            <p v-else class="mt-5 text-[13px] text-(--t3)">{{ t('pro.unavailable') }}</p>

            <button
              v-if="chosen"
              v-ripple
              class="btn btn-primary mt-5 w-full justify-center py-3 text-[15px]"
              :disabled="pro.busy.value"
              @click="buy"
            >
              {{ chosen.trialDays ? t('pro.startTrial') : t('pro.subscribe') }}
            </button>
            <p v-if="chosen" class="mt-2 text-[11px] text-(--t3)">
              {{
                chosen.trialDays
                  ? t('pro.termsTrial', { days: t('pro.trial', chosen.trialDays), price: priceLabel(chosen) })
                  : t('pro.terms', { price: priceLabel(chosen) })
              }}
            </p>
            <button class="mt-3 w-full py-1 text-[12px] font-semibold text-(--accent)" @click="restore">
              {{ t('pro.restore') }}
            </button>
            <button class="mt-1 w-full py-2 text-[13px] text-(--t3) hover:text-(--t2)" @click="emit('close')">
              {{ t('paywall.notNow') }}
            </button>
          </template>

          <template v-else>
            <h2 class="text-[18px] font-extrabold text-(--t1)">{{ t('paywall.title') }}</h2>
            <p v-if="props.bookCount" class="mt-2 text-[13px] text-(--t2)">
              {{ t('paywall.subtitleDynamic', { count: props.bookCount }) }}
            </p>
            <p v-else class="mt-2 text-[13px] text-(--t2)">{{ t('paywall.subtitle', { n: freeLimit }) }}</p>

            <div class="mt-5 space-y-2 text-left">
              <div class="flex items-center gap-2.5 rounded-lg px-3 py-2" style="background: rgba(255, 255, 255, 0.03)">
                <span class="text-[14px]">✔</span>
                <span class="text-[13px] text-(--t2)">{{ t('paywall.benefitUnlimited') }}</span>
              </div>
              <div class="flex items-center gap-2.5 rounded-lg px-3 py-2" style="background: rgba(255, 255, 255, 0.03)">
                <span class="text-[14px]">✔</span>
                <span class="text-[13px] text-(--t2)">{{ t('paywall.benefitSync') }}</span>
              </div>
              <div class="flex items-center gap-2.5 rounded-lg px-3 py-2" style="background: rgba(255, 255, 255, 0.03)">
                <span class="text-[14px]">✔</span>
                <span class="text-[13px] text-(--t2)">{{ t('paywall.benefitAccess') }}</span>
              </div>
            </div>

            <button
              v-ripple
              class="btn btn-primary mt-6 w-full justify-center py-3 text-[15px]"
              :disabled="loading"
              @click="openCheckout"
            >
              {{ t('paywall.upgrade') }}
            </button>
            <button class="mt-3 w-full py-2 text-[13px] text-(--t3) hover:text-(--t2)" @click="emit('close')">
              {{ t('paywall.notNow') }}
            </button>
          </template>
        </div>
      </div>
    </transition>
  </Teleport>
</template>
