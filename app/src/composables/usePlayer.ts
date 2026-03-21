import { ref, computed } from 'vue'
import { api, audioUrl, coverUrl, userBookCoverUrl } from '../api'
import { useDownloads } from './useDownloads'
import { useLocalBooks } from './useLocalBooks'
import { useLocalData } from './useLocalData'
import { useNetwork } from './useNetwork'
import { useToast } from './useToast'
import { useFileScanner } from './useFileScanner'
import { useTracking } from './useTelemetry'
import type { Book, Track } from '../types'
import { STORAGE } from '../constants/storage'
import { Filesystem, Directory } from '@capacitor/filesystem'
import { Capacitor } from '@capacitor/core'

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
const _storedVol = parseFloat(localStorage.getItem(STORAGE.VOLUME) || '1')
const volume = ref(isNaN(_storedVol) || _storedVol < 0 ? 1 : Math.min(_storedVol, 1))
const isPlayerVisible = ref(false)
const playingOffline = ref(false)
const _storedRate = parseFloat(localStorage.getItem(STORAGE.PLAYBACK_RATE) || '1')
const playbackRate = ref(isNaN(_storedRate) || _storedRate <= 0 ? 1 : _storedRate)
const sleepTimer = ref<number | null>(null)
const isFullscreen = ref(false)
const audioError = ref(false)

let sleepTimerId: ReturnType<typeof setTimeout> | null = null
let sleepAtTrackEnd = false

const downloads = useDownloads()
const localData = useLocalData()
const toast = useToast()
const { track: trackEvent } = useTracking()

let audio: HTMLAudioElement | null = null
let saveTimer: ReturnType<typeof setTimeout> | null = null
let saveApiDebounce: ReturnType<typeof setTimeout> | null = null
let isSeeking = false
let activeSessionBook: string | null = null
let deviceChangeRegistered = false
let coverBlobUrl: string | null = null
let coverMimeType: string | null = null
let nextTrackUrl: string | null = null
let nextTrackIndex: number | null = null
let loadOpId = 0
let playOpId = 0
let preloadInProgress = false

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

const playerState = computed<'idle' | 'loading' | 'playing' | 'paused' | 'error'>(() => {
  if (audioError.value) return 'error'
  if (isLoading.value) return 'loading'
  if (isPlaying.value) return 'playing'
  if (currentBook.value) return 'paused'
  return 'idle'
})

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
      if (sleepAtTrackEnd) {
        sleepAtTrackEnd = false
        isPlaying.value = false
        sleepTimer.value = null
        return
      }
      // Don't auto-advance if a new track/book is already loading
      if (isLoading.value) return
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
      // Only save position on user-initiated pause, not during programmatic track/book switch
      if (!isLoading.value) {
        savePosition()
        if (activeSessionBook) {
          api.stopSession(activeSessionBook).catch(() => {})
          activeSessionBook = null
        }
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
      // Ignore errors from stale/empty sources (e.g. after closePlayer or rapid track switch)
      if (!audio?.src || !currentBook.value) return
      isLoading.value = false
      audioError.value = true
      trackEvent('player_error')
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
        navigator.mediaDevices
          .enumerateDevices()
          .then((devices) => {
            const currentOutputs = devices.filter((d) => d.kind === 'audiooutput').map((d) => d.deviceId)
            if (previousDevices.length > currentOutputs.length && audio && !audio.paused && currentBook.value) {
              audio.pause()
            }
            previousDevices = currentOutputs
          })
          .catch(() => {
            /* permission denied or unavailable */
          })
      })
    }
  }
  return audio
}

// ── Save position (debounced) ───────────────────────────────────────────────

