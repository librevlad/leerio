import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from './composables/useAuth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('./views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      name: 'dashboard',
      component: () => import('./views/DashboardView.vue'),
    },
    {
      path: '/library',
      name: 'library',
      component: () => import('./views/LibraryView.vue'),
    },
    {
      path: '/book/:id',
      name: 'book',
      component: () => import('./views/BookDetailView.vue'),
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('./views/HistoryView.vue'),
    },
    {
      path: '/analytics',
      name: 'analytics',
      component: () => import('./views/AnalyticsView.vue'),
    },
    {
      path: '/queue',
      name: 'queue',
      component: () => import('./views/QueueView.vue'),
      meta: { admin: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('./views/SettingsView.vue'),
    },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true

  const { isAdmin, checkAuth } = useAuth()
  const authed = await checkAuth()

  if (!authed) {
    return { name: 'login' }
  }

  if (to.meta.admin && !isAdmin.value) {
    return { name: 'dashboard' }
  }

  return true
})

export default router
