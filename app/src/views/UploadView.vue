<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useUserBooks } from '@/composables/useUserBooks'
import { useLocalBooks } from '@/composables/useLocalBooks'
import { useNetwork } from '@/composables/useNetwork'
import { IconUpload, IconMicrophone, IconMusic, IconX, IconSmartphone } from '@/components/shared/icons'
import type { TTSVoice } from '@/types'

const router = useRouter()
const toast = useToast()
const { pollJob } = useUserBooks()
const { addLocalBook } = useLocalBooks()
const { isOnline } = useNetwork()

// Tab
const activeTab = ref<'upload' | 'tts' | 'local'>('upload')

// ── Upload state ──
const uploadTitle = ref('')
const uploadAuthor = ref('')
const uploadReader = ref('')
const uploadFiles = ref<File[]>([])
const uploadCover = ref<File | null>(null)
const uploading = ref(false)
const uploadProgress = ref(0)

function onFilesChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) {
    uploadFiles.value = [...uploadFiles.value, ...Array.from(input.files)]
  }
  input.value = ''
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
    toast.error('Укажите название книги')
    return
  }
  if (uploadFiles.value.length === 0) {
    toast.error('Добавьте MP3 файлы')
    return
  }

  uploading.value = true
  uploadProgress.value = 0

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

    await api.uploadBook(formData)
    toast.success('Книга загружена!')
    router.push('/my-library')
  } catch (e: unknown) {
    toast.error(`Ошибка: ${e instanceof Error ? e.message : 'Неизвестная ошибка'}`)
  } finally {
    uploading.value = false
  }
}

// ── TTS state ──
const ttsTitle = ref('')
const ttsAuthor = ref('')
const ttsFile = ref<File | null>(null)
const ttsVoice = ref('ru-RU-DmitryNeural')
const ttsRate = ref('+0%')
const voices = ref<TTSVoice[]>([])
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

onMounted(async () => {
  try {
    voices.value = await api.getTTSVoices()
  } catch {
    /* voices will remain empty */
  }
})

function onTTSFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.[0]) {
    ttsFile.value = input.files[0]
  }
}

// ── Local book state ──
const localTitle = ref('')
const localAuthor = ref('')
const localFiles = ref<File[]>([])
const localCover = ref<string | undefined>()
const addingLocal = ref(false)

function onLocalFilesChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) {
    const newFiles = Array.from(input.files)
    localFiles.value = [...localFiles.value, ...newFiles]
    // Auto-fill title from first file name if empty
    if (!localTitle.value && newFiles[0]) {
      const name = newFiles[0].name.replace(/\.\w+$/, '')
      // Try to extract "Author - Title" pattern
      const match = name.match(/^(.+?)\s*-\s*(.+)$/)
      if (match?.[1] && match[2]) {
        localAuthor.value = match[1].trim()
        localTitle.value = match[2].trim()
      } else {
        localTitle.value = name
      }
    }
  }
  input.value = ''
}

function removeLocalFile(index: number) {
  localFiles.value.splice(index, 1)
}

function onLocalCoverChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    localCover.value = reader.result as string
  }
  reader.readAsDataURL(file)
}

async function handleAddLocal() {
  if (!localTitle.value.trim()) {
    toast.error('Укажите название книги')
    return
  }
  if (localFiles.value.length === 0) {
    toast.error('Добавьте MP3 файлы')
    return
  }

  addingLocal.value = true
  try {
    await addLocalBook(localFiles.value, {
      title: localTitle.value.trim(),
      author: localAuthor.value.trim(),
      coverDataUrl: localCover.value,
    })
    toast.success('Книга добавлена на устройство!')
    router.push('/my-library')
  } catch (e: unknown) {
    toast.error(`Ошибка: ${e instanceof Error ? e.message : 'Неизвестная ошибка'}`)
  } finally {
    addingLocal.value = false
  }
}

