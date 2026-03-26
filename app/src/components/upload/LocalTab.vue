<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { useLocalBooks } from '@/composables/useLocalBooks'
import { usePlayer } from '@/composables/usePlayer'
import { IconUpload, IconMusic, IconX, IconSmartphone, IconCheck } from '@/components/shared/icons'

const router = useRouter()
const toast = useToast()
const player = usePlayer()
const { t } = useI18n()
const { addLocalBook } = useLocalBooks()

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
    toast.error(t('upload.errTitleRequired'))
    return
  }
  if (localFiles.value.length === 0) {
    toast.error(t('upload.errFilesRequired'))
    return
  }

  addingLocal.value = true
  try {
    const localBook = await addLocalBook(localFiles.value, {
      title: localTitle.value.trim(),
      author: localAuthor.value.trim(),
      coverDataUrl: localCover.value,
    })
    toast.success(t('upload.successLocal'))

    // Autoplay: convert local book to Book shape and start playing
    try {
      const book = {
        id: localBook.id,
        title: localBook.title,
        author: localBook.author,
        folder: '',
        category: '',
        reader: '',
        path: '',
        progress: 0,
        tags: [] as string[],
        note: '',
        mp3_count: localBook.tracks.length,
      }
      await player.loadBook(book, undefined, true)
      router.push(`/book/${localBook.id}`)
    } catch {
      router.push('/my-library')
    }
  } catch (e: unknown) {
    toast.error(t('common.errorPrefix', { msg: e instanceof Error ? e.message : t('common.unknownError') }))
  } finally {
    addingLocal.value = false
  }
}
</script>

<template>
  <div class="max-w-xl space-y-5">
    <div class="flex items-start gap-3 rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-3">
      <div class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-white/[0.06]">
        <IconSmartphone :size="16" class="text-[--t2]" />
      </div>
      <p class="text-[12px] leading-relaxed text-[--t2]">
        {{ t('upload.localOnlyNote') }}
      </p>
    </div>

    <div class="card space-y-4 px-5 py-5">
      <!-- Title -->
      <div>
        <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">{{ t('upload.labelTitle') }}</label>
        <input
          v-model="localTitle"
          type="text"
          :placeholder="t('upload.placeholderBookTitle')"
          class="input-field w-full px-3.5 py-2.5"
        />
      </div>

      <!-- Author -->
      <div>
        <label class="mb-1.5 block text-[12px] font-semibold text-[--t2]">{{ t('upload.labelAuthor') }}</label>
        <input
          v-model="localAuthor"
          type="text"
          :placeholder="t('upload.placeholderAuthor')"
          class="input-field w-full px-3.5 py-2.5"
        />
      </div>
    </div>

    <!-- MP3 Files -->
    <div class="card px-5 py-5">
      <label class="mb-3 block text-[12px] font-semibold text-[--t2]">{{ t('upload.labelMp3') }}</label>
      <div
        class="rounded-xl border-2 border-dashed border-[--border] p-8 text-center transition-all hover:border-white/15 hover:bg-white/[0.02]"
      >
        <div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.06]">
          <IconMusic :size="24" class="text-[--t2]" />
        </div>
        <p class="mb-1 text-[13px] font-medium text-[--t2]">{{ t('upload.selectDevice') }}</p>
        <p class="mb-3 text-[12px] text-[--t3]">{{ t('upload.orSelect') }}</p>
        <label
          class="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-[--accent-soft] px-4 py-2 text-[12px] font-medium text-[--accent] transition-all hover:bg-[--accent]/20"
        >
          <IconUpload :size="14" />
          {{ t('upload.selectFiles') }}
          <input type="file" accept=".mp3,audio/*" multiple class="hidden" @change="onLocalFilesChange" />
        </label>
      </div>

      <!-- File list -->
      <div v-if="localFiles.length" class="mt-4 space-y-1.5">
        <div class="mb-2 text-[11px] font-semibold text-[--t3]">
          {{ localFiles.length }} {{ t('plural.file', localFiles.length) }}
        </div>
        <div
          v-for="(file, i) in localFiles"
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
            @click="removeLocalFile(i)"
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
        {{ localCover ? t('upload.coverSelected') : t('upload.selectImage') }}
        <input type="file" accept="image/*" class="hidden" @change="onLocalCoverChange" />
      </label>
      <div v-if="localCover" class="mt-2 flex items-center gap-1.5 text-[11px] text-emerald-400">
        <IconCheck :size="12" />
        {{ t('upload.coverSelected') }}
      </div>
    </div>

    <!-- Add button -->
    <button
      class="btn btn-primary w-full justify-center text-[14px]"
      :disabled="addingLocal || !localTitle.trim() || localFiles.length === 0"
      @click="handleAddLocal"
    >
      <IconSmartphone v-if="!addingLocal" :size="16" />
      <span v-if="addingLocal">{{ t('upload.addingLocal') }}</span>
      <span v-else>{{ t('upload.addLocalBtn') }}</span>
    </button>
  </div>
</template>
