import { useEffect, useRef } from 'react'
import { useARIAStore } from '../store/ariaStore'
import type { ARIAState } from '../lib/websocket'

/* ── Step indicator per state ─────────────────────────────────────────── */
const STEPS: { state: ARIAState | '_connected'; label: string; icon: string }[] = [
  { state: '_connected', label: 'Connected',   icon: '⬡' },
  { state: 'listening',  label: 'Listening',   icon: '◎' },
  { state: 'thinking',   label: 'Thinking',    icon: '◈' },
  { state: 'acting',     label: 'Acting',      icon: '◆' },
]

const STATE_COLOR: Record<string, string> = {
  idle:        'var(--text-ghost)',
  listening:   'var(--accent-blue)',
  thinking:    '#8b5cf6',
  acting:      'var(--accent-green)',
  interrupted: 'var(--accent-orange)',
}

const STATE_BG: Record<string, string> = {
  idle:        'rgba(30,30,50,0.4)',
  listening:   'rgba(59,130,246,0.1)',
  thinking:    'rgba(139,92,246,0.1)',
  acting:      'rgba(16,185,129,0.1)',
  interrupted: 'rgba(249,115,22,0.1)',
}

/* ── Last-N action log entries ─────────────────────────────────────────── */
const MAX_LOG = 6

function ActionIcon({ action }: { action: string }) {
  const icons: Record<string, string> = {
    navigate_to: '→',
    click_element: '⊙',
    type_into_field: '✎',
    scroll_page: '↕',
    press_keyboard_key: '⌨',
    read_page_content: '📄',
    analyze_current_screen: '👁',
    describe_screen_element: '🔍',
  }
  return <span>{icons[action] ?? '◦'}</span>
}

