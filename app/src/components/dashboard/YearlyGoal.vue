<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ProgressBar from '../shared/ProgressBar.vue'
import { plural } from '../../utils/plural'

const { t } = useI18n()
const props = defineProps<{
  done: number
  goal: number
}>()

const percent = computed(() => Math.min(100, Math.round((props.done / Math.max(1, props.goal)) * 100)))

const pace = computed(() => {
  const now = new Date()
  const dayOfYear = Math.floor((now.getTime() - new Date(now.getFullYear(), 0, 0).getTime()) / 86400000)
  const daysInYear = now.getFullYear() % 4 === 0 ? 366 : 365
  if (dayOfYear < 7) return null
  const projected = Math.round((props.done / dayOfYear) * daysInYear)
  const remaining = Math.max(0, props.goal - props.done)
  const daysLeft = daysInYear - dayOfYear
  const perMonth = daysLeft > 0 ? (remaining / daysLeft) * 30 : 0
  return { projected, perMonth: Math.round(perMonth * 10) / 10, ahead: projected >= props.goal }
})
</script>

<template>
  <div class="card p-5">
    <div class="mb-4 flex items-center justify-between">
      <span class="section-label">{{ t('dashboard.yearlyGoal') }}</span>
      <span class="text-[12px] font-medium text-[--t3]">{{ done }}/{{ goal }}</span>
    </div>
    <ProgressBar :percent="percent" height="h-1.5" />
    <p class="gradient-text mt-3 text-[24px] leading-none font-bold tracking-tight">{{ percent }}%</p>
    <p class="mt-1 text-[12px] text-[--t3]">
      <template v-if="done >= goal"> Цель достигнута! </template>
      <template v-else>
        осталось {{ Math.max(0, goal - done) }} {{ plural(Math.max(0, goal - done), 'книга', 'книги', 'книг') }}
      </template>
    </p>
    <p v-if="pace" class="mt-2 text-[11px]" :class="pace.ahead ? 'text-emerald-400' : 'text-amber-400'">
      <template v-if="done >= goal">
        Темп: {{ pace.projected }} {{ plural(pace.projected, 'книга', 'книги', 'книг') }} к концу года
      </template>
      <template v-else-if="pace.ahead">
        В темпе на {{ pace.projected }} {{ plural(pace.projected, 'книгу', 'книги', 'книг') }}
      </template>
      <template v-else>
        Нужно ~{{ pace.perMonth }} {{ plural(Math.ceil(pace.perMonth), 'книга', 'книги', 'книг') }}/мес
      </template>
    </p>
  </div>
</template>
