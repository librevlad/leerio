<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api, getServerUrl, setServerUrl } from '../api'
import { useTrello } from '../composables/useTrello'
import { useDownloads } from '../composables/useDownloads'
import type { Constants, SessionStats } from '../types'
import { IconSync, IconClock, IconTrash, IconDownload } from '../components/shared/icons'

const { status: trelloStatus, loadStatus, sync } = useTrello()
const dl = useDownloads()
const constants = ref<Constants | null>(null)
const sessionStats = ref<SessionStats | null>(null)
const syncing = ref(false)
const serverUrl = ref(getServerUrl())
const serverSaved = ref(false)

function saveServerUrl() {
  setServerUrl(serverUrl.value)
  serverSaved.value = true
  setTimeout(() => { serverSaved.value = false }, 2000)
}

onMounted(async () => {
  try {
    const [c, s] = await Promise.all([
      api.getConstants(),
      api.getSessionStats(30),
    ])
    constants.value = c
    sessionStats.value = s
  } catch { /* ignore */ }
  loadStatus()
})

async function syncTrello() {
  syncing.value = true
  try {
    await sync()
  } finally {
    syncing.value = false
  }
}

const cacheLabel = computed(() => {
  if (!trelloStatus.value?.cache_age_min) return null
  const m = trelloStatus.value.cache_age_min
  if (m < 60) return `${m} мин назад`
  const h = Math.floor(m / 60)
  return `${h} ч назад`
})

const LIST_ORDER = ['Прочесть', 'В процессе', 'В телефоне', 'На Паузе', 'Скачать', 'Прочитано', 'Забраковано']

function fmtSize(bytes: number): string {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' КБ'
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' МБ'
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' ГБ'
}
</script>

