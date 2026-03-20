<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const { t } = useI18n()

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/library')
  }
}
</script>

<template>
  <div class="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
    <!-- Illustration -->
    <div class="relative mb-6">
      <div class="text-[80px] leading-none opacity-10 font-black text-[--t1]">404</div>
      <div class="absolute inset-0 flex items-center justify-center text-[40px]">🎧</div>
    </div>

    <h1 class="text-[20px] font-bold text-[--t1]">{{ t('notFound.title') }}</h1>
    <p class="mt-2 max-w-sm text-[13px] text-[--t3]">{{ t('notFound.subtitle') }}</p>

    <!-- Actions -->
    <div class="mt-6 flex flex-col items-center gap-3">
      <button
        class="btn-primary px-8 py-2.5"
        @click="goBack"
      >
        {{ t('notFound.goBack') }}
      </button>
    </div>

    <!-- Quick links -->
    <div class="mt-8 flex gap-4">
      <router-link
        v-for="link in [
          { to: '/library', label: t('nav.catalog') },
          { to: '/my-library', label: t('nav.myLibrary') },
          { to: '/settings', label: t('nav.settings') },
        ]"
        :key="link.to"
        :to="link.to"
        class="rounded-lg px-3 py-1.5 text-[12px] text-[--t3] no-underline transition-colors hover:bg-white/[0.04] hover:text-[--t2]"
      >
        {{ link.label }}
      </router-link>
    </div>
  </div>
</template>
