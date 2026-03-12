import { useEffect, useRef } from 'react'
import { useARIAStore, type TranscriptEntry } from '../store/ariaStore'

const fmt = (ts: number) =>
  new Date(ts).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })

function UserBubble({ e }: { e: TranscriptEntry }) {
  return (
    <div className="flex justify-end animate-fade-up">
      <div className="max-w-[76%]">
        <div className="px-4 py-2.5 rounded-2xl rounded-tr-sm font-syne text-sm"
          style={{
            background: 'var(--user-bubble-bg)',
            border: '1px solid var(--user-bubble-border)',
            color: 'var(--text-primary)',
          }}>
          {e.content}
        </div>
        <div className="text-right font-mono mt-0.5 pr-1"
          style={{ fontSize: 10, color: 'var(--text-ghost)' }}>
          {fmt(e.timestamp)}
        </div>
      </div>
    </div>
  )
}

function ARIABubble({ e }: { e: TranscriptEntry }) {
  return (
    <div className="flex justify-start gap-2.5 animate-fade-up">
      {/* Avatar */}
      <div className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center mt-1"
        style={{
          background: 'radial-gradient(circle at 35% 35%, rgba(59,130,246,0.35), var(--bg-void))',
          border: '1px solid var(--border-focus)',
          boxShadow: '0 0 8px rgba(59,130,246,0.2)',
        }}>
        <span className="font-orbitron font-black" style={{ fontSize: 7, color: 'var(--accent-blue)' }}>A</span>
      </div>
      <div className="max-w-[76%]">
        <div className="px-4 py-2.5 rounded-2xl rounded-tl-sm font-syne text-sm"
          style={{
            background: 'var(--aria-bubble-bg)',
            border: '1px solid var(--aria-bubble-border)',
            color: 'var(--text-secondary)',
          }}>
          {e.content}
          {!e.final && (
            <span className="inline-flex gap-1 ml-2">
              {[0, 1, 2].map((i) => (
                <span key={i} className="inline-block w-1 h-1 rounded-full animate-pulse"
                  style={{ background: 'var(--accent-blue)', animationDelay: `${i * 0.15}s` }} />
              ))}
            </span>
          )}
        </div>
        <div className="font-mono mt-0.5 pl-1"
          style={{ fontSize: 10, color: 'var(--text-ghost)' }}>
          ARIA · {fmt(e.timestamp)}
        </div>
      </div>
    </div>
  )
}

function ActionPill({ e }: { e: TranscriptEntry }) {
  return (
    <div className="flex justify-center animate-fade-up">
      <div className="px-3 py-1 rounded-full font-mono text-xs"
        style={{
          background: 'rgba(16,185,129,0.08)',
          border: '1px solid rgba(16,185,129,0.22)',
          color: 'var(--accent-green)',
        }}>
        {e.content}
      </div>
    </div>
  )
}

function SystemPill({ e }: { e: TranscriptEntry }) {
  return (
    <div className="flex justify-center animate-fade-up">
      <div className="px-3 py-1 rounded-full font-mono text-xs"
        style={{
          background: 'rgba(249,115,22,0.07)',
          border: '1px solid rgba(249,115,22,0.22)',
          color: 'var(--accent-orange)',
        }}>
        {e.content}
      </div>
    </div>
  )
}

export function TranscriptFeed() {
  const transcript = useARIAStore((s) => s.transcript)
  const connected  = useARIAStore((s) => s.connected)
  const bottomRef  = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="flex-shrink-0 pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center justify-between">
          <span className="font-orbitron text-xs tracking-[0.3em] uppercase"
            style={{ color: 'var(--text-muted)' }}>
            Live Transcript
          </span>
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full" style={{
              background: connected ? 'var(--accent-green)' : 'var(--text-ghost)',
              boxShadow: connected ? '0 0 5px var(--accent-green)' : 'none',
            }} />
            <span className="font-mono" style={{ fontSize: 10, color: 'var(--text-ghost)' }}>
              {transcript.length} entries
            </span>
          </div>
        </div>
      </div>

      {/* Feed */}
      <div className="flex-1 overflow-y-auto py-4 space-y-3 pr-1 min-h-0">
        {transcript.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-center opacity-60">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
              stroke="var(--accent-blue)" strokeWidth="1.5">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="23"/>
              <line x1="8"  y1="23" x2="16" y2="23"/>
            </svg>
            <div>
              <div className="font-syne text-sm" style={{ color: 'var(--text-muted)' }}>
                Awaiting your voice...
              </div>
              <div className="font-mono mt-1" style={{ fontSize: 11, color: 'var(--text-ghost)' }}>
                Start a session and speak to ARIA
              </div>
            </div>
          </div>
        )}

        {transcript.map((entry) => {
          if (entry.type === 'user')   return <UserBubble   key={entry.id} e={entry} />
          if (entry.type === 'aria')   return <ARIABubble   key={entry.id} e={entry} />
          if (entry.type === 'action') return <ActionPill   key={entry.id} e={entry} />
          return                              <SystemPill   key={entry.id} e={entry} />
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
