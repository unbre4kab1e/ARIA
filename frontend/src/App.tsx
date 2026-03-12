import { useEffect } from 'react'
import { StatusPanel }        from './components/StatusPanel'
import { TranscriptFeed }     from './components/TranscriptFeed'
import { ScreenPreview }      from './components/ScreenPreview'
import { ControlBar }         from './components/ControlBar'
import { SettingsModal }      from './components/SettingsModal'
import { OnboardingOverlay }  from './components/OnboardingOverlay'
import { ToastContainer }     from './components/Toast'
import { useARIAStore }       from './store/ariaStore'

function ThemeToggle() {
  const { settings, setSettings } = useARIAStore()
  const isDark = settings.theme === 'dark'

  return (
    <button
      onClick={() => setSettings({ theme: isDark ? 'light' : 'dark' })}
      title={`Switch to ${isDark ? 'light' : 'dark'} theme`}
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition-all"
      style={{
        background: 'var(--bg-pill)',
        border: '1px solid var(--border)',
        color: 'var(--text-muted)',
      }}
    >
      {isDark ? (
        /* Sun icon */
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1"  x2="12" y2="3"/>
          <line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22"   x2="5.64" y2="5.64"/>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/>
          <line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
      ) : (
        /* Moon icon */
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      )}
      <span className="font-mono text-xs hidden sm:inline" style={{ color: 'var(--text-muted)' }}>
        {isDark ? 'Light' : 'Dark'}
      </span>
    </button>
  )
}

export default function App() {
  const theme = useARIAStore((s) => s.settings.theme)

  /* Apply data-theme to <html> so CSS variables cascade everywhere */
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  return (
    <div
      className="relative w-full h-full flex flex-col grid-bg overflow-hidden"
      style={{ background: 'var(--bg-void)', fontFamily: 'Syne, sans-serif' }}
    >
      {/* Ambient glow — adapts per theme */}
      <div className="absolute pointer-events-none" style={{
        top: '-8%', left: '50%', transform: 'translateX(-50%)',
        width: 900, height: 420,
        background: theme === 'dark'
          ? 'radial-gradient(ellipse, rgba(59,130,246,0.04) 0%, transparent 68%)'
          : 'radial-gradient(ellipse, rgba(37,99,235,0.06) 0%, transparent 68%)',
        filter: 'blur(40px)',
      }} />

      {/* ── Top bar ── */}
      <header
        className="flex-shrink-0 flex items-center justify-between px-6 py-3"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{
              background: `linear-gradient(135deg, rgba(var(--accent-blue-rgb,59,130,246),0.28), rgba(var(--accent-cyan-rgb,6,182,212),0.18))`,
              border: '1px solid var(--border-focus)',
              boxShadow: '0 0 14px rgba(59,130,246,0.15)',
            }}
          >
            <span className="font-orbitron font-black" style={{ fontSize: 11, color: 'var(--accent-blue)' }}>A</span>
          </div>
          <div>
            <div className="font-orbitron text-sm font-bold tracking-[0.2em]" style={{ color: 'var(--text-primary)' }}>
              ARIA
            </div>
            <div className="font-mono tracking-widest" style={{ fontSize: 8, color: 'var(--text-ghost)' }}>
              ADAPTIVE REALITY INTELLIGENCE ASSISTANT
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="font-mono tracking-widest hidden sm:block" style={{ fontSize: 10, color: 'var(--text-ghost)' }}>
            POWERED BY GEMINI LIVE API
          </span>
          <ThemeToggle />
          <div
            className="px-2 py-0.5 rounded font-mono text-xs tracking-widest"
            style={{
              background: 'var(--bg-pill)',
              border: '1px solid var(--border)',
              color: 'var(--text-ghost)',
            }}
          >
            v0.1.0
          </div>
        </div>
      </header>

      {/* ── Main panels ── */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Left: Status */}
        <div
          className="flex-shrink-0 w-52 p-4 overflow-y-auto"
          style={{ borderRight: '1px solid var(--border)' }}
        >
          <StatusPanel />
        </div>

        {/* Center: Transcript */}
        <div className="flex-1 flex flex-col min-w-0 p-4 overflow-hidden">
          <TranscriptFeed />
        </div>

        {/* Right: Screen preview */}
        <div
          className="flex-shrink-0 w-72 p-4 overflow-hidden"
          style={{ borderLeft: '1px solid var(--border)' }}
        >
          <ScreenPreview />
        </div>
      </div>

      {/* ── Control bar ── */}
      <div
        className="flex-shrink-0 px-4 py-3"
        style={{ borderTop: '1px solid var(--border)' }}
      >
        <ControlBar />
      </div>

      {/* Overlays */}
      <SettingsModal />
      <OnboardingOverlay />
      <ToastContainer />
    </div>
  )
}
