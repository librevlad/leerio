<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '../../composables/useToast'

const { t } = useI18n()
const props = defineProps<{ folder: string; path: string }>()
const toast = useToast()
const copied = ref(false)

function copyPath() {
  navigator.clipboard
    .writeText(props.path)
    .then(() => {
      copied.value = true
      toast.success('Путь скопирован')
      setTimeout(() => {
        copied.value = false
      }, 2000)
    })
    .catch(() => {
      toast.error('Не удалось скопировать')
    })
}
</script>

<template>
  <div class="card p-5">
    <h3 class="section-label mb-3">{{ t('book.location') }}</h3>
    <div
      class="group flex cursor-pointer items-center gap-3 rounded-xl px-3.5 py-3 transition-all hover:bg-white/[0.04]"
      :title="path"
      @click="copyPath"
    >
      <div
        class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg"
        style="background: rgba(232, 146, 58, 0.1)"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="text-[--accent-2]"
        >
          <path
            d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"
          />
        </svg>
      </div>
      <div class="min-w-0 flex-1">
        <p class="truncate text-[12px] font-medium text-[--t2] transition-colors group-hover:text-[--t1]">
          {{ folder }}
        </p>
        <p class="mt-0.5 text-[10px] text-[--t3]">
          {{ copied ? t('book.copied') : t('book.copyPath') }}
        </p>
      </div>
    </div>
  </div>
</template>
