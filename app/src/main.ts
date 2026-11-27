import { createApp } from 'vue'
import { Capacitor } from '@capacitor/core'
import { registerSW } from 'virtual:pwa-register'
import App from './App.vue'
import router from './router'
import i18n from './i18n'
import ripple from './directives/ripple'
import './style.css'

if (Capacitor.isNativePlatform()) {
  // The APK ships its own assets. A service worker would keep serving the previous
  // version's precached bundle after every app update — remove any left from older builds.
  navigator.serviceWorker
    ?.getRegistrations()
    .then((regs) => regs.forEach((r) => r.unregister()))
    .catch(() => {})
} else {
  registerSW({ immediate: true })
}

const app = createApp(App)
app.use(router)
app.use(i18n)
app.directive('ripple', ripple)
app.mount('#app')
