<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useUserBooks } from '@/composables/useUserBooks'
import ProgressBar from '@/components/shared/ProgressBar.vue'
import { IconUpload, IconMicrophone, IconX, IconCheck } from '@/components/shared/icons'
import type { TTSVoice, TTSEngine } from '@/types'

const toast = useToast()
const { t } = useI18n()
const { pollJob } = useUserBooks()

// ── TTS state ──
const ttsTitle = ref('')
const ttsAuthor = ref('')
const ttsFile = ref<File | null>(null)
const ttsEngine = ref<'edge' | 'openai'>('edge')
const ttsVoice = ref('ru-RU-DmitryNeural')
const ttsRate = ref('+0%')
const voices = ref<TTSVoice[]>([])
const engines = ref<TTSEngine[]>([])
const showEngineSelector = ref(false)
const converting = ref(false)
const conversionStarted = ref(false)
const currentJobId = ref('')
const jobProgress = ref(0)
const jobStatus = ref('')

const rateOptions = [
  { label: '0.75x', value: '-25%' },
  { label: '1.0x', value: '+0%' },
  { label: '1.25x', value: '+25%' },
  { label: '1.5x', value: '+50%' },
]

async function loadVoices(engine: string) {
  try {
    voices.value = await api.getTTSVoices(engine)
    const first = voices.value[0]
    if (first) {
      ttsVoice.value = first.id
    }
  } catch {
    /* voices will remain empty */
  }
}

async function selectEngine(engine: 'edge' | 'openai') {
  ttsEngine.value = engine
  await loadVoices(engine)
}

onMounted(async () => {
  try {
    engines.value = await api.getTTSEngines()
    // Show engine selector if openai is available
    showEngineSelector.value = engines.value.some((e) => e.id === 'openai' && e.available)
  } catch {
    /* engines will remain empty */
  }
  await loadVoices('edge')
})

function onTTSFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.[0]) {
    ttsFile.value = input.files[0]
  }
}

async function handleTTSConvert() {
  if (!ttsTitle.value.trim()) {
    toast.error(t('upload.errTitleRequired'))
    return
  }
  if (!ttsFile.value) {
    toast.error(t('upload.errFileRequired'))
    return
  }

  converting.value = true
  try {
    const formData = new FormData()
    formData.append('title', ttsTitle.value.trim())
    formData.append('author', ttsAuthor.value.trim())
    formData.append('voice', ttsVoice.value)
    formData.append('rate', ttsRate.value)
    formData.append('engine', ttsEngine.value)
    formData.append('file', ttsFile.value)

    const job = await api.startTTSConversion(formData)
    currentJobId.value = job.id
    conversionStarted.value = true
    jobProgress.value = 0
    jobStatus.value = 'processing'

    pollJob(job.id, (j) => {
      jobProgress.value = j.progress
      jobStatus.value = j.status
      if (j.status === 'done') {
        toast.success(t('upload.successTts'))
        converting.value = false
      } else if (j.status === 'error') {
        toast.error(t('common.errorPrefix', { msg: j.error || t('common.unknownError') }))
        converting.value = false
      }
    })
  } catch (e: unknown) {
    toast.error(t('common.errorPrefix', { msg: e instanceof Error ? e.message : t('common.unknownError') }))
    converting.value = false
  }
}
</script>

