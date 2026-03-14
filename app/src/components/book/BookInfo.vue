<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Book } from '../../types'
import { coverUrl } from '../../api'
import CategoryBadge from '../shared/CategoryBadge.vue'
import { useCategories } from '../../composables/useCategories'
import ProgressRing from '../shared/ProgressRing.vue'
import {
  IconStar,
  IconStarOutline,
  IconHardDrive,
  IconMusic,
  IconClock,
  IconHeadphones,
  IconPlay,
} from '../shared/icons'
const props = defineProps<{ book: Book; isCurrentBook?: boolean }>()
const emit = defineEmits<{ listen: []; ratingChanged: [rating: number] }>()
const { t } = useI18n()

const descExpanded = ref(false)
const coverLoaded = ref(false)
const coverError = ref(false)
const hasCover = computed(() => props.book.has_cover && !coverError.value)

const hasMetadata = () => props.book.size_mb || props.book.mp3_count || props.book.duration_fmt || props.book.rating

const { gradient: catGradient } = useCategories()
const coverPattern = 'radial-gradient(circle at 50% 50%, rgba(255,255,255,0.1) 0%, transparent 50%)'
const hoverStar = ref(0)

function onStarClick(star: number) {
  const newRating = star === props.book.rating ? 0 : star
  emit('ratingChanged', newRating)
}

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

const lastPosition = computed(() => {
  if (!props.book.progress || !props.book.duration_hours) return null
  const totalSec = props.book.duration_hours * 3600
  const elapsedSec = (props.book.progress / 100) * totalSec
  const h = Math.floor(elapsedSec / 3600)
  const m = Math.round((elapsedSec % 3600) / 60)
  if (h > 0) return `${h}${t('common.unitH')} ${m}${t('common.unitM')}`
  return `${m}${t('common.unitM')}`
})
</script>

