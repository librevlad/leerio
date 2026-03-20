import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from './composables/useAuth'
import { STORAGE } from './constants/storage'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/welcome',
      name: 'welcome',
      component: () => import('./views/WelcomeView.vue'),
      meta: { public: true, title: 'Welcome' },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('./views/LoginView.vue'),
      meta: { public: true, title: 'Login' },
    },
    {
      path: '/',
      redirect: '/library',
    },
    {
      path: '/library',
      name: 'library',
      component: () => import('./views/LibraryView.vue'),
      meta: { title: 'Catalog', public: true },
    },
    {
      path: '/book/:id',
      name: 'book',
      component: () => import('./views/BookDetailView.vue'),
      meta: { public: true },
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('./views/HistoryView.vue'),
      meta: { title: 'History' },
    },
    {
      path: '/my-library',
      name: 'my-library',
      component: () => import('./views/MyLibraryView.vue'),
      meta: { title: 'My Library' },
    },
    {
      path: '/my-books',
      redirect: '/my-library',
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('./views/SettingsView.vue'),
      meta: { title: 'Settings' },
    },
    {
      path: '/:pathMatch(.*)*',
      component: () => import('./views/NotFoundView.vue'),
      meta: { public: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const { checkAuth } = useAuth()

  // Check auth in background for all routes — never block navigation
  checkAuth()

  // Onboarding redirect: first visit → /welcome
  if (to.name !== 'welcome' && to.name !== 'login' && localStorage.getItem(STORAGE.ONBOARDED) !== '1') {
    return { name: 'welcome' }
  }

  return true
})

const routeNavKeyMap: Record<string, string> = {
  login: 'nav.login',
  dashboard: 'nav.home',
  library: 'nav.catalog',
  history: 'nav.history',
  'my-library': 'nav.myLibrary',
  settings: 'nav.settings',
}

router.afterEach(async (to) => {
  // Book detail sets its own title dynamically
  if (to.name === 'book') return
  try {
    const i18n = (await import('./i18n')).default
    const t = i18n.global.t
    const key = routeNavKeyMap[to.name as string]
    const title = key && t(key) !== key ? t(key) : (to.meta.title as string) || ''
    document.title = title ? `${title} — Leerio` : 'Leerio'
  } catch {
    const title = (to.meta.title as string) || ''
    document.title = title ? `${title} — Leerio` : 'Leerio'
  }
})

export default router
