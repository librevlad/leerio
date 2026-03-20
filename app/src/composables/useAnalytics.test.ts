import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api', () => ({
  api: {
    getAnalytics: vi.fn(),
    getAchievements: vi.fn(),
  },
}))

import { useAnalytics } from './useAnalytics'
import { api } from '../api'

const mockedGetAnalytics = vi.mocked(api.getAnalytics)
const mockedGetAchievements = vi.mocked(api.getAchievements)

beforeEach(() => {
  const { data, achievements, error } = useAnalytics()
  data.value = null
  achievements.value = []
  error.value = false
  vi.clearAllMocks()
})

describe('useAnalytics', () => {
  it('load() fetches analytics + achievements in parallel', async () => {
    mockedGetAnalytics.mockResolvedValue({ totalMinutes: 100 })
    mockedGetAchievements.mockResolvedValue([])

    const { load } = useAnalytics()
    await load()

    expect(mockedGetAnalytics).toHaveBeenCalledOnce()
    expect(mockedGetAchievements).toHaveBeenCalledOnce()
  })

  it('load() sets data and achievements on success', async () => {
    const analyticsData = { totalMinutes: 250, streak: 5 }
    const badgesData = [{ id: '1', name: 'First Listen' }]
    mockedGetAnalytics.mockResolvedValue(analyticsData)
    mockedGetAchievements.mockResolvedValue(badgesData)

    const { load, data, achievements } = useAnalytics()
    await load()

    expect(data.value).toEqual(analyticsData)
    expect(achievements.value).toEqual(badgesData)
  })

  it('load() sets error=true on failure, clears data', async () => {
    mockedGetAnalytics.mockRejectedValue(new Error('network'))
    mockedGetAchievements.mockResolvedValue([{ id: '1', name: 'badge' }])

    const { load, data, achievements, error } = useAnalytics()
    await load()

    expect(error.value).toBe(true)
    expect(data.value).toBeNull()
    expect(achievements.value).toEqual([])
  })

  it('loading is true during fetch, false after', async () => {
    let resolveAnalytics!: (v: unknown) => void
    mockedGetAnalytics.mockImplementation(() => new Promise(r => { resolveAnalytics = r }))
    mockedGetAchievements.mockResolvedValue([])

    const { load, loading } = useAnalytics()
    expect(loading.value).toBe(false)

    const promise = load()
    expect(loading.value).toBe(true)

    resolveAnalytics({ totalMinutes: 0 })
    await promise

    expect(loading.value).toBe(false)
  })

  it('singleton state is shared across calls', async () => {
    const analyticsData = { totalMinutes: 999 }
    const badgesData = [{ id: '2', name: 'Shared' }]
    mockedGetAnalytics.mockResolvedValue(analyticsData)
    mockedGetAchievements.mockResolvedValue(badgesData)

    const instance1 = useAnalytics()
    const instance2 = useAnalytics()

    await instance1.load()

    expect(instance2.data.value).toEqual(analyticsData)
    expect(instance2.achievements.value).toEqual(badgesData)
  })
})
