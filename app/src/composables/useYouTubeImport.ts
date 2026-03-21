import { ref } from 'vue'
import { Capacitor } from '@capacitor/core'
import { Filesystem, Directory } from '@capacitor/filesystem'
import { api } from '../api'
import { useLocalBooks } from './useLocalBooks'
import { useFileScanner } from './useFileScanner'
import type { YouTubeChapter, YouTubeResolveResult } from '../types'

type Step = 'idle' | 'resolving' | 'resolved' | 'downloading' | 'splitting' | 'saving' | 'done' | 'error'

export function useYouTubeImport() {
  const step = ref<Step>('idle')
  const progress = ref(0)
  const title = ref('')
  const author = ref('')
  const duration = ref(0)
  const thumbnail = ref('')
  const chapters = ref<YouTubeChapter[]>([])
  const videoId = ref('')
  const errorMessage = ref('')
  const { addLocalBook } = useLocalBooks()

  let abortController: AbortController | null = null

  async function resolve(url: string) {
    step.value = 'resolving'
    progress.value = 0
    errorMessage.value = ''
    try {
      const result: YouTubeResolveResult = await api.youtubeResolve(url)
      videoId.value = result.video_id
      title.value = result.title
      author.value = result.author
      duration.value = result.duration
      thumbnail.value = result.thumbnail
      chapters.value = result.chapters
      step.value = 'resolved'
    } catch (e) {
      step.value = 'error'
      errorMessage.value = e instanceof Error ? e.message : 'Unknown error'
    }
  }

  async function download(): Promise<Blob | null> {
    if (!videoId.value) {
      step.value = 'error'
      errorMessage.value = 'No video selected'
      return null
    }
    step.value = 'downloading'
    progress.value = 0
    abortController = new AbortController()

    try {
      const url = api.youtubeStreamUrl(videoId.value)
      const res = await fetch(url, {
        credentials: 'include',
        signal: abortController.signal,
      })
      if (!res.ok) throw new Error(`Download failed: ${res.status}`)
      if (!res.body) throw new Error('No response body')

      const contentLength = Number(res.headers.get('content-length')) || 0
      const reader = res.body.getReader()
      const chunks: Uint8Array[] = []
      let received = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        chunks.push(value)
        received += value.length
        if (contentLength > 0) {
          progress.value = Math.round((received / contentLength) * 100)
        }
      }

      return new Blob(chunks)
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        step.value = 'idle'
        return null
      }
      step.value = 'error'
      errorMessage.value = e instanceof Error ? e.message : 'Download failed'
      return null
    }
  }

  async function splitAudio(blob: Blob, chapterList: YouTubeChapter[]): Promise<File[]> {
    step.value = 'splitting'
    progress.value = 0

    let ffmpeg: InstanceType<typeof import('@ffmpeg/ffmpeg').FFmpeg> | null = null
    try {
      const { FFmpeg } = await import('@ffmpeg/ffmpeg')
      const { fetchFile } = await import('@ffmpeg/util')

      ffmpeg = new FFmpeg()
      await ffmpeg.load()

      const inputName = 'input.webm'
      const inputData = await fetchFile(blob)
      await ffmpeg.writeFile(inputName, inputData)

      const files: File[] = []

      for (let i = 0; i < chapterList.length; i++) {
        const ch = chapterList[i]!
        const outputName = `chapter-${String(i + 1).padStart(3, '0')}.mp3`
        await ffmpeg.exec([
          '-i',
          inputName,
          '-ss',
          String(ch.start),
          '-to',
          String(ch.end),
          '-c',
          'copy',
          '-y',
          outputName,
        ])
        const data = await ffmpeg.readFile(outputName)
        const fileBlob = new Blob([data], { type: 'audio/mpeg' })
        files.push(new File([fileBlob], outputName, { type: 'audio/mpeg' }))
        progress.value = Math.round(((i + 1) / chapterList.length) * 100)
      }

      return files
    } catch (e) {
      step.value = 'error'
      errorMessage.value = e instanceof Error ? e.message : 'Audio splitting failed'
      return []
    } finally {
      ffmpeg?.terminate()
    }
  }

  function generateChapters(totalDuration: number, chunkSeconds: number): YouTubeChapter[] {
    if (!Number.isFinite(totalDuration) || !Number.isFinite(chunkSeconds) || totalDuration <= 0 || chunkSeconds <= 0)
      return []
    const result: YouTubeChapter[] = []
    let start = 0
    let i = 1
    while (start < totalDuration) {
      const end = Math.min(start + chunkSeconds, totalDuration)
      result.push({ title: `Глава ${i}`, start, end })
      start = end
      i++
    }
    return result
  }

  async function importFromYouTube(chunkMinutes?: number) {
    // Capture state at start — don't read from refs mid-operation
    const chapterList = chapters.value.length
      ? [...chapters.value]
      : generateChapters(duration.value, (chunkMinutes ?? 10) * 60)

    if (!chapterList.length) {
      step.value = 'error'
      errorMessage.value = 'No chapters to split'
      return
    }

    try {
      const blob = await download()
      if (!blob) return

      const files = await splitAudio(blob, chapterList)
      if (!files.length) {
        // splitAudio already sets error state on failure
        if (step.value !== 'error') {
          step.value = 'error'
          errorMessage.value = 'No chapters produced'
        }
        return
      }

      step.value = 'saving'
      progress.value = 0

      if (Capacitor.isNativePlatform()) {
        // APK: save to filesystem as fs: book
        const { addFsBooks } = useFileScanner()
        const folderPath = `Audiobooks/${title.value}`

        // Create folder
        try {
          await Filesystem.mkdir({
            path: folderPath,
            directory: Directory.ExternalStorage,
            recursive: true,
          })
        } catch {
          /* already exists */
        }

        // Write chapter files (chunked base64 to avoid stack overflow)
        const fsTracks = []
        for (let i = 0; i < files.length; i++) {
          const file = files[i]!
          const arrayBuf = await file.arrayBuffer()
          const bytes = new Uint8Array(arrayBuf)
          let binary = ''
          const chunkSize = 8192
          for (let offset = 0; offset < bytes.length; offset += chunkSize) {
            const chunk = bytes.subarray(offset, offset + chunkSize)
            binary += String.fromCharCode.apply(null, chunk as unknown as number[])
          }
          const base64 = btoa(binary)
          await Filesystem.writeFile({
            path: `${folderPath}/${file.name}`,
            data: base64,
            directory: Directory.ExternalStorage,
          })
          fsTracks.push({
            index: i,
            filename: file.name,
            path: `${folderPath}/${file.name}`,
            duration: 0,
          })
          progress.value = Math.round(((i + 1) / files.length) * 100)
        }

        addFsBooks([
          {
            id: `fs:${title.value}`,
            title: title.value,
            author: author.value,
            folderPath,
            tracks: fsTracks,
            sizeBytes: files.reduce((sum, f) => sum + f.size, 0),
            synced: false,
            addedAt: new Date().toISOString(),
          },
        ])
      } else {
        // Web fallback: save to IndexedDB as before
        await addLocalBook(files, {
          title: title.value,
          author: author.value,
        })
      }

      step.value = 'done'
      progress.value = 100
    } catch (e) {
      step.value = 'error'
      errorMessage.value = e instanceof Error ? e.message : 'Import failed'
    }
  }

  function cancel() {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    step.value = 'idle'
    progress.value = 0
  }

  function reset() {
    cancel()
    title.value = ''
    author.value = ''
    duration.value = 0
    thumbnail.value = ''
    chapters.value = []
    videoId.value = ''
    errorMessage.value = ''
  }

  return {
    step,
    progress,
    title,
    author,
    duration,
    thumbnail,
    chapters,
    videoId,
    errorMessage,
    resolve,
    download,
    importFromYouTube,
    splitAudio,
    cancel,
    reset,
    generateChapters,
  }
}
