/**
 * On-device narration (APK): an ebook becomes an audiobook made by the phone's own TTS engine.
 *
 * Native side: android/.../NarrationPlugin.java (voices, start/cancel/status) and
 * NarrationService.java (foreground synthesis → AAC .m4a). Chapters land in
 * Audiobooks/<Author - Title>/ and the book joins My Library as an `fs:` book when the job ends.
 */
import { ref } from 'vue'
import { Capacitor, registerPlugin, type PluginListenerHandle } from '@capacitor/core'
import { useFileScanner } from './useFileScanner'
import { usePro, FREE_NARRATION_CHAPTERS } from './usePro'
import { bookFolderName, chapterFileName, type BookChapter } from '../utils/ebook'
import type { FsBookMeta } from '../types'

export interface TtsVoice {
  id: string
  engine: string
  engineLabel: string
  name: string
  lang: string // BCP 47, e.g. "uk-UA"
  quality: number
  isDefault: boolean
}

export type NarrationState = 'idle' | 'running' | 'done' | 'error' | 'cancelled'

export interface NarrationFile {
  index: number
  title: string
  path: string // relative to external storage
  durationMs: number
  size: number
}

export interface NarrationStatus {
  state: NarrationState
  dir?: string
  title?: string
  author?: string
  total?: number
  current?: number // 0-based chapter being narrated
  progress?: number // 0..1 for the whole job
  files?: NarrationFile[]
  error?: string // no_engine | no_voice | synthesis | storage | timeout | interrupted | failed
}

/** Notification texts (the service has no i18n). `progress` takes {current} and {total}. */
export interface NarrationLabels {
  channel: string
  starting: string
  progress: string
  cancel: string
  done: string
  failed: string
}

export interface NarrationBook {
  title: string
  author: string
  chapters: BookChapter[]
}

interface NarrationPlugin {
  getVoices(): Promise<{ voices: TtsVoice[]; defaultEngine: string }>
  preview(opts: { engine: string; voice: string; text: string }): Promise<void>
  stopPreview(): Promise<void>
  openTtsSettings(): Promise<void>
  start(opts: {
    dir: string
    title: string
    author: string
    engine: string
    voice: string
    lang: string
    chapters: { title: string; text: string; file: string }[]
    labels: NarrationLabels
  }): Promise<{ dir: string }>
  cancel(): Promise<void>
  getStatus(): Promise<NarrationStatus>
  clearStatus(): Promise<void>
  addListener(
    event: 'progress' | 'chapterDone' | 'finished' | 'error',
    cb: (status: NarrationStatus) => void,
  ): Promise<PluginListenerHandle>
}

const Narration = registerPlugin<NarrationPlugin>('Narration')

// ── Singleton state ────────────────────────────────────────────────────

const status = ref<NarrationStatus>({ state: 'idle' })
const voices = ref<TtsVoice[] | null>(null)
/** File picked in the "+" menu; the narration screen parses it */
const pickedFile = ref<File | null>(null)
/** Library id of the book the last job made */
const lastBookId = ref('')
let attached = false

function attach() {
  if (attached || !Capacitor.isNativePlatform()) return
  attached = true
  const update = (s: NarrationStatus) => {
    status.value = s
  }
  const end = (s: NarrationStatus) => {
    update(s)
    claim(s)
  }
  void Narration.addListener('progress', update)
  void Narration.addListener('chapterDone', update)
  void Narration.addListener('finished', end)
  void Narration.addListener('error', end)
}

/** Puts what the job made into My Library and clears the native status */
function claim(s: NarrationStatus) {
  const book = narrationToFsBook(s)
  if (book) {
    useFileScanner().addFsBooks([book])
    lastBookId.value = book.id
  }
  void Narration.clearStatus().catch(() => {})
}

export function narrationToFsBook(s: NarrationStatus, now = new Date()): FsBookMeta | null {
  const files = s.files ?? []
  if (!s.dir || !files.length) return null
  return {
    id: `fs:${s.dir.split('/').pop()}`,
    title: s.title || s.dir,
    author: s.author ?? '',
    folderPath: s.dir,
    tracks: files.map((f, i) => ({
      index: i,
      filename: f.path.split('/').pop() ?? f.path,
      path: f.path,
      duration: Math.round(f.durationMs / 1000),
    })),
    sizeBytes: files.reduce((sum, f) => sum + (f.size || 0), 0),
    synced: false,
    addedAt: now.toISOString(),
  }
}

