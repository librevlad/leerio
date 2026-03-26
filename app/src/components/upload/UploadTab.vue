<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { useTracking } from '@/composables/useTelemetry'
import { usePlayer } from '@/composables/usePlayer'
import { api } from '@/api'
import ProgressBar from '@/components/shared/ProgressBar.vue'
import PaywallModal from '@/components/shared/PaywallModal.vue'
import { IconUpload, IconMusic, IconX, IconCheck } from '@/components/shared/icons'

const router = useRouter()
const { track } = useTracking()
const player = usePlayer()
const toast = useToast()
const { t } = useI18n()

// ── Upload state ──
const touched = ref(false)
const uploadTitle = ref('')
const uploadAuthor = ref('')
const uploadReader = ref('')
const uploadFiles = ref<File[]>([])
const uploadCover = ref<File | null>(null)
const uploading = ref(false)
const uploadProgress = ref(0)
const dragOver = ref(false)
const showPaywall = ref(false)

const AUDIO_EXTS = /\.(mp3|m4a|m4b|ogg|opus|flac|wav)$/i

function addAudioFiles(files: FileList | File[]) {
  for (const f of files) {
    if (AUDIO_EXTS.test(f.name) && !uploadFiles.value.some((x) => x.name === f.name)) {
      uploadFiles.value.push(f)
    }
  }
  // Auto-fill title from first file if empty
  if (!uploadTitle.value && uploadFiles.value.length > 0) {
    const name = uploadFiles.value[0]!.name.replace(/\.[^.]+$/, '')
    // Try "Author - Title" pattern
    if (name.includes(' - ')) {
      const parts = name.split(' - ')
      uploadAuthor.value = parts[0]?.trim() ?? ''
      uploadTitle.value = parts.slice(1).join(' - ').trim()
    } else {
      uploadTitle.value = name
    }
  }
}

function onFilesChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) addAudioFiles(input.files)
  input.value = ''
}

function onDrop(e: DragEvent) {
  dragOver.value = false
  if (!e.dataTransfer?.files) return
  addAudioFiles(e.dataTransfer.files)
}

function onCoverChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.[0]) {
    uploadCover.value = input.files[0]
  }
}

function removeFile(index: number) {
  uploadFiles.value.splice(index, 1)
}

