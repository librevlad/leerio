import { ref, computed } from 'vue'
import { api, audioUrl, coverUrl, userBookCoverUrl } from '../api'
import { useDownloads } from './useDownloads'
import { useLocalBooks } from './useLocalBooks'
import { useNetwork } from './useNetwork'
import { useToast } from './useToast'
import type { Book, Track } from '../types'

// Cached i18n instance (lazy-loaded to avoid circular dependency in tests)
let _i18n: { global: { t: (key: string) => string } } | null = null
function t(key: string): string {
  if (!_i18n) {
    try {
      // Dynamic import is async, so first call returns key as fallback
      import('../i18n').then((m) => {
        _i18n = m.default
      })
      return key
    } catch {
      return key
    }
  }
  return _i18n.global.t(key)
}

// ── Singleton state (shared across all components) ──────────────────────────

export const PLAYBACK_SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2] as const

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
const playbackRate = ref(parseFloat(localStorage.getItem('leerio_playback_rate') || '1'))
const sleepTimer = ref<number | null>(null)
const isFullscreen = ref(false)
const audioError = ref(false)

let sleepTimerId: ReturnType<typeof setTimeout> | null = null

const downloads = useDownloads()
const toast = useToast()

let audio: HTMLAudioElement | null = null
let saveTimer: ReturnType<typeof setTimeout> | null = null
let isSeeking = false
let activeSessionBook: string | null = null
let deviceChangeRegistered = false
let coverBlobUrl: string | null = null
let coverMimeType: string | null = null
let nextTrackUrl: string | null = null
let nextTrackIndex: number | null = null

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
    audio.playbackRate = playbackRate.value

    audio.addEventListener('timeupdate', () => {
      if (!isSeeking) {
        currentTime.value = audio!.currentTime
      }
    })

    audio.addEventListener('loadedmetadata', () => {
      duration.value = audio!.duration
      isLoading.value = false
      updatePositionState()
    })

    audio.addEventListener('ended', () => {
      nextTrack()
    })

    audio.addEventListener('play', () => {
      isPlaying.value = true
      startSaveTimer()
      updatePositionState()
      const title = currentBook.value?.title
      if (title && activeSessionBook !== title) {
        if (activeSessionBook) {
          api.stopSession(activeSessionBook).catch(() => {})
        }
        activeSessionBook = title
        api.startSession(title).catch(() => {})
      }
    })

    audio.addEventListener('pause', () => {
      isPlaying.value = false
      updatePositionState()
      stopSaveTimer()
      savePosition()
      if (activeSessionBook) {
        api.stopSession(activeSessionBook).catch(() => {})
        activeSessionBook = null
      }
    })

    audio.addEventListener('waiting', () => {
      isLoading.value = true
    })

    audio.addEventListener('canplay', () => {
      isLoading.value = false
      audioError.value = false
    })

    audio.addEventListener('error', () => {
      isLoading.value = false
      audioError.value = true
      toast.error(t('player.loadError'))
    })

    audio.addEventListener('seeked', () => {
      updatePositionState()
    })

    // Pause when headphones are disconnected (register only once)
    if (!deviceChangeRegistered && navigator.mediaDevices?.addEventListener) {
      deviceChangeRegistered = true
      let previousDevices: string[] = []
      navigator.mediaDevices.enumerateDevices().then((devices) => {
        previousDevices = devices.filter((d) => d.kind === 'audiooutput').map((d) => d.deviceId)
      })
      navigator.mediaDevices.addEventListener('devicechange', () => {
        navigator.mediaDevices.enumerateDevices().then((devices) => {
          const currentOutputs = devices.filter((d) => d.kind === 'audiooutput').map((d) => d.deviceId)
          if (previousDevices.length > currentOutputs.length && audio && !audio.paused) {
            audio.pause()
          }
          previousDevices = currentOutputs
        })
      })
    }
  }
  return audio
}

// ── Save position (debounced) ───────────────────────────────────────────────

