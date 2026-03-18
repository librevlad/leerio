<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../../api'
import { useAuth } from '../../composables/useAuth'
import { useToast } from '../../composables/useToast'
import { useTracking } from '../../composables/useTelemetry'

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

const props = defineProps<{ open: boolean; bookCount?: number }>()
const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()
const { user } = useAuth()
const toast = useToast()
const { track } = useTracking()

watch(
  () => props.open,
  (v) => {
    if (v) track('paywall_shown')
  },
)
const priceId = ref('')
const freeLimit = ref(10)
const loading = ref(false)

defineExpose({ freeLimit })

onMounted(async () => {
  try {
    const data = await api.getPaymentPlan()
    priceId.value = data.price_id || ''
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
    toast.error('Payment system loading...')
    // Load Paddle.js dynamically
    const script = document.createElement('script')
    script.src = 'https://cdn.paddle.com/paddle/v2/paddle.js'
    script.onload = () => openCheckout()
    document.head.appendChild(script)
    return
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

          <h2 class="text-[18px] font-extrabold text-[--t1]">{{ t('paywall.title') }}</h2>
          <p v-if="props.bookCount" class="mt-2 text-[13px] text-[--t2]">
            {{ t('paywall.subtitleDynamic', { count: props.bookCount }) }}
          </p>
          <p v-else class="mt-2 text-[13px] text-[--t2]">{{ t('paywall.subtitle', { n: freeLimit }) }}</p>

          <div class="mt-5 space-y-2 text-left">
            <div class="flex items-center gap-2.5 rounded-lg px-3 py-2" style="background: rgba(255, 255, 255, 0.03)">
              <span class="text-[14px]">✔</span>
              <span class="text-[13px] text-[--t2]">{{ t('paywall.benefitUnlimited') }}</span>
            </div>
            <div class="flex items-center gap-2.5 rounded-lg px-3 py-2" style="background: rgba(255, 255, 255, 0.03)">
              <span class="text-[14px]">✔</span>
              <span class="text-[13px] text-[--t2]">{{ t('paywall.benefitSync') }}</span>
            </div>
            <div class="flex items-center gap-2.5 rounded-lg px-3 py-2" style="background: rgba(255, 255, 255, 0.03)">
              <span class="text-[14px]">✔</span>
              <span class="text-[13px] text-[--t2]">{{ t('paywall.benefitAccess') }}</span>
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
          <button class="mt-3 w-full py-2 text-[13px] text-[--t3] hover:text-[--t2]" @click="emit('close')">
            {{ t('paywall.notNow') }}
          </button>
        </div>
      </div>
    </transition>
  </Teleport>
</template>
