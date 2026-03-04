<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useDownloads } from '../composables/useDownloads'
import { useAuth } from '../composables/useAuth'
import type { Constants, SessionStats } from '../types'
import { IconTrash, IconDownload } from '../components/shared/icons'

const router = useRouter()
const dl = useDownloads()
const { user, isAdmin, logout } = useAuth()
const constants = ref<Constants | null>(null)
const sessionStats = ref<SessionStats | null>(null)

onMounted(async () => {
  try {
    const [c, s] = await Promise.all([api.getConstants(), api.getSessionStats(30)])
    constants.value = c
    sessionStats.value = s
  } catch {
    /* ignore */
  }
})

function fmtSize(bytes: number): string {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' КБ'
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' МБ'
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' ГБ'
}

async function handleLogout() {
  await logout()
  router.push('/login')
}
</script>

<template>
  <div>
    <h1 class="page-title mb-8">Настройки</h1>

    <div class="max-w-2xl space-y-6">
      <!-- Profile -->
      <div class="card p-6">
        <h3 class="section-label mb-4">Профиль</h3>
        <div v-if="user" class="flex items-center gap-4">
          <img
            v-if="user.picture"
            :src="user.picture"
            :alt="user.name"
            class="h-14 w-14 rounded-full object-cover"
            referrerpolicy="no-referrer"
          />
          <div
            v-else
            class="flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-[18px] font-bold text-[--t2]"
            style="background: rgba(255, 255, 255, 0.08)"
          >
            {{ user.name?.charAt(0) || '?' }}
          </div>
          <div class="min-w-0 flex-1">
            <p class="text-[15px] font-semibold text-[--t1]">{{ user.name }}</p>
            <p class="text-[13px] text-[--t3]">{{ user.email }}</p>
            <p v-if="isAdmin" class="mt-1 text-[11px] font-medium text-[--accent]">Администратор</p>
          </div>
        </div>
        <button class="btn btn-ghost mt-4 text-red-400 hover:text-red-300" @click="handleLogout">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          Выйти
        </button>
      </div>

      <div v-if="sessionStats" class="card p-6">
        <h3 class="section-label mb-5">Сессии</h3>
        <div class="grid grid-cols-2 gap-6">
          <div>
            <p class="mb-1.5 text-[12px] text-[--t3]">Всего часов</p>
            <p class="text-[24px] leading-none font-bold tracking-tight text-[--t1]">
              {{ sessionStats.total_hours.toFixed(1) }}
            </p>
          </div>
          <div>
            <p class="mb-1.5 text-[12px] text-[--t3]">Сегодня (мин)</p>
            <p class="text-[24px] leading-none font-bold tracking-tight text-[--t1]">{{ sessionStats.today_min }}</p>
          </div>
          <div>
            <p class="mb-1.5 text-[12px] text-[--t3]">За неделю (ч)</p>
            <p class="text-[24px] leading-none font-bold tracking-tight text-[--t1]">
              {{ sessionStats.week_hours.toFixed(1) }}
            </p>
          </div>
          <div v-if="sessionStats.peak_hour !== null">
            <p class="mb-1.5 text-[12px] text-[--t3]">Пик</p>
            <p class="gradient-text text-[24px] leading-none font-bold tracking-tight">
              {{ sessionStats.peak_hour }}:00
            </p>
          </div>
        </div>
      </div>

      <div class="card p-6">
        <h3 class="section-label mb-4">Категории</h3>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="cat in constants?.categories"
            :key="cat"
            class="rounded-full px-3.5 py-1.5 text-[13px] font-medium text-[--t2]"
            style="background: rgba(255, 255, 255, 0.04); border: 1px solid var(--border)"
          >
            {{ cat }}
          </span>
        </div>
      </div>

      <!-- Downloads (native only) -->
      <div v-if="dl.isNative.value" class="card p-6">
        <h3 class="section-label mb-4">
          <span class="flex items-center gap-2">
            <IconDownload :size="16" />
            Загрузки
          </span>
        </h3>

        <div class="mb-4">
          <p class="mb-1 text-[12px] text-[--t3]">Общий объём</p>
          <p class="text-[20px] leading-none font-bold tracking-tight text-[--t1]">
            {{ fmtSize(dl.totalDownloadedSize.value) }}
          </p>
        </div>

        <div v-if="dl.downloadedBooks.value.length" class="mb-4 space-y-3">
          <div
            v-for="b in dl.downloadedBooks.value"
            :key="b.bookId"
            class="flex items-center justify-between gap-3 rounded-xl px-3.5 py-3"
            style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border)"
          >
            <div class="min-w-0 flex-1">
              <p class="truncate text-[13px] font-medium text-[--t1]">{{ b.title }}</p>
              <p class="text-[11px] text-[--t3]">{{ b.tracks.length }} треков · {{ fmtSize(b.totalSize) }}</p>
            </div>
            <button
              class="shrink-0 cursor-pointer rounded-lg border-0 bg-transparent p-2 text-[--t3] transition-colors hover:bg-white/5 hover:text-red-400"
              title="Удалить"
              @click="dl.deleteBook(b.bookId)"
            >
              <IconTrash :size="15" />
            </button>
          </div>
        </div>

        <p v-else class="mb-4 text-[12px] text-[--t3]">
          Нет скачанных книг. Скачайте книгу на странице книги для офлайн-прослушивания.
        </p>

        <button
          v-if="dl.downloadedBooks.value.length > 1"
          class="btn btn-ghost text-red-400 hover:text-red-300"
          @click="dl.deleteAllBooks()"
        >
          <IconTrash :size="14" />
          Удалить все загрузки
        </button>
      </div>

      <div class="card p-6">
        <h3 class="section-label mb-3">О системе</h3>
        <p class="text-[12px] leading-relaxed text-[--t3]">
          Веб-интерфейс аудиокниготеки v1.0<br />
          Backend: FastAPI / Frontend: Vue 3 + Tailwind<br />
          Данные хранятся в JSON-файлах на диске.
        </p>
      </div>
    </div>
  </div>
</template>
