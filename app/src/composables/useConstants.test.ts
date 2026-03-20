import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api', () => ({
  api: { getConstants: vi.fn() },
}))

import { useConstants } from './useConstants'
import { api } from '../api'

const mockConstants = {
  categories: [{ id: 1, name: 'Test', color: '#000', gradient: 'none', sort_order: 0 }],
  status_style: { listening: 'blue' },
  action_styles: { play: 'green' },
  action_labels: { play: 'Слушать' },
  list_to_status: { listening: 'in_progress' },
  label_to_folder: { Слушаю: 'listening' },
  folder_to_label: { listening: 'Слушаю' },
}

describe('useConstants', () => {
  beforeEach(() => {
    vi.mocked(api.getConstants).mockReset()
    const c = useConstants()
    c.constants.value = null
  })

  it('load() fetches constants from API', async () => {
    vi.mocked(api.getConstants).mockResolvedValue(mockConstants as never)
    const c = useConstants()
    await c.load()
    expect(api.getConstants).toHaveBeenCalledOnce()
    expect(c.constants.value).toEqual(mockConstants)
  })

  it('load() skips if already loaded', async () => {
    vi.mocked(api.getConstants).mockResolvedValue(mockConstants as never)
    const c = useConstants()
    await c.load()
    await c.load()
    expect(api.getConstants).toHaveBeenCalledOnce()
  })

  it('load() sets fallback defaults on error', async () => {
    vi.mocked(api.getConstants).mockRejectedValue(new Error('network'))
    const c = useConstants()
    await c.load()
    expect(c.constants.value).toEqual({
      categories: [],
      status_style: {},
      action_styles: {},
      action_labels: {},
      list_to_status: {},
      label_to_folder: {},
      folder_to_label: {},
    })
  })

  it('load() sets loading=false after completion', async () => {
    vi.mocked(api.getConstants).mockResolvedValue(mockConstants as never)
    const c = useConstants()
    await c.load()
    // loading is module-level but not returned; verify by confirming
    // a second load works after resetting constants (loading must be false)
    c.constants.value = null
    vi.mocked(api.getConstants).mockResolvedValue(mockConstants as never)
    await c.load()
    expect(api.getConstants).toHaveBeenCalledTimes(2)
    expect(c.constants.value).toEqual(mockConstants)
  })
})
