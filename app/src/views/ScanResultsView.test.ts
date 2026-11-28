import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'

/**
 * Promise (owner's decision 27.11.2026: "бесплатно — до 5 книг"): the free plan never adds more
 * than 5 books from the scan — also when Play's answer arrives after the books were ticked.
 */

const limited = ref(false)
const addFsBooks = vi.fn()
const found = Array.from({ length: 7 }, (_, i) => ({
  id: `fs:Book ${i + 1}`,
  title: `Book ${i + 1}`,
  author: '',
  folderPath: `Audiobooks/Book ${i + 1}`,
  tracks: [
    { index: 0, filename: '01.mp3', path: '', duration: 0 },
    { index: 1, filename: '02.mp3', path: '', duration: 0 },
  ],
  sizeBytes: 1,
  synced: false,
  addedAt: '',
}))

vi.mock('../composables/useFileScanner', () => ({
  useFileScanner: () => ({
    scan: async () => found,
    fsBooks: ref({}),
    addFsBooks,
    scanning: ref(false),
    scanProgress: ref(''),
    abortScan: vi.fn(),
  }),
  isLikelyNotBook: () => false,
}))
vi.mock('../composables/usePro', () => ({ usePro: () => ({ limited }), FREE_BOOKS: 5 }))
vi.mock('../composables/useToast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }) }))
vi.mock('../composables/useTelemetry', () => ({ useTracking: () => ({ track: vi.fn() }) }))
vi.mock('../composables/usePlayer', () => ({ usePlayer: () => ({ isPlayerVisible: ref(false) }) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn(), back: vi.fn() }) }))

describe('ScanResultsView', () => {
  it('does not add more than 5 books when the limit switched on after the books were ticked', async () => {
    const { default: ScanResultsView } = await import('./ScanResultsView.vue')
    const i18n = createI18n({
      legacy: false,
      locale: 'en',
      missingWarn: false,
      fallbackWarn: false,
      messages: { en: {} },
    })
    const w = mount(ScanResultsView, {
      global: {
        plugins: [i18n],
        stubs: { PaywallModal: { props: ['open'], template: '<div class="paywall">{{ open }}</div>' } },
        directives: { ripple: {} },
      },
    })
    await flushPromises()

    // Scan finished while Play had not answered yet: no limits, all 7 ticked
    limited.value = true
    const buttons = w.findAll('button')
    await buttons[buttons.length - 1]!.trigger('click') // "Add N books"
    await flushPromises()

    expect(addFsBooks).not.toHaveBeenCalled()
    expect(w.find('.paywall').text()).toBe('true')
  })
})
