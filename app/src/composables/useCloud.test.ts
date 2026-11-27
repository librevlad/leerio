import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { CloudFile } from './useCloud'

const { fs, http, device } = vi.hoisted(() => ({
  fs: { readFile: vi.fn(), stat: vi.fn(), mkdir: vi.fn(), downloadFile: vi.fn() },
  http: { get: vi.fn() },
  device: { native: true },
}))

vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => device.native },
  CapacitorHttp: http,
  registerPlugin: () => ({ request: vi.fn() }),
}))
vi.mock('@capacitor/filesystem', () => ({
  Filesystem: fs,
  Directory: { External: 'EXTERNAL', ExternalStorage: 'EXTERNAL_STORAGE' },
  Encoding: { UTF8: 'utf8' },
}))

const KEY = { endpoint: 'https://acc.r2.cloudflarestorage.com', bucket: 'leerio-books', accessKey: 'a', secretKey: 's' }
const FOLDER = 'Оливия Фокс Кабейн «Харизма» [чит. Татьяна Оверченко]'
const file = (name: string, size: number, folder = FOLDER): CloudFile => ({
  key: `books/${folder}/${name}`,
  name,
  size,
})
const charisma = { folder: FOLDER, files: [file('10.mp3', 30), file('02.mp3', 20), file('01.mp3', 10)], bytes: 60 }

/** Files on the device: path → size */
let disk: Map<string, number>
/** What each downloaded path should weigh; `cut` paths arrive one byte short */
let remote: Map<string, number>
let cut: Set<string>
let offline: Set<string>

function serve(books: { folder: string; files: CloudFile[] }[]) {
  remote = new Map(books.flatMap((b) => b.files.map((f) => [`Audiobooks/${b.folder}/${f.name}`, f.size] as const)))
  http.get.mockResolvedValue({ status: 200, data: { version: 1, books } })
}

/** Fresh modules: state is read from localStorage on import */
async function load() {
  vi.resetModules()
  const cloud = await import('./useCloud')
  const scanner = await import('./useFileScanner')
  return { ...cloud.useCloud(), parseLibrary: cloud.parseLibrary, fsBooks: scanner.useFileScanner().fsBooks }
}

const downloaded = () => fs.downloadFile.mock.calls.map(([o]) => (o as { path: string }).path.split('/').pop())

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  device.native = true
  disk = new Map()
  cut = new Set()
  offline = new Set()
  fs.readFile.mockResolvedValue({ data: JSON.stringify(KEY) })
  fs.mkdir.mockResolvedValue(undefined)
  fs.stat.mockImplementation(({ path }: { path: string }) =>
    disk.has(path) ? Promise.resolve({ size: disk.get(path) }) : Promise.reject(new Error('missing')),
  )
  fs.downloadFile.mockImplementation(({ path }: { path: string }) => {
    if (offline.has(path)) return Promise.reject(new Error('Unable to resolve host'))
    disk.set(path, (remote.get(path) ?? 0) - (cut.has(path) ? 1 : 0))
    return Promise.resolve({ path })
  })
  serve([charisma])
})

describe('useCloud — the key', () => {
  it('no cloud.json on the device: no cloud, nothing is fetched', async () => {
    fs.readFile.mockRejectedValue(new Error('File does not exist'))
    const cloud = await load()
    await cloud.init()
    await cloud.refresh()
    expect(cloud.available.value).toBe(false)
    expect(http.get).not.toHaveBeenCalled()
  })

  it('in the browser there is no cloud and the device is not asked', async () => {
    device.native = false
    const cloud = await load()
    await cloud.init()
    expect(cloud.available.value).toBe(false)
    expect(fs.readFile).not.toHaveBeenCalled()
  })

  it('cloud.json saved with a BOM (Windows Notepad) still connects', async () => {
    fs.readFile.mockResolvedValue({ data: String.fromCharCode(0xfeff) + JSON.stringify(KEY) + '\r\n' })
    const cloud = await load()
    await cloud.init()
    expect(cloud.available.value).toBe(true)
  })

  it('a key without its secret does not count', async () => {
    fs.readFile.mockResolvedValue({ data: JSON.stringify({ ...KEY, secretKey: '' }) })
    const cloud = await load()
    await cloud.init()
    expect(cloud.available.value).toBe(false)
  })
})

