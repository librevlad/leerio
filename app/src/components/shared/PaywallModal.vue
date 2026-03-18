<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()
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
          <p class="mt-2 text-[13px] text-[--t2]">{{ t('paywall.subtitle') }}</p>

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

          <button v-ripple class="btn btn-primary mt-6 w-full justify-center py-3 text-[15px]">
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
