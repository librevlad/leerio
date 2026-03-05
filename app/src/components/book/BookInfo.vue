<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Book } from '../../types'
import { coverUrl } from '../../api'
import CategoryBadge from '../shared/CategoryBadge.vue'
import ProgressRing from '../shared/ProgressRing.vue'
import { IconStar, IconStarOutline, IconHardDrive, IconMusic, IconClock, IconHeadphones } from '../shared/icons'

const props = defineProps<{ book: Book }>()
const coverLoaded = ref(false)
const coverError = ref(false)
const hasCover = computed(() => props.book.has_cover && !coverError.value)

const hasMetadata = () => props.book.size_mb || props.book.mp3_count || props.book.duration_fmt || props.book.rating

const coverGradient: Record<string, string> = {
  Бизнес: 'linear-gradient(135deg, #92400e 0%, #d97706 50%, #fbbf24 100%)',
  Отношения: 'linear-gradient(135deg, #9d174d 0%, #db2777 50%, #f472b6 100%)',
  Саморазвитие: 'linear-gradient(135deg, #9a5c16 0%, #E8923A 50%, #F0A85C 100%)',
  Художественная: 'linear-gradient(135deg, #155e75 0%, #0891b2 50%, #22d3ee 100%)',
  Языки: 'linear-gradient(135deg, #064e3b 0%, #059669 50%, #34d399 100%)',
}

const coverPattern: Record<string, string> = {
  Бизнес:
    'radial-gradient(circle at 80% 20%, rgba(255,255,255,0.18) 0%, transparent 50%), radial-gradient(circle at 20% 80%, rgba(0,0,0,0.15) 0%, transparent 50%)',
  Отношения:
    'radial-gradient(circle at 20% 30%, rgba(255,255,255,0.15) 0%, transparent 50%), radial-gradient(circle at 80% 70%, rgba(0,0,0,0.15) 0%, transparent 50%)',
  Саморазвитие:
    'radial-gradient(circle at 70% 20%, rgba(255,255,255,0.15) 0%, transparent 50%), radial-gradient(circle at 30% 80%, rgba(0,0,0,0.15) 0%, transparent 50%)',
  Художественная:
    'radial-gradient(circle at 30% 30%, rgba(255,255,255,0.18) 0%, transparent 50%), radial-gradient(circle at 70% 70%, rgba(0,0,0,0.15) 0%, transparent 50%)',
  Языки:
    'radial-gradient(circle at 80% 30%, rgba(255,255,255,0.15) 0%, transparent 50%), radial-gradient(circle at 20% 70%, rgba(0,0,0,0.15) 0%, transparent 50%)',
}

const fallbackGradient = 'linear-gradient(135deg, #78350f 0%, #b45309 50%, #d97706 100%)'
const fallbackPattern = 'radial-gradient(circle at 50% 30%, rgba(255,255,255,0.12) 0%, transparent 50%)'

const listenedHours = computed(() => {
  if (!props.book.progress || !props.book.duration_hours) return null
  return Math.round(((props.book.progress * props.book.duration_hours) / 100) * 10) / 10
})

const remainingHours = computed(() => {
  if (!props.book.progress || !props.book.duration_hours) return null
  return Math.round(props.book.duration_hours * (1 - props.book.progress / 100) * 10) / 10
})

const startDate = computed(() => {
  if (!props.book.timeline?.length) return null
  const first = props.book.timeline[props.book.timeline.length - 1]
  if (!first?.ts) return null
  try {
    return new Date(first.ts).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
  } catch {
    return null
  }
})
</script>

