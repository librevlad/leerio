import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api', () => ({
  api: {
    getAnalytics: vi.fn(),
    getAchievements: vi.fn(),
  },
}))

import { useAnalytics } from './useAnalytics'
import { api } from '../api'
import type { AnalyticsData, Achievement } from '../types'

const mockedGetAnalytics = vi.mocked(api.getAnalytics)
const mockedGetAchievements = vi.mocked(api.getAchievements)

const makeAnalytics = (overrides: Partial<AnalyticsData> = {}): AnalyticsData => ({
  total_books: 0,
  total_done: 0,
  category_counts: {},
  done_by_category: {},
  monthly_trend: [],
  rating_distribution: {},
  velocity: { total: 0 },
  heatmap: {},
  top_authors: [],
  ...overrides,
})

const makeAchievement = (name: string): Achievement => ({
  icon: '',
  name,
  desc: '',
})

beforeEach(() => {
  const { data, achievements, error } = useAnalytics()
  data.value = null
  achievements.value = []
  error.value = false
  vi.clearAllMocks()
})

describe('useAnalytics', () => {
  it('load() fetches analytics + achievements in parallel', async () => {
    mockedGetAnalytics.mockResolvedValue(makeAnalytics())
    mockedGetAchievements.mockResolvedValue([])

    const { load } = useAnalytics()
    await load()

    expect(mockedGetAnalytics).toHaveBeenCalledOnce()
    expect(mockedGetAchievements).toHaveBeenCalledOnce()
  })

  it('load() sets data and achievements on success', async () => {
    const analyticsData = makeAnalytics({ total_done: 250 })
    const badgesData = [makeAchievement('First Listen')]
    mockedGetAnalytics.mockResolvedValue(analyticsData)
    mockedGetAchievements.mockResolvedValue(badgesData)

    const { load, data, achievements } = useAnalytics()
    await load()

    expect(data.value).toEqual(analyticsData)
    expect(achievements.value).toEqual(badgesData)
  })

  it('load() sets error=true on failure, clears data', async () => {
    mockedGetAnalytics.mockRejectedValue(new Error('network'))
    mockedGetAchievements.mockResolvedValue([makeAchievement('badge')])

    const { load, data, achievements, error } = useAnalytics()
    await load()

    expect(error.value).toBe(true)
    expect(data.value).toBeNull()
    expect(achievements.value).toEqual([])
  })

  it('loading is true during fetch, false after', async () => {
    let resolveAnalytics!: (v: AnalyticsData) => void
    mockedGetAnalytics.mockImplementation(
      () =>
        new Promise((r) => {
          resolveAnalytics = r
        }),
    )
    mockedGetAchievements.mockResolvedValue([])

    const { load, loading } = useAnalytics()
    expect(loading.value).toBe(false)

    const promise = load()
    expect(loading.value).toBe(true)

    resolveAnalytics(makeAnalytics())
    await promise

    expect(loading.value).toBe(false)
  })

  it('singleton state is shared across calls', async () => {
    const analyticsData = makeAnalytics({ total_done: 999 })
    const badgesData = [makeAchievement('Shared')]
    mockedGetAnalytics.mockResolvedValue(analyticsData)
    mockedGetAchievements.mockResolvedValue(badgesData)

    const instance1 = useAnalytics()
    const instance2 = useAnalytics()

    await instance1.load()

    expect(instance2.data.value).toEqual(analyticsData)
    expect(instance2.achievements.value).toEqual(badgesData)
  })
})
