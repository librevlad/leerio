<script setup lang="ts">
import { reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import type { HistoryEntry } from '../../types'
import { coverUrl } from '../../api'
import {
  IconStar,
  IconInbox,
  IconPlay,
  IconSmartphone,
  IconCheck,
  IconPause,
  IconXCircle,
  IconSync,
  IconTrash,
  IconDownload,
  IconMusic,
} from '../shared/icons'

defineProps<{ entries: HistoryEntry[] }>()

const { t } = useI18n()
const coverErrors = reactive(new Set<string>())

const actionIcon: Record<string, unknown> = {
  inbox: IconInbox,
  listen: IconPlay,
  phone: IconSmartphone,
  done: IconCheck,
  pause: IconPause,
  reject: IconXCircle,
  relisten: IconSync,
  move: IconInbox,
  undo: IconSync,
  delete: IconTrash,
  download: IconDownload,
  rated: IconStar,
}

import { actionColor, actionFallback } from '../../composables/useStatusColors'

function timeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return t('dashboard.timeAgoMin', { n: mins })
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return t('dashboard.timeAgoH', { n: hrs })
  const days = Math.floor(hrs / 24)
  return t('dashboard.timeAgoD', { n: days })
}
</script>

<template>
  <div v-if="entries.length">
    <div class="mb-4 flex items-center justify-between">
      <h2 class="section-label">{{ t('dashboard.recentActivity') }}</h2>
      <router-link
        to="/history"
        class="inline-flex min-h-[44px] items-center text-[12px] font-medium text-[--accent] no-underline hover:underline"
      >
        {{ t('dashboard.allActions') }}
      </router-link>
    </div>
    <div class="space-y-2">
      <div
        v-for="(e, i) in entries"
        :key="i"
        v-ripple
        class="stagger-item card card-hover flex items-center gap-3 p-3"
        :style="{ animationDelay: `${i * 50}ms` }"
      >
        <!-- Action icon -->
        <div
          class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg"
          :style="{
            background: (actionColor[e.action] || actionFallback).bg,
            color: (actionColor[e.action] || actionFallback).fg,
          }"
        >
          <component :is="actionIcon[e.action] || IconInbox" :size="16" />
        </div>

        <!-- Book cover (if available) -->
        <div v-if="e.book_id" class="h-9 w-9 flex-shrink-0 overflow-hidden rounded-lg">
          <img
            v-if="!coverErrors.has(e.book_id)"
            :src="coverUrl(e.book_id)"
            :alt="e.book"
            class="h-full w-full object-cover"
            @error="coverErrors.add(e.book_id)"
          />
          <div v-else class="flex h-full w-full items-center justify-center" style="background: var(--accent-bg)">
            <IconMusic :size="14" class="text-[--t3]" />
          </div>
        </div>

        <!-- Content -->
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <span
              class="flex-shrink-0 text-[12px] font-semibold"
              :style="{ color: (actionColor[e.action] || actionFallback).fg }"
            >
              {{ e.action_label }}
            </span>
            <span class="text-[11px] text-[--t3]">{{ timeAgo(e.ts) }}</span>
          </div>
          <router-link
            v-if="e.book_id"
            :to="`/book/${e.book_id}`"
            class="mt-0.5 block truncate py-1 text-[13px] font-medium text-[--t2] no-underline transition-colors hover:text-[--t1]"
          >
            {{ e.book }}
          </router-link>
          <span v-else class="mt-0.5 block truncate text-[13px] text-[--t2]">
            {{ e.book }}
          </span>
        </div>

        <!-- Rating -->
        <div v-if="e.rating" class="ml-2 flex flex-shrink-0 gap-0.5 text-amber-400/60">
          <IconStar v-for="s in e.rating" :key="s" :size="12" />
        </div>
      </div>
    </div>
  </div>
</template>