<template>
  <div class="card overflow-hidden">
    <!-- Gradient backdrop -->
    <div
      class="relative h-[100px] overflow-hidden"
      :style="{ background: coverGradient[book.category] || fallbackGradient }"
    >
      <div class="absolute inset-0" :style="{ background: coverPattern[book.category] || fallbackPattern }" />
      <div class="absolute inset-0" style="backdrop-filter: blur(2px)" />
      <div
        class="absolute inset-0"
        style="background: linear-gradient(to bottom, transparent 0%, rgba(0, 0, 0, 0.6) 100%)"
      />
    </div>

    <!-- Content area -->
    <div class="relative px-5 pb-5">
      <!-- Mobile layout (<md) -->
      <div class="md:hidden">
        <!-- Cover + title row -->
        <div class="-mt-16 flex gap-4">
          <!-- Cover -->
          <div
            class="relative h-[140px] w-[140px] shrink-0 overflow-hidden rounded-lg shadow-lg"
            :style="!hasCover ? { background: coverGradient[book.category] || fallbackGradient } : {}"
          >
            <img
              v-if="hasCover"
              :src="coverUrl(book.id)"
              :alt="book.title"
              class="h-full w-full object-cover transition-opacity duration-300"
              :class="coverLoaded ? 'opacity-100' : 'opacity-0'"
              @load="coverLoaded = true"
              @error="coverError = true"
            />
            <div
              v-if="!hasCover"
              class="absolute inset-0"
              :style="{ background: coverPattern[book.category] || fallbackPattern }"
            />
          </div>
          <!-- Title info -->
          <div class="flex min-w-0 flex-col justify-end pt-16 pb-1">
            <CategoryBadge :category="book.category" class="mb-2 self-start" />
            <h1 class="text-[20px] leading-tight font-extrabold tracking-tight text-[--t1]" :title="book.title">
              {{ book.title }}
            </h1>
            <p v-if="book.author" class="mt-1 text-[13px] text-[--t2]" :title="book.author">{{ book.author }}</p>
            <p
              v-if="book.reader && book.reader !== book.author"
              class="mt-0.5 flex items-center gap-1.5 text-[12px] text-[--t3]"
            >
              <IconHeadphones :size="12" />
              {{ book.reader }}
            </p>
          </div>
        </div>

        <!-- Progress stats (mobile) -->
        <div v-if="book.progress > 0" class="mt-4 flex flex-wrap items-center gap-3 text-[12px]">
          <ProgressRing :percent="book.progress" :size="48" :stroke="3" />
          <div class="flex flex-wrap gap-x-4 gap-y-1">
            <span v-if="listenedHours !== null" class="text-[--t2]">
              Прослушано <span class="font-semibold text-[--t1]">{{ listenedHours }}</span> из
              {{ book.duration_hours }} ч
            </span>
            <span v-if="remainingHours !== null" class="text-[--t3]"> Осталось ~{{ remainingHours }} ч </span>
            <span v-if="startDate" class="text-[--t3]"> Начато: {{ startDate }} </span>
          </div>
        </div>
      </div>

      <!-- Desktop layout (>=md) -->
      <div class="hidden md:block">
        <div class="-mt-24 flex gap-6">
          <!-- Cover -->
          <div
            class="relative h-[200px] w-[200px] shrink-0 overflow-hidden rounded-lg shadow-lg"
            :style="!hasCover ? { background: coverGradient[book.category] || fallbackGradient } : {}"
          >
            <img
              v-if="hasCover"
              :src="coverUrl(book.id)"
              :alt="book.title"
              class="h-full w-full object-cover transition-opacity duration-300"
              :class="coverLoaded ? 'opacity-100' : 'opacity-0'"
              @load="coverLoaded = true"
              @error="coverError = true"
            />
            <div
              v-if="!hasCover"
              class="absolute inset-0"
              :style="{ background: coverPattern[book.category] || fallbackPattern }"
            />
          </div>
          <!-- Info -->
          <div class="flex min-w-0 flex-1 flex-col justify-end pt-24 pb-1">
            <CategoryBadge :category="book.category" class="mb-2.5 self-start" />
            <h1 class="text-[28px] leading-tight font-extrabold tracking-tight text-[--t1]" :title="book.title">
              {{ book.title }}
            </h1>
            <p v-if="book.author" class="mt-1.5 text-[14px] text-[--t2]" :title="book.author">{{ book.author }}</p>
            <p
              v-if="book.reader && book.reader !== book.author"
              class="mt-1 flex items-center gap-1.5 text-[13px] text-[--t3]"
            >
              <IconHeadphones :size="13" />
              {{ book.reader }}
            </p>

            <!-- Metadata + progress + rating row -->
            <div class="mt-4 flex flex-wrap items-center gap-5">
              <div v-if="book.size_mb" class="flex items-center gap-2.5">
                <span class="stat-icon" style="background: rgba(232, 146, 58, 0.1)">
                  <IconHardDrive :size="14" class="text-[--accent-2]" />
                </span>
                <div>
                  <span class="text-[12px] font-semibold text-[--t1]"
                    >{{ typeof book.size_mb === 'number' ? book.size_mb.toFixed(1) : book.size_mb }} МБ</span
                  >
                  <p class="text-[11px] text-[--t3]">Размер</p>
                </div>
              </div>
              <div v-if="book.mp3_count" class="flex items-center gap-2.5">
                <span class="stat-icon" style="background: rgba(6, 182, 212, 0.1)">
                  <IconMusic :size="14" class="text-cyan-400" />
                </span>
                <div>
                  <span class="text-[12px] font-semibold text-[--t1]">{{ book.mp3_count }}</span>
                  <p class="text-[11px] text-[--t3]">Файлов</p>
                </div>
              </div>
              <div v-if="book.duration_fmt" class="flex items-center gap-2.5">
                <span class="stat-icon" style="background: rgba(245, 158, 11, 0.1)">
                  <IconClock :size="14" class="text-amber-400" />
                </span>
                <div>
                  <span class="text-[12px] font-semibold text-[--t1]">{{ book.duration_fmt }}</span>
                  <p class="text-[11px] text-[--t3]">Длительность</p>
                </div>
              </div>
              <div v-if="book.progress > 0" class="ml-1">
                <ProgressRing :percent="book.progress" :size="64" :stroke="4" />
              </div>
              <div v-if="book.rating" class="ml-auto flex items-center gap-2.5">
                <div class="flex gap-0.5 text-amber-400">
                  <template v-for="s in 5" :key="s">
                    <component :is="s <= book.rating ? IconStar : IconStarOutline" :size="16" />
                  </template>
                </div>
              </div>
            </div>

            <!-- Listening stats -->
            <div v-if="book.progress > 0" class="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12px]">
              <span v-if="listenedHours !== null" class="text-[--t2]">
                Прослушано <span class="font-semibold text-[--t1]">{{ listenedHours }}</span> из
                {{ book.duration_hours }} ч
              </span>
              <span v-if="remainingHours !== null" class="text-[--t3]"> Осталось ~{{ remainingHours }} ч </span>
              <span v-if="startDate" class="text-[--t3]"> Начато: {{ startDate }} </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Metadata row (mobile only — desktop has it inline) -->
      <div
        v-if="hasMetadata()"
        class="mt-4 flex flex-wrap items-center gap-5 border-t border-white/[0.04] pt-4 md:hidden"
      >
        <div v-if="book.size_mb" class="flex items-center gap-2.5">
          <span class="stat-icon" style="background: rgba(232, 146, 58, 0.1)">
            <IconHardDrive :size="14" class="text-[--accent-2]" />
          </span>
          <div>
            <span class="text-[12px] font-semibold text-[--t1]"
              >{{ typeof book.size_mb === 'number' ? book.size_mb.toFixed(1) : book.size_mb }} МБ</span
            >
            <p class="text-[10px] text-[--t3]">Размер</p>
          </div>
        </div>
        <div v-if="book.mp3_count" class="flex items-center gap-2.5">
          <span class="stat-icon" style="background: rgba(6, 182, 212, 0.1)">
            <IconMusic :size="14" class="text-cyan-400" />
          </span>
          <div>
            <span class="text-[12px] font-semibold text-[--t1]">{{ book.mp3_count }}</span>
            <p class="text-[10px] text-[--t3]">Файлов</p>
          </div>
        </div>
        <div v-if="book.duration_fmt" class="flex items-center gap-2.5">
          <span class="stat-icon" style="background: rgba(245, 158, 11, 0.1)">
            <IconClock :size="14" class="text-amber-400" />
          </span>
          <div>
            <span class="text-[12px] font-semibold text-[--t1]">{{ book.duration_fmt }}</span>
            <p class="text-[10px] text-[--t3]">Длительность</p>
          </div>
        </div>
        <div v-if="book.rating" class="ml-auto flex items-center gap-2.5">
          <div class="flex gap-0.5 text-amber-400">
            <template v-for="s in 5" :key="s">
              <component :is="s <= book.rating ? IconStar : IconStarOutline" :size="16" />
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
