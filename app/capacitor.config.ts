import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.leerio.app',
  appName: 'Leerio',
  webDir: 'dist',
  android: {
    allowMixedContent: true,
  },
}

export default config
