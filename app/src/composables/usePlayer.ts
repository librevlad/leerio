import { ref, computed } from 'vue'
import { api, audioUrl } from '../api'
import { useDownloads } from './useDownloads'
import { useToast } from './useToast'
import type { Book, Track } from '../types'

// ── Singleton state (shared across all components) ──────────────────────────

const currentBook = ref<Book | null>(null)
const tracks = ref<Track[]>([])
const currentTrackIndex = ref(0)
const isPlaying = ref(false)
const isLoading = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const volume = ref(1)
const isPlayerVisible = ref(false)
const playingOffline = ref(false)

const downloads = useDownloads()
const toast = useToast()

let audio: HTMLAudioElement | null = null
let saveTimer: ReturnType<typeof setTimeout> | null = null
let isSeeking = false

// ── Computed ────────────────────────────────────────────────────────────────

const currentTrack = computed(() => tracks.value[currentTrackIndex.value] ?? null)

const totalDuration = computed(() => tracks.value.reduce((sum, t) => sum + t.duration, 0))

const totalElapsed = computed(() => {
  let elapsed = 0
  for (let i = 0; i < currentTrackIndex.value; i++) {
    elapsed += tracks.value[i]?.duration ?? 0
  }
  return elapsed + currentTime.value
})

const overallProgress = computed(() => (totalDuration.value > 0 ? (totalElapsed.value / totalDuration.value) * 100 : 0))

// ── Audio engine ────────────────────────────────────────────────────────────

function ensureAudio(): HTMLAudioElement {
  if (!audio) {
    audio = new Audio()
    audio.volume = volume.value

    audio.addEventListener('timeupdate', () => {
      if (!isSeeking) {
        currentTime.value = audio!.currentTime
      }
    })

    audio.addEventListener('loadedmetadata', () => {
      duration.value = audio!.duration
      isLoading.value = false
    })

    audio.addEventListener('ended', () => {
      nextTrack()
    })

    audio.addEventListener('play', () => {
      isPlaying.value = true
      startSaveTimer()
    })

    audio.addEventListener('pause', () => {
      isPlaying.value = false
      stopSaveTimer()
      savePosition()
    })

    audio.addEventListener('waiting', () => {
      isLoading.value = true
    })

    audio.addEventListener('canplay', () => {
      isLoading.value = false
    })

    audio.addEventListener('error', () => {
      isLoading.value = false
      toast.error('Ошибка загрузки аудио')
    })
  }
  return audio
}

// ── Save position (debounced) ───────────────────────────────────────────────

function savePosition() {
  if (!currentBook.value || !currentTrack.value) return
  api
    .setPlaybackPosition(currentBook.value.id, currentTrackIndex.value, currentTime.value, currentTrack.value.filename)
    .catch((e) => console.warn('Не удалось сохранить позицию:', e))

  // Auto-track book progress (0-100%)
  const pct = Math.round(overallProgress.value)
  if (pct > 0) {
    api.setProgress(currentBook.value.title, pct).catch((e) => console.warn('Не удалось сохранить прогресс:', e))
  }
}

function startSaveTimer() {
  stopSaveTimer()
  saveTimer = setInterval(savePosition, 10_000)
}

function stopSaveTimer() {
  if (saveTimer) {
    clearInterval(saveTimer)
    saveTimer = null
  }
}

// ── Media Session ───────────────────────────────────────────────────────────

function updateMediaSession() {
  if (!('mediaSession' in navigator) || !currentBook.value) return

  navigator.mediaSession.metadata = new MediaMetadata({
    title: currentTrack.value?.filename ?? 'Unknown',
    artist: currentBook.value.author,
    album: currentBook.value.title,
  })

  navigator.mediaSession.setActionHandler('play', () => togglePlay())
  navigator.mediaSession.setActionHandler('pause', () => togglePlay())
  navigator.mediaSession.setActionHandler('previoustrack', () => prevTrack())
  navigator.mediaSession.setActionHandler('nexttrack', () => nextTrack())
  navigator.mediaSession.setActionHandler('seekto', (details) => {
    if (details.seekTime != null) seek(details.seekTime)
  })
}

// ── Resolve audio source (local or server) ──────────────────────────────────