<template>
  <div class="card overflow-hidden">
    <!-- Gradient backdrop -->
    <div class="relative h-[100px] overflow-hidden" :style="{ background: catGradient(book.category) }">
      <div class="absolute inset-0" :style="{ background: coverPattern }" />
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
            class="relative h-[160px] w-[160px] shrink-0 overflow-hidden rounded-lg shadow-lg"
            :style="!hasCover ? { background: catGradient(book.category) } : {}"
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
            <div v-if="!hasCover" class="absolute inset-0" :style="{ background: coverPattern }" />
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

        <!-- Progress bar (mobile) -->
        <div v-if="book.progress > 0" class="mt-4">
          <div class="flex items-center justify-between text-[11px]">
            <span class="font-semibold text-[--accent]"
              >{{ Math.round(book.progress) }}% {{ t('book.percentListened') }}</span
            >
            <span v-if="remainingHours !== null" class="text-[--t3]">{{
              t('book.remainingH', { hours: remainingHours })
            }}</span>
          </div>
          <div class="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
            <div
              class="h-full rounded-full transition-all duration-500"
              style="background: linear-gradient(90deg, var(--accent), var(--accent-2))"
              :style="{ width: `${Math.min(book.progress, 100)}%` }"
            />
          </div>
        </div>

        <!-- Listen button (mobile) -->
        <button
          v-if="book.mp3_count && book.mp3_count > 0"
          class="btn btn-primary mt-4 w-full px-7 py-3 text-[15px]"
          style="
            box-shadow:
              0 6px 28px rgba(232, 146, 58, 0.3),
              inset 0 1px 0 rgba(255, 255, 255, 0.15);
          "
          @click="emit('listen')"
        >
          <IconPlay :size="16" />
          {{ isCurrentBook ? t('book.continue') : t('book.listen') }}
        </button>
        <p v-if="isCurrentBook && lastPosition" class="mt-2 text-center text-[11px] text-[--t3]">
          {{ t('book.lastPosition', { pos: lastPosition }) }}
        </p>

        <!-- Progress stats (mobile) -->
        <div v-if="book.progress > 0" class="mt-3 flex flex-wrap items-center gap-3 text-[12px]">
          <ProgressRing :percent="book.progress" :size="48" :stroke="3" />
          <div class="flex flex-wrap gap-x-4 gap-y-1">
            <span v-if="listenedHours !== null" class="text-[--t2]">
              {{ t('book.listenedOf', { hours: listenedHours }) }}
              {{ book.duration_hours }} {{ t('common.unitH') }}
            </span>
            <span v-if="startDate" class="text-[--t3]"> {{ t('book.startedAt', { date: startDate }) }} </span>
          </div>
        </div>
      </div>

      <!-- Desktop layout (>=md) -->
      <div class="hidden md:block">
        <div class="-mt-24 flex gap-6">
          <!-- Cover -->
          <div
            class="relative h-[200px] w-[200px] shrink-0 overflow-hidden rounded-lg shadow-lg"
            :style="!hasCover ? { background: catGradient(book.category) } : {}"
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
            <div v-if="!hasCover" class="absolute inset-0" :style="{ background: coverPattern }" />
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
                  <p class="text-[11px] text-[--t3]">{{ t('book.size') }}</p>
                </div>
              </div>
              <div v-if="book.mp3_count" class="flex items-center gap-2.5">
                <span class="stat-icon" style="background: rgba(6, 182, 212, 0.1)">
                  <IconMusic :size="14" class="text-cyan-400" />
                </span>
                <div>
                  <span class="text-[12px] font-semibold text-[--t1]">{{ book.mp3_count }}</span>
                  <p class="text-[11px] text-[--t3]">{{ t('book.files') }}</p>
                </div>
              </div>
              <div v-if="book.duration_fmt" class="flex items-center gap-2.5">
                <span class="stat-icon" style="background: rgba(245, 158, 11, 0.1)">
                  <IconClock :size="14" class="text-amber-400" />
                </span>
                <div>
                  <span class="text-[12px] font-semibold text-[--t1]">{{ book.duration_fmt }}</span>
                  <p class="text-[11px] text-[--t3]">{{ t('book.duration') }}</p>
                </div>
              </div>
              <div v-if="book.progress > 0" class="ml-1">
                <ProgressRing :percent="book.progress" :size="64" :stroke="4" />
              </div>
              <div class="ml-auto flex items-center gap-2.5" @mouseleave="hoverStar = 0">
                <div class="flex gap-0.5">
                  <button
                    v-for="s in 5"
                    :key="s"
                    class="cursor-pointer border-0 bg-transparent p-0.5 transition-transform hover:scale-110"
                    :class="
                      (hoverStar ? s <= hoverStar : s <= (book.rating || 0))
                        ? 'text-amber-400'
                        : 'text-white/15 hover:text-amber-400/50'
                    "
                    :title="`${s} ${t('common.outOf')} 5`"
                    @mouseenter="hoverStar = s"
                    @click="onStarClick(s)"
                  >
                    <component
                      :is="(hoverStar ? s <= hoverStar : s <= (book.rating || 0)) ? IconStar : IconStarOutline"
                      :size="18"
                    />
                  </button>
                </div>
              </div>
            </div>

            <!-- Progress bar (desktop) -->
            <div v-if="book.progress > 0" class="mt-3">
              <div class="flex items-center justify-between text-[11px]">
                <span class="font-semibold text-[--accent]"
                  >{{ Math.round(book.progress) }}% {{ t('book.percentListened') }}</span
                >
                <span v-if="remainingHours !== null" class="text-[--t3]">{{
                  t('book.remainingH', { hours: remainingHours })
                }}</span>
              </div>
              <div class="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  style="background: linear-gradient(90deg, var(--accent), var(--accent-2))"
                  :style="{ width: `${Math.min(book.progress, 100)}%` }"
                />
              </div>
            </div>

            <!-- Listening stats -->
            <div v-if="book.progress > 0" class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px]">
              <span v-if="listenedHours !== null" class="text-[--t2]">
                {{ t('book.listenedOf', { hours: listenedHours }) }}
                {{ book.duration_hours }} {{ t('common.unitH') }}
              </span>
              <span v-if="startDate" class="text-[--t3]"> {{ t('book.startedAt', { date: startDate }) }} </span>
            </div>

            <!-- Listen button (desktop) -->
            <div class="mt-4 flex items-center gap-3">
              <button
                v-if="book.mp3_count && book.mp3_count > 0"
                class="btn btn-primary self-start px-7 py-3 text-[15px]"
                style="
                  box-shadow:
                    0 6px 28px rgba(232, 146, 58, 0.3),
                    inset 0 1px 0 rgba(255, 255, 255, 0.15);
                "
                @click="emit('listen')"
              >
                <IconPlay :size="16" />
                {{ isCurrentBook ? t('book.continue') : t('book.listen') }}
              </button>
              <span v-if="isCurrentBook && lastPosition" class="text-[12px] text-[--t3]">
                {{ t('book.lastPosition', { pos: lastPosition }) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Description -->
      <div v-if="book.description" class="mt-4 border-t border-white/[0.04] px-1 pt-4">
        <p class="text-[13px] leading-relaxed text-[--t2]" :class="{ 'line-clamp-3': !descExpanded }">
          {{ book.description }}
        </p>
        <button
          v-if="book.description.length > 200"
          class="mt-1 cursor-pointer border-0 bg-transparent p-0 text-[12px] text-[--accent] hover:underline"
          @click="descExpanded = !descExpanded"
        >
          {{ descExpanded ? t('book.collapse') : t('book.readMore') }}
        </button>
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
            <p class="text-[10px] text-[--t3]">{{ t('book.size') }}</p>
          </div>
        </div>
        <div v-if="book.mp3_count" class="flex items-center gap-2.5">
          <span class="stat-icon" style="background: rgba(6, 182, 212, 0.1)">
            <IconMusic :size="14" class="text-cyan-400" />
          </span>
          <div>
            <span class="text-[12px] font-semibold text-[--t1]">{{ book.mp3_count }}</span>
            <p class="text-[10px] text-[--t3]">{{ t('book.files') }}</p>
          </div>
        </div>
        <div v-if="book.duration_fmt" class="flex items-center gap-2.5">
          <span class="stat-icon" style="background: rgba(245, 158, 11, 0.1)">
            <IconClock :size="14" class="text-amber-400" />
          </span>
          <div>
            <span class="text-[12px] font-semibold text-[--t1]">{{ book.duration_fmt }}</span>
            <p class="text-[10px] text-[--t3]">{{ t('book.duration') }}</p>
          </div>
        </div>
        <div class="ml-auto flex items-center gap-2.5" @mouseleave="hoverStar = 0">
          <div class="flex gap-0.5">
            <button
              v-for="s in 5"
              :key="s"
              class="cursor-pointer border-0 bg-transparent p-0.5 transition-transform hover:scale-110"
              :class="
                (hoverStar ? s <= hoverStar : s <= (book.rating || 0))
                  ? 'text-amber-400'
                  : 'text-white/15 hover:text-amber-400/50'
              "
              @mouseenter="hoverStar = s"
              @click="onStarClick(s)"
            >
              <component
                :is="(hoverStar ? s <= hoverStar : s <= (book.rating || 0)) ? IconStar : IconStarOutline"
                :size="16"
              />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
