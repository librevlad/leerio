<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { Velocity } from '../../types'

const { t } = useI18n()
defineProps<{ velocity: Velocity }>()
</script>

<template>
  <div class="card p-6">
    <h3 class="section-label mb-5">{{ t('analytics.velocityTitle') }}</h3>
    <div class="grid grid-cols-2 gap-6">
      <div>
        <p class="mb-1.5 text-[12px] text-[--t3]">{{ t('analytics.velocityTotal') }}</p>
        <p class="text-[26px] leading-none font-bold tracking-tight text-[--t1]">{{ velocity.total }}</p>
      </div>
      <div>
        <p class="mb-1.5 text-[12px] text-[--t3]">{{ t('analytics.velocityAvgMonth') }}</p>
        <p class="gradient-text text-[26px] leading-none font-bold tracking-tight">
          {{ (velocity.avg_per_month || 0).toFixed(1) }}
        </p>
      </div>
      <div>
        <p class="mb-1.5 text-[12px] text-[--t3]">{{ t('analytics.velocityThisYear') }}</p>
        <p class="text-[26px] leading-none font-bold tracking-tight text-[--t1]">{{ velocity.this_year || 0 }}</p>
      </div>
      <div>
        <p class="mb-1.5 text-[12px] text-[--t3]">{{ t('analytics.velocityRecent90') }}</p>
        <p class="text-[26px] leading-none font-bold tracking-tight text-[--t1]">{{ velocity.recent_90d || 0 }}</p>
      </div>
      <div v-if="velocity.best_month" class="col-span-2 pt-2" style="border-top: 1px solid var(--border)">
        <p class="mb-1 text-[12px] text-[--t3]">{{ t('analytics.velocityBestMonth') }}</p>
        <p class="text-[14px] font-semibold text-[--t2]">
          {{ velocity.best_month }} <span class="text-[--t3]">({{ velocity.best_month_count }})</span>
        </p>
      </div>
    </div>
  </div>
</template>
