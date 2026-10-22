import { useState } from 'react'
import { useARIAStore } from '../store/ariaStore'

type Source = 'aria' | 'user'

export function ScreenPreview() {
  const lastScreenshot    = useARIAStore((s) => s.lastScreenshot)
  const browserFrame      = useARIAStore((s) => s.browserFrame)
  const screenShareActive = useARIAStore((s) => s.screenShareActive)
  const lastClickPos      = useARIAStore((s) => s.lastClickPos)
  const [source, setSource] = useState<Source>('aria')

  // ARIA's own browser is the default view; the user's screen is the shared one
  const image = source === 'aria' ? browserFrame : lastScreenshot
  const live  = source === 'aria' ? !!browserFrame : screenShareActive

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="flex-shrink-0 pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center justify-between">
          <span className="font-orbitron text-xs tracking-[0.3em] uppercase"
            style={{ color: 'var(--text-muted)' }}>
            Screen Feed
          </span>
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full"
            style={{
              background: live ? 'rgba(16,185,129,0.09)' : 'var(--bg-pill)',
              border: `1px solid ${live ? 'rgba(16,185,129,0.3)' : 'var(--border)'}`,
            }}>
            <div className="w-1.5 h-1.5 rounded-full" style={{
              background: live ? 'var(--accent-green)' : 'var(--text-ghost)',
              boxShadow: live ? '0 0 4px var(--accent-green)' : 'none',
            }} />
            <span className="font-mono text-xs"
              style={{ color: live ? 'var(--accent-green)' : 'var(--text-ghost)' }}>
              {live ? 'LIVE' : 'INACTIVE'}
            </span>
          </div>
        </div>

        {/* Source switch */}
        <div className="flex gap-1.5 mt-3">
          {([['aria', 'ARIA browser'], ['user', 'Your screen']] as const).map(([key, label]) => (
            <button key={key} onClick={() => setSource(key)}
              className="flex-1 py-1 rounded-lg font-mono transition-all"
              style={{
                fontSize: 10,
                background: source === key ? 'rgba(59,130,246,0.15)' : 'var(--bg-pill)',
                border: source === key ? '1px solid var(--border-focus)' : '1px solid var(--border)',
                color: source === key ? 'var(--accent-blue)' : 'var(--text-muted)',
              }}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Preview */}
      <div className="flex-1 mt-3 relative overflow-hidden rounded-xl group" style={{ minHeight: 0 }}>
        {image ? (
          <>
            <img
              src={`data:image/jpeg;base64,${image}`}
              alt={source === 'aria' ? "ARIA's browser" : 'Your screen'}
              className="w-full h-full object-contain transition-transform duration-500 group-hover:scale-[1.03]"
              style={{ background: 'var(--bg-void)' }}
            />
            {/* Corner brackets */}
            {[
              'top-0 left-0 border-t border-l',
              'top-0 right-0 border-t border-r',
              'bottom-0 left-0 border-b border-l',
              'bottom-0 right-0 border-b border-r',
            ].map((cls) => (
              <div key={cls} className={`absolute ${cls} w-4 h-4 pointer-events-none`}
                style={{ borderColor: 'rgba(6,182,212,0.35)' }} />
            ))}

            {/* Click indicator — percentages relative to 1280x800 viewport */}
            {source === 'aria' && lastClickPos && (
              <div className="absolute pointer-events-none"
                style={{
                  left: `${(lastClickPos.x / 1280) * 100}%`,
                  top:  `${(lastClickPos.y / 800) * 100}%`,
                  transform: 'translate(-50%, -50%)',
                }}>
                <div className="w-5 h-5 rounded-full animate-ping"
                  style={{ background: 'rgba(6,182,212,0.5)' }} />
                <div className="absolute inset-0 m-auto w-2.5 h-2.5 rounded-full"
                  style={{ background: 'var(--accent-cyan)' }} />
              </div>
            )}

            {/* Scan line */}
            <div className="absolute inset-0 pointer-events-none overflow-hidden rounded-xl opacity-15">
              <div style={{
                position: 'absolute', top: 0, left: 0, right: 0, height: 1,
                background: `linear-gradient(90deg, transparent, var(--scan-overlay), transparent)`,
                animation: 'scan-line 4s linear infinite',
              }} />
            </div>
          </>
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center gap-3 rounded-xl"
            style={{
              background: 'var(--bg-pill)',
              border: '1px dashed var(--border-bright)',
              minHeight: 180,
            }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
              stroke="var(--text-ghost)" strokeWidth="1.5">
              <rect x="2" y="3" width="20" height="14" rx="2"/>
              <line x1="8"  y1="21" x2="16" y2="21"/>
              <line x1="12" y1="17" x2="12" y2="21"/>
            </svg>
            <div className="font-mono text-center"
              style={{ fontSize: 11, color: 'var(--text-ghost)' }}>
              {source === 'aria'
                ? <>ARIA's browser appears here<br />once it opens a page</>
                : <>No screen feed<br />Enable screen share below</>}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
