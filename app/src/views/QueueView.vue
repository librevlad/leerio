<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useTrello } from '../composables/useTrello'
import SearchInput from '../components/shared/SearchInput.vue'
import CategoryBadge from '../components/shared/CategoryBadge.vue'
import EmptyState from '../components/shared/EmptyState.vue'

const { cards, status, loading, loadCards, loadStatus, moveCard } = useTrello()

const TABS = ['Прочесть', 'В процессе', 'В телефоне', 'На Паузе', 'Скачать', 'Прочитано', 'Забраковано'] as const

type TabName = (typeof TABS)[number]

const TAB_ACTIONS: Record<string, { target: string; label: string; style: string }[]> = {
  Прочесть: [
    { target: 'В процессе', label: 'Слушать', style: 'ghost' },
    { target: 'В телефоне', label: 'Телефон', style: 'ghost' },
    { target: 'Забраковано', label: 'Отклонить', style: 'danger' },
  ],
  'В процессе': [
    { target: 'На Паузе', label: 'Пауза', style: 'ghost' },
    { target: 'Прочитано', label: 'Прослушано', style: 'primary' },
  ],
  'В телефоне': [
    { target: 'В процессе', label: 'Слушать', style: 'ghost' },
    { target: 'Прочитано', label: 'Прослушано', style: 'primary' },
  ],
  'На Паузе': [
    { target: 'В процессе', label: 'Продолжить', style: 'ghost' },
    { target: 'Забраковано', label: 'Отклонить', style: 'danger' },
  ],
  Скачать: [{ target: 'Прочесть', label: 'В очередь', style: 'ghost' }],
  Забраковано: [{ target: 'Прочесть', label: 'Восстановить', style: 'ghost' }],
  Прочитано: [],
}

const activeTab = ref<TabName>('Прочесть')
const search = ref('')
const actionLoading = ref<string | null>(null)

const filteredCards = computed(() => {
  if (!search.value) return cards.value
  const q = search.value.toLowerCase()
  return cards.value.filter(
    (c) => c.title.toLowerCase().includes(q) || c.author.toLowerCase().includes(q) || c.name.toLowerCase().includes(q),
  )
})

function tabCount(tab: string): number {
  return status.value?.list_counts[tab] ?? 0
}

async function switchTab(tab: TabName) {
  activeTab.value = tab
  await loadCards(tab)
}

async function doMove(cardId: string, target: string) {
  actionLoading.value = cardId
  await moveCard(cardId, target)
  await loadCards(activeTab.value)
  actionLoading.value = null
}

onMounted(async () => {
  await Promise.all([loadCards('Прочесть'), loadStatus()])
})
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <h1 class="page-title">Очередь</h1>
      <span class="text-[12px] text-[--t3]">{{ status?.total_cards ?? '...' }} карточек</span>
    </div>

    <SearchInput v-model="search" placeholder="Поиск по очереди..." class="mb-5" />

    <!-- Tabs -->
    <div
      class="scrollbar-hide -mx-4 mb-6 flex gap-1.5 overflow-x-auto px-4 pb-1 md:-mx-1 md:px-1"
      style="-webkit-overflow-scrolling: touch"
    >
      <button
        v-for="tab in TABS"
        :key="tab"
        class="flex cursor-pointer items-center gap-1.5 rounded-full border-0 px-3.5 py-2.5 text-[13px] font-medium whitespace-nowrap transition-all md:py-2 md:text-[12px]"
        :class="
          activeTab === tab
            ? 'bg-white/10 text-[--t1] shadow-sm'
            : 'bg-transparent text-[--t3] hover:bg-white/5 hover:text-[--t2]'
        "
        @click="switchTab(tab)"
      >
        {{ tab }}
        <span
          v-if="tabCount(tab)"
          class="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full px-1 text-[10px] font-bold"
          :class="activeTab === tab ? 'bg-white/15 text-[--t1]' : 'bg-white/5 text-[--t3]'"
        >
          {{ tabCount(tab) }}
        </span>
      </button>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 5" :key="i" class="skeleton h-20" />
    </div>

    <!-- Cards list -->
    <div v-else-if="filteredCards.length" class="space-y-2">
      <div
        v-for="card in filteredCards"
        :key="card.id"
        class="card flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center"
      >
        <div class="min-w-0 flex-1">
          <div class="mb-1 flex items-center gap-2">
            <CategoryBadge v-if="card.category" :category="card.category" />
          </div>
          <h3 class="truncate text-[14px] font-medium text-[--t1]">
            {{ card.title }}
          </h3>
          <p class="text-[12px] text-[--t3]">
            {{ card.author }}
            <span v-if="card.reader"> · {{ card.reader }}</span>
          </p>
        </div>

        <div v-if="TAB_ACTIONS[activeTab]?.length" class="flex w-full flex-shrink-0 gap-2 sm:w-auto">
          <button
            v-for="action in TAB_ACTIONS[activeTab]"
            :key="action.target"
            class="btn flex-1 justify-center sm:flex-initial"
            :class="`btn-${action.style}`"
            :disabled="actionLoading === card.id"
            @click="doMove(card.id, action.target)"
          >
            {{ action.label }}
          </button>
        </div>
        <div v-else class="flex-shrink-0 text-[11px] text-[--t3] italic">Без действий</div>
      </div>
    </div>

    <EmptyState v-else :title="`Список «${activeTab}» пуст`" description="Нет карточек в этом списке" />
  </div>
</template>
