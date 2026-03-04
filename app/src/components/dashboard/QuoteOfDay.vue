<script setup lang="ts">
import type { Quote } from '../../types'

defineProps<{ quote: Quote | null }>()
</script>

<template>
  <div v-if="quote" class="card relative overflow-hidden p-5">
    <div
      class="absolute top-0 right-0 h-24 w-24 rounded-full opacity-[0.04]"
      style="background: var(--accent); filter: blur(24px); transform: translate(30%, -30%)"
    />
    <svg class="mb-3 h-6 w-6 opacity-20" viewBox="0 0 24 24" fill="var(--accent)">
      <path
        d="M4.583 17.321C3.553 16.227 3 15 3 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311 1.804.167 3.226 1.648 3.226 3.489a3.5 3.5 0 01-3.5 3.5c-1.073 0-2.099-.49-2.748-1.179zm10 0C13.553 16.227 13 15 13 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311 1.804.167 3.226 1.648 3.226 3.489a3.5 3.5 0 01-3.5 3.5c-1.073 0-2.099-.49-2.748-1.179z"
      />
    </svg>
    <p class="relative text-[14px] leading-relaxed text-[--t2] italic">
      {{ quote.text }}
    </p>
    <p class="relative mt-3 text-[12px] text-[--t3]">
      — {{ quote.book }}
      <span v-if="quote.author">, {{ quote.author }}</span>
    </p>
  </div>
</template>