function savePosition() {
  if (!currentBook.value || !currentTrack.value) return

  // Always save to localStorage for offline fallback
  try {
    localStorage.setItem(
      `leerio_pos_${currentBook.value.id}`,
      JSON.stringify({ track_index: currentTrackIndex.value, position: currentTime.value }),
    )
  } catch {
    // localStorage full
  }

  // For local-only books, don't call API
  if (currentBook.value.id.startsWith('lb:')) return

  api
    .setPlaybackPosition(currentBook.value.id, currentTrackIndex.value, currentTime.value, currentTrack.value.filename)
    .catch((e) => console.warn('Failed to save position:', e))

  // Auto-track book progress (0-100%)
  const pct = Math.round(overallProgress.value)
  if (pct > 0) {
    api.setProgress(currentBook.value.id, pct).catch((e) => console.warn('Failed to save progress:', e))
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

async function loadCoverBlobUrl(book: Book): Promise<void> {
  if (coverBlobUrl) {
    URL.revokeObjectURL(coverBlobUrl)
    coverBlobUrl = null
    coverMimeType = null
  }

  try {
    let url: string
    if (book.id.startsWith('lb:')) {
      // Local books: cover in IndexedDB — skip (no HTTP URL available)
      return
    } else if (book.id.startsWith('ub:')) {
      const slug = book.id.split(':')[2] ?? ''
      url = userBookCoverUrl(slug)
    } else {
      url = coverUrl(book.id)
    }

    const response = await fetch(url, { credentials: 'include', redirect: 'follow' })
    if (!response.ok) return

    const contentType = response.headers.get('Content-Type') || 'image/jpeg'
    if (contentType.includes('svg')) return

    const blob = await response.blob()
    coverBlobUrl = URL.createObjectURL(blob)
    coverMimeType = contentType
  } catch {
    // Cover fetch failed (network, CORS on S3 redirect, etc.) — skip artwork
  }
}

function updateMediaSession() {
  if (!('mediaSession' in navigator) || !currentBook.value) return

  const artwork: MediaImage[] | undefined =
    coverBlobUrl && coverMimeType ? [{ src: coverBlobUrl, sizes: '512x512', type: coverMimeType }] : undefined

  navigator.mediaSession.metadata = new MediaMetadata({
    title: currentTrack.value?.filename ?? 'Unknown',
    artist: currentBook.value.author,
    album: currentBook.value.title,
    ...(artwork && { artwork }),
  })

  navigator.mediaSession.setActionHandler('play', () => togglePlay())
  navigator.mediaSession.setActionHandler('pause', () => togglePlay())
  navigator.mediaSession.setActionHandler('previoustrack', () => prevTrack())
  navigator.mediaSession.setActionHandler('nexttrack', () => nextTrack())
  navigator.mediaSession.setActionHandler('seekto', (details) => {
    if (details.seekTime != null) seek(details.seekTime)
  })
  navigator.mediaSession.setActionHandler('seekbackward', (details) => {
    skipBackward(details.seekOffset ?? 10)
  })
  navigator.mediaSession.setActionHandler('seekforward', (details) => {
    skipForward(details.seekOffset ?? 30)
  })
}

function updatePositionState() {
  if (!('mediaSession' in navigator) || !audio) return
  try {
    navigator.mediaSession.setPositionState({
      duration: audio.duration || 0,
      position: audio.currentTime || 0,
      playbackRate: audio.playbackRate || 1,
    })
  } catch {
    // setPositionState can throw if duration is NaN or 0
  }
}

// ── Resolve audio source (local or server) ──────────────────────────────────

async function resolveAudioSrc(bookId: string, trackIndex: number): Promise<string> {
  // Local book (device-only, stored in IndexedDB)
  if (bookId.startsWith('lb:')) {
    const { getLocalAudioUrl: getLocalUrl } = useLocalBooks()
    const url = await getLocalUrl(bookId, trackIndex)
    playingOffline.value = true
    return url || ''
  }
  // External URL (e.g. direct MP3 link)
  const track = tracks.value[trackIndex]
  if (track?.url) {
    playingOffline.value = false
    return track.url
  }
  // Local downloads (native app)
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
  if (activeSessionBook && activeSessionBook !== book.title) {
    api.stopSession(activeSessionBook).catch(() => {})
    activeSessionBook = null
  }
  isLoading.value = true
  currentBook.value = book
  isPlayerVisible.value = true
  isFullscreen.value = true

  try {
    const isLocalBook = book.id.startsWith('lb:')
    const isUserBook = book.id.startsWith('ub:')
    const { isOnline } = useNetwork()

    if (isLocalBook) {
      // Local-only book: load from IndexedDB
      const { getLocalBook, getLocalAudioUrl: getLocalUrl } = useLocalBooks()
      const lb = getLocalBook(book.id)
      if (!lb) throw new Error('Local book not found')
      tracks.value = lb.tracks.map((t) => ({
        index: t.index,
        filename: t.filename,
        path: t.path,
        duration: t.duration,
      }))
      playingOffline.value = true
      currentTrackIndex.value = 0

      // Restore position from localStorage
      let pos = { track_index: 0, position: 0 }
      try {
        const savedPos = localStorage.getItem(`leerio_pos_${book.id}`)
        if (savedPos) pos = JSON.parse(savedPos)
      } catch {
        /* corrupted localStorage */
      }
      const idx = pos.track_index >= 0 && pos.track_index < tracks.value.length ? pos.track_index : 0
      const seekPos = pos.position >= 0 ? pos.position : 0
      currentTrackIndex.value = idx

      const a = ensureAudio()
      const localUrl = await getLocalUrl(book.id, idx)
      a.src = localUrl || ''
      a.load()

      if (seekPos > 0) {
        const onLoaded = () => {
          a.currentTime = seekPos
          a.removeEventListener('loadedmetadata', onLoaded)
        }
        a.addEventListener('loadedmetadata', onLoaded)
      }

      await loadCoverBlobUrl(book)
      updateMediaSession()
      return
    }

    // Offline + downloaded book: use local track metadata
    if (!isOnline.value && downloads.isBookDownloaded(book.id)) {
      const meta = downloads.meta.value.books[book.id]
      if (meta?.tracks) {
        tracks.value = meta.tracks.map((t: { index: number; filename: string }, i: number) => ({
          index: i,
          filename: t.filename,
          path: '',
          duration: 0,
        }))
        playingOffline.value = true
      }
    } else {
      const ubSlug = isUserBook ? (book.id.split(':')[2] ?? '') : ''
      const res = isUserBook ? await api.getUserBookTracks(ubSlug) : await api.getBookTracks(book.id)
      tracks.value = res.tracks
    }

    // Restore saved position
    let pos = { track_index: 0, position: 0 }
    try {
      pos = await api.getPlaybackPosition(book.id)
    } catch {
      // Offline — try localStorage fallback
      try {
        const savedPos = localStorage.getItem(`leerio_pos_${book.id}`)
        if (savedPos) pos = JSON.parse(savedPos)
      } catch {
        /* corrupted localStorage */
      }
    }
    const idx = pos.track_index >= 0 && pos.track_index < tracks.value.length ? pos.track_index : 0
    const seekPos = pos.position >= 0 ? pos.position : 0
    currentTrackIndex.value = idx

    const a = ensureAudio()
    a.src = await resolveAudioSrc(book.id, idx)
    a.load()

    // Seek to saved position after metadata loads
    if (seekPos > 0) {
      const onLoaded = () => {
        a.currentTime = seekPos
        a.removeEventListener('loadedmetadata', onLoaded)
      }
      a.addEventListener('loadedmetadata', onLoaded)
    }

    await loadCoverBlobUrl(book)
    updateMediaSession()
    preloadNextTrack()
  } catch {
    isLoading.value = false
    toast.error(t('player.tracksLoadError'))
  }
}

async function playTrack(index: number) {
  if (!currentBook.value || index < 0 || index >= tracks.value.length) return
  if (isLoading.value) return // prevent double-tap race condition

  savePosition()
  currentTrackIndex.value = index
  currentTime.value = 0

  const a = ensureAudio()
  if (nextTrackUrl && nextTrackIndex === index) {
    a.src = nextTrackUrl
  } else {
    a.src = await resolveAudioSrc(currentBook.value.id, index)
  }
  nextTrackUrl = null
  nextTrackIndex = null
  a.load()
  a.play().catch(() => toast.error(t('player.playbackError')))
  updateMediaSession()
  preloadNextTrack()
}

function togglePlay() {
  const a = ensureAudio()
  if (!a.src) return
  if (a.paused) {
    a.play().catch(() => toast.error(t('player.playbackError')))
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

function setPlaybackRate(rate: number) {
  playbackRate.value = rate
  if (audio) audio.playbackRate = rate
  localStorage.setItem('leerio_playback_rate', String(rate))
  updatePositionState()
}

function skipForward(seconds = 15) {
  if (!audio) return
  const newTime = currentTime.value + seconds
  if (newTime >= (audio.duration || Infinity)) {
    nextTrack()
  } else {
    seek(newTime)
  }
}

function skipBackward(seconds = 15) {
  if (!audio) return
  const newTime = currentTime.value - seconds
  if (newTime < 0 && currentTrackIndex.value > 0) {
    playTrack(currentTrackIndex.value - 1)
  } else {
    seek(Math.max(0, newTime))
  }
}

function setSleepTimer(minutes: number | null) {
  if (sleepTimerId) {
    clearTimeout(sleepTimerId)
    sleepTimerId = null
  }
  if (minutes === null) {
    sleepTimer.value = null
    return
  }
  if (minutes === -1) {
    // End of current track
    sleepTimer.value = null
    const onEnded = () => {
      const a = ensureAudio()
      a.pause()
      a.removeEventListener('ended', onEnded)
    }
    const a = ensureAudio()
    a.addEventListener('ended', onEnded, { once: true })
    sleepTimer.value = 0
    return
  }
  sleepTimer.value = minutes
  // Countdown every minute
  const tick = () => {
    if (sleepTimer.value === null) return
    sleepTimer.value--
    if (sleepTimer.value <= 0) {
      sleepTimer.value = null
      const a = ensureAudio()
      a.pause()
    } else {
      sleepTimerId = setTimeout(tick, 60_000)
    }
  }
  sleepTimerId = setTimeout(tick, 60_000)
}

function openFullscreen() {
  isFullscreen.value = true
}

function closeFullscreen() {
  isFullscreen.value = false
}

function closePlayer() {
  if (coverBlobUrl) {
    URL.revokeObjectURL(coverBlobUrl)
    coverBlobUrl = null
    coverMimeType = null
  }
  if (activeSessionBook) {
    api.stopSession(activeSessionBook).catch(() => {})
    activeSessionBook = null
  }
  savePosition()
  stopSaveTimer()
  setSleepTimer(null)
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

async function preloadNextTrack() {
  if (!currentBook.value) return
  const nextIdx = currentTrackIndex.value + 1
  if (nextIdx >= tracks.value.length) {
    nextTrackUrl = null
    nextTrackIndex = null
    return
  }
  try {
    nextTrackUrl = await resolveAudioSrc(currentBook.value.id, nextIdx)
    nextTrackIndex = nextIdx
  } catch {
    nextTrackUrl = null
    nextTrackIndex = null
  }
}

function retryAudio() {
  if (!audio || !currentBook.value) return
  audioError.value = false
  isLoading.value = true
  audio.load()
  audio.play().catch(() => toast.error(t('player.playbackError')))
}

function skipErrorTrack() {
  audioError.value = false
  nextTrack()
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
    playbackRate,
    sleepTimer,
    isFullscreen,
    audioError,

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
    skipForward,
    skipBackward,
    setPlaybackRate,
    setSleepTimer,
    openFullscreen,
    closeFullscreen,
    closePlayer,
    retryAudio,
    skipErrorTrack,

    // Helpers
    formatTime,
  }
}
