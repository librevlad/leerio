<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useNarration, voiceLang, voiceLanguages, voiceLabel, type TtsVoice } from '../composables/useNarration'
import { useFileScanner } from '../composables/useFileScanner'
import { usePlayer } from '../composables/usePlayer'
import { useToast } from '../composables/useToast'
import { BookParseError, estimateSeconds, parseBookFile, type ParsedBook } from '../utils/ebook'
import ProgressBar from '../components/shared/ProgressBar.vue'
import PaywallModal from '../components/shared/PaywallModal.vue'
import { IconArrowLeft, IconPlay, IconCheck } from '../components/shared/icons'

const router = useRouter()
const { t, locale } = useI18n()
const toast = useToast()
const narration = useNarration()
const { status, voices, pickedFile, lastBookId } = narration
const showPaywall = ref(false)
const { getFsBook } = useFileScanner()
const player = usePlayer()

const fileInput = ref<HTMLInputElement | null>(null)
const book = ref<ParsedBook | null>(null)
const title = ref('')
const author = ref('')
const parsing = ref(false)
const parseError = ref('')
const lang = ref('')
const voiceId = ref('')
const starting = ref(false)
let parseOp = 0

type Phase = 'pick' | 'parsing' | 'form' | 'running' | 'result'
const phase = computed<Phase>(() => {
  const s = status.value.state
  if (s === 'running') return 'running'
  if (s === 'done' || s === 'error') return 'result'
  if (parsing.value) return 'parsing'
  return book.value ? 'form' : 'pick'
})

// ── File ──────────────────────────────────────────────────────────────

function pick() {
  fileInput.value?.click()
}

function onFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (file) pickedFile.value = file
}

watch(pickedFile, (file) => file && parse(file), { immediate: true })

async function parse(file: File) {
  pickedFile.value = null
  narration.reset()
  const op = ++parseOp
  parsing.value = true
  parseError.value = ''
  book.value = null
  try {
    const parsed = await parseBookFile(file)
    if (op !== parseOp) return
    book.value = parsed
    title.value = parsed.title
    author.value = parsed.author
    lang.value = parsed.lang
  } catch (e) {
    if (op !== parseOp) return
    parseError.value = e instanceof BookParseError ? e.code : 'broken'
  } finally {
    if (op === parseOp) parsing.value = false
  }
}

const parseErrorText = computed(() => {
  const keys: Record<string, string> = {
    unsupported: 'narrate.errUnsupported',
    empty: 'narrate.errEmpty',
    broken: 'narrate.errBroken',
  }
  return parseError.value ? t(keys[parseError.value] ?? 'narrate.errBroken') : ''
})

// ── Voice ─────────────────────────────────────────────────────────────

const languages = computed(() => voiceLanguages(voices.value ?? [], book.value?.lang ?? 'uk'))
const langVoices = computed(() => (voices.value ?? []).filter((v) => voiceLang(v) === lang.value))
const voice = computed<TtsVoice | undefined>(() => langVoices.value.find((v) => v.id === voiceId.value))

// Keep a voice of the chosen language selected (the best one comes first)
watch(
  langVoices,
  (list) => {
    if (!list.some((v) => v.id === voiceId.value)) voiceId.value = list[0]?.id ?? ''
  },
  { immediate: true },
)

function languageName(code: string): string {
  try {
    const name = new Intl.DisplayNames([locale.value], { type: 'language' }).of(code)
    return name ? name.charAt(0).toUpperCase() + name.slice(1) : code
  } catch {
    return code
  }
}

function previewVoice() {
  const v = voice.value
  const text = book.value?.chapters[0]?.text ?? ''
  if (!v || !text) return
  // First sentences of the book itself
  const sample = text.slice(0, 220).replace(/\s+\S*$/, '')
  void narration.preview(v, sample)
}

// Voices may be installed in system settings: refresh on return
function onVisible() {
  if (document.visibilityState === 'visible' && phase.value === 'form') void narration.loadVoices(true)
}

onMounted(() => {
  void narration.loadVoices()
  document.addEventListener('visibilitychange', onVisible)
})
onUnmounted(() => {
  document.removeEventListener('visibilitychange', onVisible)
  void narration.stopPreview()
})

// ── Start ─────────────────────────────────────────────────────────────

const chapters = computed(() => (book.value ? narration.allowedChapters(book.value) : []))
const limited = computed(() => (book.value?.chapters.length ?? 0) > chapters.value.length)

