<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { Achievement } from '../../types'

const { t } = useI18n()
defineProps<{ achievements: Achievement[] }>()
</script>

<template>
  <div class="card p-6">
    <h3 class="section-label mb-5">{{ t('analytics.achievementsTitle') }}</h3>
    <div v-if="achievements.length" class="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <div
        v-for="(a, i) in achievements"
        :key="i"
        class="rounded-2xl p-4 text-center transition-all duration-200 hover:scale-[1.03]"
        style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border)"
      >
        <span class="mb-2 block text-2xl">{{ a.icon }}</span>
        <p class="text-[12px] font-semibold text-[--t1]">{{ a.name }}</p>
        <p class="mt-0.5 text-[11px] text-[--t3]">{{ a.desc }}</p>
      </div>
    </div>
    <p v-else class="py-8 text-center text-[12px] text-[--t3]">{{ t('analytics.achievementsEmpty') }}</p>
  </div>
</template>