<template>
  <div>
    <h1 class="page-title mb-8">Настройки</h1>

    <div class="space-y-6 max-w-2xl">
      <!-- Server URL -->
      <div class="card p-6">
        <h3 class="section-label mb-4">Сервер</h3>
        <p class="text-[12px] text-[--t3] mb-3">
          URL сервера для доступа с другого устройства (например, телефона по Wi-Fi).
          Оставьте пустым для локального режима.
        </p>
        <div class="flex gap-3">
          <input
            v-model="serverUrl"
            type="text"
            class="input-field flex-1 px-4 py-2.5"
            placeholder="http://192.168.1.100:8000"
            @keyup.enter="saveServerUrl"
          />
          <button class="btn btn-primary shrink-0" @click="saveServerUrl">
            {{ serverSaved ? 'Сохранено!' : 'Сохранить' }}
          </button>
        </div>
      </div>

      <div class="card p-6">
        <h3 class="section-label mb-4">Trello</h3>
        <div class="flex items-center gap-3 mb-4">
          <span
            class="w-2.5 h-2.5 rounded-full"
            :class="constants?.trello_connected ? 'bg-emerald-400' : 'bg-red-400'"
            :style="constants?.trello_connected ? 'box-shadow: 0 0 8px rgba(52,211,153,0.4)' : 'box-shadow: 0 0 8px rgba(248,113,113,0.4)'"
          />
          <span class="text-[13px] text-[--t2] font-medium">
            {{ constants?.trello_connected ? 'Подключено' : 'Не подключено' }}
          </span>
        </div>

        <div class="flex flex-col sm:flex-row sm:items-center gap-3 mb-5">
          <button
            v-if="constants?.trello_connected"
            class="btn btn-ghost w-full sm:w-auto justify-center"
            :disabled="syncing"
            @click="syncTrello"
          >
            <IconSync :size="14" :class="syncing ? 'animate-spin' : ''" />
            {{ syncing ? 'Синхронизация...' : 'Синхронизировать' }}
          </button>

          <div v-if="cacheLabel" class="flex items-center gap-1.5 text-[12px] text-[--t3]">
            <IconClock :size="13" />
            <span>Кэш обновлён {{ cacheLabel }}</span>
          </div>
        </div>

        <!-- Mini stats -->
        <div v-if="trelloStatus" class="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div
            v-for="listName in LIST_ORDER.filter(l => (trelloStatus!.list_counts[l] ?? 0) > 0)"
            :key="listName"
            class="px-3.5 py-3 rounded-xl"
            style="background: rgba(255,255,255,0.03); border: 1px solid var(--border)"
          >
            <p class="text-[11px] text-[--t3] mb-1">{{ listName }}</p>
            <p class="text-[18px] font-bold text-[--t1] tracking-tight leading-none">
              {{ trelloStatus!.list_counts[listName] }}
            </p>
          </div>
        </div>
      </div>

      <div v-if="sessionStats" class="card p-6">
        <h3 class="section-label mb-5">Сессии</h3>
        <div class="grid grid-cols-2 gap-6">
          <div>
            <p class="text-[12px] text-[--t3] mb-1.5">Всего часов</p>
            <p class="text-[24px] font-bold text-[--t1] tracking-tight leading-none">{{ sessionStats.total_hours.toFixed(1) }}</p>
          </div>
          <div>
            <p class="text-[12px] text-[--t3] mb-1.5">Сегодня (мин)</p>
            <p class="text-[24px] font-bold text-[--t1] tracking-tight leading-none">{{ sessionStats.today_min }}</p>
          </div>
          <div>
            <p class="text-[12px] text-[--t3] mb-1.5">За неделю (ч)</p>
            <p class="text-[24px] font-bold text-[--t1] tracking-tight leading-none">{{ sessionStats.week_hours.toFixed(1) }}</p>
          </div>
          <div v-if="sessionStats.peak_hour !== null">
            <p class="text-[12px] text-[--t3] mb-1.5">Пик</p>
            <p class="text-[24px] font-bold gradient-text tracking-tight leading-none">{{ sessionStats.peak_hour }}:00</p>
          </div>
        </div>
      </div>

      <div class="card p-6">
        <h3 class="section-label mb-4">Категории</h3>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="cat in constants?.categories"
            :key="cat"
            class="px-3.5 py-1.5 text-[13px] rounded-full text-[--t2] font-medium"
            style="background: rgba(255,255,255,0.04); border: 1px solid var(--border)"
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
          <p class="text-[12px] text-[--t3] mb-1">Общий объём</p>
          <p class="text-[20px] font-bold text-[--t1] tracking-tight leading-none">
            {{ fmtSize(dl.totalDownloadedSize.value) }}
          </p>
        </div>

        <div v-if="dl.downloadedBooks.value.length" class="space-y-3 mb-4">
          <div
            v-for="b in dl.downloadedBooks.value"
            :key="b.bookId"
            class="flex items-center justify-between gap-3 px-3.5 py-3 rounded-xl"
            style="background: rgba(255,255,255,0.03); border: 1px solid var(--border)"
          >
            <div class="min-w-0 flex-1">
              <p class="text-[13px] font-medium text-[--t1] truncate">{{ b.title }}</p>
              <p class="text-[11px] text-[--t3]">
                {{ b.tracks.length }} треков · {{ fmtSize(b.totalSize) }}
              </p>
            </div>
            <button
              class="p-2 bg-transparent border-0 text-[--t3] hover:text-red-400 transition-colors cursor-pointer shrink-0 rounded-lg hover:bg-white/5"
              @click="dl.deleteBook(b.bookId)"
              title="Удалить"
            >
              <IconTrash :size="15" />
            </button>
          </div>
        </div>

        <p v-else class="text-[12px] text-[--t3] mb-4">
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
          Веб-интерфейс аудиокниготеки v1.0<br>
          Backend: FastAPI / Frontend: Vue 3 + Tailwind<br>
          Данные хранятся в JSON-файлах на диске.
        </p>
      </div>
    </div>
  </div>
</template>