function savePosition() {
  if (!currentBook.value || !currentTrack.value) return
  // Don't save position 0 during loading — seek hasn't happened yet
  if (isLoading.value && currentTime.value === 0) return

  // Save to IndexedDB (primary offline store)
  const bookId = currentBook.value.id
  const trackIdx = currentTrackIndex.value
  const pos = currentTime.value
  localData.setPosition(bookId, { track_index: trackIdx, position: pos }).catch(() => {})

  const pct = Math.round(overallProgress.value)
  if (pct > 0) {
    localData.setProgress(bookId, pct).catch(() => {})
  }

  // Always save to localStorage for instant recovery
  try {
    localStorage.setItem(
      `${STORAGE.POSITION_PREFIX}${currentBook.value.id}`,
      JSON.stringify({ track_index: trackIdx, position: pos }),
    )
  } catch {
    // localStorage full
  }

  // For local-only books (lb: or fs:), don't call API
  if (currentBook.value.id.startsWith('lb:') || currentBook.value.id.startsWith('fs:')) return

  // Debounce API saves — prevent storm during rapid navigation
  if (saveApiDebounce) clearTimeout(saveApiDebounce)
  const filename = currentTrack.value.filename
  saveApiDebounce = setTimeout(() => {
    api.setPlaybackPosition(bookId, trackIdx, pos, filename).catch(() => {})
    if (pct > 0) api.setProgress(bookId, pct).catch(() => {})
    saveApiDebounce = null
  }, 1_000)
}

function startSaveTimer() {
  stopSaveTimer()
  saveTimer = setInterval(savePosition, 5_000)
}

// Save position when user closes/refreshes tab — never lose progress
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', savePosition)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') savePosition()
  })
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

  const coverOpId = loadOpId

  try {
    let url: string
    if (book.id.startsWith('lb:') || book.id.startsWith('fs:')) {
      return
    } else if (book.id.startsWith('ub:')) {
      const slug = book.id.split(':')[2] ?? ''
      url = userBookCoverUrl(slug)
    } else {
      url = coverUrl(book.id)
    }

    const response = await fetch(url, { credentials: 'include', redirect: 'follow' })
    if (!response.ok || loadOpId !== coverOpId) return

    const contentType = response.headers.get('Content-Type') || 'image/jpeg'
    if (contentType.includes('svg')) return

    const blob = await response.blob()
    if (loadOpId !== coverOpId) return // book changed during fetch — discard
    coverBlobUrl = URL.createObjectURL(blob)
    coverMimeType = contentType
  } catch {
    // Cover fetch failed — skip artwork
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
    const dur = isFinite(audio.duration) ? audio.duration : 0
    const pos = isFinite(audio.currentTime) ? audio.currentTime : 0
    if (dur > 0) {
      navigator.mediaSession.setPositionState({
        duration: dur,
        position: Math.min(pos, dur),
        playbackRate: audio.playbackRate || 1,
      })
    }
  } catch {
    // setPositionState can throw in some browsers
  }
}

// ── Resolve audio source (local or server) ──────────────────────────────────

async function resolveAudioSrc(bookId: string, trackIndex: number): Promise<string> {
  // Filesystem book (scanned from device, ExternalStorage)
  if (bookId.startsWith('fs:')) {
    const track = tracks.value[trackIndex]
    if (!track?.path) return ''
    try {
      const uri = await Filesystem.getUri({
        path: track.path,
        directory: Directory.ExternalStorage,
      })
      playingOffline.value = true
      return Capacitor.convertFileSrc(uri.uri)
    } catch {
      return ''
    }
  }
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
  // If offline — server URL won't work, tell user
  const { isOnline } = useNetwork()
  if (!isOnline.value) {
    toast.error(t('player.unavailableOffline'))
    playingOffline.value = false
    return ''
  }
  playingOffline.value = false
  return audioUrl(bookId, trackIndex)
}

// ── Actions ─────────────────────────────────────────────────────────────────

function restorePosition(bookId: string, startTrackIndex?: number): { trackIndex: number; seekPos: number } {
  if (startTrackIndex !== undefined) {
    return { trackIndex: startTrackIndex, seekPos: 0 }
  }
  try {
    const saved = localStorage.getItem(`${STORAGE.POSITION_PREFIX}${bookId}`)
    if (saved) {
      const pos = JSON.parse(saved)
      return {
        trackIndex: pos.track_index >= 0 ? pos.track_index : 0,
        seekPos: isFinite(pos.position) && pos.position >= 0 ? pos.position : 0,
      }
    }
  } catch {
    /* corrupted */
  }
  return { trackIndex: 0, seekPos: 0 }
}

