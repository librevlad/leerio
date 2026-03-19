import { defineComponent, h } from 'vue'

// SECURITY: paths must be string literals only, never user input
function icon(paths: string, opts?: { fill?: boolean; viewBox?: string; strokeWidth?: string }) {
  return defineComponent({
    props: { size: { type: [Number, String], default: 24 } },
    setup(props) {
      return () =>
        h('svg', {
          xmlns: 'http://www.w3.org/2000/svg',
          width: props.size,
          height: props.size,
          viewBox: opts?.viewBox || '0 0 24 24',
          fill: opts?.fill ? 'currentColor' : 'none',
          stroke: opts?.fill ? 'none' : 'currentColor',
          'stroke-width': opts?.fill ? undefined : opts?.strokeWidth || '1.5',
          'stroke-linecap': opts?.fill ? undefined : 'round',
          'stroke-linejoin': opts?.fill ? undefined : 'round',
          innerHTML: paths,
        })
    },
  })
}

export const IconHome = icon(
  '<path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1h-2z"/>',
)
export const IconLibrary = icon(
  '<path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>',
)
export const IconQueue = icon(
  '<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>',
)
export const IconHistory = icon('<path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>')
export const IconChart = icon(
  '<path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>',
)
export const IconSettings = icon(
  '<path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.573-1.066z"/><circle cx="12" cy="12" r="3"/>',
)
export const IconSearch = icon('<path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/>')
export const IconMenu = icon('<path d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"/>')
export const IconX = icon('<path d="M6 18L18 6M6 6l12 12"/>')
export const IconArrowLeft = icon('<path d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"/>')
export const IconStar = icon(
  '<path d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.562.562 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"/>',
  { fill: true },
)
export const IconStarOutline = icon(
  '<path d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.562.562 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"/>',
)
export const IconClock = icon('<path d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/>')
export const IconMusic = icon(
  '<path d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z"/>',
)
export const IconHardDrive = icon(
  '<path d="M21.75 17.25v-.228a4.328 4.328 0 00-.12-.7l-2.71-7.975A2.25 2.25 0 0016.8 6.75H7.2a2.25 2.25 0 00-2.12 1.597l-2.71 7.975a4.33 4.33 0 00-.12.7v.228m19.5 0a3 3 0 01-3 3H5.25a3 3 0 01-3-3m19.5 0a3 3 0 00-3-3H5.25a3 3 0 00-3 3m16.5 0h.008v.008h-.008v-.008zm-3 0h.008v.008h-.008v-.008z"/>',
)
export const IconSync = icon(
  '<path d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182"/>',
)
export const IconTarget = icon(
  '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
)
export const IconBolt = icon('<path d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"/>')
export const IconCalendar = icon(
  '<path d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/>',
)
export const IconTrophy = icon(
  '<path d="M16.5 18.75h-9m9 0a3 3 0 013 3h-15a3 3 0 013-3m9 0v-4.5A3.375 3.375 0 0019.875 10.875h0A1.125 1.125 0 0021 9.75V6.375a1.125 1.125 0 00-1.125-1.125h-1.5a3.375 3.375 0 00-1.875.563M7.5 18.75v-4.5A3.375 3.375 0 004.125 10.875h0A1.125 1.125 0 013 9.75V6.375A1.125 1.125 0 014.125 5.25h1.5a3.375 3.375 0 011.875.563"/>',
)
export const IconInbox = icon(
  '<path d="M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.859m-19.5.338V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18v-4.162c0-.224-.034-.447-.1-.661L19.24 5.338a2.25 2.25 0 00-2.15-1.588H6.911a2.25 2.25 0 00-2.15 1.588L2.35 13.177a2.25 2.25 0 00-.1.661z"/>',
)

export const IconShuffle = icon('<path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/>', { strokeWidth: '2' })
export const IconShare = icon(
  '<path d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z"/>',
)

// Player icons
export const IconPlay = icon('<polygon points="5 3 19 12 5 21 5 3"/>', { fill: true })
export const IconPause = icon('<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>', {
  fill: true,
})
export const IconSkipForward = icon('<polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19"/>')
export const IconSkipBack = icon('<polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5"/>')
export const IconVolume = icon(
  '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07"/>',
)
export const IconVolumeMute = icon(
  '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>',
)
export const IconXCircle = icon('<circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/>')

