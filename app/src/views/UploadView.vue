<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useUserBooks } from '@/composables/useUserBooks'
import { useLocalBooks } from '@/composables/useLocalBooks'
import { useNetwork } from '@/composables/useNetwork'
import ProgressBar from '@/components/shared/ProgressBar.vue'
import { IconUpload, IconMicrophone, IconMusic, IconX, IconSmartphone, IconCheck } from '@/components/shared/icons'
import type { TTSVoice, TTSEngine } from '@/types'
import { plural } from '@/utils/plural'

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

const tabDefs = [
  { key: 'upload' as const, label: 'Загрузить MP3', icon: IconUpload },
  { key: 'tts' as const, label: 'Озвучить документ', icon: IconMicrophone },
  { key: 'local' as const, label: 'С устройства', icon: IconSmartphone },
]
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6">
      <h1 class="page-title">Загрузить</h1>
      <p class="mt-1 text-[13px] text-[--t3]">Загрузите MP3 или создайте аудиокнигу из документа</p>
    </div>

    <!-- Tabs -->
    <div class="scrollbar-hide mb-6 flex gap-2 overflow-x-auto">
      <button
        v-for="tab in tabDefs"
        :key="tab.key"
        class="flex flex-shrink-0 cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 text-[13px] font-medium transition-colors"
        :class="
          activeTab === tab.key
            ? 'border-white/10 bg-white/[0.08] text-[--t1]'
            : 'border-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="activeTab = tab.key"
      >
        <component :is="tab.icon" :size="16" />
        {{ tab.label }}
      </button>
    </div>

    <!-- Upload MP3 Tab -->
    <div v-if="activeTab === 'upload'" class="max-w-xl space-y-5">
      <div class="card space-y-4 px-5 py-5">
        <!-- Title -->
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">Название *</label>
          <input v-model="uploadTitle" type="text" placeholder="Война и Мир" class="input-field w-full px-3.5 py-2.5" />
        </div>

        <!-- Author -->
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">Автор</label>
          <input
            v-model="uploadAuthor"
            type="text"
            placeholder="Лев Толстой"
            class="input-field w-full px-3.5 py-2.5"
          />
        </div>

        <!-- Reader -->
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">Чтец</label>
          <input v-model="uploadReader" type="text" placeholder="Иван Козий" class="input-field w-full px-3.5 py-2.5" />
        </div>
      </div>

      <!-- MP3 Files -->
      <div class="card px-5 py-5">
        <label class="mb-3 block text-[12px] font-semibold text-[--t2]">MP3 файлы *</label>
        <div
          class="rounded-xl border-2 border-dashed border-[--border] p-8 text-center transition-all hover:border-white/15 hover:bg-white/[0.02]"
        >
          <div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.06]">
            <IconMusic :size="24" class="text-[--t2]" />
          </div>
          <p class="mb-1 text-[13px] font-medium text-[--t2]">Перетащите MP3 файлы сюда</p>
          <p class="mb-3 text-[12px] text-[--t3]">или выберите с устройства</p>
          <label
            class="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-[--accent-soft] px-4 py-2 text-[12px] font-medium text-[--accent] transition-all hover:bg-[--accent]/20"
          >
            <IconUpload :size="14" />
            Выбрать файлы
            <input type="file" accept=".mp3" multiple class="hidden" @change="onFilesChange" />
          </label>
        </div>

        <!-- File list -->
        <div v-if="uploadFiles.length" class="mt-4 space-y-1.5">
          <div class="mb-2 text-[11px] font-semibold text-[--t3]">
            {{ uploadFiles.length }} {{ plural(uploadFiles.length, 'файл', 'файла', 'файлов') }}
          </div>
          <div
            v-for="(file, i) in uploadFiles"
            :key="i"
            class="flex items-center justify-between rounded-xl bg-white/[0.03] px-3.5 py-2.5"
          >
            <div class="flex min-w-0 items-center gap-2.5">
              <IconMusic :size="14" class="flex-shrink-0 text-[--t3]" />
              <span class="truncate text-[12px] text-[--t2]">{{ file.name }}</span>
              <span class="flex-shrink-0 text-[11px] text-[--t3]">{{ (file.size / 1024 / 1024).toFixed(1) }} МБ</span>
            </div>
            <button
              class="flex-shrink-0 rounded-full p-1 text-[--t3] transition-all hover:bg-red-500/15 hover:text-red-400"
              aria-label="Удалить файл"
              @click="removeFile(i)"
            >
              <IconX :size="14" />
            </button>
          </div>
        </div>
      </div>

      <!-- Cover -->
      <div class="card px-5 py-5">
        <label class="mb-3 block text-[12px] font-semibold text-[--t2]">Обложка (опционально)</label>
        <label
          class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-[--border] px-4 py-3 text-[12px] text-[--t3] transition-all hover:border-white/15 hover:bg-white/[0.02]"
        >
          <IconUpload :size="14" />
          {{ uploadCover ? uploadCover.name : 'Выбрать изображение' }}
          <input type="file" accept="image/*" class="hidden" @change="onCoverChange" />
        </label>
        <div v-if="uploadCover" class="mt-2 flex items-center gap-1.5 text-[11px] text-emerald-400">
          <IconCheck :size="12" />
          Обложка выбрана
        </div>
      </div>

      <!-- Upload button -->
      <button
        class="btn btn-primary w-full justify-center text-[14px]"
        :disabled="uploading || !uploadTitle.trim() || uploadFiles.length === 0"
        @click="handleUpload"
      >
        <IconUpload v-if="!uploading" :size="16" />
        <span v-if="uploading">Загрузка... {{ uploadProgress }}%</span>
        <span v-else>Загрузить</span>
      </button>
    </div>

    <!-- TTS Tab -->
    <div v-if="activeTab === 'tts'" class="max-w-xl space-y-5">
      <div class="card space-y-4 px-5 py-5">
        <!-- Title -->
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">Название *</label>
          <input v-model="ttsTitle" type="text" placeholder="Название книги" class="input-field w-full px-3.5 py-2.5" />
        </div>

        <!-- Author -->
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">Автор</label>
          <input v-model="ttsAuthor" type="text" placeholder="Автор" class="input-field w-full px-3.5 py-2.5" />
        </div>

        <!-- Document file -->
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">Документ (PDF, EPUB, TXT, FB2) *</label>
          <label
            class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-[--border] px-4 py-3 text-[13px] transition-all hover:border-white/15 hover:bg-white/[0.02]"
            :class="ttsFile ? 'text-[--t1]' : 'text-[--t3]'"
          >
            <IconUpload :size="14" />
            {{ ttsFile ? ttsFile.name : 'Выбрать файл' }}
            <input type="file" accept=".pdf,.epub,.txt,.fb2" class="hidden" @change="onTTSFileChange" />
          </label>
        </div>
      </div>

      <!-- Voice settings card -->
      <div class="card space-y-4 px-5 py-5">
        <h3 class="section-label">Настройки голоса</h3>

        <!-- Engine selector -->
        <div v-if="showEngineSelector">
          <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">Движок</label>
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
          <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">Голос</label>
          <select v-model="ttsVoice" class="input-field w-full px-3.5 py-2.5">
            <option v-for="v in voices" :key="v.id" :value="v.id">
              {{ v.name }} ({{ v.lang }}, {{ v.gender === 'male' ? 'муж.' : v.gender === 'female' ? 'жен.' : '' }})
            </option>
          </select>
        </div>

        <!-- Rate -->
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">Скорость</label>
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
        <span v-if="converting && !conversionStarted">Загрузка...</span>
        <span v-else>Создать аудиокнигу</span>
      </button>

      <!-- Conversion progress -->
      <div
        v-if="conversionStarted"
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
                {{ jobStatus === 'done' ? 'Готово!' : jobStatus === 'error' ? 'Ошибка' : 'Конвертация...' }}
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
            Перейти к моим книгам
          </router-link>
        </div>
      </div>
    </div>

    <!-- Local Book Tab -->
    <div v-if="activeTab === 'local'" class="max-w-xl space-y-5">
      <div class="flex items-start gap-3 rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-3">
        <div class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-white/[0.06]">
          <IconSmartphone :size="16" class="text-[--t2]" />
        </div>
        <p class="text-[12px] leading-relaxed text-[--t2]">
          Книга будет доступна только на этом устройстве и не синхронизируется с облаком
        </p>
      </div>

      <div class="card space-y-4 px-5 py-5">
        <!-- Title -->
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">Название *</label>
          <input
            v-model="localTitle"
            type="text"
            placeholder="Название книги"
            class="input-field w-full px-3.5 py-2.5"
          />
        </div>

        <!-- Author -->
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">Автор</label>
          <input v-model="localAuthor" type="text" placeholder="Автор" class="input-field w-full px-3.5 py-2.5" />
        </div>
      </div>

      <!-- MP3 Files -->
      <div class="card px-5 py-5">
        <label class="mb-3 block text-[12px] font-semibold text-[--t2]">MP3 файлы *</label>
        <div
          class="rounded-xl border-2 border-dashed border-[--border] p-8 text-center transition-all hover:border-white/15 hover:bg-white/[0.02]"
        >
          <div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.06]">
            <IconMusic :size="24" class="text-[--t2]" />
          </div>
          <p class="mb-1 text-[13px] font-medium text-[--t2]">Выберите MP3 файлы с устройства</p>
          <p class="mb-3 text-[12px] text-[--t3]">Поддерживаются MP3 и другие аудио форматы</p>
          <label
            class="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-[--accent-soft] px-4 py-2 text-[12px] font-medium text-[--accent] transition-all hover:bg-[--accent]/20"
          >
            <IconUpload :size="14" />
            Выбрать файлы
            <input type="file" accept=".mp3,audio/*" multiple class="hidden" @change="onLocalFilesChange" />
          </label>
        </div>

        <!-- File list -->
        <div v-if="localFiles.length" class="mt-4 space-y-1.5">
          <div class="mb-2 text-[11px] font-semibold text-[--t3]">
            {{ localFiles.length }} {{ plural(localFiles.length, 'файл', 'файла', 'файлов') }}
          </div>
          <div
            v-for="(file, i) in localFiles"
            :key="i"
            class="flex items-center justify-between rounded-xl bg-white/[0.03] px-3.5 py-2.5"
          >
            <div class="flex min-w-0 items-center gap-2.5">
              <IconMusic :size="14" class="flex-shrink-0 text-[--t3]" />
              <span class="truncate text-[12px] text-[--t2]">{{ file.name }}</span>
              <span class="flex-shrink-0 text-[11px] text-[--t3]">{{ (file.size / 1024 / 1024).toFixed(1) }} МБ</span>
            </div>
            <button
              class="flex-shrink-0 rounded-full p-1 text-[--t3] transition-all hover:bg-red-500/15 hover:text-red-400"
              aria-label="Удалить файл"
              @click="removeLocalFile(i)"
            >
              <IconX :size="14" />
            </button>
          </div>
        </div>
      </div>

      <!-- Cover -->
      <div class="card px-5 py-5">
        <label class="mb-3 block text-[12px] font-semibold text-[--t2]">Обложка (опционально)</label>
        <label
          class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-[--border] px-4 py-3 text-[12px] text-[--t3] transition-all hover:border-white/15 hover:bg-white/[0.02]"
        >
          <IconUpload :size="14" />
          {{ localCover ? 'Обложка выбрана' : 'Выбрать изображение' }}
          <input type="file" accept="image/*" class="hidden" @change="onLocalCoverChange" />
        </label>
        <div v-if="localCover" class="mt-2 flex items-center gap-1.5 text-[11px] text-emerald-400">
          <IconCheck :size="12" />
          Обложка выбрана
        </div>
      </div>

      <!-- Add button -->
      <button
        class="btn btn-primary w-full justify-center text-[14px]"
        :disabled="addingLocal || !localTitle.trim() || localFiles.length === 0"
        @click="handleAddLocal"
      >
        <IconSmartphone v-if="!addingLocal" :size="16" />
        <span v-if="addingLocal">Добавление...</span>
        <span v-else>Добавить на устройство</span>
      </button>
    </div>

    <!-- Offline notice for upload/tts tabs -->
    <div
      v-if="!isOnline && (activeTab === 'upload' || activeTab === 'tts')"
      class="mt-5 max-w-xl rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-[13px] text-[--t2]"
    >
      Загрузка и TTS доступны только онлайн
    </div>
  </div>
</template>
