<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Capacitor } from '@capacitor/core'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import { useToast } from '../composables/useToast'
import { useTracking } from '../composables/useTelemetry'
import { useLocalBooks } from '../composables/useLocalBooks'
import { useAuth } from '../composables/useAuth'
import { formatSize } from '../utils/format'
import { STORAGE } from '../constants/storage'

const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const { track } = useTracking()
const { addLocalBook } = useLocalBooks()
const { isLoggedIn } = useAuth()

onMounted(() => track('onboarding_started'))

const isNative = Capacitor.isNativePlatform()

const step = ref(1)
const files = ref<File[]>([])
const uploading = ref(false)

function next() {
  if (step.value < 3) step.value++
}

function prev() {
  if (step.value > 1) step.value--
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

function pickFolder() {
  const input = document.createElement('input')
  input.type = 'file'
  input.setAttribute('webkitdirectory', '')
  input.setAttribute('directory', '')
  input.multiple = true
  input.accept = '.mp3,.m4a,.m4b,.ogg,.opus,.flac,.wav'
  input.onchange = () => {
    if (input.files) addFiles(input.files)
  }
  input.click()
}

function fmtSize(bytes: number): string {
  return formatSize(bytes, t)
}

async function finish() {
  track('onboarding_completed', { files: files.value.length })
  localStorage.setItem(STORAGE.ONBOARDED, '1')

  // If files were added, upload or save locally
  if (files.value.length > 0) {
    uploading.value = true
    try {
      if (isLoggedIn.value) {
        // Upload to server for logged-in users
        let uploaded = 0
        for (const file of files.value) {
          try {
            const formData = new FormData()
            formData.append('files', file)
            formData.append('title', file.name.replace(/\.[^.]+$/, ''))
            formData.append('author', '')
            await api.uploadBook(formData)
            uploaded++
          } catch {
            break
          }
        }
        if (uploaded > 0) {
          toast.success(t('welcome.uploadSuccess', { n: uploaded }))
        } else {
          toast.error(t('welcome.uploadFailed'))
        }
      } else {
        // Save locally for guests
        const title = files.value[0]?.name.replace(/\.[^.]+$/, '') ?? 'Audiobook'
        await addLocalBook(files.value, { title, author: '' })
        toast.success(t('upload.successLocal'))
      }
    } finally {
      uploading.value = false
    }
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

        <!-- Step 2: Add books -->
        <div v-else-if="step === 2" key="step2">
          <h1 class="font-display mb-1 text-center text-[20px] font-extrabold tracking-tight text-[--t1]">
            {{ t('welcome.addBooksTitle') }}
          </h1>
          <p class="mb-6 text-center text-[13px] text-[--t3]">{{ t('welcome.addBooksSubtitle') }}</p>

          <!-- Scan device (APK only) -->
          <button
            v-if="isNative"
            v-ripple
            class="mb-2.5 flex w-full items-center gap-3 rounded-xl px-4 py-3.5 text-left text-white"
            style="background: var(--gradient-accent)"
            @click="$router.push('/scan-results')"
          >
            <span class="text-[22px]">📱</span>
            <div>
              <div class="text-[14px] font-semibold">{{ t('welcome.scanDevice') }}</div>
              <div class="mt-0.5 text-[11px] opacity-80">{{ t('welcome.scanDeviceHint') }}</div>
            </div>
          </button>

          <!-- Choose files -->
          <button
            v-ripple
            class="mb-2.5 flex w-full items-center gap-3 rounded-xl border px-4 py-3.5 text-left"
            :class="isNative ? 'border-white/[0.08] bg-white/[0.05]' : ''"
            :style="!isNative ? 'background: var(--gradient-accent); color: white' : ''"
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
            <span class="text-[22px]">📄</span>
            <div>
              <div class="text-[14px] font-semibold" :class="isNative ? 'text-[--t1]' : ''">
                {{ t('welcome.chooseFiles') }}
              </div>
              <div class="mt-0.5 text-[11px]" :class="isNative ? 'text-[--t3]' : 'opacity-80'">
                MP3, M4A, M4B, OGG, FLAC, ZIP
              </div>
            </div>
          </button>

          <!-- Choose folder (web only — webkitdirectory not supported in APK WebView) -->
          <button
            v-if="!isNative"
            v-ripple
            class="mb-4 flex w-full items-center gap-3 rounded-xl border border-white/[0.08] bg-white/[0.05] px-4 py-3.5 text-left"
            @click="pickFolder"
          >
            <span class="text-[22px]">📂</span>
            <div>
              <div class="text-[14px] font-semibold text-[--t1]">{{ t('welcome.chooseFolder') }}</div>
              <div class="mt-0.5 text-[11px] text-[--t3]">{{ t('welcome.chooseFolderHint') }}</div>
            </div>
          </button>

          <!-- File list (if files selected) -->
          <div v-if="files.length" class="mb-4 max-h-[160px] space-y-1.5 overflow-y-auto">
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

          <button
            v-if="files.length"
            v-ripple
            class="btn btn-primary mt-2 w-full justify-center py-3 text-[15px]"
            @click="next"
          >
            {{ t('welcome.continue') }}
          </button>

          <div class="mt-3 flex justify-center gap-4">
            <button class="py-2 text-[12px] text-[--t3] hover:text-[--t2]" @click="prev">
              {{ t('common.back') }}
            </button>
            <button class="py-2 text-[12px] text-[--t3] hover:text-[--t2]" @click="next">
              {{ t('welcome.skip') }} →
            </button>
          </div>
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
          <button class="mt-2 w-full py-2 text-center text-[12px] text-[--t3] hover:text-[--t2]" @click="prev">
            {{ t('common.back') }}
          </button>
        </div>
      </transition>
    </div>
  </div>
</template>
