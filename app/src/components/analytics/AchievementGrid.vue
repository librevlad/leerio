<script setup lang="ts">
import type { Achievement } from '../../types'

defineProps<{ achievements: Achievement[] }>()
</script>

<template>
  <div class="card p-6">
    <h3 class="section-label mb-5">Достижения</h3>
    <div v-if="achievements.length" class="grid grid-cols-2 sm:grid-cols-3 gap-3">
      <div
        v-for="(a, i) in achievements"
        :key="i"
        class="p-4 rounded-2xl text-center transition-all duration-200 hover:scale-[1.03]"
        style="background: rgba(255,255,255,0.03); border: 1px solid var(--border)"
      >
        <span class="text-2xl block mb-2">{{ a.icon }}</span>
        <p class="text-[12px] font-semibold text-[--t1]">{{ a.name }}</p>
        <p class="text-[11px] mt-0.5 text-[--t3]">{{ a.desc }}</p>
      </div>
    </div>
    <p v-else class="text-[12px] text-center py-8 text-[--t3]">
      Достижения появятся с ростом библиотеки
    </p>
  </div>
</template>