<template>
  <div class="max-w-xl space-y-5">
    <div class="card space-y-4 px-5 py-5">
      <!-- Title -->
      <div>
        <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">{{ t('upload.labelTitle') }}</label>
        <input
          v-model="ttsTitle"
          type="text"
          :placeholder="t('upload.placeholderBookTitle')"
          class="input-field w-full px-3.5 py-2.5"
        />
      </div>

      <!-- Author -->
      <div>
        <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">{{ t('upload.labelAuthor') }}</label>
        <input
          v-model="ttsAuthor"
          type="text"
          :placeholder="t('upload.placeholderAuthor')"
          class="input-field w-full px-3.5 py-2.5"
        />
      </div>

      <!-- Document file -->
      <div>
        <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">{{ t('upload.labelDocument') }}</label>
        <label
          class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-[--border] px-4 py-3 text-[13px] transition-all hover:border-white/15 hover:bg-white/[0.02]"
          :class="ttsFile ? 'text-[--t1]' : 'text-[--t3]'"
        >
          <IconUpload :size="14" />
          {{ ttsFile ? ttsFile.name : t('upload.selectFile') }}
          <input type="file" accept=".pdf,.epub,.txt,.fb2" class="hidden" @change="onTTSFileChange" />
        </label>
      </div>
    </div>

    <!-- Voice settings card -->
    <div class="card space-y-4 px-5 py-5">
      <h3 class="section-label">{{ t('upload.labelVoiceSettings') }}</h3>

      <!-- Engine selector -->
      <div v-if="showEngineSelector">
        <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">{{ t('upload.labelEngine') }}</label>
        <div class="flex gap-2">
          <button
            v-for="eng in engines.filter((e) => e.available)"
            :key="eng.id"
            class="cursor-pointer rounded-lg border px-3.5 py-1.5 text-[12px] font-medium transition-colors"
            :class="
              ttsEngine === eng.id
                ? 'border-white/10 bg-white/[0.08] text-[--t1]'
                : 'border-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
            "
            @click="selectEngine(eng.id as 'edge' | 'openai')"
          >
            {{ eng.name }}
          </button>
        </div>
      </div>

      <!-- Voice selection -->
      <div>
        <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">{{ t('upload.labelVoice') }}</label>
        <select v-model="ttsVoice" class="input-field w-full px-3.5 py-2.5">
          <option v-for="v in voices" :key="v.id" :value="v.id">
            {{ v.name }} ({{ v.lang }},
            {{
              v.gender === 'male' ? t('upload.genderMale') : v.gender === 'female' ? t('upload.genderFemale') : ''
            }})
          </option>
        </select>
      </div>

      <!-- Rate -->
      <div>
        <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">{{ t('upload.labelSpeed') }}</label>
        <div class="flex gap-2">
          <button
            v-for="opt in rateOptions"
            :key="opt.value"
            class="cursor-pointer rounded-lg border px-3.5 py-1.5 text-[12px] font-medium transition-colors"
            :class="
              ttsRate === opt.value
                ? 'border-white/10 bg-white/[0.08] text-[--t1]'
                : 'border-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
            "
            @click="ttsRate = opt.value"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- Convert button -->
    <button
      class="btn btn-primary w-full justify-center text-[14px]"
      :disabled="converting || !ttsTitle.trim() || !ttsFile"
      @click="handleTTSConvert"
    >
      <IconMicrophone v-if="!converting || !conversionStarted" :size="16" />
      <span v-if="converting && !conversionStarted">{{ t('upload.creating') }}</span>
      <span v-else>{{ t('upload.createBtn') }}</span>
    </button>

    <!-- Conversion progress -->
    <div
      v-if="conversionStarted"
      :aria-busy="jobStatus === 'processing'"
      class="card overflow-hidden"
      :class="
        jobStatus === 'done'
          ? 'border-emerald-500/30'
          : jobStatus === 'error'
            ? 'border-red-500/30'
            : 'border-violet-500/30'
      "
    >
      <div
        class="px-5 py-4"
        :class="
          jobStatus === 'done' ? 'bg-emerald-500/5' : jobStatus === 'error' ? 'bg-red-500/5' : 'bg-violet-500/5'
        "
      >
        <div class="mb-3 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <div
              class="flex h-8 w-8 items-center justify-center rounded-xl"
              :class="
                jobStatus === 'done'
                  ? 'bg-emerald-500/15'
                  : jobStatus === 'error'
                    ? 'bg-red-500/15'
                    : 'bg-violet-500/15'
              "
            >
              <IconCheck v-if="jobStatus === 'done'" :size="16" class="text-emerald-400" />
              <IconX v-else-if="jobStatus === 'error'" :size="16" class="text-red-400" />
              <IconMicrophone v-else :size="16" class="text-violet-400" />
            </div>
            <span class="text-[13px] font-semibold text-[--t1]">
              {{
                jobStatus === 'done'
                  ? t('upload.conversionDone')
                  : jobStatus === 'error'
                    ? t('upload.conversionError')
                    : t('upload.conversionProgress')
              }}
            </span>
          </div>
          <span class="text-[12px] font-semibold" :class="jobStatus === 'done' ? 'text-emerald-400' : 'text-[--t3]'">
            {{ jobProgress }}%
          </span>
        </div>
        <ProgressBar :percent="jobProgress" height="h-2" />
        <router-link
          v-if="jobStatus === 'done'"
          to="/my-library"
          class="mt-3 inline-flex items-center gap-1.5 text-[12px] font-semibold text-emerald-400 no-underline hover:underline"
        >
          {{ t('upload.goToMyBooks') }}
        </router-link>
      </div>
    </div>
  </div>
</template>