// ── Voices ─────────────────────────────────────────────────────────────

export function voiceLang(v: TtsVoice): string {
  return (v.lang.split('-')[0] ?? '').toLowerCase()
}

/** Default engine first, then each engine's default voice, then better quality */
export function sortVoices(list: TtsVoice[], defaultEngine: string): TtsVoice[] {
  const rank = (v: TtsVoice) => (v.engine === defaultEngine ? 0 : 2) + (v.isDefault ? 0 : 1)
  return [...list].sort((a, b) => rank(a) - rank(b) || b.quality - a.quality || a.name.localeCompare(b.name))
}

/** Languages that have voices; the book's language first, then uk/ru/en, then the rest */
export function voiceLanguages(list: TtsVoice[], bookLang: string): string[] {
  const order = [bookLang, 'uk', 'ru', 'en']
  const langs = new Set([bookLang, ...list.map(voiceLang)])
  const rank = (l: string) => {
    const i = order.indexOf(l)
    return i < 0 ? order.length : i
  }
  return [...langs].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b))
}

/** "Samsung TTS · uk-UA · 2" — voice names like "ru-ru-x-dfc-local" mean nothing to people */
export function voiceLabel(v: TtsVoice, sameLang: TtsVoice[]): string {
  const same = sameLang.filter((o) => o.engine === v.engine && o.lang === v.lang)
  const n = same.length > 1 ? ` · ${same.indexOf(v) + 1}` : ''
  return `${v.engineLabel} · ${v.lang}${n}`
}

// ── Public API ─────────────────────────────────────────────────────────

export function useNarration() {
  attach()
  const { limited } = usePro()

  async function loadVoices(force = false): Promise<TtsVoice[]> {
    if (voices.value && !force) return voices.value
    try {
      const res = await Narration.getVoices()
      voices.value = sortVoices(res.voices, res.defaultEngine)
    } catch {
      voices.value = []
    }
    return voices.value
  }

  /** Chapters this plan narrates */
  function allowedChapters(book: NarrationBook): BookChapter[] {
    return limited.value ? book.chapters.slice(0, FREE_NARRATION_CHAPTERS) : book.chapters
  }

  async function start(book: NarrationBook, voice: TtsVoice, labels: NarrationLabels): Promise<void> {
    const chapters = allowedChapters(book)
    lastBookId.value = ''
    status.value = { state: 'running', title: book.title, author: book.author, total: chapters.length, current: 0 }
    try {
      const res = await Narration.start({
        dir: `Audiobooks/${bookFolderName(book.author, book.title)}`,
        title: book.title,
        author: book.author,
        engine: voice.engine,
        voice: voice.name,
        lang: voice.lang,
        chapters: chapters.map((c, i) => ({
          title: c.title,
          text: c.text,
          file: chapterFileName(i, chapters.length, c.title),
        })),
        labels,
      })
      if (status.value.state === 'running') status.value = { ...status.value, dir: res.dir }
    } catch (e) {
      const code = (e as { code?: string })?.code
      status.value = { state: 'error', error: code === 'busy' ? 'busy' : 'failed', files: [] }
      throw e
    }
  }

  /** On app start: pick up a job that finished while the app was closed */
  async function sync(): Promise<void> {
    if (!Capacitor.isNativePlatform()) return
    try {
      const s = await Narration.getStatus()
      if (s.state === 'idle') return
      status.value = s
      if (s.state !== 'running') claim(s)
    } catch {
      // Plugin missing in an old build
    }
  }

  /** Back to the form after a finished job (not while one is running) */
  function reset() {
    if (status.value.state !== 'running') status.value = { state: 'idle' }
  }

  return {
    status,
    voices,
    pickedFile,
    lastBookId,
    loadVoices,
    allowedChapters,
    start,
    sync,
    reset,
    cancel: () => Narration.cancel(),
    preview: (voice: TtsVoice, text: string) =>
      Narration.preview({ engine: voice.engine, voice: voice.name, text }).catch(() => {}),
    stopPreview: () => Narration.stopPreview().catch(() => {}),
    openTtsSettings: () => Narration.openTtsSettings().catch(() => {}),
  }
}
