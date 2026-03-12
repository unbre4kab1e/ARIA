import { useARIAStore } from '../store/ariaStore'
import type { ARIAState } from '../lib/websocket'

const CFG: Record<ARIAState, { core: string; ring: string; label: string; glow: string; anim: string }> = {
  idle:        { core: '#1e293b', ring: '#334155', label: 'Standby',          glow: 'rgba(51,65,85,0.5)',     anim: 'animate-orb-idle'   },
  listening:   { core: '#0f2952', ring: '#3b82f6', label: 'Listening...',     glow: 'rgba(59,130,246,0.65)',  anim: 'animate-orb-listen' },
  thinking:    { core: '#170f40', ring: '#8b5cf6', label: 'Thinking...',      glow: 'rgba(139,92,246,0.65)',  anim: 'animate-orb-think'  },
  acting:      { core: '#042214', ring: '#10b981', label: 'Acting on screen', glow: 'rgba(16,185,129,0.65)',  anim: 'animate-orb-act'    },
  interrupted: { core: '#2c0e04', ring: '#f97316', label: 'Interrupted',      glow: 'rgba(249,115,22,0.65)',  anim: 'animate-orb-idle'   },
}

export function ARIAOrb() {
  const ariaState = useARIAStore((s) => s.ariaState)
  const connected = useARIAStore((s) => s.connected)
  const theme     = useARIAStore((s) => s.settings.theme)
  const c = CFG[ariaState]
  const isActive = ariaState === 'listening' || ariaState === 'acting'

  /* In light theme, lighten the orb core */
  const orbCore = theme === 'light'
    ? (() => {
        const hex = c.core.replace('#', '')
        const r = Math.min(255, parseInt(hex.slice(0, 2), 16) + 40)
        const g = Math.min(255, parseInt(hex.slice(2, 4), 16) + 40)
        const b = Math.min(255, parseInt(hex.slice(4, 6), 16) + 40)
        return `#${r.toString(16).padStart(2,'0')}${g.toString(16).padStart(2,'0')}${b.toString(16).padStart(2,'0')}`
      })()
    : c.core

  return (
    <div className="flex flex-col items-center gap-5 select-none">
      <div className="relative flex items-center justify-center" style={{ width: 156, height: 156 }}>

        {/* Pulse rings */}
        {isActive && [0, 1].map((i) => (
          <div key={i} className="absolute rounded-full animate-pulse-ring pointer-events-none"
            style={{ width: 156, height: 156, border: `1px solid ${c.ring}`, animationDelay: `${i * 0.7}s` }} />
        ))}

        {/* Orbit ring */}
        <div className="absolute rounded-full pointer-events-none"
          style={{
            width: 136, height: 136,
            border: `1px solid ${c.ring}44`,
            ...(ariaState === 'thinking' ? {
              animation: 'orb-think 2.5s linear infinite',
              borderTopColor: c.ring,
            } : {}),
          }} />

        {/* Main orb */}
        <div className={`relative rounded-full ${c.anim}`}
          style={{
            width: 108, height: 108,
            background: `radial-gradient(circle at 33% 33%, ${c.ring}99, ${orbCore} 68%)`,
            boxShadow: `0 0 28px ${c.glow}, 0 0 56px ${c.glow.replace('0.65', '0.2')}, inset 0 0 18px rgba(255,255,255,0.04)`,
          }}>

          {/* Gloss */}
          <div className="absolute rounded-full pointer-events-none"
            style={{ top: '12%', left: '14%', width: '36%', height: '28%',
              background: 'radial-gradient(ellipse, rgba(255,255,255,0.22), transparent)' }} />

          {/* Label */}
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-orbitron font-black tracking-widest"
              style={{ fontSize: 11, color: c.ring, textShadow: `0 0 8px ${c.ring}` }}>
              ARIA
            </span>
          </div>

          {/* Thinking scan line */}
          {ariaState === 'thinking' && (
            <div className="absolute inset-0 rounded-full overflow-hidden pointer-events-none opacity-30">
              <div style={{
                position: 'absolute', top: 0, left: 0, right: 0, height: 2,
                background: `linear-gradient(90deg, transparent, ${c.ring}, transparent)`,
                animation: 'scan-line 0.9s linear infinite',
              }} />
            </div>
          )}
        </div>

        {/* Connection dot */}
        <div className="absolute rounded-full"
          style={{
            bottom: 6, right: 6, width: 11, height: 11,
            background: connected ? '#10b981' : '#ef4444',
            boxShadow: connected ? '0 0 7px #10b981' : '0 0 7px #ef4444',
          }} />
      </div>

      {/* State label */}
      <div className="text-center">
        <div className="font-orbitron text-xs tracking-[0.3em] uppercase"
          style={{ color: c.ring, textShadow: `0 0 8px ${c.ring}55` }}>
          {c.label}
        </div>
        <div className="font-mono mt-0.5" style={{ fontSize: 9, letterSpacing: '0.2em', color: 'var(--text-ghost)' }}>
          {connected ? 'SYS:ONLINE' : 'SYS:OFFLINE'}
        </div>
      </div>
    </div>
  )
}
