import { useARIAStore } from '../store/ariaStore'

export function SettingsModal() {
  const { settings, settingsOpen, setSettings, setSettingsOpen } = useARIAStore()
  if (!settingsOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(10px)' }}
      onClick={(e) => e.target === e.currentTarget && setSettingsOpen(false)}>

      <div className="relative w-full max-w-md rounded-2xl p-7 space-y-6"
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-bright)',
          boxShadow: '0 25px 60px rgba(0,0,0,0.3)',
        }}>

        {/* Corner marks */}
        <div className="absolute top-0 left-0 w-4 h-4 border-t border-l rounded-tl-2xl"
          style={{ borderColor: 'var(--accent-cyan)', opacity: 0.5 }} />
        <div className="absolute bottom-0 right-0 w-4 h-4 border-b border-r rounded-br-2xl"
          style={{ borderColor: 'var(--accent-cyan)', opacity: 0.5 }} />

        {/* Title */}
        <div className="flex items-center justify-between">
          <h2 className="font-orbitron text-sm tracking-[0.28em] uppercase"
            style={{ color: 'var(--text-primary)' }}>
            Configuration
          </h2>
          <button onClick={() => setSettingsOpen(false)}
            className="transition-colors"
            style={{ color: 'var(--text-muted)' }}>
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6"  x2="6"  y2="18"/>
              <line x1="6"  y1="6"  x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {/* API URL */}
        <div className="space-y-1.5">
          <label className="font-mono uppercase tracking-widest"
            style={{ fontSize: 10, color: 'var(--text-muted)' }}>
            Backend URL
          </label>
          <input type="text" value={settings.apiUrl}
            onChange={(e) => setSettings({ apiUrl: e.target.value })}
            className="w-full px-3 py-2.5 rounded-lg font-mono text-sm outline-none"
            style={{
              background: 'var(--bg-input)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
            }}
            onFocus={(e)  => e.target.style.borderColor = 'var(--border-focus)'}
            onBlur={(e)   => e.target.style.borderColor = 'var(--border)'}
          />
        </div>

        {/* Mic sensitivity */}
        <div className="space-y-1.5">
          <div className="flex justify-between">
            <label className="font-mono uppercase tracking-widest"
              style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              Mic Sensitivity
            </label>
            <span className="font-mono text-xs" style={{ color: 'var(--accent-cyan)' }}>
              {Math.round(settings.micSensitivity * 100)}%
            </span>
          </div>
          <input type="range" min="0" max="1" step="0.05" value={settings.micSensitivity}
            onChange={(e) => setSettings({ micSensitivity: parseFloat(e.target.value) })}
            className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
            style={{ accentColor: 'var(--accent-blue)' }}
          />
        </div>

        {/* Screenshot interval */}
        <div className="space-y-1.5">
          <div className="flex justify-between">
            <label className="font-mono uppercase tracking-widest"
              style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              Screenshot Interval
            </label>
            <span className="font-mono text-xs" style={{ color: 'var(--accent-cyan)' }}>
              {settings.screenshotIntervalMs}ms
            </span>
          </div>
          <input type="range" min="500" max="5000" step="500" value={settings.screenshotIntervalMs}
            onChange={(e) => setSettings({ screenshotIntervalMs: parseInt(e.target.value) })}
            className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
            style={{ accentColor: 'var(--accent-cyan)' }}
          />
        </div>

        {/* Voice toggle */}
        <div className="flex items-center justify-between">
          <div>
            <div className="font-mono uppercase tracking-wider"
              style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
              ARIA Voice Output
            </div>
            <div className="font-syne text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              Hear ARIA speak responses
            </div>
          </div>
          <button onClick={() => setSettings({ voiceEnabled: !settings.voiceEnabled })}
            className="relative w-10 h-5 rounded-full transition-all duration-200"
            style={{
              background: settings.voiceEnabled ? 'rgba(59,130,246,0.38)' : 'var(--bg-pill)',
              border: settings.voiceEnabled ? '1px solid var(--border-focus)' : '1px solid var(--border)',
            }}>
            <div className="absolute top-0.5 w-4 h-4 rounded-full transition-all duration-200"
              style={{
                background: settings.voiceEnabled ? 'var(--accent-blue)' : 'var(--text-muted)',
                left: settings.voiceEnabled ? 'calc(100% - 18px)' : '2px',
                boxShadow: settings.voiceEnabled ? '0 0 8px rgba(59,130,246,0.5)' : 'none',
              }} />
          </button>
        </div>

        {/* Theme toggle */}
        <div className="space-y-1.5">
          <label className="font-mono uppercase tracking-widest"
            style={{ fontSize: 10, color: 'var(--text-muted)' }}>
            Theme
          </label>
          <div className="flex gap-2">
            {(['dark', 'light'] as const).map((t) => (
              <button key={t} onClick={() => setSettings({ theme: t })}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl font-mono text-xs uppercase tracking-wider transition-all"
                style={{
                  background: settings.theme === t ? 'rgba(59,130,246,0.15)' : 'var(--bg-pill)',
                  border: settings.theme === t ? '1px solid var(--border-focus)' : '1px solid var(--border)',
                  color: settings.theme === t ? 'var(--accent-blue)' : 'var(--text-muted)',
                }}>
                {t === 'dark'
                  ? <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
                  : <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
                }
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
