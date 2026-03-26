import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ── Mocks (before importing usePlayer) ─────────────────────────────────────

vi.mock('../api', () => ({
  api: {
    getBookTracks: vi.fn(),
    getPlaybackPosition: vi.fn(),
    setPlaybackPosition: vi.fn().mockResolvedValue(undefined),
    setProgress: vi.fn().mockResolvedValue(undefined),
    startSession: vi.fn().mockResolvedValue(undefined),
    stopSession: vi.fn().mockResolvedValue(undefined),
    getUserBookTracks: vi.fn(),
  },
  audioUrl: vi.fn((_id: string, _idx: number) => 'http://test/audio.mp3'),
  coverUrl: vi.fn((id: string) => `http://test/books/${id}/cover`),
  userBookCoverUrl: vi.fn((slug: string) => `http://test/user/books/${slug}/cover`),
}))

vi.mock('./useDownloads', () => ({
  useDownloads: () => ({
    isNative: { value: false },
    isBookDownloaded: () => false,
    isTrackDownloaded: () => false,
    getLocalAudioUrl: vi.fn(),
    meta: { value: { books: {} } },
  }),
}))

vi.mock('./useLocalBooks', () => ({
  useLocalBooks: () => ({
    getLocalBook: vi.fn(),
    getLocalAudioUrl: vi.fn(),
  }),
}))

vi.mock('./useLocalData', () => ({
  useLocalData: () => ({
    setPosition: vi.fn().mockResolvedValue(undefined),
    getPosition: vi.fn().mockResolvedValue(undefined),
    setProgress: vi.fn().mockResolvedValue(undefined),
    getProgress: vi.fn().mockResolvedValue(undefined),
    getTrackMeta: vi.fn().mockResolvedValue(undefined),
    setTrackMeta: vi.fn().mockResolvedValue(undefined),
  }),
}))

vi.mock('./useNetwork', () => ({
  useNetwork: () => ({
    isOnline: { value: true },
  }),
}))

vi.mock('./useToast', () => ({
  useToast: () => ({
    toasts: { value: [] },
    add: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  }),
}))

vi.mock('./useTelemetry', () => ({
  useTracking: () => ({
    track: vi.fn(),
    trackFirstAudio: vi.fn(),
  }),
}))

// Stub MediaMetadata (not available in JSDOM)
vi.stubGlobal(
  'MediaMetadata',
  class MediaMetadata {
    title?: string
    artist?: string
    album?: string
    artwork?: { src: string; sizes: string; type: string }[]
    constructor(init: Record<string, unknown>) {
      Object.assign(this, init)
    }
  },
)

// Stub HTMLAudioElement
function createMockAudio() {
  let _src = ''
  let _currentTime = 0
  let _duration = 0
  let _paused = true
  let _volume = 1
  let _playbackRate = 1
  const listeners: Record<string, Array<(...args: unknown[]) => void>> = {}

  return {
    get src() {
      return _src
    },
    set src(v: string) {
      _src = v
    },
    get currentTime() {
      return _currentTime
    },
    set currentTime(v: number) {
      _currentTime = v
    },
    get duration() {
      return _duration
    },
    set duration(v: number) {
      _duration = v
    },
    get paused() {
      return _paused
    },
    get volume() {
      return _volume
    },
    set volume(v: number) {
      _volume = v
    },
    get playbackRate() {
      return _playbackRate
    },
    set playbackRate(v: number) {
      _playbackRate = v
    },
    load: vi.fn(),
    play: vi.fn(() => {
      _paused = false
      return Promise.resolve()
    }),
    pause: vi.fn(() => {
      _paused = true
    }),
    addEventListener: vi.fn((evt: string, fn: (...args: unknown[]) => void) => {
      ;(listeners[evt] ??= []).push(fn)
    }),
    removeEventListener: vi.fn((evt: string, fn: (...args: unknown[]) => void) => {
      listeners[evt] = (listeners[evt] ?? []).filter((f) => f !== fn)
    }),
    _emit(evt: string) {
      ;(listeners[evt] ?? []).forEach((fn) => fn())
    },
    _setDuration(d: number) {
      _duration = d
    },
    _listeners: listeners,
  }
}

// Create once — the module's singleton `audio` will hold this reference permanently
const mockAudio = createMockAudio()

