<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useTrello } from '../composables/useTrello'
import SearchInput from '../components/shared/SearchInput.vue'
import CategoryBadge from '../components/shared/CategoryBadge.vue'
import EmptyState from '../components/shared/EmptyState.vue'

const { cards, status, loading, loadCards, loadStatus, moveCard } = useTrello()

const TABS = [
  'Прочесть', 'В процессе', 'В телефоне', 'На Паузе', 'Скачать', 'Прочитано', 'Забраковано',
] as const

type TabName = (typeof TABS)[number]

const TAB_ACTIONS: Record<string, { target: string; label: string; style: string }[]> = {
  'Прочесть':    [{ target: 'В процессе', label: 'Слушать', style: 'ghost' }, { target: 'В телефоне', label: 'Телефон', style: 'ghost' }, { target: 'Забраковано', label: 'Отклонить', style: 'danger' }],
  'В процессе':  [{ target: 'На Паузе', label: 'Пауза', style: 'ghost' }, { target: 'Прочитано', label: 'Прослушано', style: 'primary' }],
  'В телефоне':  [{ target: 'В процессе', label: 'Слушать', style: 'ghost' }, { target: 'Прочитано', label: 'Прослушано', style: 'primary' }],
  'На Паузе':    [{ target: 'В процессе', label: 'Продолжить', style: 'ghost' }, { target: 'Забраковано', label: 'Отклонить', style: 'danger' }],
  'Скачать':     [{ target: 'Прочесть', label: 'В очередь', style: 'ghost' }],
  'Забраковано': [{ target: 'Прочесть', label: 'Восстановить', style: 'ghost' }],
  'Прочитано':   [],
}

const activeTab = ref<TabName>('Прочесть')
const search = ref('')
const actionLoading = ref<string | null>(null)

const filteredCards = computed(() => {
  if (!search.value) return cards.value
  const q = search.value.toLowerCase()
  return cards.value.filter(c =>
    c.title.toLowerCase().includes(q) ||
    c.author.toLowerCase().includes(q) ||
    c.name.toLowerCase().includes(q)
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
    <div class="flex items-center justify-between mb-6">
      <h1 class="page-title">Очередь</h1>
      <span class="text-[12px] text-[--t3]">{{ status?.total_cards ?? '...' }} карточек</span>
    </div>

    <SearchInput v-model="search" placeholder="Поиск по очереди..." class="mb-5" />

    <!-- Tabs -->
    <div class="flex gap-1.5 overflow-x-auto pb-1 mb-6 -mx-4 px-4 md:-mx-1 md:px-1 scrollbar-hide" style="-webkit-overflow-scrolling: touch">
      <button
        v-for="tab in TABS"
        :key="tab"
        class="flex items-center gap-1.5 px-3.5 py-2.5 md:py-2 rounded-full text-[13px] md:text-[12px] font-medium whitespace-nowrap transition-all cursor-pointer border-0"
        :class="activeTab === tab
          ? 'bg-white/10 text-[--t1] shadow-sm'
          : 'bg-transparent text-[--t3] hover:text-[--t2] hover:bg-white/5'"
        @click="switchTab(tab)"
      >
        {{ tab }}
        <span
          v-if="tabCount(tab)"
          class="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold"
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
        class="card px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3"
      >
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <CategoryBadge v-if="card.category" :category="card.category" />
          </div>
          <h3 class="text-[14px] font-medium truncate text-[--t1]">
            {{ card.title }}
          </h3>
          <p class="text-[12px] text-[--t3]">
            {{ card.author }}
            <span v-if="card.reader"> · {{ card.reader }}</span>
          </p>
        </div>

        <div v-if="TAB_ACTIONS[activeTab]?.length" class="flex gap-2 flex-shrink-0 w-full sm:w-auto">
          <button
            v-for="action in TAB_ACTIONS[activeTab]"
            :key="action.target"
            class="btn flex-1 sm:flex-initial justify-center"
            :class="`btn-${action.style}`"
            :disabled="actionLoading === card.id"
            @click="doMove(card.id, action.target)"
          >
            {{ action.label }}
          </button>
        </div>
        <div v-else class="text-[11px] text-[--t3] italic flex-shrink-0">
          Без действий
        </div>
      </div>
    </div>

    <EmptyState v-else :title="`Список «${activeTab}» пуст`" description="Нет карточек в этом списке" />
  </div>
</template>