async function loadBook(book: Book, startTrackIndex?: number, autoplay = true) {
  trackEvent('player_load_book', { bookId: book.id })
  const opId = ++loadOpId
  playOpId++ // Cancel any in-flight playTrack
  nextTrackUrl = null
  nextTrackIndex = null

  // Stop current audio immediately — no overlap between books
  if (audio && !audio.paused) {
    savePosition()
    audio.pause()
  }

  if (activeSessionBook && activeSessionBook !== book.title) {
    api.stopSession(activeSessionBook).catch(() => {})
    activeSessionBook = null
  }
  isLoading.value = true
  audioError.value = false
  currentBook.value = book
  isPlayerVisible.value = true
  try {
    localStorage.setItem(STORAGE.LAST_PLAYED, JSON.stringify({ id: book.id, title: book.title, author: book.author }))
  } catch {
    /* full */
  }
  isFullscreen.value = true

  try {
    const isFsBook = book.id.startsWith('fs:')
    const isLocalBook = book.id.startsWith('lb:')
    const isUserBook = book.id.startsWith('ub:')
    const { isOnline } = useNetwork()

    if (isFsBook) {
      // Filesystem book: load from persistent scanner storage
      const { getFsBook } = useFileScanner()
      const fsMeta = getFsBook(book.id)
      if (!fsMeta) throw new Error('Filesystem book not found')
      tracks.value = fsMeta.tracks.map((t) => ({
        index: t.index,
        filename: t.filename,
        path: t.path,
        duration: t.duration,
      }))
      playingOffline.value = true
      currentTrackIndex.value = 0

      const { trackIndex: rawIdx, seekPos } = restorePosition(book.id, startTrackIndex)
      const boundedIdx = rawIdx >= 0 && rawIdx < tracks.value.length ? rawIdx : 0
      currentTrackIndex.value = boundedIdx

      const a = ensureAudio()
      const fsUrl = await resolveAudioSrc(book.id, boundedIdx)
      if (loadOpId !== opId) return
      a.src = fsUrl || ''
      a.load()

      if (autoplay) {
        if (seekPos > 0) {
          const onLoaded = () => {
            a.removeEventListener('loadedmetadata', onLoaded)
            if (loadOpId !== opId) return
            a.currentTime = seekPos
            currentTime.value = seekPos
            a.play().catch((e) => console.warn('Auto-play blocked:', e))
          }
          a.addEventListener('loadedmetadata', onLoaded)
        } else {
          a.play().catch((e) => console.warn('Auto-play blocked:', e))
        }
      }

      updateMediaSession()
      preloadNextTrack()
      isLoading.value = false
      return
    }

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

      const { trackIndex: rawIdx, seekPos } = restorePosition(book.id, startTrackIndex)
      const boundedIdx = rawIdx >= 0 && rawIdx < tracks.value.length ? rawIdx : 0
      currentTrackIndex.value = boundedIdx

      const a = ensureAudio()
      const localUrl = await getLocalUrl(book.id, boundedIdx)
      if (loadOpId !== opId) return
      a.src = localUrl || ''
      a.load()

      if (autoplay) {
        if (seekPos > 0) {
          const onLoaded = () => {
            a.removeEventListener('loadedmetadata', onLoaded)
            if (loadOpId !== opId) return // stale — don't seek or play
            a.currentTime = seekPos
            currentTime.value = seekPos
            a.play().catch((e) => console.warn('Auto-play blocked:', e))
          }
          a.addEventListener('loadedmetadata', onLoaded)
        } else {
          a.play().catch((e) => console.warn('Auto-play blocked:', e))
        }
      }

      await loadCoverBlobUrl(book)
      if (loadOpId !== opId) return
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
      try {
        const ubSlug = isUserBook ? (book.id.split(':')[2] ?? '') : ''
        const res = isUserBook ? await api.getUserBookTracks(ubSlug) : await api.getBookTracks(book.id)
        if (loadOpId !== opId) return
        tracks.value = res.tracks
        // Cache for offline
        localData.setTrackMeta(book.id, res.tracks).catch(() => {})
      } catch {
        // Offline fallback — try cached track metadata
        const cached = await localData.getTrackMeta(book.id)
        if (loadOpId !== opId) return
        if (cached && cached.length) {
          tracks.value = cached
        } else {
          throw new Error('No tracks available offline')
        }
      }
    }

    // Restore saved position (skip if explicit startTrackIndex given)
    let pos = { track_index: startTrackIndex ?? 0, position: 0 }
    if (startTrackIndex === undefined) {
      try {
        pos = await api.getPlaybackPosition(book.id)
      } catch {
        // Offline — try IndexedDB first, then localStorage
        try {
          const idbPos = await localData.getPosition(book.id)
          if (idbPos) {
            pos = idbPos
          } else {
            const savedPos = localStorage.getItem(`${STORAGE.POSITION_PREFIX}${book.id}`)
            if (savedPos) pos = JSON.parse(savedPos)
          }
        } catch {
          try {
            const savedPos = localStorage.getItem(`${STORAGE.POSITION_PREFIX}${book.id}`)
            if (savedPos) pos = JSON.parse(savedPos)
          } catch {
            /* corrupted localStorage */
          }
        }
      }
      if (loadOpId !== opId) return
    }
    const { trackIndex: rawIdx, seekPos } = {
      trackIndex: pos.track_index >= 0 && pos.track_index < tracks.value.length ? pos.track_index : 0,
      seekPos: isFinite(pos.position) && pos.position >= 0 ? pos.position : 0,
    }
    const boundedIdx = rawIdx >= 0 && rawIdx < tracks.value.length ? rawIdx : 0
    currentTrackIndex.value = boundedIdx

    const a = ensureAudio()
    a.src = await resolveAudioSrc(book.id, boundedIdx)
    if (loadOpId !== opId) return
    a.load()

    // Seek to saved position after metadata loads, THEN play
    if (autoplay) {
      if (seekPos > 0) {
        const onLoaded = () => {
          a.removeEventListener('loadedmetadata', onLoaded)
          if (loadOpId !== opId) return // stale — don't seek or play
          a.currentTime = seekPos
          currentTime.value = seekPos
          a.play().catch((e) => console.warn('Auto-play blocked:', e))
        }
        a.addEventListener('loadedmetadata', onLoaded)
      } else {
        a.play().catch((e) => console.warn('Auto-play blocked:', e))
      }
    }

    await loadCoverBlobUrl(book)
    if (loadOpId !== opId) return
    updateMediaSession()
    preloadNextTrack()
  } catch {
    if (loadOpId === opId) {
      isLoading.value = false
      toast.error(t('player.tracksLoadError'))
    }
  }
}

