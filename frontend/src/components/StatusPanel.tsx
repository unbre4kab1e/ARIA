import { useEffect, useState, memo } from 'react'
import { useARIAStore } from '../store/ariaStore'
import { ARIAOrb } from './ARIAOrb'
import { ActivityFeed } from './ActivityFeed'

/* ── Isolated timer component — only this re-renders every second ── */
const ElapsedTimer = memo(function ElapsedTimer({ start }: { start: number | null }) {
  const [display, setDisplay] = useState('00:00:00')

  useEffect(() => {
    if (!start) { setDisplay('00:00:00'); return }
    const update = () => {
      const s = Math.floor((Date.now() - start) / 1000)
      const h = String(Math.floor(s / 3600)).padStart(2, '0')
      const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0')
      const sec = String(s % 60).padStart(2, '0')
      setDisplay(`${h}:${m}:${sec}`)
    }
    update()
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [start])

  return <>{display}</>
})

function MetricRow({ label, value, highlight }: { label: string; value: React.ReactNode; highlight: boolean }) {
  return (
    <div className="flex justify-between items-center px-2.5 py-1.5 rounded-lg"
      style={{ background: 'var(--bg-pill)', border: '1px solid var(--border)' }}>
      <span className="font-mono" style={{ fontSize: 9, letterSpacing: '0.2em', color: 'var(--text-ghost)' }}>
        {label}
      </span>
      <span className="font-mono text-xs tracking-wider"
        style={{ color: highlight ? 'var(--accent-cyan)' : 'var(--text-muted)' }}>
        {value}
      </span>
    </div>
  )
}

export function StatusPanel() {
  const sessionId = useARIAStore((s) => s.sessionId)
  const connected = useARIAStore((s) => s.connected)
  const actionCount = useARIAStore((s) => s.actionCount)
  const sessionStartTime = useARIAStore((s) => s.sessionStartTime)
  const ariaState = useARIAStore((s) => s.ariaState)

  return (
    <div className="flex flex-col items-center gap-5 h-full">
      {/* Header */}
      <div className="w-full text-center">
        <div className="font-orbitron text-xs tracking-[0.35em] uppercase mb-2"
          style={{ color: 'var(--text-muted)' }}>
          System Core
        </div>
        <div className="h-px" style={{ background: 'linear-gradient(to right, transparent, var(--accent-blue), transparent)', opacity: 0.3 }} />
      </div>

      <ARIAOrb />

      {/* Metrics */}
      <div className="w-full space-y-1.5">
        <MetricRow label="SESSION" highlight={connected}
          value={sessionId ? sessionId.slice(0, 8).toUpperCase() : '--------'} />
        <MetricRow label="DURATION" highlight={connected}
          value={<ElapsedTimer start={sessionStartTime} />} />
        <MetricRow label="ACTIONS" highlight={connected}
          value={String(actionCount).padStart(4, '0')} />
        <MetricRow label="STATE" highlight={connected}
          value={ariaState.toUpperCase()} />
      </div>

      {/* Activity feed widget */}
      <div className="w-full flex-1 overflow-y-auto">
        <ActivityFeed />
      </div>
    </div>
  )
}
