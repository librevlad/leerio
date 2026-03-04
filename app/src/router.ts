import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
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
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('./views/SettingsView.vue'),
    },
  ],
})

export default router
