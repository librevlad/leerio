import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, RouterLinkStub } from '@vue/test-utils'
import { ref } from 'vue'
import i18n from '../i18n'
import MyLibraryView from './MyLibraryView.vue'

const env = vi.hoisted(() => ({ native: true, server: false, cloud: false }))

vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => env.native, getPlatform: () => (env.native ? 'android' : 'web') },
  registerPlugin: () => ({}),
}))
vi.mock('@/composables/useAuth', () => ({ useAuth: () => ({ serverReachable: ref(env.server) }) }))
vi.mock('@/composables/useCloud', () => ({ useCloud: () => ({ available: ref(env.cloud) }) }))
vi.mock('@/composables/useUserBooks', () => ({
  useUserBooks: () => ({
    userBooks: ref([]),
    ttsJobs: ref([]),
    loading: ref(false),
    loadUserBooks: vi.fn(() => Promise.resolve()),
    loadTTSJobs: vi.fn(() => Promise.resolve()),
    deleteBook: vi.fn(),
    pollJob: vi.fn(),
  }),
}))
vi.mock('@/composables/useLocalBooks', () => ({
  useLocalBooks: () => ({
    localBooks: ref([]),
    removeLocalBook: vi.fn(),
    getLocalBook: vi.fn(),
    getLocalAudioUrl: vi.fn(),
    loadLocalBooks: vi.fn(() => Promise.resolve()),
  }),
}))
vi.mock('@/composables/useDownloads', () => ({
  useDownloads: () => ({ downloadedBooks: ref([]), books: ref([]), isDownloaded: () => false, load: vi.fn() }),
}))
const scanner = vi.hoisted(() => ({ books: {} as Record<string, unknown>, removed: [] as string[] }))
vi.mock('@/composables/useFileScanner', () => {
  const fsBooks = ref(scanner.books)
  return {
    useFileScanner: () => ({
      fsBooks,
      fetchMissingCovers: vi.fn(),
      removeFsBook: (id: string) => {
        scanner.removed.push(id)
        delete fsBooks.value[id]
      },
    }),
  }
})
vi.mock('@/composables/usePlayer', () => ({
  usePlayer: () => ({ currentBook: ref(null) }),
  resumePosition: () => null,
}))
const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }))
vi.mock('@/composables/useToast', () => ({ useToast: () => toast }))

async function emptyLibrary() {
  const w = mount(MyLibraryView, {
    global: { plugins: [i18n], stubs: { RouterLink: RouterLinkStub, AddBookFab: true } },
  })
  await flushPromises()
  return w.findAllComponents(RouterLinkStub).map((l) => ({ to: l.props('to'), text: l.text() }))
}

describe('My Library, empty: every button leads somewhere that works', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'ru'
    Object.assign(env, { native: true, server: false, cloud: false })
  })

  it('APK without the server: no catalog or upload, the device folders instead', async () => {
    expect(await emptyLibrary()).toEqual([{ to: '/scan-results', text: 'Найти книги на устройстве' }])
  })

  it("APK with the owner's cloud key: the cloud first, then the device", async () => {
    env.cloud = true
    expect((await emptyLibrary()).map((l) => l.to)).toEqual(['/cloud', '/scan-results'])
  })

  it('APK with the server up, and the web app: catalog and upload as before', async () => {
    env.server = true
    expect((await emptyLibrary()).map((l) => l.to)).toEqual(['/library', '/upload'])
    env.native = false
    env.server = false
    expect((await emptyLibrary()).map((l) => l.to)).toEqual(['/library', '/upload'])
  })
})

describe('My Library: removing a book from the device folders', () => {
  const book = { id: 'fs:Харизма', title: 'Харизма', author: '', tracks: [{}, {}], folderPath: 'Audiobooks/Харизма' }

  beforeEach(() => {
    i18n.global.locale.value = 'ru'
    Object.assign(env, { native: true, server: false, cloud: false })
    scanner.books[book.id] = book
    scanner.removed.length = 0
    toast.success.mockClear()
  })

  async function tapTrash(answer: boolean) {
    const ask = vi.fn(() => answer)
    vi.stubGlobal('confirm', ask)
    const w = mount(MyLibraryView, {
      global: { plugins: [i18n], stubs: { RouterLink: RouterLinkStub, AddBookFab: true } },
    })
    await flushPromises()
    await w.find('button[aria-label="Удалить книгу"]').trigger('click')
    await flushPromises()
    const question = (ask.mock.calls[0] as unknown[] | undefined)?.[0]
    vi.unstubAllGlobals()
    return { w, question }
  }

  it('the book leaves the list, and the question says the files stay', async () => {
    const { w, question } = await tapTrash(true)
    expect(question).toBe('Убрать «Харизма» из библиотеки? Файлы останутся на устройстве')
    expect(scanner.removed).toEqual(['fs:Харизма'])
    expect(toast.success).toHaveBeenCalledWith('Убрано из библиотеки')
    expect(w.text()).not.toContain('Харизма')
  })

  it('"Cancel" leaves everything as it was', async () => {
    const { w } = await tapTrash(false)
    expect(scanner.removed).toEqual([])
    expect(toast.success).not.toHaveBeenCalled()
    expect(w.text()).toContain('Харизма')
  })
})