// Download / offline icons
export const IconDownload = icon(
  '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
)
export const IconEdit = icon(
  '<path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>',
)
export const IconTrash = icon(
  '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>',
)
export const IconCheck = icon('<polyline points="20 6 9 17 4 12"/>')

// Player feature icons
// Material Design Icons — rewind-15 / fast-forward-30 (Pictogrammers, Apache 2.0)
export const IconRewind15 = icon(
  '<path d="M12.5 3C17.15 3 21.08 6.03 22.47 10.22L20.1 11C19.05 7.81 16.04 5.5 12.5 5.5C10.54 5.5 8.77 6.22 7.38 7.38L10 10H3V3L5.6 5.6C7.45 4 9.85 3 12.5 3M10 12V22H8V14H6V12H10M12 12H18V14H14V16H16C17.11 16 18 16.9 18 18V20C18 21.11 17.11 22 16 22H12V20H16V18H12V12Z"/>',
  { fill: true },
)
export const IconForward15 = icon(
  '<path d="M11.5 3C6.85 3 2.92 6.03 1.53 10.22L3.9 11C4.95 7.81 7.96 5.5 11.5 5.5C13.46 5.5 15.23 6.22 16.62 7.38L14 10H21V3L18.4 5.6C16.55 4 14.15 3 11.5 3M10 12V22H8V14H6V12H10M12 12H18V14H14V16H16C17.11 16 18 16.9 18 18V20C18 21.11 17.11 22 16 22H12V20H16V18H12V12Z"/>',
  { fill: true },
)
export const IconForward30 = icon(
  '<path d="M11.5 3C6.85 3 2.92 6.03 1.53 10.22L3.9 11C4.95 7.81 7.96 5.5 11.5 5.5C13.46 5.5 15.23 6.22 16.62 7.38L14 10H21V3L18.4 5.6C16.55 4 14.15 3 11.5 3M19 14V20C19 21.11 18.11 22 17 22H15A2 2 0 0 1 13 20V14A2 2 0 0 1 15 12H17C18.11 12 19 12.9 19 14M15 14V20H17V14H15M11 20C11 21.11 10.1 22 9 22H5V20H9V18H7V16H9V14H5V12H9A2 2 0 0 1 11 14V15.5A1.5 1.5 0 0 1 9.5 17A1.5 1.5 0 0 1 11 18.5V20Z"/>',
  { fill: true },
)
export const IconSpeed = icon('<path d="M12 12l-3-7m0 0a9 9 0 110 14"/><circle cx="12" cy="12" r="2"/>')
export const IconMoon = icon('<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>')
export const IconBookmark = icon('<path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/>')
export const IconBookmarkFilled = icon('<path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/>', { fill: true })

// Cloud / device / offline icons
export const IconCloud = icon(
  '<path d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z"/>',
)
export const IconSmartphone = icon(
  '<rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/>',
)
export const IconWifiOff = icon(
  '<line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0119 12.55"/><path d="M5 12.55a10.94 10.94 0 015.17-2.39"/><path d="M10.71 5.05A16 16 0 0122.56 9"/><path d="M1.42 9a15.91 15.91 0 014.7-2.88"/><path d="M8.53 16.11a6 6 0 016.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/>',
)
export const IconChevronDown = icon('<path d="M6 9l6 6 6-6"/>')
export const IconChevronUp = icon('<path d="M18 15l-6-6-6 6"/>')
export const IconList = icon(
  '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
)

// Upload & TTS icons
export const IconUpload = icon(
  '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
)
export const IconMicrophone = icon(
  '<path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>',
)
export const IconPlus = icon('<path d="M12 5v14m-7-7h14"/>')
export const IconFolder = icon('<path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>')
export const IconHeadphones = icon(
  '<path d="M3 18v-6a9 9 0 0118 0v6"/><path d="M21 19a2 2 0 01-2 2h-1a2 2 0 01-2-2v-3a2 2 0 012-2h3zM3 19a2 2 0 002 2h1a2 2 0 002-2v-3a2 2 0 00-2-2H3z"/>',
)
export const IconChevronRight = icon('<path d="M9 18l6-6-6-6"/>')
export const IconTag = icon(
  '<path d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z"/><path d="M6 6h.008v.008H6V6z"/>',
)
export const IconInfo = icon('<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>')
export const IconQuote = icon(
  '<path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V21z"/><path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/>',
)
export const IconLogout = icon(
  '<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
)
