<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

const { t } = useI18n()
const router = useRouter()
</script>

<template>
  <div class="flex min-h-screen items-center justify-center px-4" style="background: var(--bg)">
    <div class="text-center">
      <p class="text-[120px] leading-none font-bold text-[--accent]/20">404</p>
      <h1 class="mt-4 text-[24px] font-bold text-[--t1]">{{ t('common.notFoundTitle') }}</h1>
      <p class="mt-2 text-[14px] text-[--t3]">{{ t('common.notFoundDesc') }}</p>
      <button
        class="mt-6 inline-flex cursor-pointer items-center gap-2 rounded-xl border-0 px-6 py-3 text-[14px] font-semibold text-white"
        style="background: var(--gradient-accent)"
        @click="router.push('/')"
      >
        {{ t('common.goHome') }}
      </button>
      <div class="mt-8 flex flex-wrap justify-center gap-4">
        <router-link to="/library" class="text-[13px] text-[--accent] hover:underline">
          {{ t('nav.catalog') }}
        </router-link>
        <router-link to="/my-library" class="text-[13px] text-[--accent] hover:underline">
          {{ t('nav.myLibrary') }}
        </router-link>
        <router-link to="/settings" class="text-[13px] text-[--accent] hover:underline">
          {{ t('nav.settings') }}
        </router-link>
      </div>
    </div>
  </div>
</template>
