<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Capacitor } from '@capacitor/core'
import { usePlayer } from '../../composables/usePlayer'
import { IconPlus } from '../shared/icons'

const router = useRouter()
const { t } = useI18n()
const { isPlayerVisible } = usePlayer()

const isOpen = ref(false)
const isNative = Capacitor.isNativePlatform()

const bottomOffset = () => (isPlayerVisible.value ? '130px' : '80px')

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

function pickFiles() {
  close()
  router.push('/upload')
}

function pickFolder() {
  close()
  router.push('/upload')
}

function openYouTube() {
  close()
  router.push('/youtube-import')
}

function openTTS() {
  close()
  router.push('/upload?tab=tts')
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && isOpen.value) close()
}
onMounted(() => document.addEventListener('keydown', onKeydown))
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
            <div class="text-[13px] font-semibold text-[--t1]">{{ t('fab.scan') }}</div>
            <div class="text-[10px] text-[--t3]">{{ t('fab.scanHint') }}</div>
          </div>
        </button>

        <!-- Files -->
        <button
          role="menuitem"
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="pickFiles"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-[16px]">📄</div>
          <div>
            <div class="text-[13px] font-semibold text-[--t1]">{{ t('fab.files') }}</div>
            <div class="text-[10px] text-[--t3]">MP3, M4A, M4B, ZIP</div>
          </div>
        </button>

        <!-- Folder -->
        <button
          role="menuitem"
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="pickFolder"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-[16px]">📂</div>
          <div>
            <div class="text-[13px] font-semibold text-[--t1]">{{ t('fab.folder') }}</div>
            <div class="text-[10px] text-[--t3]">{{ t('fab.folderHint') }}</div>
          </div>
        </button>

        <!-- Divider -->
        <div class="mx-3 my-1 h-px bg-white/[0.06]" />

        <!-- YouTube -->
        <button
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
            <div class="text-[13px] font-semibold text-[--t1]">YouTube</div>
            <div class="text-[10px] text-[--t3]">{{ t('fab.youtube') }}</div>
          </div>
        </button>

        <!-- TTS -->
        <button
          role="menuitem"
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
          @click="openTTS"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-[16px]">🗣</div>
          <div>
            <div class="text-[13px] font-semibold text-[--t1]">{{ t('fab.tts') }}</div>
            <div class="text-[10px] text-[--t3]">{{ t('fab.ttsHint') }}</div>
          </div>
        </button>
      </div>
    </transition>

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
