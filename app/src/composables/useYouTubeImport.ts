import { ref } from 'vue'
import { api } from '../api'
import { useLocalBooks } from './useLocalBooks'
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
    if (!videoId.value) return null
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

    const { FFmpeg } = await import('@ffmpeg/ffmpeg')
    const { fetchFile } = await import('@ffmpeg/util')

    const ffmpeg = new FFmpeg()
    await ffmpeg.load()

    const inputName = 'input.webm'
    const inputData = await fetchFile(blob)
    await ffmpeg.writeFile(inputName, inputData)

    const files: File[] = []

    for (let i = 0; i < chapterList.length; i++) {
      const ch = chapterList[i]!
      const outputName = `chapter-${String(i + 1).padStart(3, '0')}.mp3`
      await ffmpeg.exec([
        '-i', inputName,
        '-ss', String(ch.start),
        '-to', String(ch.end),
        '-c', 'copy',
        '-y', outputName,
      ])
      const data = await ffmpeg.readFile(outputName)
      const fileBlob = new Blob([data], { type: 'audio/mpeg' })
      files.push(new File([fileBlob], outputName, { type: 'audio/mpeg' }))
      progress.value = Math.round(((i + 1) / chapterList.length) * 100)
    }

    ffmpeg.terminate()
    return files
  }

  function generateChapters(totalDuration: number, chunkSeconds: number): YouTubeChapter[] {
    if (totalDuration <= 0 || chunkSeconds <= 0) return []
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
    try {
      const blob = await download()
      if (!blob) return

      let chapterList = chapters.value
      if (!chapterList.length) {
        chapterList = generateChapters(duration.value, (chunkMinutes ?? 10) * 60)
      }

      const files = await splitAudio(blob, chapterList)
      if (!files.length) {
        step.value = 'error'
        errorMessage.value = 'No chapters produced'
        return
      }

      step.value = 'saving'
      progress.value = 0

      const { addLocalBook } = useLocalBooks()
      await addLocalBook(files, {
        title: title.value,
        author: author.value,
      })

      step.value = 'done'
      progress.value = 100
    } catch (e) {
      step.value = 'error'
      errorMessage.value = e instanceof Error ? e.message : 'Import failed'
    }
  }

  function cancel() {
    abortController?.abort()
    abortController = null
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
    step, progress, title, author, duration, thumbnail,
    chapters, videoId, errorMessage,
    resolve, download, importFromYouTube, splitAudio,
    cancel, reset, generateChapters,
  }
}
