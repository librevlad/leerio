import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.leerio.app',
  appName: 'Leerio',
  webDir: 'dist',
  android: {
    allowMixedContent: true,
  },
  server: {
    url: 'https://app.leerio.app',
    cleartext: true,
  },
}

export default config
