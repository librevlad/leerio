import { ref } from 'vue'
import { api } from '@/api'
import type { UserBook, TTSJob } from '@/types'

const userBooks = ref<UserBook[]>([])
const ttsJobs = ref<TTSJob[]>([])
const loading = ref(false)

export function useUserBooks() {
  // Server lists are best-effort: offline, as a guest or with the server down,
  // keep what we have — device-folder and local books must still render
  async function loadUserBooks() {
    loading.value = true
    try {
      userBooks.value = await api.getUserBooks()
    } catch {
      /* offline / guest — keep the last known list */
    } finally {
      loading.value = false
    }
  }

  async function loadTTSJobs() {
    try {
      ttsJobs.value = await api.getTTSJobs()
    } catch {
      /* offline / guest */
    }
  }

  async function deleteBook(slug: string) {
    await api.deleteUserBook(slug)
    userBooks.value = userBooks.value.filter((b) => b.slug !== slug)
  }

  function pollJob(jobId: string, callback: (job: TTSJob) => void, interval = 3000) {
    const timer = setInterval(async () => {
      try {
        const job = await api.getTTSJob(jobId)
        callback(job)
        if (job.status === 'done' || job.status === 'error') {
          clearInterval(timer)
        }
      } catch {
        clearInterval(timer)
      }
    }, interval)
    return () => clearInterval(timer)
  }

  return {
    userBooks,
    ttsJobs,
    loading,
    loadUserBooks,
    loadTTSJobs,
    deleteBook,
    pollJob,
  }
}
