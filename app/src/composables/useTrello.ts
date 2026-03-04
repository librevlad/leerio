import { ref } from 'vue'
import { api } from '../api'
import { useToast } from './useToast'
import type { TrelloCard, TrelloStatus } from '../types'

const cards = ref<TrelloCard[]>([])
const status = ref<TrelloStatus | null>(null)
const loading = ref(false)

export function useTrello() {
  const toast = useToast()

  async function loadCards(listName?: string) {
    loading.value = true
    try {
      cards.value = await api.getTrelloCards(listName)
    } catch {
      cards.value = []
    } finally {
      loading.value = false
    }
  }

  async function loadStatus() {
    try {
      status.value = await api.getTrelloStatus()
    } catch {
      status.value = null
    }
  }

  async function moveCard(cardId: string, target: string, rating = 0) {
    try {
      await api.moveCard(cardId, target, rating)
      toast.success(`Перемещено → ${target}`)
      await loadCards()
    } catch (e: any) {
      toast.error(`Ошибка: ${e.message}`)
    }
  }

  async function createCard(name: string, listName: string, label?: string, desc?: string): Promise<string | null> {
    try {
      const res = await api.createTrelloCard(name, listName, label, desc)
      toast.success('Карточка создана')
      return res.card_id
    } catch (e: any) {
      toast.error(`Ошибка: ${e.message}`)
      return null
    }
  }

  async function sync() {
    try {
      const res = await api.syncTrello()
      toast.success(`Синхронизировано: ${res.cards} карточек`)
      await Promise.all([loadCards(), loadStatus()])
    } catch (e: any) {
      toast.error(`Ошибка синхронизации: ${e.message}`)
    }
  }

  return { cards, status, loading, loadCards, loadStatus, moveCard, createCard, sync }
}
