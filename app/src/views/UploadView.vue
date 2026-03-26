<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { useNetwork } from '@/composables/useNetwork'
import { useAuth } from '@/composables/useAuth'
import { IconUpload, IconPlay, IconMicrophone, IconSmartphone } from '@/components/shared/icons'
import UploadTab from '@/components/upload/UploadTab.vue'
import TTSTab from '@/components/upload/TTSTab.vue'
import LocalTab from '@/components/upload/LocalTab.vue'

const { t } = useI18n()
const { isOnline } = useNetwork()
const { isGuest } = useAuth()
const route = useRoute()

type Tab = 'upload' | 'youtube' | 'tts' | 'local'
const defaultTab = isGuest.value ? 'local' : 'upload'
const initTab = (['upload', 'youtube', 'tts', 'local'] as Tab[]).includes(route.query.tab as Tab)
  ? (route.query.tab as Tab)
  : defaultTab
const activeTab = ref<Tab>(initTab)

const tabDefs = [
  { key: 'upload' as const, label: t('upload.tabUpload'), icon: IconUpload },
  { key: 'youtube' as const, label: t('upload.tabYouTube'), icon: IconPlay },
  { key: 'tts' as const, label: t('upload.tabTts'), icon: IconMicrophone },
  { key: 'local' as const, label: t('upload.tabLocal'), icon: IconSmartphone },
]
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="page-title">{{ t('upload.title') }}</h1>
      <p class="mt-1 text-[13px] text-[--t3]">{{ t('upload.subtitle') }}</p>
    </div>

    <div class="scrollbar-hide mb-6 flex gap-2 overflow-x-auto">
      <button
        v-for="tab in tabDefs"
        :key="tab.key"
        class="flex flex-shrink-0 cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 text-[13px] font-medium transition-colors"
        :class="
          activeTab === tab.key
            ? 'border-[--accent]/30 bg-[--accent]/10 text-[--accent]'
            : 'border-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="activeTab = tab.key"
      >
        <component :is="tab.icon" :size="16" />
        {{ tab.label }}
      </button>
    </div>

    <UploadTab v-if="activeTab === 'upload'" />
    <div v-else-if="activeTab === 'youtube'" class="flex flex-col items-center gap-4 py-12 text-center">
      <div class="text-[40px]">🎥</div>
      <p class="text-[14px] text-[--t2]">{{ t('upload.youtubeRedirect') }}</p>
      <router-link to="/youtube-import" class="btn btn-primary">{{ t('upload.youtubeGoTo') }}</router-link>
    </div>
    <TTSTab v-else-if="activeTab === 'tts'" />
    <LocalTab v-else-if="activeTab === 'local'" />

    <div
      v-if="!isOnline && activeTab !== 'local'"
      class="mt-5 max-w-xl rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-[13px] text-[--t2]"
    >
      {{ t('upload.offlineNote') }}
    </div>
  </div>
</template>
