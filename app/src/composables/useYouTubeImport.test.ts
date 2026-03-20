import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api', () => ({
  api: {
    youtubeResolve: vi.fn(),
    youtubeStreamUrl: vi.fn((id: string) => `/api/youtube/stream/${id}`),
  },
}))

const mockAddLocalBook = vi.fn().mockResolvedValue({
  id: 'lb:test-uuid',
  title: 'Test',
  author: 'Author',
  tracks: [],
  addedAt: '2026-01-01',
})

vi.mock('./useLocalBooks', () => ({
  useLocalBooks: () => ({
    addLocalBook: mockAddLocalBook,
  }),
}))

// Mock @ffmpeg/ffmpeg
const mockFfmpegExec = vi.fn().mockResolvedValue(0)
const mockFfmpegWriteFile = vi.fn().mockResolvedValue(undefined)
const mockFfmpegReadFile = vi.fn().mockResolvedValue(new Uint8Array([0xff, 0xfb, 0x90, 0x00]))
const mockFfmpegTerminate = vi.fn()
const mockFfmpegLoad = vi.fn().mockResolvedValue(undefined)

vi.mock('@ffmpeg/ffmpeg', () => ({
  FFmpeg: class MockFFmpeg {
    load = mockFfmpegLoad
    exec = mockFfmpegExec
    writeFile = mockFfmpegWriteFile
    readFile = mockFfmpegReadFile
    terminate = mockFfmpegTerminate
  },
}))

vi.mock('@ffmpeg/util', () => ({
  fetchFile: vi.fn().mockResolvedValue(new Uint8Array([1, 2, 3])),
}))

import { useYouTubeImport } from './useYouTubeImport'
import { api } from '../api'

