<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useYouTubeImport } from '@/composables/useYouTubeImport'
import { IconCheck, IconArrowLeft } from '@/components/shared/icons'

const { t } = useI18n()
const router = useRouter()
const yt = useYouTubeImport()
const youtubeUrl = ref('')
const chunkMinutes = ref(10)

function handleRetry() {
  yt.reset()
  youtubeUrl.value = ''
}
</script>

<template>
  <div class="min-h-dvh min-h-screen px-4 py-6" style="background: var(--bg)">
    <!-- Header -->
    <div class="mb-6 flex items-center gap-3">
      <button class="flex items-center text-[--t3] hover:text-[--t1]" @click="router.back()">
        <IconArrowLeft :size="20" />
      </button>
      <h1 class="text-[18px] font-bold text-[--t1]">YouTube</h1>
    </div>

    <div class="mx-auto max-w-xl space-y-5">
      <!-- URL Input -->
      <div class="card space-y-4 px-5 py-5">
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">{{ t('upload.youtubeUrl') }}</label>
          <div class="flex gap-2">
            <input
              v-model="youtubeUrl"
              type="url"
              :placeholder="t('upload.youtubeUrlPlaceholder')"
              class="input-field min-w-0 flex-1 px-3.5 py-2.5"
              :disabled="yt.step.value !== 'idle' && yt.step.value !== 'resolved' && yt.step.value !== 'error'"
              @keydown.enter="yt.resolve(youtubeUrl)"
            />
            <button
              class="btn-primary shrink-0 px-5"
              :disabled="!youtubeUrl.trim() || yt.step.value === 'resolving'"
              @click="yt.resolve(youtubeUrl)"
            >
              {{ yt.step.value === 'resolving' ? '...' : t('upload.youtubeFind') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Resolve Result -->
      <div
        v-if="
          yt.step.value === 'resolved' ||
          yt.step.value === 'downloading' ||
          yt.step.value === 'splitting' ||
          yt.step.value === 'saving'
        "
        class="card space-y-4 px-5 py-5"
      >
        <!-- Thumbnail + Info -->
        <div class="flex gap-4">
          <img
            v-if="yt.thumbnail.value"
            :src="yt.thumbnail.value"
            :alt="yt.title.value"
            class="h-24 w-24 shrink-0 rounded-lg object-cover"
          />
          <div class="min-w-0 flex-1 space-y-3">
            <div>
              <label class="mb-1 block text-[11px] font-semibold text-[--t3]">{{ t('upload.labelTitle') }}</label>
              <input
                v-model="yt.title.value"
                type="text"
                class="input-field w-full px-3 py-2 text-[13px]"
                :disabled="yt.step.value !== 'resolved'"
              />
            </div>
            <div>
              <label class="mb-1 block text-[11px] font-semibold text-[--t3]">{{ t('upload.labelAuthor') }}</label>
              <input
                v-model="yt.author.value"
                type="text"
                class="input-field w-full px-3 py-2 text-[13px]"
                :disabled="yt.step.value !== 'resolved'"
              />
            </div>
          </div>
        </div>

        <!-- Chapters info -->
        <div class="text-[12px] text-[--t3]">
          <span v-if="yt.chapters.value.length">
            {{ yt.chapters.value.length }} {{ t('upload.youtubeChapters', { n: yt.chapters.value.length }) }}
          </span>
          <span v-else>
            {{ t('upload.youtubeNoChapters', { n: chunkMinutes }) }}
          </span>
          <span class="ml-2">&middot;</span>
          <span class="ml-2"
            >{{ Math.round(yt.duration.value / 60) }}
            {{ t('upload.youtubeDuration', { m: Math.round(yt.duration.value / 60) }) }}</span
          >
        </div>

        <!-- Chunk slider (only when no chapters) -->
        <div v-if="!yt.chapters.value.length && yt.step.value === 'resolved'" class="flex items-center gap-3">
          <label class="text-[12px] text-[--t2]">{{ t('upload.youtubeChunkLength') }}</label>
          <input v-model.number="chunkMinutes" type="range" min="5" max="30" step="5" class="flex-1" />
          <span class="w-10 text-right text-[12px] font-semibold text-[--t1]">{{ chunkMinutes }}</span>
        </div>

        <!-- Download button -->
        <button
          v-if="yt.step.value === 'resolved'"
          class="btn-primary w-full py-3"
          @click="yt.importFromYouTube(chunkMinutes)"
        >
          {{ t('upload.youtubeDownload') }}
        </button>

        <!-- Progress -->
        <div v-if="yt.step.value === 'downloading' || yt.step.value === 'splitting' || yt.step.value === 'saving'">
          <div class="mb-2 flex items-center justify-between text-[12px]">
            <span class="text-[--t2]">
              <template v-if="yt.step.value === 'downloading'">{{
                t('upload.youtubeDownloading', { progress: yt.progress.value })
              }}</template>
              <template v-else-if="yt.step.value === 'splitting'"
                >{{ t('upload.youtubeSplitting') }} {{ yt.progress.value }}%</template
              >
              <template v-else>{{ t('upload.youtubeSaving') }}</template>
            </span>
            <button class="cursor-pointer border-0 bg-transparent text-[--t3] hover:text-[--t1]" @click="yt.cancel()">
              {{ t('upload.youtubeCancel') }}
            </button>
          </div>
          <div class="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
            <div
              class="h-full rounded-full transition-all duration-300"
              style="background: var(--gradient-accent)"
              :style="{ width: yt.progress.value + '%' }"
            />
          </div>
        </div>
      </div>

      <!-- Done -->
      <div v-if="yt.step.value === 'done'" class="card flex items-center gap-3 px-5 py-4">
        <IconCheck :size="20" class="text-green-400" />
        <span class="text-[13px] font-medium text-[--t1]">{{ t('upload.youtubeDone') }}</span>
        <router-link to="/my-library" class="ml-auto text-[12px] font-semibold text-[--accent] no-underline">
          {{ t('nav.myLibrary') }}
        </router-link>
      </div>

      <!-- Error -->
      <div v-if="yt.step.value === 'error'" class="card flex items-center gap-3 border-red-500/20 px-5 py-4">
        <span class="text-[13px] text-red-400">{{ yt.errorMessage.value }}</span>
        <button
          class="ml-auto cursor-pointer border-0 bg-transparent text-[12px] font-semibold text-[--accent]"
          @click="handleRetry"
        >
          {{ t('upload.youtubeRetry') }}
        </button>
      </div>
    </div>
  </div>
</template>
