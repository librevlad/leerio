export const dotColor: Record<string, string> = {
  inbox: 'bg-cyan-400',
  listen: 'bg-purple-400',
  phone: 'bg-blue-400',
  done: 'bg-emerald-400',
  pause: 'bg-yellow-400',
  reject: 'bg-red-400',
  relisten: 'bg-cyan-400',
  move: 'bg-slate-400',
  undo: 'bg-slate-500',
  delete: 'bg-red-500',
}

export const actionColor: Record<string, { bg: string; fg: string }> = {
  inbox: { bg: 'rgba(34, 211, 238, 0.1)', fg: '#22d3ee' },
  listen: { bg: 'rgba(192, 132, 252, 0.1)', fg: '#c084fc' },
  phone: { bg: 'rgba(96, 165, 250, 0.1)', fg: '#60a5fa' },
  done: { bg: 'rgba(52, 211, 153, 0.1)', fg: '#34d399' },
  pause: { bg: 'rgba(250, 204, 21, 0.1)', fg: '#facc15' },
  reject: { bg: 'rgba(248, 113, 113, 0.1)', fg: '#f87171' },
  relisten: { bg: 'rgba(34, 211, 238, 0.1)', fg: '#22d3ee' },
  move: { bg: 'rgba(148, 163, 184, 0.1)', fg: '#94a3b8' },
  undo: { bg: 'rgba(148, 163, 184, 0.1)', fg: '#94a3b8' },
  delete: { bg: 'rgba(248, 113, 113, 0.1)', fg: '#f87171' },
  download: { bg: 'rgba(148, 163, 184, 0.1)', fg: '#94a3b8' },
  rated: { bg: 'rgba(251, 191, 36, 0.1)', fg: '#fbbf24' },
}

export const actionFallback = { bg: 'rgba(148, 163, 184, 0.1)', fg: '#94a3b8' }

export const glowColor: Record<string, string> = {
  phone: 'rgba(96,165,250,0.3)',
  listen: 'rgba(168,85,247,0.3)',
  pause: 'rgba(250,204,21,0.3)',
  done: 'rgba(74,222,128,0.3)',
  reject: 'rgba(248,113,113,0.3)',
  inbox: 'rgba(34,211,238,0.25)',
  relisten: 'rgba(34,211,238,0.25)',
  move: 'rgba(148,163,184,0.2)',
  undo: 'rgba(148,163,184,0.2)',
  delete: 'rgba(248,113,113,0.25)',
  download: 'rgba(148,163,184,0.2)',
}
