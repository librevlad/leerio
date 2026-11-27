<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Capacitor } from '@capacitor/core'
import { usePlayer } from '../../composables/usePlayer'
import { useAuth } from '../../composables/useAuth'
import { useNarration } from '../../composables/useNarration'
import { useCloud } from '../../composables/useCloud'
import { IconPlus } from '../shared/icons'

const router = useRouter()
const { t } = useI18n()
const { isPlayerVisible } = usePlayer()

const isOpen = ref(false)
const isNative = Capacitor.isNativePlatform()
const { serverReachable } = useAuth()
// Upload and server TTS need the server: hidden in the APK while it is unreachable
const serverItems = computed(() => !isNative || serverReachable.value)
const narration = useNarration()
// The owner's bucket: shown only where its key is on the device
const cloud = useCloud()
const bookInput = ref<HTMLInputElement | null>(null)

// Above the bottom nav (+ mini player) and the system navigation bar
const bottomOffset = () => `calc(${isPlayerVisible.value ? '130px' : '80px'} + env(safe-area-inset-bottom, 0px))`

function toggle() {
  isOpen.value = !isOpen.value
}

function close() {
  isOpen.value = false
}

function scanDevice() {
  close()
  router.push('/scan-results')
}

function openCloud() {
  close()
  router.push('/cloud')
}

function pickFiles() {
  close()
  router.push('/upload')
}

function openLocal() {
  close()
  router.push('/upload?tab=local')
}

function openYouTube() {
  close()
  router.push('/youtube-import')
}

function openTTS() {
  close()
  router.push('/upload?tab=tts')
}

// On-device narration: straight to the file picker; a running job shows its progress instead
function narrateBook() {
  close()
  if (narration.status.value.state === 'running') router.push('/narrate')
  else bookInput.value?.click()
}

function onBookPicked(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  narration.pickedFile.value = file
  router.push('/narrate')
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && isOpen.value) close()
}
onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  void cloud.init()
})
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <!-- Overlay -->
  <Teleport to="body">
    <transition name="fade">
      <div v-if="isOpen" class="fixed inset-0 z-40 bg-black/50" @click="close" />
    </transition>

    <!-- Popup menu -->
    <transition name="scale-up">
      <div
        v-if="isOpen"
        role="menu"
        :aria-label="t('fab.menuLabel')"
        class="fixed right-4 z-50 w-[220px] rounded-2xl p-1.5 shadow-2xl"
        :style="{ bottom: `calc(${bottomOffset()} + 60px)` }"
        style="background: var(--card-solid)"
      >
        <!-- Scan (APK only) -->
        <button
          v-if="isNative"
          role="menuitem"
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="scanDevice"
        >
          <div
            class="flex h-8 w-8 items-center justify-center rounded-lg text-[16px]"
            style="background: rgba(249, 115, 22, 0.15)"
          >
            📱
          </div>
          <div>
            <div class="text-[13px] font-semibold text-(--t1)">{{ t('fab.scan') }}</div>
            <div class="text-[10px] text-(--t3)">{{ t('fab.scanHint') }}</div>
          </div>
        </button>

        <!-- The owner's cloud bucket (APK with cloud.json) -->
        <button
          v-if="cloud.available.value"
          role="menuitem"
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="openCloud"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-[16px]">☁️</div>
          <div>
            <div class="text-[13px] font-semibold text-(--t1)">{{ t('fab.cloud') }}</div>
            <div class="text-[10px] text-(--t3)">{{ t('fab.cloudHint') }}</div>
          </div>
        </button>

        <!-- Files (server upload) -->
        <button
          v-if="serverItems"
          role="menuitem"
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="pickFiles"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-[16px]">📄</div>
          <div>
            <div class="text-[13px] font-semibold text-(--t1)">{{ t('fab.files') }}</div>
            <div class="text-[10px] text-(--t3)">MP3, M4A, M4B, ZIP</div>
          </div>
        </button>

        <!-- Local (web only — saves to IndexedDB, no server upload) -->
        <button
          v-if="!isNative"
          role="menuitem"
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="openLocal"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-[16px]">📂</div>
          <div>
            <div class="text-[13px] font-semibold text-(--t1)">{{ t('fab.local') }}</div>
            <div class="text-[10px] text-(--t3)">{{ t('fab.localHint') }}</div>
          </div>
        </button>

        <!-- Divider -->
        <div v-if="serverItems" class="mx-3 my-1 h-px bg-white/[0.06]" />

        <!-- YouTube (web only: downloading from YouTube is against Google Play policy) -->
        <button
          v-if="!isNative"
          role="menuitem"
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="openYouTube"
        >
          <div
            class="flex h-8 w-8 items-center justify-center rounded-lg text-[16px]"
            style="background: rgba(255, 0, 0, 0.1)"
          >
            🎥
          </div>
          <div>
            <div class="text-[13px] font-semibold text-(--t1)">YouTube</div>
            <div class="text-[10px] text-(--t3)">{{ t('fab.youtube') }}</div>
          </div>
        </button>

        <!-- Narration on the phone (APK) -->
        <button
          v-if="isNative"
          role="menuitem"
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="narrateBook"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-[16px]">🎙</div>
          <div>
            <div class="text-[13px] font-semibold text-(--t1)">{{ t('fab.narrate') }}</div>
            <div class="text-[10px] text-(--t3)">{{ t('fab.narrateHint') }}</div>
          </div>
        </button>

        <!-- TTS (server; the APK narrates on the phone instead) -->
        <button
          v-if="serverItems && !isNative"
          role="menuitem"
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="openTTS"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-[16px]">🗣</div>
          <div>
            <div class="text-[13px] font-semibold text-(--t1)">{{ t('fab.tts') }}</div>
            <div class="text-[10px] text-(--t3)">{{ t('fab.ttsHint') }}</div>
          </div>
        </button>
      </div>
    </transition>

    <!-- Ebook for narration: any type — Android hides .fb2 behind a MIME filter -->
    <input v-if="isNative" ref="bookInput" type="file" class="hidden" @change="onBookPicked" />

    <!-- FAB button -->
    <button
      :aria-label="t('fab.addBook')"
      :aria-expanded="isOpen"
      class="fixed right-4 z-50 flex h-[52px] w-[52px] items-center justify-center rounded-full text-white shadow-lg transition-transform duration-200"
      :class="isOpen ? 'rotate-45' : ''"
      :style="{
        bottom: bottomOffset(),
        background: 'var(--gradient-accent)',
        boxShadow: '0 4px 12px rgba(249,115,22,0.4)',
      }"
      @click="toggle"
    >
      <IconPlus :size="24" />
    </button>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.scale-up-enter-active {
  transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.scale-up-leave-active {
  transition: all 0.15s ease-in;
}
.scale-up-enter-from {
  opacity: 0;
  transform: scale(0.8) translateY(10px);
}
.scale-up-leave-to {
  opacity: 0;
  transform: scale(0.9);
}
</style>
