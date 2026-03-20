import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api', () => ({
  api: {
    youtubeResolve: vi.fn(),
    youtubeStreamUrl: vi.fn((id: string) => `/api/youtube/stream/${id}`),
  },
}))

vi.mock('./useLocalBooks', () => ({
  useLocalBooks: () => ({
    addLocalBook: vi.fn().mockResolvedValue({
      id: 'lb:test-uuid',
      title: 'Test',
      author: 'Author',
      tracks: [],
      addedAt: '2026-01-01',
    }),
  }),
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
    let resolvePromise: ((v: any) => void) | null = null
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
    yt.step.value = 'error' as any
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
    yt.step.value = 'downloading' as any
    yt.cancel()
    expect(yt.step.value).toBe('idle')
  })
})