async function handleUpload() {
  if (!uploadTitle.value.trim()) {
    toast.error(t('upload.errTitleRequired'))
    return
  }
  if (uploadFiles.value.length === 0) {
    toast.error(t('upload.errFilesRequired'))
    return
  }

  uploading.value = true
  uploadProgress.value = 0
  track('upload_started', { files: uploadFiles.value.length })

  try {
    const formData = new FormData()
    formData.append('title', uploadTitle.value.trim())
    formData.append('author', uploadAuthor.value.trim())
    formData.append('reader', uploadReader.value.trim())
    for (const f of uploadFiles.value) {
      formData.append('files', f)
    }
    if (uploadCover.value) {
      formData.append('cover', uploadCover.value)
    }

    // Upload with progress tracking
    const uploadResult = await new Promise<{ id: string; slug: string }>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/user/books')
      xhr.withCredentials = true
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) uploadProgress.value = Math.round((e.loaded / e.total) * 100)
      }
      xhr.onload = () => {
        if (xhr.status === 403) reject(new Error('limit_reached'))
        else if (xhr.status >= 400) reject(new Error(xhr.responseText))
        else {
          try {
            resolve(JSON.parse(xhr.responseText))
          } catch {
            resolve({ id: '', slug: '' })
          }
        }
      }
      xhr.onerror = () => reject(new Error('Network error'))
      xhr.send(formData)
    })

    track('upload_completed', { files: uploadFiles.value.length })
    toast.success(t('upload.successUploaded'))

    // Autoplay: load the uploaded book and start playing immediately
    if (uploadResult.id) {
      try {
        const book = await api.getBook(uploadResult.id)
        await player.loadBook(book, undefined, true)
        router.push(`/book/${uploadResult.id}`)
      } catch {
        router.push('/my-library')
      }
    } else {
      router.push('/my-library')
    }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : ''
    track('upload_failed', { reason: msg || 'unknown' })
    if (msg.includes('limit_reached') || msg.includes('403')) {
      showPaywall.value = true
    } else {
      toast.error(t('common.errorPrefix', { msg: msg || t('common.unknownError') }))
    }
  } finally {
    uploading.value = false
    uploadProgress.value = 0
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
          v-model="uploadTitle"
          type="text"
          :placeholder="t('upload.placeholderTitle')"
          class="input-field w-full px-3.5 py-2.5"
          :class="{ 'border-red-400/50': touched && !uploadTitle.trim() }"
          @blur="touched = true"
        />
        <p v-if="touched && !uploadTitle.trim()" class="mt-1 text-[11px] text-red-400">
          {{ t('upload.titleRequired') }}
        </p>
      </div>

      <!-- Author -->
      <div>
        <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">{{ t('upload.labelAuthor') }}</label>
        <input
          v-model="uploadAuthor"
          type="text"
          :placeholder="t('upload.placeholderAuthor')"
          class="input-field w-full px-3.5 py-2.5"
        />
      </div>

      <!-- Reader -->
      <div>
        <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">{{ t('upload.labelReader') }}</label>
        <input
          v-model="uploadReader"
          type="text"
          :placeholder="t('upload.placeholderReader')"
          class="input-field w-full px-3.5 py-2.5"
        />
      </div>
    </div>

    <!-- MP3 Files -->
    <div class="card px-5 py-5">
      <label class="mb-3 block text-[12px] font-semibold text-[--t2]">{{ t('upload.labelMp3') }}</label>
      <div
        class="rounded-xl border-2 border-dashed p-8 text-center transition-all duration-200"
        :class="
          dragOver
            ? 'border-[--accent] bg-[--accent-soft]'
            : 'border-[--border] hover:border-white/15 hover:bg-white/[0.02]'
        "
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="onDrop"
      >
        <div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.06]">
          <IconMusic :size="24" class="text-[--t2]" />
        </div>
        <p class="mb-1 text-[13px] font-medium text-[--t2]">{{ t('upload.dragDrop') }}</p>
        <p class="mb-3 text-[12px] text-[--t3]">{{ t('upload.orSelect') }}</p>
        <label
          class="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-[--accent-soft] px-4 py-2 text-[12px] font-medium text-[--accent] transition-all hover:bg-[--accent]/20"
        >
          <IconUpload :size="14" />
          {{ t('upload.selectFiles') }}
          <input
            type="file"
            accept=".mp3,.m4a,.m4b,.ogg,.opus,.flac,.wav"
            multiple
            class="hidden"
            @change="onFilesChange"
          />
        </label>
        <p class="mt-2 text-[11px] text-[--t3]">MP3, M4A, M4B, OGG, FLAC, WAV</p>
      </div>

      <!-- File list -->
      <div v-if="uploadFiles.length" class="mt-4 space-y-1.5">
        <div class="mb-2 text-[11px] font-semibold text-[--t3]">
          {{ uploadFiles.length }} {{ t('plural.file', uploadFiles.length) }}
        </div>
        <div
          v-for="(file, i) in uploadFiles"
          :key="i"
          class="flex items-center justify-between rounded-xl bg-white/[0.03] px-3.5 py-2.5"
        >
          <div class="flex min-w-0 items-center gap-2.5">
            <IconMusic :size="14" class="flex-shrink-0 text-[--t3]" />
            <span class="truncate text-[12px] text-[--t2]">{{ file.name }}</span>
            <span class="flex-shrink-0 text-[11px] text-[--t3]"
              >{{ (file.size / 1024 / 1024).toFixed(1) }} {{ t('upload.mb') }}</span
            >
          </div>
          <button
            class="flex-shrink-0 rounded-full p-1 text-[--t3] transition-all hover:bg-red-500/15 hover:text-red-400"
            :aria-label="t('upload.deleteFileAria')"
            @click="removeFile(i)"
          >
            <IconX :size="14" />
          </button>
        </div>
      </div>
    </div>

    <!-- Cover -->
    <div class="card px-5 py-5">
      <label class="mb-3 block text-[12px] font-semibold text-[--t2]">{{ t('upload.labelCover') }}</label>
      <label
        class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-[--border] px-4 py-3 text-[12px] text-[--t3] transition-all hover:border-white/15 hover:bg-white/[0.02]"
      >
        <IconUpload :size="14" />
        {{ uploadCover ? uploadCover.name : t('upload.selectImage') }}
        <input type="file" accept="image/*" class="hidden" @change="onCoverChange" />
      </label>
      <div v-if="uploadCover" class="mt-2 flex items-center gap-1.5 text-[11px] text-emerald-400">
        <IconCheck :size="12" />
        {{ t('upload.coverSelected') }}
      </div>
    </div>

    <!-- Upload button -->
    <button
      class="btn btn-primary w-full justify-center text-[14px]"
      :disabled="uploading || !uploadTitle.trim() || uploadFiles.length === 0"
      @click="handleUpload"
    >
      <IconUpload v-if="!uploading" :size="16" />
      <span v-if="uploading && uploadProgress > 0">{{ uploadProgress }}%</span>
      <span v-else-if="uploading">{{ t('upload.uploadingIndeterminate') }}</span>
      <span v-else>{{ t('upload.uploadBtn') }}</span>
    </button>
    <ProgressBar v-if="uploading" :percent="uploadProgress" height="h-1" class="mt-2" />

    <PaywallModal :open="showPaywall" @close="showPaywall = false" />
  </div>
</template>
