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
vi.mock('@/composables/useFileScanner', () => ({
  useFileScanner: () => ({ fsBooks: ref({}), fetchMissingCovers: vi.fn() }),
}))
vi.mock('@/composables/usePlayer', () => ({ usePlayer: () => ({}), resumePosition: () => null }))
vi.mock('@/composables/useToast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }) }))

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