async function resolveAudioSrc(bookId: string, trackIndex: number): Promise<string> {
  if (downloads.isNative.value && downloads.isTrackDownloaded(bookId, trackIndex)) {
    const localUrl = await downloads.getLocalAudioUrl(bookId, trackIndex)
    if (localUrl) {
      playingOffline.value = true
      return localUrl
    }
  }
  playingOffline.value = false
  return audioUrl(bookId, trackIndex)
}

// ── Actions ─────────────────────────────────────────────────────────────────

async function loadBook(book: Book) {
  isLoading.value = true
  currentBook.value = book
  isPlayerVisible.value = true

  try {
    const res = await api.getBookTracks(book.id)
    tracks.value = res.tracks

    // Restore saved position
    const pos = await api.getPlaybackPosition(book.id)
    const idx = pos.track_index < res.tracks.length ? pos.track_index : 0
    currentTrackIndex.value = idx

    const a = ensureAudio()
    a.src = await resolveAudioSrc(book.id, idx)
    a.load()

    // Seek to saved position after metadata loads
    if (pos.position > 0) {
      const onLoaded = () => {
        a.currentTime = pos.position
        a.removeEventListener('loadedmetadata', onLoaded)
      }
      a.addEventListener('loadedmetadata', onLoaded)
    }

    updateMediaSession()
  } catch {
    isLoading.value = false
    toast.error('Не удалось загрузить треки')
  }
}

async function playTrack(index: number) {
  if (!currentBook.value || index < 0 || index >= tracks.value.length) return

  savePosition()
  currentTrackIndex.value = index
  currentTime.value = 0

  const a = ensureAudio()
  a.src = await resolveAudioSrc(currentBook.value.id, index)
  a.load()
  a.play().catch(() => toast.error('Ошибка воспроизведения'))
  updateMediaSession()
}

function togglePlay() {
  const a = ensureAudio()
  if (!a.src) return
  if (a.paused) {
    a.play().catch(() => toast.error('Ошибка воспроизведения'))
  } else {
    a.pause()
  }
}

function seek(sec: number) {
  const a = ensureAudio()
  a.currentTime = Math.max(0, Math.min(sec, a.duration || 0))
  currentTime.value = a.currentTime
}

function startSeek() {
  isSeeking = true
}

function endSeek(sec: number) {
  isSeeking = false
  seek(sec)
}

function nextTrack() {
  if (currentTrackIndex.value < tracks.value.length - 1) {
    playTrack(currentTrackIndex.value + 1)
  } else {
    // End of book
    const a = ensureAudio()
    a.pause()
    isPlaying.value = false
    savePosition()
  }
}

function prevTrack() {
  // If more than 3 sec into track, restart it; otherwise go to previous
  if (currentTime.value > 3) {
    seek(0)
  } else if (currentTrackIndex.value > 0) {
    playTrack(currentTrackIndex.value - 1)
  }
}

function setVolume(v: number) {
  volume.value = Math.max(0, Math.min(1, v))
  if (audio) audio.volume = volume.value
}

function closePlayer() {
  savePosition()
  stopSaveTimer()
  if (audio) {
    audio.pause()
    audio.src = ''
  }
  isPlaying.value = false
  isPlayerVisible.value = false
  currentBook.value = null
  tracks.value = []
  currentTrackIndex.value = 0
  currentTime.value = 0
  duration.value = 0
}

// ── Format helpers ──────────────────────────────────────────────────────────

function formatTime(sec: number): string {
  if (!sec || !isFinite(sec)) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// ── Export ───────────────────────────────────────────────────────────────────

export function usePlayer() {
  return {
    // State
    currentBook,
    tracks,
    currentTrackIndex,
    isPlaying,
    isLoading,
    currentTime,
    duration,
    volume,
    isPlayerVisible,
    playingOffline,

    // Computed
    currentTrack,
    totalDuration,
    totalElapsed,
    overallProgress,

    // Actions
    loadBook,
    playTrack,
    togglePlay,
    seek,
    startSeek,
    endSeek,
    nextTrack,
    prevTrack,
    setVolume,
    closePlayer,

    // Helpers
    formatTime,
  }
}