describe('useCloud — the list', () => {
  it('reads library.json with a signed link and keeps the list for offline', async () => {
    const cloud = await load()
    await cloud.init()
    await cloud.refresh()
    expect(http.get.mock.calls[0]![0].url).toMatch(
      /^https:\/\/acc\.r2\.cloudflarestorage\.com\/leerio-books\/library\.json\?X-Amz-/,
    )
    expect(cloud.books.value).toEqual([charisma])
    expect(cloud.listError.value).toBe(false)

    // Next start without a network: the saved list, and a word that it may be old
    http.get.mockRejectedValue(new Error('offline'))
    const again = await load()
    await again.init()
    await again.refresh()
    expect(again.books.value).toEqual([charisma])
    expect(again.listError.value).toBe(true)
  })

  it('drops books that are malformed or point outside their folder', async () => {
    const { parseLibrary } = await load()
    const ok = { folder: 'A', files: [file('CD1/01.mp3', 5, 'A')] }
    expect(
      parseLibrary({
        books: [
          ok,
          { folder: '../Download', files: [file('01.mp3', 5)] },
          { folder: 'B', files: [file('../../x.mp3', 5)] },
          { folder: 'C/D', files: [file('01.mp3', 5)] },
          { folder: 'E', files: [] },
          { folder: 'F', files: [{ key: 'k', name: '01.mp3' }] },
        ],
      }),
    ).toEqual([{ ...ok, bytes: 5 }])
    expect(parseLibrary(null)).toEqual([])
  })
})

describe('useCloud — downloading', () => {
  it('a book goes to Audiobooks/<folder>/ and joins My Library, tracks in file order', async () => {
    disk.set(`Audiobooks/${FOLDER}/01.mp3`, 10) // already there in full
    const cloud = await load()
    await cloud.init()
    cloud.download(charisma)
    await vi.waitFor(() => expect(cloud.fsBooks.value[`fs:${FOLDER}`]).toBeDefined())

    expect(downloaded()).toEqual(['10.mp3', '02.mp3'])
    expect(fs.mkdir).toHaveBeenCalledWith(expect.objectContaining({ path: `Audiobooks/${FOLDER}` }))
    expect(cloud.fsBooks.value[`fs:${FOLDER}`]).toMatchObject({
      title: 'Харизма',
      author: 'Оливия Фокс Кабейн',
      folderPath: `Audiobooks/${FOLDER}`,
      sizeBytes: 60,
    })
    expect(cloud.fsBooks.value[`fs:${FOLDER}`]!.tracks.map((t) => t.filename)).toEqual(['01.mp3', '02.mp3', '10.mp3'])
    expect(cloud.jobs.value[FOLDER]).toBeUndefined()
  })

  it('a dropped connection leaves no half book; the retry fetches only what is missing', async () => {
    offline.add(`Audiobooks/${FOLDER}/02.mp3`)
    const cloud = await load()
    await cloud.init()
    cloud.download(charisma)
    await vi.waitFor(() => expect(cloud.jobs.value[FOLDER]?.state).toBe('failed'))
    expect(cloud.fsBooks.value[`fs:${FOLDER}`]).toBeUndefined()

    offline.clear()
    fs.downloadFile.mockClear()
    cloud.download(charisma)
    await vi.waitFor(() => expect(cloud.fsBooks.value[`fs:${FOLDER}`]).toBeDefined())
    expect(downloaded()).toEqual(['02.mp3', '01.mp3'])
  })

  it('a file that arrives short is a failure, not a finished book', async () => {
    cut.add(`Audiobooks/${FOLDER}/01.mp3`)
    const cloud = await load()
    await cloud.init()
    cloud.download(charisma)
    await vi.waitFor(() => expect(cloud.jobs.value[FOLDER]?.state).toBe('failed'))
    expect(cloud.fsBooks.value[`fs:${FOLDER}`]).toBeUndefined()
  })

  it('one book at a time: the second waits, a second tap changes nothing', async () => {
    const other = {
      folder: 'Брайан Трейси «Нет оправданий!»',
      files: [file('01.mp3', 7, 'Брайан Трейси «Нет оправданий!»')],
      bytes: 7,
    }
    serve([charisma, other])
    let release!: () => void
    const gate = new Promise<void>((r) => (release = r))
    const plain = fs.downloadFile.getMockImplementation()!
    fs.downloadFile.mockImplementationOnce(async (o: { path: string }) => {
      await gate
      return plain(o)
    })

    const cloud = await load()
    await cloud.init()
    cloud.download(charisma)
    cloud.download(other)
    cloud.download(charisma)
    await vi.waitFor(() => expect(fs.downloadFile).toHaveBeenCalledTimes(1))
    expect(cloud.jobs.value[FOLDER]?.state).toBe('downloading')
    expect(cloud.jobs.value[other.folder]?.state).toBe('queued')
    await new Promise((r) => setTimeout(r, 20))
    expect(fs.downloadFile).toHaveBeenCalledTimes(1) // the gate holds the first file; nothing else starts

    release()
    await vi.waitFor(() => expect(cloud.fsBooks.value[`fs:${other.folder}`]).toBeDefined())
    expect(cloud.fsBooks.value[`fs:${FOLDER}`]).toBeDefined()
    expect(fs.downloadFile).toHaveBeenCalledTimes(4)
  })
})