function formatDuration(sec: number): string {
  const h = Math.floor(sec / 3600)
  const m = Math.max(1, Math.round((sec % 3600) / 60))
  return h ? t('narrate.hours', { h, m }) : t('narrate.minutes', { m })
}

const summary = computed(() => {
  if (!book.value) return ''
  const all = book.value.chapters
  return `${t('narrate.chapters', all.length)} · ≈ ${formatDuration(estimateSeconds(all))}`
})

async function start() {
  const v = voice.value
  if (!book.value || !v || starting.value) return
  void narration.stopPreview()
  starting.value = true
  try {
    await narration.start(
      { title: title.value.trim() || book.value.title, author: author.value.trim(), chapters: book.value.chapters },
      v,
      {
        channel: t('narrate.notifChannel'),
        starting: t('narrate.notifStarting'),
        progress: t('narrate.progress', { current: '{current}', total: '{total}' }),
        cancel: t('narrate.cancel'),
        done: t('narrate.notifDone'),
        failed: t('narrate.notifFailed'),
      },
    )
  } catch {
    // The result screen shows the error
  } finally {
    starting.value = false
  }
}

// ── Running / result ──────────────────────────────────────────────────

const percent = computed(() => Math.round((status.value.progress ?? 0) * 100))

async function cancel() {
  if (!confirm(t('narrate.cancelConfirm'))) return
  await narration.cancel()
}

// Cancelled: back to the form with the same book
watch(
  () => status.value.state,
  (s) => {
    if (s === 'cancelled') {
      toast.info(t('narrate.cancelled'))
      narration.reset()
    }
  },
)

const savedCount = computed(() => status.value.files?.length ?? 0)
const resultBook = computed(() => (lastBookId.value ? getFsBook(lastBookId.value) : undefined))

const errorText = computed(() => {
  const code = status.value.error ?? 'failed'
  const known = ['no_engine', 'no_voice', 'synthesis', 'storage', 'timeout', 'interrupted', 'busy']
  return t(`narrate.err.${known.includes(code) ? code : 'failed'}`)
})

function listen() {
  const meta = resultBook.value
  if (!meta) return
  void player.loadBook({
    id: meta.id,
    title: meta.title,
    author: meta.author,
    folder: meta.folderPath,
    category: '',
    reader: '',
    path: '',
    progress: 0,
    tags: [],
    note: '',
  })
}

function another() {
  narration.reset()
  book.value = null
  pick()
}
</script>