export function ActivityFeed() {
  const { ariaState, connected, transcript, actionCount } = useARIAStore()
  const scrollRef = useRef<HTMLDivElement>(null)

  // Only action entries from transcript, last MAX_LOG
  const actions = transcript
    .filter((e) => e.type === 'action')
    .slice(-MAX_LOG)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [actions.length])

  const color  = STATE_COLOR[ariaState] ?? 'var(--text-ghost)'
  const bgCard = STATE_BG[ariaState]    ?? 'rgba(30,30,50,0.4)'

  // Progress: which step index is active
  const stepIdx = connected
    ? ariaState === 'thinking'  ? 2
    : ariaState === 'acting'    ? 3
    : ariaState === 'listening' ? 1
    : 0
    : -1

  return (
    <div className="flex flex-col gap-3 w-full">

      {/* ── Title ── */}
      <div className="flex items-center justify-between">
        <span className="font-orbitron text-xs tracking-[0.28em] uppercase"
          style={{ color: 'var(--text-muted)' }}>
          Activity
        </span>
        <span className="font-mono" style={{ fontSize: 9, color: 'var(--text-ghost)', letterSpacing: '0.15em' }}>
          {actionCount} ops
        </span>
      </div>

      {/* ── State card ── */}
      <div className="rounded-xl px-3 py-2.5 transition-all duration-500"
        style={{ background: bgCard, border: `1px solid ${color}22` }}>

        {/* Animated status bar */}
        <div className="flex items-center gap-2 mb-2">
          <div className="relative w-2 h-2 rounded-full flex-shrink-0"
            style={{ background: color, boxShadow: `0 0 6px ${color}` }}>
            {(ariaState === 'listening' || ariaState === 'acting') && (
              <div className="absolute inset-0 rounded-full animate-ping opacity-60"
                style={{ background: color }} />
            )}
          </div>
          <span className="font-mono text-xs tracking-widest uppercase"
            style={{ color }}>
            {ariaState === 'idle' && !connected ? 'Offline'
              : ariaState === 'idle' ? 'Standby'
              : ariaState === 'listening' ? 'Listening…'
              : ariaState === 'thinking' ? 'Processing…'
              : ariaState === 'acting' ? 'Executing…'
              : 'Interrupted'}
          </span>
        </div>

        {/* Progress bar */}
        <div className="h-0.5 w-full rounded-full overflow-hidden"
          style={{ background: 'var(--border)' }}>
          <div className="h-full rounded-full transition-all duration-700"
            style={{
              width: ariaState === 'idle' ? '0%'
                : ariaState === 'listening' ? '33%'
                : ariaState === 'thinking'  ? '66%'
                : ariaState === 'acting'    ? '100%'
                : '20%',
              background: ariaState === 'thinking'
                ? 'linear-gradient(90deg, #8b5cf6, #3b82f6)'
                : ariaState === 'acting'
                  ? 'linear-gradient(90deg, var(--accent-blue), var(--accent-green))'
                  : color,
              ...(ariaState === 'thinking' || ariaState === 'acting'
                ? { animation: 'progress-shimmer 1.5s linear infinite' }
                : {}),
            }} />
        </div>
      </div>

      {/* ── Step pipeline with connectors ── */}
      <div className="flex items-center px-1">
        {STEPS.map((step, i) => {
          const active  = i === stepIdx
          const done    = i < stepIdx
          const c = active ? color : done ? 'var(--accent-cyan)' : 'var(--border-bright)'
          return (
            <div key={step.state} className="contents">
              {/* Connector line before step (except first) */}
              {i > 0 && (
                <div className="flex-1 h-px transition-all duration-500"
                  style={{
                    background: i <= stepIdx ? 'var(--accent-cyan)' : 'var(--border)',
                    opacity: 0.5,
                  }} />
              )}
              {/* Step icon + label */}
              <div className="flex flex-col items-center gap-1">
                <div className="w-6 h-6 rounded-lg flex items-center justify-center transition-all duration-300"
                  style={{
                    background: active ? `${color}22` : 'transparent',
                    border: `1px solid ${c}`,
                    fontSize: 10,
                    color: c,
                    boxShadow: active ? `0 0 8px ${color}44` : 'none',
                  }}>
                  {step.icon}
                </div>
                <span className="font-mono text-center transition-colors duration-300"
                  style={{ fontSize: 7, letterSpacing: '0.1em', color: c }}>
                  {step.label.toUpperCase()}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* ── Action log ── */}
      <div className="flex flex-col gap-1">
        <span className="font-mono" style={{ fontSize: 9, color: 'var(--text-ghost)', letterSpacing: '0.2em' }}>
          RECENT OPS
        </span>
        <div ref={scrollRef}
          className="flex flex-col gap-1 overflow-y-auto"
          style={{ maxHeight: 130 }}>
          {actions.length === 0 ? (
            <div className="font-mono py-2 text-center"
              style={{ fontSize: 9, color: 'var(--text-ghost)', letterSpacing: '0.1em' }}>
              — no actions yet —
            </div>
          ) : actions.map((entry) => {
            const parts = entry.content.replace('→ ', '').split(': ')
            const actionName = parts[0] ?? entry.content
            const detail     = parts.slice(1).join(': ')
            return (
              <div key={entry.id}
                className="flex items-start gap-2 px-2 py-1.5 rounded-lg"
                style={{ background: 'var(--bg-pill)', border: '1px solid var(--border)' }}>
                <span className="font-mono text-xs flex-shrink-0"
                  style={{ color: 'var(--accent-green)', marginTop: 1 }}>
                  <ActionIcon action={actionName} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-mono truncate"
                    style={{ fontSize: 9, color: 'var(--accent-cyan)', letterSpacing: '0.08em' }}>
                    {actionName.replace(/_/g, ' ')}
                  </div>
                  {detail && (
                    <div className="font-mono truncate"
                      style={{ fontSize: 8, color: 'var(--text-muted)', marginTop: 1 }}>
                      {detail}
                    </div>
                  )}
                </div>
                <span className="font-mono flex-shrink-0"
                  style={{ fontSize: 8, color: 'var(--text-ghost)' }}>
                  {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