describe('useYouTubeImport', () => {
  beforeEach(() => {
    vi.mocked(api.youtubeResolve).mockReset()
  })

  it('starts in idle state', () => {
    const yt = useYouTubeImport()
    expect(yt.step.value).toBe('idle')
    expect(yt.progress.value).toBe(0)
    expect(yt.title.value).toBe('')
    expect(yt.author.value).toBe('')
  })

  it('resolve sets metadata from API', async () => {
    vi.mocked(api.youtubeResolve).mockResolvedValue({
      video_id: 'abc12345678',
      title: 'Test Book',
      author: 'Author',
      duration: 3600,
      thumbnail: 'https://img.youtube.com/thumb.jpg',
      chapters: [{ title: 'Ch 1', start: 0, end: 1800 }],
    })

    const yt = useYouTubeImport()
    await yt.resolve('https://youtube.com/watch?v=abc12345678')

    expect(yt.step.value).toBe('resolved')
    expect(yt.title.value).toBe('Test Book')
    expect(yt.author.value).toBe('Author')
    expect(yt.videoId.value).toBe('abc12345678')
    expect(yt.chapters.value).toHaveLength(1)
    expect(yt.duration.value).toBe(3600)
    expect(yt.thumbnail.value).toBe('https://img.youtube.com/thumb.jpg')
  })

  it('resolve handles API errors', async () => {
    vi.mocked(api.youtubeResolve).mockRejectedValue(new Error('400: Invalid URL'))

    const yt = useYouTubeImport()
    await yt.resolve('invalid')

    expect(yt.step.value).toBe('error')
    expect(yt.errorMessage.value).toContain('Invalid URL')
  })

  it('resolve sets step to resolving during fetch', async () => {
    let resolvePromise: ((v: unknown) => void) | null = null
    vi.mocked(api.youtubeResolve).mockImplementation(
      () => new Promise((r) => { resolvePromise = r }),
    )

    const yt = useYouTubeImport()
    const p = yt.resolve('https://youtube.com/watch?v=abc12345678')
    expect(yt.step.value).toBe('resolving')

    resolvePromise!({
      video_id: 'abc12345678',
      title: 'T',
      author: 'A',
      duration: 100,
      thumbnail: '',
      chapters: [],
    })
    await p
    expect(yt.step.value).toBe('resolved')
  })

  it('generateChapters splits evenly', () => {
    const yt = useYouTubeImport()
    const chapters = yt.generateChapters(3600, 600)
    expect(chapters).toHaveLength(6)
    expect(chapters[0]).toEqual({ title: 'Глава 1', start: 0, end: 600 })
    expect(chapters[5]).toEqual({ title: 'Глава 6', start: 3000, end: 3600 })
  })

  it('generateChapters handles non-divisible duration', () => {
    const yt = useYouTubeImport()
    const chapters = yt.generateChapters(700, 600)
    expect(chapters).toHaveLength(2)
    expect(chapters[1]).toEqual({ title: 'Глава 2', start: 600, end: 700 })
  })

  it('generateChapters returns empty for 0 duration', () => {
    const yt = useYouTubeImport()
    expect(yt.generateChapters(0, 600)).toEqual([])
  })

  it('reset clears all state', () => {
    const yt = useYouTubeImport()
    yt.title.value = 'Something'
    yt.author.value = 'Someone'
    yt.step.value = 'error' as typeof yt.step.value
    yt.errorMessage.value = 'fail'
    yt.videoId.value = 'abc'
    yt.reset()
    expect(yt.step.value).toBe('idle')
    expect(yt.title.value).toBe('')
    expect(yt.author.value).toBe('')
    expect(yt.videoId.value).toBe('')
    expect(yt.errorMessage.value).toBe('')
    expect(yt.progress.value).toBe(0)
  })

  it('cancel resets to idle', () => {
    const yt = useYouTubeImport()
    yt.step.value = 'downloading' as typeof yt.step.value
    yt.cancel()
    expect(yt.step.value).toBe('idle')
  })

  // ── Edge cases ──────────────────────────────────────────────────────
  describe('edge cases', () => {
    it('download sets error when videoId is empty', async () => {
      const yt = useYouTubeImport()
      yt.videoId.value = ''
      const blob = await yt.download()
      expect(blob).toBeNull()
      expect(yt.step.value).toBe('error')
      expect(yt.errorMessage.value).toContain('No video')
    })

    it('generateChapters returns empty for NaN duration', () => {
      const yt = useYouTubeImport()
      expect(yt.generateChapters(NaN, 600)).toEqual([])
    })

    it('generateChapters returns empty for Infinity chunkSeconds', () => {
      const yt = useYouTubeImport()
      expect(yt.generateChapters(3600, Infinity)).toEqual([])
    })

    it('generateChapters returns empty for negative values', () => {
      const yt = useYouTubeImport()
      expect(yt.generateChapters(-100, 600)).toEqual([])
      expect(yt.generateChapters(3600, -10)).toEqual([])
    })

    it('resolve does not crash on network error', async () => {
      vi.mocked(api.youtubeResolve).mockRejectedValue(new TypeError('Failed to fetch'))
      const yt = useYouTubeImport()
      await yt.resolve('https://youtube.com/watch?v=abc12345678')
      expect(yt.step.value).toBe('error')
      expect(yt.errorMessage.value).toContain('Failed to fetch')
    })

    it('multiple resolve calls use latest result', async () => {
      vi.mocked(api.youtubeResolve)
        .mockResolvedValueOnce({
          video_id: 'aaa11111111', title: 'First', author: 'A1',
          duration: 100, thumbnail: '', chapters: [],
        })
        .mockResolvedValueOnce({
          video_id: 'bbb22222222', title: 'Second', author: 'A2',
          duration: 200, thumbnail: '', chapters: [],
        })

      const yt = useYouTubeImport()
      await yt.resolve('url1')
      await yt.resolve('url2')
      expect(yt.title.value).toBe('Second')
      expect(yt.videoId.value).toBe('bbb22222222')
    })
  })

  // ── download ────────────────────────────────────────────────────────
  describe('download', () => {
    function mockFetch(chunks: Uint8Array[], ok = true, contentLength?: number) {
      let readIndex = 0
      const mockReader = {
        read: vi.fn(async () => {
          if (readIndex >= chunks.length) return { done: true, value: undefined }
          return { done: false, value: chunks[readIndex++] }
        }),
      }
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
        ok,
        status: ok ? 200 : 500,
        body: { getReader: () => mockReader },
        headers: new Headers(contentLength ? { 'content-length': String(contentLength) } : {}),
      }))
    }

    it('downloads and returns blob', async () => {
      const data = new Uint8Array([1, 2, 3, 4])
      mockFetch([data], true, 4)

      const yt = useYouTubeImport()
      yt.videoId.value = 'abc12345678'
      const blob = await yt.download()

      expect(blob).toBeInstanceOf(Blob)
      expect(blob!.size).toBe(4)
      expect(yt.progress.value).toBe(100)
    })

    it('tracks progress during download', async () => {
      const chunk1 = new Uint8Array([1, 2])
      const chunk2 = new Uint8Array([3, 4])
      mockFetch([chunk1, chunk2], true, 4)

      const yt = useYouTubeImport()
      yt.videoId.value = 'abc12345678'
      await yt.download()

      expect(yt.progress.value).toBe(100)
    })

    it('handles fetch error', async () => {
      mockFetch([], false)

      const yt = useYouTubeImport()
      yt.videoId.value = 'abc12345678'
      const blob = await yt.download()

      expect(blob).toBeNull()
      expect(yt.step.value).toBe('error')
      expect(yt.errorMessage.value).toContain('500')
    })

    it('handles no content-length (no progress tracking)', async () => {
      mockFetch([new Uint8Array([1])], true)

      const yt = useYouTubeImport()
      yt.videoId.value = 'abc12345678'
      await yt.download()

      // Progress stays 0 when content-length unknown
      expect(yt.progress.value).toBe(0)
    })
  })

  // ── splitAudio ──────────────────────────────────────────────────────
  describe('splitAudio', () => {
    beforeEach(() => {
      mockFfmpegExec.mockClear()
      mockFfmpegWriteFile.mockClear()
      mockFfmpegReadFile.mockClear()
      mockFfmpegTerminate.mockClear()
      mockFfmpegLoad.mockClear()
    })

    it('splits blob into chapter files', async () => {
      const yt = useYouTubeImport()
      const blob = new Blob([new Uint8Array([1, 2, 3])])
      const chapters = [
        { title: 'Ch 1', start: 0, end: 300 },
        { title: 'Ch 2', start: 300, end: 600 },
      ]

      const files = await yt.splitAudio(blob, chapters)

      expect(files).toHaveLength(2)
      expect(files[0]!.name).toBe('chapter-001.mp3')
      expect(files[1]!.name).toBe('chapter-002.mp3')
      expect(mockFfmpegExec).toHaveBeenCalledTimes(2)
      expect(mockFfmpegTerminate).toHaveBeenCalled()
      expect(yt.progress.value).toBe(100)
    })

    it('handles ffmpeg load failure', async () => {
      mockFfmpegLoad.mockRejectedValueOnce(new Error('WASM load failed'))

      const yt = useYouTubeImport()
      const files = await yt.splitAudio(new Blob([]), [{ title: 'Ch', start: 0, end: 60 }])

      expect(files).toEqual([])
      expect(yt.step.value).toBe('error')
      expect(yt.errorMessage.value).toContain('WASM load failed')
    })

    it('always terminates ffmpeg even on error', async () => {
      mockFfmpegExec.mockRejectedValueOnce(new Error('exec failed'))

      const yt = useYouTubeImport()
      await yt.splitAudio(new Blob([]), [{ title: 'Ch', start: 0, end: 60 }])

      expect(mockFfmpegTerminate).toHaveBeenCalled()
    })
  })

  // ── importFromYouTube ───────────────────────────────────────────────
  describe('importFromYouTube', () => {
    function setupForImport(yt: ReturnType<typeof useYouTubeImport>) {
      yt.videoId.value = 'abc12345678'
      yt.title.value = 'Test Book'
      yt.author.value = 'Author'
      yt.duration.value = 600
      yt.chapters.value = [{ title: 'Ch 1', start: 0, end: 600 }]

      // Mock fetch for download
      let readIndex = 0
      const data = new Uint8Array([1, 2, 3])
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: {
          getReader: () => ({
            read: vi.fn(async () => {
              if (readIndex > 0) return { done: true, value: undefined }
              readIndex++
              return { done: false, value: data }
            }),
          }),
        },
        headers: new Headers({ 'content-length': '3' }),
      }))
    }

    beforeEach(() => {
      mockAddLocalBook.mockClear()
      mockFfmpegExec.mockClear()
      mockFfmpegTerminate.mockClear()
      mockFfmpegLoad.mockClear().mockResolvedValue(undefined)
      mockFfmpegReadFile.mockClear().mockResolvedValue(new Uint8Array([0xff, 0xfb]))
    })

    it('full flow: download → split → save → done', async () => {
      const yt = useYouTubeImport()
      setupForImport(yt)

      await yt.importFromYouTube()

      expect(yt.step.value).toBe('done')
      expect(mockAddLocalBook).toHaveBeenCalledWith(
        expect.arrayContaining([expect.any(File)]),
        { title: 'Test Book', author: 'Author' },
      )
    })

    it('generates chapters when none provided', async () => {
      const yt = useYouTubeImport()
      setupForImport(yt)
      yt.chapters.value = [] // no chapters
      yt.duration.value = 1200 // 20 min

      await yt.importFromYouTube(10) // 10 min chunks

      expect(yt.step.value).toBe('done')
      // Should have generated 2 chapters (20min / 10min)
      expect(mockFfmpegExec).toHaveBeenCalledTimes(2)
    })

    it('errors when no chapters and no duration', async () => {
      const yt = useYouTubeImport()
      yt.videoId.value = 'abc12345678'
      yt.chapters.value = []
      yt.duration.value = 0

      await yt.importFromYouTube()

      expect(yt.step.value).toBe('error')
      expect(yt.errorMessage.value).toContain('No chapters')
    })
  })
})