<template>
  <div class="mx-auto max-w-xl">
    <input ref="fileInput" type="file" class="hidden" @change="onFile" />

    <!-- Header -->
    <div class="mb-6 flex items-center gap-3">
      <button
        class="flex items-center text-(--t3) hover:text-(--t1)"
        :aria-label="t('common.back')"
        @click="router.back()"
      >
        <IconArrowLeft :size="20" />
      </button>
      <h1 class="text-[18px] font-bold text-(--t1)">{{ t('narrate.title') }}</h1>
    </div>

    <!-- Pick a file -->
    <div v-if="phase === 'pick'" class="card px-5 py-8 text-center">
      <div class="mb-4 text-[40px]">📖</div>
      <p class="mb-6 text-[14px] text-(--t2)">{{ t('narrate.intro') }}</p>
      <p v-if="parseErrorText" class="mb-4 text-[13px] text-(--error)">{{ parseErrorText }}</p>
      <button v-ripple class="btn btn-primary justify-center px-8 py-3.5 text-[15px]" @click="pick">
        {{ t('narrate.pick') }}
      </button>
      <p class="mt-3 text-[12px] text-(--t3)">{{ t('narrate.formats') }}</p>
    </div>

    <!-- Parsing -->
    <div v-else-if="phase === 'parsing'" class="flex flex-col items-center gap-3 py-12">
      <div class="h-8 w-8 animate-spin rounded-full border-2 border-(--accent) border-t-transparent" />
      <p class="text-[13px] text-(--t3)">{{ t('narrate.parsing') }}</p>
    </div>

    <!-- Book + voice -->
    <div v-else-if="phase === 'form' && book" class="space-y-4">
      <div class="card space-y-4 px-5 py-5">
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold text-(--t2)">{{ t('narrate.labelTitle') }}</label>
          <input v-model="title" type="text" class="input-field w-full px-3.5 py-2.5" />
        </div>
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold text-(--t2)">{{ t('narrate.labelAuthor') }}</label>
          <input v-model="author" type="text" class="input-field w-full px-3.5 py-2.5" />
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="text-[12px] text-(--t3)">{{ summary }}</span>
          <button class="text-[12px] font-semibold text-(--accent)" @click="pick">{{ t('narrate.pickOther') }}</button>
        </div>
      </div>

      <div class="card space-y-4 px-5 py-5">
        <div class="section-label">{{ t('narrate.voice') }}</div>
        <div v-if="voices === null" class="h-10 animate-pulse rounded-lg bg-white/[0.04]" />
        <template v-else>
          <select v-model="lang" :aria-label="t('narrate.language')" class="input-field w-full px-3.5 py-2.5">
            <option v-for="code in languages" :key="code" :value="code">{{ languageName(code) }}</option>
          </select>
          <div v-if="langVoices.length" class="flex items-center gap-2">
            <select v-model="voiceId" :aria-label="t('narrate.voice')" class="input-field min-w-0 flex-1 px-3.5 py-2.5">
              <option v-for="v in langVoices" :key="v.id" :value="v.id">{{ voiceLabel(v, langVoices) }}</option>
            </select>
            <button
              class="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-lg bg-white/[0.06] text-(--t1)"
              :aria-label="t('narrate.preview')"
              @click="previewVoice"
            >
              <IconPlay :size="16" />
            </button>
          </div>
          <div v-else class="space-y-3">
            <p class="text-[13px] text-(--t2)">{{ t('narrate.noVoice') }}</p>
            <button class="btn btn-ghost" @click="narration.openTtsSettings()">{{ t('narrate.installVoices') }}</button>
          </div>
        </template>
      </div>

      <div>
        <button
          v-ripple
          class="btn btn-primary w-full justify-center py-3.5 text-[15px]"
          :disabled="!voice || starting"
          @click="start"
        >
          {{ limited ? t('narrate.startFree') : t('narrate.start') }}
        </button>
        <p v-if="limited" class="mt-2 text-center text-[11px] text-(--t3)">
          {{ t('narrate.freeHint') }}
          <button class="font-semibold text-(--accent)" @click="showPaywall = true">{{ t('pro.more') }}</button>
        </p>
      </div>
    </div>

    <!-- Narrating -->
    <div v-else-if="phase === 'running'" class="card space-y-4 px-5 py-6">
      <div>
        <div class="truncate text-[14px] font-semibold text-(--t1)">{{ status.title }}</div>
        <div class="mt-1 text-[12px] text-(--t3)">
          {{ t('narrate.progress', { current: (status.current ?? 0) + 1, total: status.total ?? 1 }) }} · {{ percent }}%
        </div>
      </div>
      <ProgressBar :percent="percent" height="h-[6px]" />
      <p class="text-[12px] text-(--t3)">{{ t('narrate.background') }}</p>
      <button class="btn btn-ghost w-full justify-center" @click="cancel">{{ t('narrate.cancel') }}</button>
    </div>

    <!-- Done / failed -->
    <div v-else-if="phase === 'result'" class="card space-y-4 px-5 py-6 text-center">
      <template v-if="status.state === 'done'">
        <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-(--accent)/15 text-(--accent)">
          <IconCheck :size="24" />
        </div>
        <div>
          <div class="text-[18px] font-bold text-(--t1)">{{ t('narrate.done') }}</div>
          <div class="mt-1 text-[13px] text-(--t2)">{{ status.title }} · {{ t('narrate.chapters', savedCount) }}</div>
          <div class="mt-1 text-[12px] text-(--t3)">{{ t('narrate.doneHint') }}</div>
        </div>
      </template>
      <template v-else>
        <div class="text-[18px] font-bold text-(--t1)">{{ t('narrate.failed') }}</div>
        <p class="text-[13px] text-(--t2)">{{ errorText }}</p>
        <p v-if="savedCount" class="text-[12px] text-(--t3)">{{ t('narrate.savedChapters', { n: savedCount }) }}</p>
      </template>
      <button
        v-if="resultBook"
        v-ripple
        class="btn btn-primary w-full justify-center py-3.5 text-[15px]"
        @click="listen"
      >
        <IconPlay :size="16" /> {{ t('narrate.play') }}
      </button>
      <button
        v-if="status.state === 'error' && book"
        class="btn btn-ghost w-full justify-center"
        @click="narration.reset()"
      >
        {{ t('narrate.retry') }}
      </button>
      <button class="btn btn-ghost w-full justify-center" @click="another">{{ t('narrate.another') }}</button>
    </div>

    <PaywallModal :open="showPaywall" reason="narration" @close="showPaywall = false" />
  </div>
</template>