async function playTrack(index: number, seekTo?: number) {
  if (!currentBook.value || index < 0 || index >= tracks.value.length) return

  const opId = ++playOpId

  savePosition()

  // Stop current audio immediately — no overlap between tracks (AIMP-style)
  const a = ensureAudio()
  a.pause()

  currentTrackIndex.value = index
  // Don't reset currentTime visually — keep old position until new track loads (AIMP-style)
  audioError.value = false
  isLoading.value = true

  if (nextTrackUrl && nextTrackIndex === index) {
    a.src = nextTrackUrl
  } else {
    const src = await resolveAudioSrc(currentBook.value.id, index)
    if (playOpId !== opId) return // stale — newer operation started
    a.src = src
  }
  nextTrackUrl = null
  nextTrackIndex = null

  a.load()

  // Seek after metadata loads if requested, THEN play
  if (seekTo !== undefined && seekTo > 0) {
    const onLoaded = () => {
      a.removeEventListener('loadedmetadata', onLoaded)
      if (playOpId !== opId) return // stale — don't seek or play
      a.currentTime = seekTo
      currentTime.value = seekTo
      a.play().catch((e) => {
        if (e instanceof DOMException && e.name === 'AbortError') return
        if (playOpId === opId) toast.error(t('player.playbackError'))
      })
    }
    a.addEventListener('loadedmetadata', onLoaded)
  } else {
    a.play().catch((e) => {
      if (e instanceof DOMException && e.name === 'AbortError') return
      if (playOpId === opId) toast.error(t('player.playbackError'))
    })
  }
  updateMediaSession()
  preloadNextTrack()
}

