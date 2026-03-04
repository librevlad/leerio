<script setup lang="ts">
import type { Velocity } from '../../types'

defineProps<{ velocity: Velocity }>()
</script>

<template>
  <div class="card p-6">
    <h3 class="section-label mb-5">Темп чтения</h3>
    <div class="grid grid-cols-2 gap-6">
      <div>
        <p class="text-[12px] text-[--t3] mb-1.5">Всего</p>
        <p class="text-[26px] font-bold text-[--t1] tracking-tight leading-none">{{ velocity.total }}</p>
      </div>
      <div>
        <p class="text-[12px] text-[--t3] mb-1.5">В среднем / мес</p>
        <p class="text-[26px] font-bold gradient-text tracking-tight leading-none">{{ (velocity.avg_per_month || 0).toFixed(1) }}</p>
      </div>
      <div>
        <p class="text-[12px] text-[--t3] mb-1.5">В этом году</p>
        <p class="text-[26px] font-bold text-[--t1] tracking-tight leading-none">{{ velocity.this_year || 0 }}</p>
      </div>
      <div>
        <p class="text-[12px] text-[--t3] mb-1.5">За 90 дней</p>
        <p class="text-[26px] font-bold text-[--t1] tracking-tight leading-none">{{ velocity.recent_90d || 0 }}</p>
      </div>
      <div v-if="velocity.best_month" class="col-span-2 pt-2" style="border-top: 1px solid var(--border)">
        <p class="text-[12px] text-[--t3] mb-1">Лучший месяц</p>
        <p class="text-[14px] font-semibold text-[--t2]">
          {{ velocity.best_month }} <span class="text-[--t3]">({{ velocity.best_month_count }})</span>
        </p>
      </div>
    </div>
  </div>
</template>
