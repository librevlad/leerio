/** Centralized localStorage key names to prevent typos and ease refactoring. */
export const STORAGE = {
  USER: 'leerio_user',
  ONBOARDED: 'leerio_onboarded',
  PLAYBACK_RATE: 'leerio_playback_rate',
  VOLUME: 'leerio_volume',
  LOCALE: 'leerio_locale',
  OFFLINE_QUEUE: 'leerio_offline_queue',
  LOCAL_BOOKS: 'leerio_local_books',
  FS_BOOKS: 'leerio_fs_books',
  PWA_DISMISSED: 'pwa-install-dismissed',
  APK_DISMISSED: 'apk-prompt-dismissed',
  UPGRADE_DISMISSED: 'upgrade-banner-dismissed',
  /** Dynamic: append book ID */
  POSITION_PREFIX: 'leerio_pos_',
  CACHE_PREFIX: 'leerio_cache_',
  LAST_PLAYED: 'leerio_last_played',
  COVER_CACHE: 'leerio_cover_cache',
  /** Leerio Pro: last answer from Google Play — { active, offers } */
  PRO: 'leerio_pro',
  /** Books in the owner's cloud bucket: the last library.json, shown offline */
  CLOUD_BOOKS: 'leerio_cloud_books',
} as const