function togglePlay() {
  // If in error state, retry instead of play
  if (audioError.value) {
    retryAudio()
    return
  }
  const a = ensureAudio()
  if (!a.src) return
  if (a.paused) {
    trackEvent('player_play')
    a.play().catch((e) => {
      if (e instanceof DOMException && e.name === 'AbortError') return
      toast.error(t('player.playbackError'))
    })
  } else {
    trackEvent('player_pause')
    a.pause()
  }
}

function seek(sec: number) {
  if (!isFinite(sec)) return
  const a = ensureAudio()
  a.currentTime = Math.max(0, Math.min(sec, a.duration || 0))
  currentTime.value = a.currentTime
}

function startSeek() {
  isSeeking = true
}

function endSeek(sec: number) {
  seek(sec)
  // Always clear — even if seek throws, seeking must not stay locked
  isSeeking = false
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
  if (!isFinite(v)) return
  volume.value = Math.max(0, Math.min(1, v))
  if (audio) audio.volume = volume.value
  localStorage.setItem(STORAGE.VOLUME, String(volume.value))
}

function setPlaybackRate(rate: number) {
  if (!isFinite(rate) || rate <= 0) return
  playbackRate.value = rate
  if (audio) audio.playbackRate = rate
  localStorage.setItem(STORAGE.PLAYBACK_RATE, String(rate))
  updatePositionState()
}

function skipForward(seconds = 15) {
  if (!audio || isLoading.value) return
  const newTime = currentTime.value + seconds
  if (newTime >= (audio.duration || Infinity)) {
    nextTrack()
  } else {
    seek(newTime)
  }
}

function skipBackward(seconds = 15) {
  if (!audio || isLoading.value) return
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
    sleepAtTrackEnd = false
    return
  }
  if (minutes === -1) {
    // Pause at end of current track (flag checked in main ended handler)
    sleepAtTrackEnd = true
    sleepTimer.value = 0
    return
  }
  if (!isFinite(minutes) || minutes < 0) return
  sleepAtTrackEnd = false
  sleepTimer.value = Math.ceil(minutes)
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
  // Cancel all in-flight async operations
  loadOpId++
  playOpId++

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
  if (saveApiDebounce) {
    clearTimeout(saveApiDebounce)
    saveApiDebounce = null
  }
  setSleepTimer(null)
  nextTrackUrl = null
  nextTrackIndex = null
  isSeeking = false
  audioError.value = false
  if (audio) {
    audio.pause()
    audio.src = ''
  }
  isPlaying.value = false
  isPlayerVisible.value = false
  isFullscreen.value = false
  currentBook.value = null
  tracks.value = []
  currentTrackIndex.value = 0
  currentTime.value = 0
  duration.value = 0
}

async function preloadNextTrack() {
  if (preloadInProgress || !currentBook.value) return
  // No preload for filesystem books on web (no Capacitor)
  if (currentBook.value.id.startsWith('fs:') && !Capacitor.isNativePlatform()) return
  preloadInProgress = true
  const bookId = currentBook.value.id
  const currentLoadOp = loadOpId
  const nextIdx = currentTrackIndex.value + 1
  if (nextIdx >= tracks.value.length) {
    nextTrackUrl = null
    nextTrackIndex = null
    preloadInProgress = false
    return
  }
  try {
    const url = await resolveAudioSrc(bookId, nextIdx)
    // Only apply if book AND load operation haven't changed during async resolve
    if (currentBook.value?.id === bookId && loadOpId === currentLoadOp && url) {
      nextTrackUrl = url
      nextTrackIndex = nextIdx
    }
  } catch {
    nextTrackUrl = null
    nextTrackIndex = null
  } finally {
    preloadInProgress = false
  }
}

function retryAudio() {
  if (!audio || !currentBook.value) return
  const opId = playOpId // Capture current opId
  audioError.value = false
  isLoading.value = true
  audio.load()
  audio.play().catch((e) => {
    if (playOpId !== opId) return // Stale — ignore
    if (e instanceof DOMException && e.name === 'AbortError') return
    audioError.value = true
    isLoading.value = false
    toast.error(t('player.playbackError'))
  })
}

function skipErrorTrack() {
  audioError.value = false
  nextTrack()
}

// ── Format helpers ──────────────────────────────────────────────────────────

function formatTime(sec: number): string {
  if (!sec || !isFinite(sec) || sec < 0) return '0:00'
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
    playerState,

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