async function handleTTSConvert() {
  if (!ttsTitle.value.trim()) {
    toast.error('Укажите название')
    return
  }
  if (!ttsFile.value) {
    toast.error('Выберите файл')
    return
  }

  converting.value = true
  try {
    const formData = new FormData()
    formData.append('title', ttsTitle.value.trim())
    formData.append('author', ttsAuthor.value.trim())
    formData.append('voice', ttsVoice.value)
    formData.append('rate', ttsRate.value)
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
        toast.success('Аудиокнига создана!')
        converting.value = false
      } else if (j.status === 'error') {
        toast.error(`Ошибка: ${j.error || 'Неизвестная ошибка'}`)
        converting.value = false
      }
    })
  } catch (e: unknown) {
    toast.error(`Ошибка: ${e instanceof Error ? e.message : 'Неизвестная ошибка'}`)
    converting.value = false
  }
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-[20px] font-bold text-[--t1]">Загрузить</h1>
      <p class="mt-1 text-[13px] text-[--t3]">Загрузите MP3 или создайте аудиокнигу из документа</p>
    </div>

    <!-- Tabs -->
    <div class="mb-6 flex gap-2">
      <button
        class="flex items-center gap-2 rounded-full border px-4 py-2 text-[13px] font-medium transition-all"
        :class="
          activeTab === 'upload'
            ? 'border-teal-500/40 bg-teal-500/15 text-teal-300'
            : 'border-[--border] text-[--t3] hover:border-[--t3] hover:text-[--t2]'
        "
        @click="activeTab = 'upload'"
      >
        <IconUpload :size="16" />
        Загрузить MP3
      </button>
      <button
        class="flex items-center gap-2 rounded-full border px-4 py-2 text-[13px] font-medium transition-all"
        :class="
          activeTab === 'tts'
            ? 'border-violet-500/40 bg-violet-500/15 text-violet-300'
            : 'border-[--border] text-[--t3] hover:border-[--t3] hover:text-[--t2]'
        "
        @click="activeTab = 'tts'"
      >
        <IconMicrophone :size="16" />
        Озвучить документ
      </button>
      <button
        class="flex items-center gap-2 rounded-full border px-4 py-2 text-[13px] font-medium transition-all"
        :class="
          activeTab === 'local'
            ? 'border-indigo-500/40 bg-indigo-500/15 text-indigo-300'
            : 'border-[--border] text-[--t3] hover:border-[--t3] hover:text-[--t2]'
        "
        @click="activeTab = 'local'"
      >
        <IconSmartphone :size="16" />
        С устройства
      </button>
    </div>

    <!-- Upload MP3 Tab -->
    <div v-if="activeTab === 'upload'" class="max-w-xl space-y-4">
      <!-- Title -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">Название *</label>
        <input
          v-model="uploadTitle"
          type="text"
          placeholder="Война и Мир"
          class="w-full rounded-lg border border-[--border] bg-transparent px-3 py-2 text-[13px] text-[--t1] transition-all outline-none focus:border-teal-500/50"
        />
      </div>

      <!-- Author -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">Автор</label>
        <input
          v-model="uploadAuthor"
          type="text"
          placeholder="Лев Толстой"
          class="w-full rounded-lg border border-[--border] bg-transparent px-3 py-2 text-[13px] text-[--t1] transition-all outline-none focus:border-teal-500/50"
        />
      </div>

      <!-- Reader -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">Чтец</label>
        <input
          v-model="uploadReader"
          type="text"
          placeholder="Иван Козий"
          class="w-full rounded-lg border border-[--border] bg-transparent px-3 py-2 text-[13px] text-[--t1] transition-all outline-none focus:border-teal-500/50"
        />
      </div>

      <!-- MP3 Files -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">MP3 файлы *</label>
        <div
          class="rounded-lg border-2 border-dashed border-[--border] p-6 text-center transition-all hover:border-teal-500/30"
        >
          <IconMusic :size="32" class="mx-auto mb-2 text-[--t3]" />
          <p class="text-[13px] text-[--t3]">Перетащите MP3 файлы сюда</p>
          <label
            class="mt-2 inline-block cursor-pointer rounded-lg bg-teal-500/15 px-4 py-2 text-[12px] font-medium text-teal-300 transition-all hover:bg-teal-500/25"
          >
            Выбрать файлы
            <input type="file" accept=".mp3" multiple class="hidden" @change="onFilesChange" />
          </label>
        </div>

        <!-- File list -->
        <div v-if="uploadFiles.length" class="mt-3 space-y-1">
          <div
            v-for="(file, i) in uploadFiles"
            :key="i"
            class="flex items-center justify-between rounded-lg border border-[--border] px-3 py-2"
          >
            <div class="flex items-center gap-2 text-[12px] text-[--t2]">
              <IconMusic :size="14" class="text-teal-400" />
              {{ file.name }}
              <span class="text-[--t3]">({{ (file.size / 1024 / 1024).toFixed(1) }} МБ)</span>
            </div>
            <button class="text-[--t3] transition-all hover:text-red-400" @click="removeFile(i)">
              <IconX :size="14" />
            </button>
          </div>
        </div>
      </div>

      <!-- Cover -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">Обложка (опционально)</label>
        <label
          class="inline-block cursor-pointer rounded-lg border border-[--border] px-4 py-2 text-[12px] text-[--t3] transition-all hover:border-teal-500/30"
        >
          {{ uploadCover ? uploadCover.name : 'Выбрать изображение' }}
          <input type="file" accept="image/*" class="hidden" @change="onCoverChange" />
        </label>
      </div>

      <!-- Upload button -->
      <button
        class="w-full rounded-lg bg-teal-500 px-4 py-3 text-[14px] font-semibold text-white transition-all hover:bg-teal-600 disabled:opacity-50"
        :disabled="uploading || !uploadTitle.trim() || uploadFiles.length === 0"
        @click="handleUpload"
      >
        <span v-if="uploading">Загрузка... {{ uploadProgress }}%</span>
        <span v-else>Загрузить</span>
      </button>
    </div>

    <!-- TTS Tab -->
    <div v-if="activeTab === 'tts'" class="max-w-xl space-y-4">
      <!-- Title -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">Название *</label>
        <input
          v-model="ttsTitle"
          type="text"
          placeholder="Название книги"
          class="w-full rounded-lg border border-[--border] bg-transparent px-3 py-2 text-[13px] text-[--t1] transition-all outline-none focus:border-violet-500/50"
        />
      </div>

      <!-- Author -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">Автор</label>
        <input
          v-model="ttsAuthor"
          type="text"
          placeholder="Автор"
          class="w-full rounded-lg border border-[--border] bg-transparent px-3 py-2 text-[13px] text-[--t1] transition-all outline-none focus:border-violet-500/50"
        />
      </div>

      <!-- Document file -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">Документ (PDF, EPUB, TXT, FB2) *</label>
        <label
          class="inline-block cursor-pointer rounded-lg border border-dashed border-[--border] px-4 py-3 text-[13px] text-[--t3] transition-all hover:border-violet-500/30"
        >
          {{ ttsFile ? ttsFile.name : 'Выбрать файл' }}
          <input type="file" accept=".pdf,.epub,.txt,.fb2" class="hidden" @change="onTTSFileChange" />
        </label>
      </div>

      <!-- Voice selection -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">Голос</label>
        <select
          v-model="ttsVoice"
          class="w-full rounded-lg border border-[--border] bg-transparent px-3 py-2 text-[13px] text-[--t1] outline-none"
        >
          <option v-for="v in voices" :key="v.id" :value="v.id">
            {{ v.name }} ({{ v.lang }}, {{ v.gender === 'male' ? 'муж.' : 'жен.' }})
          </option>
        </select>
      </div>

      <!-- Rate -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">Скорость</label>
        <div class="flex gap-2">
          <button
            v-for="opt in rateOptions"
            :key="opt.value"
            class="rounded-full border px-3 py-1.5 text-[12px] font-medium transition-all"
            :class="
              ttsRate === opt.value
                ? 'border-violet-500/40 bg-violet-500/15 text-violet-300'
                : 'border-[--border] text-[--t3] hover:text-[--t2]'
            "
            @click="ttsRate = opt.value"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>

      <!-- Convert button -->
      <button
        class="w-full rounded-lg bg-violet-500 px-4 py-3 text-[14px] font-semibold text-white transition-all hover:bg-violet-600 disabled:opacity-50"
        :disabled="converting || !ttsTitle.trim() || !ttsFile"
        @click="handleTTSConvert"
      >
        <span v-if="converting && !conversionStarted">Загрузка...</span>
        <span v-else>Создать аудиокнигу</span>
      </button>

      <!-- Conversion progress -->
      <div
        v-if="conversionStarted"
        class="rounded-xl border border-[--border] p-4"
        :class="
          jobStatus === 'done'
            ? 'border-emerald-500/30 bg-emerald-500/5'
            : jobStatus === 'error'
              ? 'border-red-500/30 bg-red-500/5'
              : 'border-violet-500/30 bg-violet-500/5'
        "
      >
        <div class="mb-2 flex items-center justify-between">
          <span class="text-[13px] font-medium text-[--t1]">
            {{ jobStatus === 'done' ? 'Готово!' : jobStatus === 'error' ? 'Ошибка' : 'Конвертация...' }}
          </span>
          <span class="text-[12px] text-[--t3]">{{ jobProgress }}%</span>
        </div>
        <div class="h-2 overflow-hidden rounded-full bg-white/10">
          <div
            class="h-full rounded-full transition-all duration-300"
            :class="jobStatus === 'done' ? 'bg-emerald-500' : jobStatus === 'error' ? 'bg-red-500' : 'bg-violet-500'"
            :style="{ width: `${jobProgress}%` }"
          />
        </div>
        <router-link
          v-if="jobStatus === 'done'"
          to="/my-library"
          class="mt-3 inline-block text-[12px] font-medium text-emerald-400 hover:underline"
        >
          Перейти к моим книгам
        </router-link>
      </div>
    </div>

    <!-- Local Book Tab -->
    <div v-if="activeTab === 'local'" class="max-w-xl space-y-4">
      <div class="rounded-lg border border-indigo-500/20 bg-indigo-500/5 px-4 py-3 text-[12px] text-indigo-300">
        <IconSmartphone :size="14" class="mr-1 inline" />
        Книга будет доступна только на этом устройстве и не синхронизируется
      </div>

      <!-- Title -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">Название *</label>
        <input
          v-model="localTitle"
          type="text"
          placeholder="Название книги"
          class="w-full rounded-lg border border-[--border] bg-transparent px-3 py-2 text-[13px] text-[--t1] transition-all outline-none focus:border-indigo-500/50"
        />
      </div>

      <!-- Author -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">Автор</label>
        <input
          v-model="localAuthor"
          type="text"
          placeholder="Автор"
          class="w-full rounded-lg border border-[--border] bg-transparent px-3 py-2 text-[13px] text-[--t1] transition-all outline-none focus:border-indigo-500/50"
        />
      </div>

      <!-- MP3 Files -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">MP3 файлы *</label>
        <div
          class="rounded-lg border-2 border-dashed border-[--border] p-6 text-center transition-all hover:border-indigo-500/30"
        >
          <IconMusic :size="32" class="mx-auto mb-2 text-[--t3]" />
          <p class="text-[13px] text-[--t3]">Выберите MP3 файлы с устройства</p>
          <label
            class="mt-2 inline-block cursor-pointer rounded-lg bg-indigo-500/15 px-4 py-2 text-[12px] font-medium text-indigo-300 transition-all hover:bg-indigo-500/25"
          >
            Выбрать файлы
            <input type="file" accept=".mp3,audio/*" multiple class="hidden" @change="onLocalFilesChange" />
          </label>
        </div>

        <!-- File list -->
        <div v-if="localFiles.length" class="mt-3 space-y-1">
          <div
            v-for="(file, i) in localFiles"
            :key="i"
            class="flex items-center justify-between rounded-lg border border-[--border] px-3 py-2"
          >
            <div class="flex items-center gap-2 text-[12px] text-[--t2]">
              <IconMusic :size="14" class="text-indigo-400" />
              {{ file.name }}
              <span class="text-[--t3]">({{ (file.size / 1024 / 1024).toFixed(1) }} МБ)</span>
            </div>
            <button class="text-[--t3] transition-all hover:text-red-400" @click="removeLocalFile(i)">
              <IconX :size="14" />
            </button>
          </div>
        </div>
      </div>

      <!-- Cover -->
      <div>
        <label class="mb-1 block text-[12px] font-medium text-[--t2]">Обложка (опционально)</label>
        <label
          class="inline-block cursor-pointer rounded-lg border border-[--border] px-4 py-2 text-[12px] text-[--t3] transition-all hover:border-indigo-500/30"
        >
          {{ localCover ? 'Обложка выбрана' : 'Выбрать изображение' }}
          <input type="file" accept="image/*" class="hidden" @change="onLocalCoverChange" />
        </label>
      </div>

      <!-- Add button -->
      <button
        class="w-full rounded-lg bg-indigo-500 px-4 py-3 text-[14px] font-semibold text-white transition-all hover:bg-indigo-600 disabled:opacity-50"
        :disabled="addingLocal || !localTitle.trim() || localFiles.length === 0"
        @click="handleAddLocal"
      >
        <span v-if="addingLocal">Добавление...</span>
        <span v-else>Добавить на устройство</span>
      </button>
    </div>

    <!-- Offline notice for upload/tts tabs -->
    <div
      v-if="!isOnline && (activeTab === 'upload' || activeTab === 'tts')"
      class="mt-4 max-w-xl rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-[13px] text-amber-300"
    >
      Загрузка и TTS доступны только онлайн
    </div>
  </div>
</template>