vi.stubGlobal('Audio', function () {
  return mockAudio
})

import { usePlayer } from './usePlayer'

describe('usePlayer', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    localStorage.clear()
    // Reset player state
    const p = usePlayer()
    p.closePlayer()
    // Reset mock call counts but keep the same object reference
    mockAudio.load.mockClear()
    mockAudio.play.mockClear()
    mockAudio.pause.mockClear()
    mockAudio.addEventListener.mockClear()
    mockAudio.removeEventListener.mockClear()
    mockAudio._setDuration(0)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // ── formatTime ──────────────────────────────────────────────────────────
  describe('formatTime', () => {
    it('formats 0 as 0:00', () => {
      expect(usePlayer().formatTime(0)).toBe('0:00')
    })

    it('formats 65 seconds as 1:05', () => {
      expect(usePlayer().formatTime(65)).toBe('1:05')
    })

    it('formats 3661 as 61:01', () => {
      expect(usePlayer().formatTime(3661)).toBe('61:01')
    })

    it('returns 0:00 for NaN', () => {
      expect(usePlayer().formatTime(NaN)).toBe('0:00')
    })

    it('returns 0:00 for Infinity', () => {
      expect(usePlayer().formatTime(Infinity)).toBe('0:00')
    })

    it('returns 0:00 for negative values', () => {
      expect(usePlayer().formatTime(-5)).toBe('0:00')
      expect(usePlayer().formatTime(-100)).toBe('0:00')
    })
  })

  // ── seek ────────────────────────────────────────────────────────────────
  describe('seek', () => {
    it('clamps to 0 when seeking negative', () => {
      const p = usePlayer()
      // Need to init audio first
      p.setVolume(1) // force ensureAudio on next real action
      mockAudio._setDuration(100)
      p.seek(-10)
      expect(p.currentTime.value).toBe(0)
    })

    it('clamps to duration when seeking past end', () => {
      const p = usePlayer()
      mockAudio._setDuration(100)
      p.seek(200)
      expect(p.currentTime.value).toBe(100)
    })

    it('seeks to exact time within range', () => {
      const p = usePlayer()
      mockAudio._setDuration(100)
      p.seek(50)
      expect(p.currentTime.value).toBe(50)
    })
  })

  // ── setVolume ───────────────────────────────────────────────────────────
  describe('setVolume', () => {
    it('clamps volume to 0', () => {
      const p = usePlayer()
      p.setVolume(-0.5)
      expect(p.volume.value).toBe(0)
    })

    it('clamps volume to 1', () => {
      const p = usePlayer()
      p.setVolume(1.5)
      expect(p.volume.value).toBe(1)
    })

    it('sets volume within range', () => {
      const p = usePlayer()
      p.setVolume(0.5)
      expect(p.volume.value).toBe(0.5)
    })

    it('persists volume to localStorage', () => {
      const p = usePlayer()
      p.setVolume(0.3)
      expect(localStorage.getItem('leerio_volume')).toBe('0.3')
    })
  })

  // ── setPlaybackRate ─────────────────────────────────────────────────────
  describe('setPlaybackRate', () => {
    it('persists to localStorage', () => {
      const p = usePlayer()
      p.setPlaybackRate(1.5)
      expect(p.playbackRate.value).toBe(1.5)
      expect(localStorage.getItem('leerio_playback_rate')).toBe('1.5')
    })
  })

  // ── track navigation ───────────────────────────────────────────────────
  describe('prevTrack', () => {
    it('restarts track if >3s in', () => {
      const p = usePlayer()
      p.tracks.value = [
        { index: 0, filename: 'a.mp3', path: '', duration: 60 },
        { index: 1, filename: 'b.mp3', path: '', duration: 60 },
      ]
      p.currentTrackIndex.value = 1
      p.currentTime.value = 10
      mockAudio._setDuration(60)
      p.prevTrack()
      expect(p.currentTime.value).toBe(0)
      // Still on same track
      expect(p.currentTrackIndex.value).toBe(1)
    })
  })

  describe('nextTrack', () => {
    it('pauses at end of book (last track)', () => {
      const p = usePlayer()
      p.tracks.value = [{ index: 0, filename: 'a.mp3', path: '', duration: 60 }]
      p.currentTrackIndex.value = 0
      p.currentBook.value = {
        id: 'test',
        folder: '',
        category: '',
        author: '',
        title: 'Test',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      }
      mockAudio._setDuration(60)
      p.nextTrack()
      expect(p.isPlaying.value).toBe(false)
    })
  })

  // ── skipForward / skipBackward ──────────────────────────────────────────
  describe('skipForward', () => {
    it('seeks forward by default 15s', () => {
      const p = usePlayer()
      mockAudio._setDuration(100)
      p.currentTime.value = 10
      p.isLoading.value = false
      p.skipForward()
      expect(p.currentTime.value).toBe(25)
    })

    it('goes to next track if skip exceeds duration', async () => {
      const p = usePlayer()
      p.tracks.value = [
        { index: 0, filename: 'a.mp3', path: '', duration: 20 },
        { index: 1, filename: 'b.mp3', path: '', duration: 60 },
      ]
      p.currentTrackIndex.value = 0
      p.currentBook.value = {
        id: 'test',
        folder: '',
        category: '',
        author: '',
        title: 'Test',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      }
      mockAudio._setDuration(20)
      p.currentTime.value = 10
      p.isLoading.value = false
      p.skipForward()
      // nextTrack → playTrack is async (resolveAudioSrc), flush microtasks
      await vi.advanceTimersByTimeAsync(0)
      expect(p.currentTrackIndex.value).toBe(1)
    })
  })

  describe('skipBackward', () => {
    it('seeks backward by default 15s', () => {
      const p = usePlayer()
      mockAudio._setDuration(100)
      p.currentTime.value = 30
      p.isLoading.value = false
      p.skipBackward()
      expect(p.currentTime.value).toBe(15)
    })

    it('clamps to 0 if skip goes negative on first track', () => {
      const p = usePlayer()
      p.tracks.value = [{ index: 0, filename: 'a.mp3', path: '', duration: 60 }]
      p.currentTrackIndex.value = 0
      mockAudio._setDuration(60)
      p.currentTime.value = 5
      p.isLoading.value = false
      p.skipBackward()
      expect(p.currentTime.value).toBe(0)
    })
  })

  // ── sleep timer ─────────────────────────────────────────────────────────
  describe('setSleepTimer', () => {
    it('sets countdown timer', () => {
      const p = usePlayer()
      p.setSleepTimer(5)
      expect(p.sleepTimer.value).toBe(5)
    })

    it('counts down each minute', () => {
      const p = usePlayer()
      p.setSleepTimer(3)
      vi.advanceTimersByTime(60_000)
      expect(p.sleepTimer.value).toBe(2)
      vi.advanceTimersByTime(60_000)
      expect(p.sleepTimer.value).toBe(1)
    })

    it('pauses audio when timer reaches 0', () => {
      const p = usePlayer()
      p.setSleepTimer(1)
      mockAudio.pause.mockClear()
      vi.advanceTimersByTime(60_000)
      expect(p.sleepTimer.value).toBe(null)
      expect(mockAudio.pause).toHaveBeenCalled()
    })

    it('cancels timer with null', () => {
      const p = usePlayer()
      p.setSleepTimer(5)
      p.setSleepTimer(null)
      expect(p.sleepTimer.value).toBe(null)
    })
  })

  // ── computed: totalDuration / totalElapsed / overallProgress ───────────
  describe('computed properties', () => {
    it('totalDuration sums all track durations', () => {
      const p = usePlayer()
      p.tracks.value = [
        { index: 0, filename: 'a.mp3', path: '', duration: 100 },
        { index: 1, filename: 'b.mp3', path: '', duration: 200 },
        { index: 2, filename: 'c.mp3', path: '', duration: 150 },
      ]
      expect(p.totalDuration.value).toBe(450)
    })

    it('totalElapsed = sum of prior tracks + currentTime', () => {
      const p = usePlayer()
      p.tracks.value = [
        { index: 0, filename: 'a.mp3', path: '', duration: 100 },
        { index: 1, filename: 'b.mp3', path: '', duration: 200 },
        { index: 2, filename: 'c.mp3', path: '', duration: 150 },
      ]
      p.currentTrackIndex.value = 2
      p.currentTime.value = 50
      expect(p.totalElapsed.value).toBe(350) // 100 + 200 + 50
    })

    it('overallProgress is 0 when no tracks', () => {
      const p = usePlayer()
      p.tracks.value = []
      expect(p.overallProgress.value).toBe(0)
    })

    it('overallProgress computes percentage', () => {
      const p = usePlayer()
      p.tracks.value = [
        { index: 0, filename: 'a.mp3', path: '', duration: 100 },
        { index: 1, filename: 'b.mp3', path: '', duration: 100 },
      ]
      p.currentTrackIndex.value = 1
      p.currentTime.value = 0
      // 100/200 = 50%
      expect(p.overallProgress.value).toBe(50)
    })
  })

  // ── closePlayer ─────────────────────────────────────────────────────────
  describe('closePlayer', () => {
    it('resets all state', () => {
      const p = usePlayer()
      p.tracks.value = [{ index: 0, filename: 'a.mp3', path: '', duration: 60 }]
      p.currentTrackIndex.value = 0
      p.currentTime.value = 30
      p.isPlayerVisible.value = true
      p.closePlayer()
      expect(p.currentBook.value).toBe(null)
      expect(p.tracks.value).toEqual([])
      expect(p.currentTrackIndex.value).toBe(0)
      expect(p.currentTime.value).toBe(0)
      expect(p.isPlayerVisible.value).toBe(false)
      expect(p.isPlaying.value).toBe(false)
    })
  })

  // ── Media Session ─────────────────────────────────────────────────────
  describe('media session', () => {
    const mockMetadata = vi.fn()
    const mockSetActionHandler = vi.fn()
    const mockSetPositionState = vi.fn()

    let origCreateObjectURL: typeof URL.createObjectURL
    let origRevokeObjectURL: typeof URL.revokeObjectURL

    beforeEach(() => {
      origCreateObjectURL = URL.createObjectURL
      origRevokeObjectURL = URL.revokeObjectURL

      Object.defineProperty(navigator, 'mediaSession', {
        value: {
          _metadata: null,
          get metadata() {
            return this._metadata
          },
          set metadata(v: MediaMetadata) {
            this._metadata = v
            mockMetadata(v)
          },
          setActionHandler: mockSetActionHandler,
          setPositionState: mockSetPositionState,
        },
        writable: true,
        configurable: true,
      })
      mockMetadata.mockClear()
      mockSetActionHandler.mockClear()
      mockSetPositionState.mockClear()
    })

    afterEach(() => {
      URL.createObjectURL = origCreateObjectURL
      URL.revokeObjectURL = origRevokeObjectURL
    })

    const testBook = {
      id: '1',
      folder: 'test',
      category: 'test',
      author: 'Author',
      title: 'Title',
      reader: '',
      path: '',
      progress: 0,
      tags: [] as string[],
      note: '',
    }

    async function setupBookMocks(bookId = '1') {
      const { api } = await import('../api')
      vi.mocked(api.getBookTracks).mockResolvedValue({
        book_id: bookId,
        count: 1,
        tracks: [{ index: 0, filename: '01.mp3', path: '', duration: 60 }],
      })
      vi.mocked(api.getPlaybackPosition).mockResolvedValue({
        track_index: 0,
        position: 0,
      })
    }

    it('fetches cover and creates blob URL on loadBook', async () => {
      await setupBookMocks()

      const mockBlob = new Blob(['fake-image'], { type: 'image/jpeg' })
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          blob: () => Promise.resolve(mockBlob),
          headers: new Headers({ 'Content-Type': 'image/jpeg' }),
        }),
      )

      const mockBlobUrl = 'blob:http://localhost/fake-cover'
      URL.createObjectURL = vi.fn(() => mockBlobUrl)
      URL.revokeObjectURL = vi.fn()

      const p = usePlayer()
      await p.loadBook({ ...testBook, id: '1' })

      expect(mockMetadata).toHaveBeenCalled()
      const metadata = mockMetadata.mock.calls[0]![0]
      expect(metadata.artwork).toEqual([{ src: mockBlobUrl, sizes: '512x512', type: 'image/jpeg' }])
    })

    it('skips artwork when cover is SVG placeholder', async () => {
      await setupBookMocks('2')

      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          blob: () => Promise.resolve(new Blob(['<svg></svg>'], { type: 'image/svg+xml' })),
          headers: new Headers({ 'Content-Type': 'image/svg+xml' }),
        }),
      )

      const p = usePlayer()
      await p.loadBook({ ...testBook, id: '2' })

      expect(mockMetadata).toHaveBeenCalled()
      const metadata = mockMetadata.mock.calls[0]![0]
      expect(metadata.artwork).toBeUndefined()
    })

    it('omits artwork when cover fetch fails', async () => {
      await setupBookMocks('3')
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network error')))

      const p = usePlayer()
      await p.loadBook({ ...testBook, id: '3' })

      expect(mockMetadata).toHaveBeenCalled()
      const metadata = mockMetadata.mock.calls[0]![0]
      expect(metadata.artwork).toBeUndefined()
    })

    it('registers seekbackward handler with 10s default', async () => {
      await setupBookMocks('4')
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('no cover')))

      const p = usePlayer()
      await p.loadBook({ ...testBook, id: '4' })

      const seekbackwardCall = mockSetActionHandler.mock.calls.find((c: unknown[]) => c[0] === 'seekbackward')
      expect(seekbackwardCall).toBeTruthy()

      mockAudio._setDuration(120)
      p.currentTime.value = 50
      p.isLoading.value = false
      seekbackwardCall![1]({})
      expect(p.currentTime.value).toBe(40)
    })

    it('registers seekforward handler with 30s default', async () => {
      await setupBookMocks('5')
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('no cover')))

      const p = usePlayer()
      await p.loadBook({ ...testBook, id: '5' })

      const seekforwardCall = mockSetActionHandler.mock.calls.find((c: unknown[]) => c[0] === 'seekforward')
      expect(seekforwardCall).toBeTruthy()

      mockAudio._setDuration(120)
      p.currentTime.value = 20
      p.isLoading.value = false
      seekforwardCall![1]({})
      expect(p.currentTime.value).toBe(50)
    })

    it('calls setPositionState on play event', async () => {
      await setupBookMocks('6')
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('no cover')))

      const p = usePlayer()
      await p.loadBook({ ...testBook, id: '6' })

      mockSetPositionState.mockClear()
      mockAudio._setDuration(60)
      mockAudio._emit('play')

      expect(mockSetPositionState).toHaveBeenCalledWith({
        duration: 60,
        position: expect.any(Number),
        playbackRate: expect.any(Number),
      })
    })
  })

  // ── Regression: position 0 must not be saved during load ──────────────
  describe('position save guard', () => {
    it('does not save position 0 while loading', async () => {
      const { api } = await import('../api')
      const mockSetPos = api.setPlaybackPosition as ReturnType<typeof vi.fn>
      mockSetPos.mockClear()

      const p = usePlayer()
      p.currentBook.value = {
        id: 'guard-test',
        folder: '',
        category: '',
        author: '',
        title: 'Guard Test',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      }
      p.tracks.value = [{ index: 0, filename: 'a.mp3', path: '', duration: 300 }]
      p.currentTrackIndex.value = 0
      p.isLoading.value = true
      p.currentTime.value = 0

      // Simulate pause event calling savePosition internally —
      // trigger the save timer which calls savePosition
      mockAudio._emit('pause')

      // Position 0 during loading should NOT be saved to API
      expect(mockSetPos).not.toHaveBeenCalled()
    })

    it('saves position when not loading', async () => {
      const { api } = await import('../api')
      const mockSetPos = api.setPlaybackPosition as ReturnType<typeof vi.fn>
      mockSetPos.mockClear()

      // Simulate logged-in state so API save is not skipped
      Object.defineProperty(document, 'cookie', { value: 'access_token=test', configurable: true })

      const p = usePlayer()
      p.currentBook.value = {
        id: 'save-test',
        folder: '',
        category: '',
        author: '',
        title: 'Save Test',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      }
      p.tracks.value = [{ index: 0, filename: 'a.mp3', path: '', duration: 300 }]
      p.currentTrackIndex.value = 0
      p.isLoading.value = false
      p.currentTime.value = 120

      mockAudio._emit('pause')

      // API save is debounced by 1s
      vi.advanceTimersByTime(1_100)

      // Position 120 with isLoading=false should be saved
      expect(mockSetPos).toHaveBeenCalledWith('save-test', 0, 120, 'a.mp3')
    })
  })

  // ── startSeek / endSeek ─────────────────────────────────────────────────
  describe('startSeek / endSeek', () => {
    it('startSeek suppresses timeupdate, endSeek seeks and resumes updates', () => {
      const p = usePlayer()
      mockAudio._setDuration(100)
      p.currentTime.value = 10

      // Start seeking — timeupdate should be suppressed
      p.startSeek()
      mockAudio.currentTime = 50
      mockAudio._emit('timeupdate')
      // currentTime should NOT have updated to 50 because isSeeking is true
      expect(p.currentTime.value).toBe(10)

      // End seeking — should seek to given position and resume updates
      p.endSeek(30)
      expect(p.currentTime.value).toBe(30)

      // After endSeek, timeupdate should work again
      mockAudio.currentTime = 40
      mockAudio._emit('timeupdate')
      expect(p.currentTime.value).toBe(40)
    })
  })

  // ── openFullscreen / closeFullscreen ──────────────────────────────────
  describe('openFullscreen / closeFullscreen', () => {
    it('openFullscreen sets isFullscreen to true', () => {
      const p = usePlayer()
      p.closeFullscreen() // ensure clean state
      expect(p.isFullscreen.value).toBe(false)
      p.openFullscreen()
      expect(p.isFullscreen.value).toBe(true)
    })

    it('closeFullscreen sets isFullscreen to false', () => {
      const p = usePlayer()
      p.openFullscreen()
      expect(p.isFullscreen.value).toBe(true)
      p.closeFullscreen()
      expect(p.isFullscreen.value).toBe(false)
    })
  })

  // ── setSleepTimer with -1 (end-of-track mode) ────────────────────────
  describe('setSleepTimer end-of-track', () => {
    it('setSleepTimer(-1) sets sleepTimer to 0 and pauses at track end', () => {
      const p = usePlayer()
      p.tracks.value = [
        { index: 0, filename: 'a.mp3', path: '', duration: 60 },
        { index: 1, filename: 'b.mp3', path: '', duration: 60 },
      ]
      p.currentTrackIndex.value = 0
      p.currentBook.value = {
        id: 'sleep-test',
        folder: '',
        category: '',
        author: '',
        title: 'Sleep Test',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      }

      p.setSleepTimer(-1)
      expect(p.sleepTimer.value).toBe(0)

      // Simulate track ending — should pause instead of going to next track
      mockAudio.pause.mockClear()
      mockAudio._emit('ended')
      expect(p.isPlaying.value).toBe(false)
      // Should NOT have advanced to next track
      expect(p.currentTrackIndex.value).toBe(0)
    })

    it('sleepAtTrackEnd is cleared by setSleepTimer(null)', () => {
      const p = usePlayer()
      p.tracks.value = [
        { index: 0, filename: 'a.mp3', path: '', duration: 60 },
        { index: 1, filename: 'b.mp3', path: '', duration: 60 },
      ]
      p.currentTrackIndex.value = 0
      p.currentBook.value = {
        id: 'sleep-cancel',
        folder: '',
        category: '',
        author: '',
        title: 'Sleep Cancel',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      }

      p.setSleepTimer(-1)
      expect(p.sleepTimer.value).toBe(0)

      // Cancel the sleep timer
      p.setSleepTimer(null)
      expect(p.sleepTimer.value).toBe(null)

      // Now ended should call nextTrack, not pause
      mockAudio._emit('ended')
      // nextTrack would try to playTrack(1) which is async
    })
  })

  // ── retryAudio ────────────────────────────────────────────────────────
  describe('retryAudio', () => {
    it('clears audioError and calls load + play', () => {
      const p = usePlayer()
      p.currentBook.value = {
        id: 'retry-test',
        folder: '',
        category: '',
        author: '',
        title: 'Retry Test',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      }
      p.audioError.value = true

      mockAudio.load.mockClear()
      mockAudio.play.mockClear()

      p.retryAudio()

      expect(p.audioError.value).toBe(false)
      expect(p.isLoading.value).toBe(true)
      expect(mockAudio.load).toHaveBeenCalled()
      expect(mockAudio.play).toHaveBeenCalled()
    })

    it('returns early when no book is loaded', () => {
      const p = usePlayer()
      p.currentBook.value = null
      p.audioError.value = true

      mockAudio.load.mockClear()
      mockAudio.play.mockClear()

      p.retryAudio()

      // audioError should remain true (early return, no action)
      expect(p.audioError.value).toBe(true)
      expect(mockAudio.load).not.toHaveBeenCalled()
      expect(mockAudio.play).not.toHaveBeenCalled()
    })
  })

  // ── skipErrorTrack ────────────────────────────────────────────────────
  describe('skipErrorTrack', () => {
    it('clears audioError and advances to next track', async () => {
      const p = usePlayer()
      p.tracks.value = [
        { index: 0, filename: 'a.mp3', path: '', duration: 60 },
        { index: 1, filename: 'b.mp3', path: '', duration: 60 },
      ]
      p.currentTrackIndex.value = 0
      p.currentBook.value = {
        id: 'skip-err',
        folder: '',
        category: '',
        author: '',
        title: 'Skip Error',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      }
      p.audioError.value = true

      p.skipErrorTrack()
      await vi.advanceTimersByTimeAsync(0)

      expect(p.audioError.value).toBe(false)
      expect(p.currentTrackIndex.value).toBe(1)
    })
  })

  // ── prevTrack goes to previous when ≤3s ──────────────────────────────
  describe('prevTrack (go to previous track)', () => {
    it('goes to previous track when currentTime <= 3 and not on first track', async () => {
      const p = usePlayer()
      p.tracks.value = [
        { index: 0, filename: 'a.mp3', path: '', duration: 60 },
        { index: 1, filename: 'b.mp3', path: '', duration: 60 },
      ]
      p.currentTrackIndex.value = 1
      p.currentBook.value = {
        id: 'prev-test',
        folder: '',
        category: '',
        author: '',
        title: 'Prev Test',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      }
      p.currentTime.value = 2 // <= 3 seconds
      mockAudio._setDuration(60)

      p.prevTrack()
      await vi.advanceTimersByTimeAsync(0)

      expect(p.currentTrackIndex.value).toBe(0)
    })

    it('does nothing when <=3s on first track', () => {
      const p = usePlayer()
      p.tracks.value = [{ index: 0, filename: 'a.mp3', path: '', duration: 60 }]
      p.currentTrackIndex.value = 0
      p.currentTime.value = 2
      mockAudio._setDuration(60)

      p.prevTrack()

      // Should stay on track 0 with same time (no seek, no prev)
      expect(p.currentTrackIndex.value).toBe(0)
    })
  })

  // ── skipBackward goes to prev track ───────────────────────────────────
  describe('skipBackward (prev track on underflow)', () => {
    it('goes to previous track when skip goes negative on non-first track', async () => {
      const p = usePlayer()
      p.tracks.value = [
        { index: 0, filename: 'a.mp3', path: '', duration: 60 },
        { index: 1, filename: 'b.mp3', path: '', duration: 60 },
      ]
      p.currentTrackIndex.value = 1
      p.currentBook.value = {
        id: 'skipback-test',
        folder: '',
        category: '',
        author: '',
        title: 'Skipback Test',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      }
      p.currentTime.value = 5
      mockAudio._setDuration(60)
      p.isLoading.value = false

      // Skip back 30 seconds from 5s => newTime = -25 => should go to prev track
      p.skipBackward(30)
      await vi.advanceTimersByTimeAsync(0)

      expect(p.currentTrackIndex.value).toBe(0)
    })
  })

  // ── togglePlay ────────────────────────────────────────────────────────
  describe('togglePlay', () => {
    it('plays when paused', () => {
      const p = usePlayer()
      // Set a src so togglePlay doesn't early-return
      mockAudio.src = 'http://test/audio.mp3'
      mockAudio.pause() // ensure paused
      mockAudio.play.mockClear()

      p.togglePlay()

      expect(mockAudio.play).toHaveBeenCalled()
    })

    it('pauses when playing', () => {
      const p = usePlayer()
      mockAudio.src = 'http://test/audio.mp3'
      // Simulate playing state
      mockAudio.play()
      mockAudio.pause.mockClear()

      p.togglePlay()

      expect(mockAudio.pause).toHaveBeenCalled()
    })

    it('does nothing when no src', () => {
      const p = usePlayer()
      mockAudio.src = ''
      mockAudio.play.mockClear()
      mockAudio.pause.mockClear()

      p.togglePlay()

      expect(mockAudio.play).not.toHaveBeenCalled()
      expect(mockAudio.pause).not.toHaveBeenCalled()
    })
  })

  // ── Edge cases: NaN/Infinity guards ─────────────────────────────────────
  describe('NaN/Infinity guards', () => {
    it('seek ignores NaN', () => {
      const p = usePlayer()
      mockAudio._setDuration(100)
      p.currentTime.value = 50
      p.seek(NaN)
      expect(p.currentTime.value).toBe(50)
    })

    it('seek ignores Infinity', () => {
      const p = usePlayer()
      mockAudio._setDuration(100)
      p.currentTime.value = 50
      p.seek(Infinity)
      expect(p.currentTime.value).toBe(50)
    })

    it('setVolume ignores NaN', () => {
      const p = usePlayer()
      p.setVolume(0.5)
      p.setVolume(NaN)
      expect(p.volume.value).toBe(0.5)
    })

    it('setPlaybackRate ignores NaN', () => {
      const p = usePlayer()
      p.setPlaybackRate(1.5)
      p.setPlaybackRate(NaN)
      expect(p.playbackRate.value).toBe(1.5)
    })

    it('setPlaybackRate ignores 0', () => {
      const p = usePlayer()
      p.setPlaybackRate(1.5)
      p.setPlaybackRate(0)
      expect(p.playbackRate.value).toBe(1.5)
    })

    it('setPlaybackRate ignores negative', () => {
      const p = usePlayer()
      p.setPlaybackRate(1.5)
      p.setPlaybackRate(-1)
      expect(p.playbackRate.value).toBe(1.5)
    })

    it('setSleepTimer ignores NaN', () => {
      const p = usePlayer()
      p.setSleepTimer(NaN)
      expect(p.sleepTimer.value).toBe(null)
    })

    it('setSleepTimer ignores negative (except -1)', () => {
      const p = usePlayer()
      p.setSleepTimer(-5)
      expect(p.sleepTimer.value).toBe(null)
    })

    it('setSleepTimer rounds up fractional minutes', () => {
      const p = usePlayer()
      p.setSleepTimer(2.3)
      expect(p.sleepTimer.value).toBe(3)
    })

    it('formatTime returns 0:00 for negative', () => {
      const p = usePlayer()
      expect(p.formatTime(-1)).toBe('0:00')
      expect(p.formatTime(-100)).toBe('0:00')
    })

    it('nextTrack is safe with empty tracks', () => {
      const p = usePlayer()
      p.tracks.value = []
      p.currentTrackIndex.value = 0
      p.currentBook.value = {
        id: 'test',
        folder: '',
        category: '',
        author: '',
        title: 'T',
        reader: '',
        path: '',
        progress: 0,
        tags: [],
        note: '',
      }
      mockAudio.pause.mockClear()
      p.nextTrack()
      // 0 < -1 is false → pauses
      expect(mockAudio.pause).toHaveBeenCalled()
    })

    it('prevTrack is no-op on first track with <3s', () => {
      const p = usePlayer()
      p.tracks.value = [{ index: 0, filename: 'a.mp3', path: '', duration: 60 }]
      p.currentTrackIndex.value = 0
      p.currentTime.value = 1
      const prevIndex = p.currentTrackIndex.value
      p.prevTrack()
      expect(p.currentTrackIndex.value).toBe(prevIndex)
    })

    it('closePlayer is safe to call twice', () => {
      const p = usePlayer()
      p.closePlayer()
      p.closePlayer()
      expect(p.currentBook.value).toBe(null)
      expect(p.tracks.value).toEqual([])
    })

    it('endSeek with NaN is safe (seek ignores it)', () => {
      const p = usePlayer()
      mockAudio._setDuration(100)
      p.currentTime.value = 50
      p.endSeek(NaN)
      // seek(NaN) is ignored, isSeeking cleared
      expect(p.currentTime.value).toBe(50)
    })
  })
})
