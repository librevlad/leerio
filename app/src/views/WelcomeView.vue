<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { useToast } from '../composables/useToast'
import { useTracking } from '../composables/useTelemetry'
import { formatSize } from '../utils/format'

const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const { track } = useTracking()

onMounted(() => track('onboarding_started'))

const step = ref(1)
const files = ref<File[]>([])
const uploading = ref(false)
const dragOver = ref(false)

function next() {
  if (step.value < 3) {
    step.value++
  }
}

function handleDrop(e: DragEvent) {
  dragOver.value = false
  if (!e.dataTransfer?.files) return
  addFiles(e.dataTransfer.files)
}

function handleFileInput(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) addFiles(input.files)
  input.value = ''
}

function addFiles(fileList: FileList) {
  const validExts = /\.(mp3|m4a|m4b|ogg|opus|flac|wav|zip)$/i
  for (const f of fileList) {
    if (validExts.test(f.name) && !files.value.some((x) => x.name === f.name)) {
      files.value.push(f)
    }
  }
}

function removeFile(idx: number) {
  files.value.splice(idx, 1)
}

function fmtSize(bytes: number): string {
  return formatSize(bytes, t)
}

async function finish() {
  track('onboarding_completed', { files: files.value.length })
  localStorage.setItem('leerio_onboarded', '1')

  // If files were added, upload them via API module
  if (files.value.length > 0) {
    uploading.value = true
    try {
      for (const file of files.value) {
        const formData = new FormData()
        formData.append('files', file)
        formData.append('title', file.name.replace(/\.[^.]+$/, ''))
        formData.append('author', '')
        await api.uploadBook(formData).catch(() => {})
      }
      toast.success(t('welcome.uploadSuccess', { n: files.value.length }))
    } catch {
      // Upload failures are non-blocking
    }
    uploading.value = false
  }

  router.push('/library')
}
</script>

<template>
  <div class="flex min-h-dvh min-h-screen items-center justify-center px-4" style="background: var(--bg)">
    <!-- Subtle glow -->
    <div
      class="pointer-events-none absolute inset-0"
      style="background: radial-gradient(ellipse 60% 50% at 50% 30%, rgba(255, 138, 0, 0.06) 0%, transparent 70%)"
    />

    <div class="relative w-full max-w-md">
      <!-- Progress dots -->
      <div class="mb-8 flex justify-center gap-2">
        <div
          v-for="i in 3"
          :key="i"
          class="h-1.5 rounded-full transition-all duration-300"
          :class="i === step ? 'w-6 bg-[--accent]' : i < step ? 'w-1.5 bg-[--accent]' : 'w-1.5 bg-white/10'"
        />
      </div>

      <!-- Step 1: Value prop -->
      <transition name="tab-fade" mode="out-in">
        <div v-if="step === 1" key="step1" class="text-center">
          <div
            class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-2xl text-[40px]"
            style="background: var(--accent-soft)"
          >
            🎧
          </div>
          <h1 class="text-[22px] font-extrabold tracking-tight text-[--t1]">{{ t('welcome.title') }}</h1>
          <p class="mt-3 text-[14px] leading-relaxed text-[--t2]">{{ t('welcome.subtitle') }}</p>
          <button v-ripple class="btn btn-primary mt-8 w-full justify-center py-3 text-[15px]" @click="next">
            {{ t('welcome.continue') }}
          </button>
        </div>

        <!-- Step 2: Upload -->
        <div v-else-if="step === 2" key="step2">
          <h1 class="mb-2 text-center text-[20px] font-extrabold tracking-tight text-[--t1]">
            {{ t('welcome.uploadTitle') }}
          </h1>
          <p class="mb-6 text-center text-[13px] text-[--t3]">MP3, M4B, ZIP</p>

          <!-- Drop zone -->
          <div
            class="relative flex min-h-[160px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 transition-all duration-200"
            :class="dragOver ? 'border-[--accent] bg-[--accent-soft]' : 'border-[--border] bg-white/[0.02]'"
            @dragover.prevent="dragOver = true"
            @dragleave="dragOver = false"
            @drop.prevent="handleDrop"
            @click="($refs.fileInput as HTMLInputElement)?.click()"
          >
            <input
              ref="fileInput"
              type="file"
              accept=".mp3,.m4a,.m4b,.ogg,.opus,.flac,.wav,.zip"
              multiple
              hidden
              @change="handleFileInput"
            />
            <div class="text-[32px]">{{ dragOver ? '📂' : '📁' }}</div>
            <p class="mt-3 text-[13px] font-medium text-[--t2]">{{ t('welcome.dropHere') }}</p>
            <p class="mt-1 text-[11px] text-[--t3]">{{ t('welcome.orClick') }}</p>
          </div>

          <!-- File list -->
          <div v-if="files.length" class="mt-4 max-h-[200px] space-y-1.5 overflow-y-auto">
            <div
              v-for="(f, i) in files"
              :key="f.name"
              class="stagger-item flex items-center gap-2 rounded-lg px-3 py-2 text-[12px]"
              style="background: var(--card)"
              :style="{ animationDelay: `${i * 40}ms` }"
            >
              <span class="text-[14px]">🎵</span>
              <span class="min-w-0 flex-1 truncate text-[--t2]">{{ f.name }}</span>
              <span class="shrink-0 text-[--t3]">{{ fmtSize(f.size) }}</span>
              <button class="shrink-0 text-[--t3] hover:text-red-400" @click.stop="removeFile(i)">✕</button>
            </div>
          </div>

          <p v-if="files.length" class="mt-2 text-center text-[11px] text-[--t3]">
            {{ files.length }} {{ t('welcome.filesSelected') }}
          </p>

          <button v-ripple class="btn btn-primary mt-6 w-full justify-center py-3 text-[15px]" @click="next">
            {{ t('welcome.continue') }}
          </button>
          <button class="mt-2 w-full py-2 text-center text-[12px] text-[--t3] hover:text-[--t2]" @click="next">
            {{ t('welcome.skip') }}
          </button>
        </div>

        <!-- Step 3: Done -->
        <div v-else key="step3" class="text-center">
          <div
            class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-2xl text-[40px]"
            style="background: var(--accent-soft)"
          >
            ✨
          </div>
          <h1 class="text-[22px] font-extrabold tracking-tight text-[--t1]">{{ t('welcome.doneTitle') }}</h1>
          <p class="mt-3 text-[14px] leading-relaxed text-[--t2]">{{ t('welcome.doneSubtitle') }}</p>
          <p v-if="files.length" class="mt-2 text-[13px] text-[--accent]">
            {{ t('welcome.filesReady', { n: files.length }) }}
          </p>
          <button
            v-ripple
            class="btn btn-primary mt-8 w-full justify-center py-3 text-[15px]"
            :disabled="uploading"
            @click="finish"
          >
            {{ uploading ? t('welcome.uploading') : t('welcome.start') }}
          </button>
        </div>
      </transition>
    </div>
  </div>
</template>
